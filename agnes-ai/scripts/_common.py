#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
短剧流水线 · 公共模块
所有原子工具共用：配置、落盘、API 客户端、统一 RESULT_JSON 输出。

契约（每个工具脚本都遵守）：
- 一次调用只产出【一个】产物（一张参考图 / 一帧 / 一段视频 …）。
- 工具无记忆：自己从磁盘读所需状态、装配自己这次调用的上下文，跑完写回磁盘。
- 进度日志走 stderr；最后一行 stdout 打印 `RESULT_JSON: {...}`，供 agent 解析。
- RESULT_JSON 一定带 progress / next / stage_complete，让调用方知道循环是否要继续、
  是否到了该停下问用户的 gate。
- 落盘根目录从环境变量读（见 _root）；API_KEY 从环境变量读（见 SKILL.md 的 envVars）。
"""
import os
import re
import sys
import json
import time
import uuid
import hashlib

import requests

# ======================= 配置（可被 env 覆盖） =======================
API_BASE    = os.environ.get("AGNES_API_BASE",  "https://apihub.agnes-ai.com/v1")
VIDEO_QUERY = os.environ.get("AGNES_VIDEO_QUERY", "https://apihub.agnes-ai.com/agnesapi")

# API_KEY 由 SKILL.md 的 metadata.openclaw.envVars 注入，类型 PasswordInput（不落 SKILL.md 明文）
API_KEY = os.environ.get("AGNES_API_KEY", "")

MODEL_CHAT  = os.environ.get("AGNES_MODEL_CHAT",  "agnes-2.0-flash")
MODEL_IMAGE = os.environ.get("AGNES_MODEL_IMAGE", "agnes-image-2.1-flash")
MODEL_VIDEO = os.environ.get("AGNES_MODEL_VIDEO", "agnes-video-v2.0")

IMAGE_SIZE   = "768x1024"
FRAME_RATE   = 24
HTTP_TIMEOUT = 180
DOWNLOAD_TIMEOUT = 600
VIDEO_TIMEOUT    = 600          # 兼容保留（旧引用），实际创建请求改用下面两个
VIDEO_CREATE_TIMEOUT = 45      # 创建视频任务：提交拿 video_id，超时放宽到 45s
VIDEO_CREATE_RETRIES = 5       # 创建请求失败快速重试次数（提交本身轻量，多试无妨）
VIDEO_QUERY_TIMEOUT  = 15      # 轮询查状态：单次查询超时设短，失败续查
RETRY_MAX        = 3
RETRY_BACKOFF    = 2.0
CHAT_MAX_TOKENS  = 3000
# 是否把生成的图片/视频文件下载到本地服务器。
# 默认 False：只在 manifest 里记 URL + prompt + 版本 + 血缘，不落本地文件（产物自带公网 URL，可直接访问）。
# 设环境变量 KEEP_LOCAL=1 可恢复下载到本地。
KEEP_LOCAL = os.environ.get("KEEP_LOCAL", "").strip() in ("1", "true", "True", "yes")

PREV_CHAPTERS_KEEP = 2
PREV_SUMMARY_CHARS = 300

STYLE_SUFFIX = "日系动漫风格，赛璐璐上色，干净线条，细腻光影，电影感构图，高质量动漫插画"
VIDEO_VOICE_SUFFIX = "。人物说中文普通话，中文配音，普通话语音；画面干净，不出现任何字幕或文字。"
VIDEO_NEG = ("英文, 英文语音, 英文配音, 英文对白, 英文字幕, 英文文字, "
             "English, English speech, English voice, English text, "
             "字幕, 硬字幕, 文字, subtitles, captions, text, watermark")


def _headers():
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


# ======================= 落盘根目录（从 env 读） =======================
def _root():
    """落盘根目录：优先 env，其次当前目录下 project/。
    在 Runify/OpenClaw 里由平台把会话挂载目录通过该 env 注入。"""
    return os.environ.get("RUNIFY_OUTPUT_DIR") or os.path.join(os.getcwd(), "project")


class P:
    @staticmethod
    def root():     return _root()
    @staticmethod
    def proj():     return os.path.join(_root(), "project.json")
    @staticmethod
    def refs_dir(): return os.path.join(_root(), "refs")
    @staticmethod
    def refs_mf():  return os.path.join(_root(), "refs", "manifest.json")


def ch_paths(ch):
    d = os.path.join(_root(), ch)
    return {
        "dir":        d,
        "state":      os.path.join(d, "state.json"),
        "storyboard": os.path.join(d, "storyboard.json"),
        "frames_dir": os.path.join(d, "frames"),
        "frames_mf":  os.path.join(d, "frames", "manifest.json"),
        "clips_dir":  os.path.join(d, "clips"),
        "clips_mf":   os.path.join(d, "clips", "manifest.json"),
        "final":      os.path.join(d, "final.mp4"),
        "srt":        os.path.join(d, "subs.srt"),
    }


# ======================= 落盘工具 =======================
def load_json(path, default=None):
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, obj):
    """原子写：先写 .tmp 再 replace，崩溃也不会留半个文件。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def parse_json_loose(text):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    if not t.lstrip().startswith("{"):
        l, r = t.find("{"), t.rfind("}")
        if l != -1 and r != -1:
            t = t[l:r + 1]
    return json.loads(t)

