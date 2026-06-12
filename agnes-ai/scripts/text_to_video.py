#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
text_to_video — 文生视频，一步出片。落 scratch（版本化）。
时长由 --duration 秒控制（内部换算 num_frames=8n+1，≤441）。

用法:
  python text_to_video.py --prompt "宇航员走过红色沙漠星球，慢镜头跟拍，夕阳" --duration 5
  python text_to_video.py --prompt "..." --audio "只有雨声，人物不说话"   # 自定义声音；不传则默认中文配音

返回 RESULT_JSON: produced{id,url,local,version}
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (save_path_for, gen_video_simple, scratch_record, scratch_commit,
                     emit, fail, require_api_key, log)

STAGE = "text_to_video"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--duration", type=float, default=5)
    ap.add_argument("--intent", default=None)
    ap.add_argument("--audio", default=None,
                    help='声音描述，如 "只有背景音乐，人物不说话" / "无声" / "人物说中文，有街道环境声"；不传则默认中文配音')
    ap.add_argument("--save", action="store_true", help="把生成的产物下载到本地（默认只记 URL，不下载）")
    a = ap.parse_args()
    require_api_key(STAGE)

    item, local = scratch_record("vid", "mp4", prompt=a.prompt, intent=a.intent,
                                 extra={"duration": a.duration})
    if a.save:
        local = save_path_for(item, "mp4")
    log(f"文生视频 {item['id']}（{a.duration}s）…")
    try:
        _, url = gen_video_simple(a.prompt, local, image_url=None,
                                  duration_sec=a.duration, audio=a.audio)
    except Exception as e:
        scratch_commit(item["id"], status="error")
        fail(STAGE, f"生成失败：{e}", item_id=item["id"])
    scratch_commit(item["id"], url=url, local=local)
    log(f"  ✓ {url}")
    emit({"stage": STAGE,
          "produced": {"id": item["id"], "url": url, "local": local,
                       "intent": item["intent"], "version": item["version"]}})

if __name__ == "__main__":
    main()
