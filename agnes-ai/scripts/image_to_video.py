#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
image_to_video — 图生视频：把图动画化。落 scratch（版本化+血缘）。
支持单图 / 多图 / 关键帧三种模式（agnes-video-v2.0）：
  · 单图：--image-url / --file / --parent 任一
  · 多图：--images url1,url2[,...] 或多次 --image（多张参考图指导生成、平滑过渡，保持一致性）
  · 关键帧：在多图基础上加 --keyframes（在关键帧之间生成平滑过渡）

图源每一项都可以是：公网URL / 本机文件路径 / scratch 产物 id。
⚠ 视频模型只吃公网 URL、不支持 base64：本机图会先经 oss_upload 换公网 URL，
   未配置 OSS 时返回 needs_config 指引（让用户去技能界面配置）。

用法:
  python3 image_to_video.py --file ./char.png --prompt "人物缓缓转身" --duration 5
  python3 image_to_video.py --parent img_xxx --prompt "..."
  python3 image_to_video.py --images img_aaa,./last_frame.png --prompt "在两张参考图之间平滑过渡，保持角色一致"
  python3 image_to_video.py --images k1.png,k2.png --keyframes --prompt "关键帧间平滑过渡"

返回 RESULT_JSON: produced{id,url,local,version,parent}
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (save_path_for, gen_video_simple, scratch_record, scratch_commit, scratch_get,
                     resolve_image_public_url, emit, fail, require_api_key, log)

STAGE = "image_to_video"


def _resolve_one(src):
    """把单个图源（公网URL / scratch产物id / 本机路径）解析成公网 URL。
    返回 (public_url, parent_id_or_None)。本机图经 OSS；未配置 OSS 会在 resolve 内透传 needs_config 退出。"""
    if not src:
        return None, None
    # 1) 真公网 URL：直用
    if src.lower().startswith(("http://", "https://")):
        return src, None
    # 2) scratch 产物 id：取其 url，没有 url 用 local 走 OSS
    p = scratch_get(src)
    if p:
        if p.get("url"):
            return p["url"], src
        if p.get("local"):
            return resolve_image_public_url(None, p["local"], STAGE), src
        fail(STAGE, f"父产物既无 url 也无 local：{src}")
    # 3) 否则当本机文件路径，走 OSS
    return resolve_image_public_url(None, src, STAGE), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image-url", default=None)
    ap.add_argument("--file", default=None)
    ap.add_argument("--parent", default=None)
    ap.add_argument("--images", default=None,
                    help="多图：逗号分隔，每项可为 URL / 本机路径 / scratch产物id")
    ap.add_argument("--image", action="append", default=[],
                    help="多图：可重复传，每次一张（与 --images 等价，可混用）")
    ap.add_argument("--keyframes", action="store_true",
                    help="多图时启用关键帧模式（在关键帧之间生成平滑过渡）")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--duration", type=float, default=5)
    ap.add_argument("--intent", default=None)
    ap.add_argument("--audio", default=None,
                    help='声音描述，如 "只有背景音乐，人物不说话" / "无声"；不传则默认中文配音')
    ap.add_argument("--save", action="store_true", help="把生成的产物下载到本地（默认只记 URL，不下载）")
    a = ap.parse_args()
    require_api_key(STAGE)

    # 汇总所有图源（保持顺序，单图三参数 + 多图两参数都收进来）
    raw_sources = []
    for s in (a.image_url, a.file, a.parent):
        if s:
            raw_sources.append(s)
    if a.images:
        raw_sources.extend([s.strip() for s in a.images.split(",") if s.strip()])
    if a.image:
        raw_sources.extend([s for s in a.image if s])

    if not raw_sources:
        fail(STAGE, "至少提供一个图源：--image-url / --file / --parent / --images / --image")

    # 逐个解析成公网 URL（本机图自动走 OSS；未配置 OSS 会在此透传 needs_config 退出）
    public_urls, parent_id = [], None
    for src in raw_sources:
        url, pid = _resolve_one(src)
        if url:
            public_urls.append(url)
            if pid and not parent_id:
                parent_id = pid   # 记第一个 scratch 父产物作血缘

    if not public_urls:
        fail(STAGE, "未能解析出任何可用图片 URL")

    intent = a.intent or (scratch_get(parent_id)["intent"] if parent_id else None)
    multi = len(public_urls) >= 2
    mode_desc = ("关键帧动画" if (multi and a.keyframes)
                 else "多图视频" if multi else "单图生视频")
    item, local = scratch_record("vid", "mp4", prompt=a.prompt, parent=parent_id,
                                 intent=intent, extra={"duration": a.duration,
                                                       "from_images": public_urls,
                                                       "mode": mode_desc})
    if a.save:
        local = save_path_for(item, "mp4")
    log(f"{mode_desc} {item['id']}（{a.duration}s，{len(public_urls)} 张图）…")
    try:
        if multi:
            _, url = gen_video_simple(a.prompt, local, image_urls=public_urls,
                                      keyframes=a.keyframes,
                                      duration_sec=a.duration, audio=a.audio)
        else:
            _, url = gen_video_simple(a.prompt, local, image_url=public_urls[0],
                                      duration_sec=a.duration, audio=a.audio)
    except Exception as e:
        scratch_commit(item["id"], status="error")
        fail(STAGE, f"生成失败：{e}", item_id=item["id"])
    scratch_commit(item["id"], url=url, local=local)
    log(f"  ✓ {url}")
    emit({"stage": STAGE,
          "produced": {"id": item["id"], "url": url, "local": local,
                       "intent": item["intent"], "version": item["version"],
                       "parent": parent_id}})


if __name__ == "__main__":
    main()