def slug(name):
    s = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return s or ("ref_" + hashlib.md5((name or "").encode("utf-8")).hexdigest()[:6])


# ======================= 统一输出 =======================
def log(*a):
    """进度日志走 stderr，不污染 stdout 的 RESULT_JSON。"""
    print(*a, file=sys.stderr, flush=True)

def emit(result: dict, code: int = 0):
    """工具唯一的成功出口：stdout 打印一行 RESULT_JSON 后退出。"""
    result.setdefault("status", "ok")
    print("RESULT_JSON: " + json.dumps(result, ensure_ascii=False), flush=True)
    sys.exit(code)

def fail(stage: str, message: str, **extra):
    """失败出口：status=error，但退出码 0。
    约定：结果（成功/失败/needs_config）统一走 stdout，调用方只读 stdout 并按 status 区分；
    退出码恒为 0，进度日志走 stderr（不入调用方上下文）。"""
    payload = {"status": "error", "stage": stage, "error": message}
    payload.update(extra)
    print("RESULT_JSON: " + json.dumps(payload, ensure_ascii=False), flush=True)  # stdout
    sys.exit(0)

def require_api_key(stage):
    if not API_KEY:
        fail(stage, "缺少 AGNES_API_KEY 环境变量（应由 SKILL.md 的 envVars 注入）")


# ======================= API 客户端（带重试） =======================
def _request_with_retry(method, url, max_retries=RETRY_MAX, **kwargs):
    last = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                log(f"  ↻ 第 {attempt}/{max_retries} 次重试请求 {method} {url.split('?')[0]} …")
            r = requests.request(method, url, **kwargs)
            if r.status_code >= 500 or r.status_code == 429:
                raise requests.HTTPError(f"HTTP {r.status_code}: {r.text[:200]}")
            if 400 <= r.status_code < 500:
                raise RuntimeError(f"HTTP {r.status_code}（请求有误，不重试）：{r.text[:800]}")
            return r
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.HTTPError) as e:
            last = e
            if attempt < max_retries:
                wait = RETRY_BACKOFF * (2 ** attempt)
                log(f"  ⚠ 请求失败（第 {attempt+1}/{max_retries} 次重试），{wait:.0f}s 后重试：{str(e)[:120]}")
                time.sleep(wait)
            else:
                break
    raise RuntimeError(f"重试 {max_retries} 次仍失败：{last}")

def _post(url, **kwargs): return _request_with_retry("POST", url, **kwargs)
def _get(url, **kwargs):  return _request_with_retry("GET",  url, **kwargs)


