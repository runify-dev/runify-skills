#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
understand_image — 理解一张图（描述/问答/信息提取），或对生成结果做结构化自检。
独立能力，不依赖小说流水线。

输入二选一：
  --image-url <公网URL>     已是公网图，直接用
  --file <本地路径>          本地图：自动调 oss_upload.py 上传换公网 URL（需配好 OSS）
说明：agnes 图片理解只吃公网 URL、不支持 base64，故本地图必须先上传。

模式：
  默认       自由理解：--question 指定要关注什么，不给则整体描述
  --check    结构化自检：返回 JSON 检查项（有无可读文字、与期望是否一致、画面问题等）
             配合 --expect 传入“这张图本应是什么”（如某帧的画面描述），让模型对照判断

用法:
  python understand_image.py --image-url https://x/y.png --question "画面里有几个人，在做什么"
  python understand_image.py --file ./k3.png --check --expect "林岩握刀走到单元门前，近景"

返回 RESULT_JSON: 默认 {understanding}；--check {check:{has_text,matches_expect,issues[],ok}}
"""
import os, sys, json, subprocess, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import chat_vision, parse_json_loose, emit, fail, require_api_key, log

STAGE = "understand_image"

CHECK_SYS = """你是图片质检助手。对照【期望】检查这张图，只做封闭的、可判定的检查，不做主观审美评分。
严格只输出JSON，无解释无围栏：
{"has_text": true/false,          // 画面里是否出现了可读的文字/字幕/界面文案（短剧关键帧不应出现）
 "matches_expect": true/false,    // 画面内容是否与【期望】基本一致（无期望则填 true）
 "issues": ["简短中文问题描述"],   // 发现的问题（如形象不符、肢体异常、文字乱入、与期望偏离）；无则空数组
 "ok": true/false}                // 综合判断这张图是否可用"""

def _resolve_url(args):
    if args.image_url:
        return args.image_url
    if not args.file:
        fail(STAGE, "需提供 --image-url 或 --file 之一")
    if not os.path.exists(args.file):
        fail(STAGE, f"文件不存在：{args.file}")
    # 本地图：调 oss_upload 换公网 URL
    here = os.path.dirname(os.path.abspath(__file__))
    log("本地图，先上传 OSS 换公网 URL …")
    r = subprocess.run([sys.executable, os.path.join(here, "oss_upload.py"),
                        "--file", args.file],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True, encoding="utf-8", errors="ignore")
    line = next((l for l in r.stdout.splitlines() if l.startswith("RESULT_JSON:")), None)
    if not line:
        fail(STAGE, f"上传失败：{(r.stderr or r.stdout)[-400:]}")
    data = json.loads(line[len("RESULT_JSON:"):].strip())
    if data.get("status") == "needs_config":
        # OSS 未配置：把指引原样透传给上层，让 agent 提示用户去技能界面配置
        print("RESULT_JSON: " + json.dumps(data, ensure_ascii=False), flush=True)
        sys.exit(0)   # 退出码 0（成功通道）：数据在 stdout，调用方按成功读 stdout 即可拿到配置指引
    if data.get("status") == "error":
        fail(STAGE, f"上传失败：{data.get('error')}")
    return data["url"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image-url", default=None)
    ap.add_argument("--file", default=None)
    ap.add_argument("--question", default=None)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--expect", default=None, help="--check 时：这张图本应呈现什么")
    a = ap.parse_args()
    require_api_key(STAGE)

    url = _resolve_url(a)

    if a.check:
        text = CHECK_SYS + "\n【期望】" + (a.expect or "（未提供，matches_expect 填 true）")
        log("结构化自检中 …")
        try:
            out = chat_vision(text, url, temperature=0.2)
            check = parse_json_loose(out)
        except Exception as e:
            fail(STAGE, f"自检失败：{e}")
        emit({"stage": STAGE, "mode": "check", "image_url": url, "check": check})
    else:
        q = a.question or "请用简体中文整体描述这张图：主体、场景、动作、风格。"
        log("理解中 …")
        try:
            understanding = chat_vision(q, url)
        except Exception as e:
            fail(STAGE, f"理解失败：{e}")
        emit({"stage": STAGE, "mode": "describe", "image_url": url,
              "understanding": understanding})

if __name__ == "__main__":
    main()