def _download_to(url, out_path, max_seconds=DOWNLOAD_TIMEOUT, chunk=1 << 16,
                 max_retries=RETRY_MAX):
    """流式下载到 out_path，带“总时长上限”“停滞检测”和“整段重试”，
    避免大文件/慢源把进程挂死，同时保留与普通请求一致的重试能力。
    requests 的 timeout 只管连接和单次 read 间隔，不限制整体下载时长；
    慢源每隔几秒挤一点数据就永远不超时——这里用 monotonic 计总时长强制封顶。"""
    import time as _t
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    last_err = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait = RETRY_BACKOFF * (2 ** (attempt - 1))
            log(f"  ↻ 下载第 {attempt}/{max_retries} 次重试，{wait:.0f}s 后重试：{str(last_err)[:120]}")
            _t.sleep(wait)
        start = _t.monotonic()
        last_data = start
        written = 0
        try:
            # connect 超时给 30s，read 单次间隔给 60s；总时长由下面的循环强制封顶
            with requests.get(url, stream=True, timeout=(30, 60)) as r:
                if 400 <= r.status_code < 500:
                    # 客户端错误（如签名过期 403）重试无意义，直接失败
                    raise RuntimeError(f"下载 HTTP {r.status_code}（不重试）：{url[:120]}")
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    for blk in r.iter_content(chunk_size=chunk):
                        now = _t.monotonic()
                        if now - start > max_seconds:
                            raise TimeoutError(
                                f"下载超过 {max_seconds}s 仍未完成（已写 {written} 字节），主动中断")
                        if blk:
                            f.write(blk)
                            written += len(blk)
                            last_data = now
                        elif now - last_data > 120:
                            raise TimeoutError("下载停滞超过 120s 无新数据，主动中断")
            if written == 0:
                raise RuntimeError(f"下载完成但文件为空：{url[:120]}")
            log(f"  ↓ 已下载 {written} 字节 → {out_path}")
            return out_path
        except RuntimeError as e:
            # 标记为“不重试”的客户端错误：直接抛出
            if "不重试" in str(e):
                raise
            last_err = e
        except (requests.exceptions.RequestException, TimeoutError, OSError) as e:
            last_err = e
    raise RuntimeError(f"下载重试 {max_retries} 次仍失败：{last_err}")


def chat_messages(messages, temperature=0.7, max_tokens=CHAT_MAX_TOKENS):
    payload = {"model": MODEL_CHAT, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    r = _post(f"{API_BASE}/chat/completions", headers=_headers(), json=payload, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def chat_vision(text, image_url, temperature=0.4, max_tokens=CHAT_MAX_TOKENS):
    """图片理解：agnes-2.0-flash 走 chat/completions，content 为 [text, image_url] 数组。
    注意 image_url 必须是公网可访问 URL（不支持 base64）。"""
    messages = [{"role": "user", "content": [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]}]
    return chat_messages(messages, temperature=temperature, max_tokens=max_tokens)


def gen_image(prompt, ref_urls=None, out_path=None):
    extra = {"response_format": "url"}
    if ref_urls:
        extra["image"] = ref_urls
    payload = {"model": MODEL_IMAGE, "prompt": prompt, "size": IMAGE_SIZE, "extra_body": extra}
    log(f"  ▶ 图片任务已提交，生成中…（prompt: {prompt[:40]}{'…' if len(prompt) > 40 else ''}）")
    r = _post(f"{API_BASE}/images/generations", headers=_headers(), json=payload, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    try:
        url = data["data"][0]["url"]
    except (KeyError, IndexError, TypeError):
        url = data.get("url") or data.get("output")
    if not url:
        raise RuntimeError(f"图像接口未返回 url：{data}")
    log("  ✓ 图片已生成，取得 URL")
    if out_path:
        log(f"  ↓ 下载图片到 {out_path} …")
        _download_to(url, out_path)
        log("  ✓ 图片下载完成")
    return url, out_path


def _calc_frames(duration_sec, fps):
    n = int(round(duration_sec * fps))
    n = ((n - 1) // 8) * 8 + 1
    return max(9, min(n, 441))

def _video_url(data):
    v = data.get("remixed_from_video_id")
    if isinstance(v, str) and v.startswith("http"):
        return v
    for k in ("url", "video_url", "output"):
        if isinstance(data.get(k), str) and data[k].startswith("http"):
            return data[k]
    return None

def _poll_video(video_id, interval=5, max_wait=1800):
    """轮询视频任务直到完成：开始即反馈、每次报进度、单次查询失败自动重试续查。"""
    log(f"  ▶ 视频任务已提交（id={video_id}），生成中…（异步，通常数十秒~数分钟）")
    waited = 0
    consecutive_errors = 0
    last_progress = -1
    while waited < max_wait:
        cycle_start = time.monotonic()
        # 单飞：一次只发一个查询，它没返回（或超时）前绝不发下一个。
        # 这里直接用 requests，不走 _get 的内层重试，避免“查询里再套重试”导致节奏叠加。
        try:
            r = requests.request("GET", VIDEO_QUERY, headers=_headers(),
                                  params={"video_id": video_id, "model_name": MODEL_VIDEO},
                                  timeout=VIDEO_QUERY_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            consecutive_errors = 0           # 查询成功，清零
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors > RETRY_MAX:
                raise RuntimeError(f"连续 {consecutive_errors} 次查询视频状态失败：{e}")
            log(f"  ⚠ 查询状态失败（第 {consecutive_errors}/{RETRY_MAX} 次，已等 {waited}s），下个周期续查…")
            data = None
        if data is not None:
            status = (data.get("status") or "").lower()
            progress = data.get("progress", 0)
            if status == "completed":
                url = _video_url(data)
                if url:
                    log(f"  ✓ 视频生成完成（共等 {waited}s）")
                    return url
                raise RuntimeError(f"任务已完成但未取到视频URL：{data}")
            if status == "failed":
                raise RuntimeError(f"视频生成失败：{data.get('error')}")
            # 有进度变化才打，避免刷屏；但至少每 30s 报一次“还活着”
            if progress != last_progress or waited % 30 == 0:
                log(f"  …{status or 'queued'} {progress}%（已等 {waited}s，仍在生成）")
                last_progress = progress
        # 周期对齐：扣掉本次查询已耗费的时间，只补足到 interval。
        # 若本次查询已超过一个周期（慢/超时），立刻进入下一轮，不额外叠加等待。
        elapsed = time.monotonic() - cycle_start
        sleep_left = interval - elapsed
        if sleep_left > 0:
            time.sleep(sleep_left)
        waited += max(interval, elapsed)
    raise TimeoutError(f"视频任务 {video_id} 超过 {max_wait}s 未完成")


def gen_video_simple(prompt, out_path, image_url=None, image_urls=None,
                     keyframes=False, duration_sec=5, audio=None):
    """根据 agnes-video-v2.0 文档支持四种模式：
      · 文生视频    ：image_url=None 且 image_urls=None        → 仅 prompt
      · 单图生视频  ：image_url=单个公网URL                    → 顶层 image（文档示例2）
      · 多图视频    ：image_urls=[URL,...] 且 keyframes=False  → extra_body.image（文档示例3，无 mode）
      · 关键帧动画  ：image_urls=[URL,...] 且 keyframes=True   → extra_body.image + mode:keyframes（示例4）
    视频只吃公网 URL，不支持 base64。"""
    num_frames = _calc_frames(duration_sec, FRAME_RATE)
    if audio is None:
        # 默认：中文配音（短剧主场景），并压制英文语音/字幕
        full_prompt = prompt + VIDEO_VOICE_SUFFIX
        neg = VIDEO_NEG
    else:
        # 用户用 --audio 自定义声音（如"只有雨声，人物不说话"/"无声"/"背景轻音乐"）。
        # 把描述拼进 prompt；负向只压字幕/文字，不强加人声限制，让用户描述自己决定。
        a = audio.strip()
        full_prompt = prompt + ("。音频：" + a + "；画面干净，不出现任何字幕或文字。" if a else "")
        neg = "字幕, 硬字幕, 文字, subtitles, captions, text, watermark"
    payload = {"model": MODEL_VIDEO, "prompt": full_prompt, "negative_prompt": neg,
               "num_frames": num_frames, "frame_rate": FRAME_RATE}
    # 归一化图片入参
    urls = []
    if image_urls:
        urls = [u for u in image_urls if u]
    elif image_url:
        urls = [image_url]
    if len(urls) == 1 and not keyframes:
        payload["image"] = urls[0]                          # 单图：顶层 image
    elif len(urls) >= 2 or (urls and keyframes):
        extra = {"image": urls}                             # 多图 / 关键帧：extra_body.image
        if keyframes:
            extra["mode"] = "keyframes"
        payload["extra_body"] = extra
    # urls 为空即文生视频，不加 image
    r = _post(f"{API_BASE}/videos", headers=_headers(), json=payload,
            timeout=VIDEO_CREATE_TIMEOUT, max_retries=VIDEO_CREATE_RETRIES)
    r.raise_for_status()
    data = r.json()
    vid = data.get("video_id") or data.get("task_id") or data.get("id")
    url = _poll_video(vid) if vid else _video_url(data)
    if not url:
        raise RuntimeError(f"创建视频任务未返回 video_id：{data}")
    if out_path:
        _download_to(url, out_path)
    return out_path, url


# ======================= 跨阶段上下文装配（从磁盘，非对话历史） =======================
def chapter_ctx(ch, state):
    """每步从磁盘重建本步所需的最小上下文，而不是继承上一阶段的对话历史。"""
    proj = load_json(P.proj(), default={}) or {}
    chapters = proj.get("chapters", [])
    idx = chapters.index(ch) if ch in chapters else max(0, len(chapters) - 1)
    reflib = load_json(P.refs_mf(), default={}) or {}
    used = state.get("refs_used", [])
    avail = [{"id": rid, "name": reflib.get(rid, {}).get("name", ""),
              "kind": reflib.get(rid, {}).get("kind", "")} for rid in used]
    prev_ids = chapters[:idx][-PREV_CHAPTERS_KEEP:] if PREV_CHAPTERS_KEEP > 0 else []
    prev = []
    for pid in prev_ids:
        st = load_json(ch_paths(pid)["state"], default={}) or {}
        prev.append({"title": st.get("title", pid),
                     "正文摘要": (st.get("raw_text") or "")[:PREV_SUMMARY_CHARS]})
    return {
        "项目标题": proj.get("title", ""),
        "本章位置": f"第{idx+1}章 / 共{len(chapters)}章",
        "可用参考": avail,
        "前情梗概": prev,
        "本章": {"title": state.get("title", ""), "正文": state.get("raw_text", "")},
    }


# ======================= 自由工作区 scratch（6 个原子工具用，版本化+血缘） =======================
# 这些工具无章节概念、自由调用、反复交互，
# 故每次生成落【新文件】不覆盖，manifest 记录血缘（来源/prompt/父产物），支持回退与“接着上一个做”。
import base64, datetime

def scratch_dir():
    d = os.path.join(_root(), "scratch")
    os.makedirs(d, exist_ok=True)
    return d

def scratch_mf_path():
    return os.path.join(scratch_dir(), "manifest.json")

def save_path_for(item, ext):
    """为某个产物生成本地保存路径（供 --save 使用）。
    若 item 已有 local（KEEP_LOCAL 模式）直接用它；否则按 id 在 scratch 目录生成路径。"""
    if item.get("local"):
        return item["local"]
    return os.path.join(scratch_dir(), f"{item['id']}.{ext.lstrip('.')}")

def _new_id(kind):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{kind}_{ts}_{uuid.uuid4().hex[:4]}"

def scratch_record(kind, ext, *, prompt="", parent=None, intent=None, extra=None):
    """登记一个新产物，返回 (item_id, local_path)。先登记拿路径，工具把文件写到该路径后再 commit。
    kind: img|vid|frame ; parent: 基于哪个产物做的(血缘) ; intent: 同一意图分组键(用于版本计数)。"""
    mf = load_json(scratch_mf_path(), default={"items": []}) or {"items": []}
    item_id = _new_id(kind)
    # 默认不下载到本地：local=None，只靠 manifest 里的 url + prompt + 版本 + 血缘追溯。
    # KEEP_LOCAL=1 时才预留本地路径供下载。
    local = os.path.join(scratch_dir(), f"{item_id}.{ext.lstrip('.')}") if KEEP_LOCAL else None
    # 同一 intent 下是第几次尝试（用于前端“第N版/回退”）
    ver = 1 + sum(1 for it in mf["items"] if intent and it.get("intent") == intent)
    item = {"id": item_id, "kind": kind, "local": local, "url": None,
            "prompt": prompt, "parent": parent, "intent": intent or item_id,
            "version": ver, "ts": int(time.time()), "status": "pending"}
    if extra:
        item.update(extra)
    mf["items"].append(item)
    save_json(scratch_mf_path(), mf)
    return item, local

def scratch_commit(item_id, *, url=None, status="ok", **fields):
    """产物文件写好后回填 url/状态。"""
    mf = load_json(scratch_mf_path(), default={"items": []}) or {"items": []}
    for it in mf["items"]:
        if it["id"] == item_id:
            if url is not None:
                it["url"] = url
            it["status"] = status
            it.update(fields)
            break
    save_json(scratch_mf_path(), mf)
    return mf

def scratch_get(item_id):
    mf = load_json(scratch_mf_path(), default={"items": []}) or {"items": []}
    return next((it for it in mf["items"] if it["id"] == item_id), None)


# ======================= 图片入参解析（URL 直用 / 本机图按目标模型处理） =======================
def _is_url(s):
    return isinstance(s, str) and s.startswith(("http://", "https://", "data:"))

def to_data_uri(local_path):
    """本机图 -> data:image/<ext>;base64,xxx（图生图/润色用；视频与图片理解不支持）。"""
    ext = (os.path.splitext(local_path)[1].lstrip(".") or "png").lower()
    if ext == "jpg":
        ext = "jpeg"
    with open(local_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/{ext};base64,{b64}"

def resolve_image_for_image_model(image_url, file):
    """图生图/润色：URL 直用；本机文件转 data-uri（这两个模型支持 base64，永不上传 OSS）。"""
    if image_url:
        return image_url
    if file and os.path.exists(file):
        return to_data_uri(file)
    return None

def resolve_image_public_url(image_url, file, stage):
    """图片理解/图生视频：只吃公网 URL。真 http(s) URL 直用；
    本机文件 / 本地路径 / base64 一律必须经 oss_upload 换公网 URL。
    未配置 OSS 时透传 needs_config 指引并退出（退出码 0）。"""
    # 只有 http:// 或 https:// 开头才算真正的公网 URL，可直接用。
    if image_url and image_url.lower().startswith(("http://", "https://")):
        return image_url
    # 走到这里说明 image_url 是空、或本地路径、或 base64/data: —— 都需要换成公网 URL。
    # 若没单独给 file，但 image_url 其实是个存在的本地路径，就把它当 file 处理。
    if not file and image_url and not image_url.lower().startswith("data:") and os.path.exists(image_url):
        file = image_url
    if not (file and os.path.exists(file)):
        fail(stage, "视频/图片理解只接受公网 http(s) URL 或存在的本机文件；"
                    "收到的不是公网 URL 也找不到对应本机文件（不支持 base64）")
    here = os.path.dirname(os.path.abspath(__file__))
    log("本机图，先上传 OSS 换公网 URL …")
    import subprocess
    r = subprocess.run([sys.executable, os.path.join(here, "oss_upload.py"), "--file", file],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True, encoding="utf-8", errors="ignore")
    line = next((l for l in r.stdout.splitlines() if l.startswith("RESULT_JSON:")), None)
    if not line:
        fail(stage, f"上传失败：{(r.stderr or r.stdout)[-400:]}")
    data = json.loads(line[len("RESULT_JSON:"):].strip())
    if data.get("status") == "needs_config":
        print("RESULT_JSON: " + json.dumps(data, ensure_ascii=False), flush=True)
        sys.exit(0)   # 退出码 0（成功通道）：数据在 stdout，调用方按成功读 stdout 即可拿到配置指引
    if data.get("status") == "error":
        fail(stage, f"上传失败：{data.get('error')}")
    return data["url"]
