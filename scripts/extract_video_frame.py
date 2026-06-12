#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_video_frame — 从视频抽一帧存为图片，落 scratch（血缘指向源视频）。
用于“拿上一个视频接着做下一个”：抽末帧/某时刻帧 → 交给 understand_image 理解，
或交给 image_to_image / image_to_video 继续生成，保持衔接。需要本机 ffmpeg。

图源：--video-url（公网视频）/ --file（本机视频）/ --parent（scratch 里的视频产物 id）
取帧位置：--at last（末帧，默认）| --at <秒，如 2.5>

用法:
  python extract_video_frame.py --parent vid_20260611_154500_e5f6 --at last
  python extract_video_frame.py --file ./clip.mp4 --at 2.0

返回 RESULT_JSON: produced{id,local,from_video,at}  (注意：抽出的帧是本机文件，
若要喂图片理解/图生视频需再走 OSS；喂图生图可直接 base64)
"""
import os, sys, shutil, subprocess, tempfile, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (scratch_record, scratch_commit, scratch_get, _get,
                     DOWNLOAD_TIMEOUT, emit, fail, log)

STAGE = "extract_video_frame"

def _run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, encoding="utf-8", errors="ignore")

def _probe_dur(path):
    if not shutil.which("ffprobe"):
        return None
    r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
              "-of", "default=nw=1:nk=1", path])
    try:
        return float(r.stdout.strip())
    except (ValueError, AttributeError):
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-url", default=None)
    ap.add_argument("--file", default=None)
    ap.add_argument("--parent", default=None)
    ap.add_argument("--at", default="last", help="last（末帧）或秒数，如 2.5")
    a = ap.parse_args()

    if not shutil.which("ffmpeg"):
        fail(STAGE, "未找到 ffmpeg")

    parent_id = None
    local_video = a.file
    if not local_video and a.parent:
        p = scratch_get(a.parent)
        if not p or not p.get("local"):
            fail(STAGE, f"找不到父视频产物：{a.parent}")
        local_video = p["local"]; parent_id = a.parent
    tmp = None
    if not local_video and a.video_url:
        try:
            v = _get(a.video_url, timeout=DOWNLOAD_TIMEOUT); v.raise_for_status()
        except Exception as e:
            fail(STAGE, f"下载视频失败：{e}")
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.write(v.content); tmp.close(); local_video = tmp.name
    if not (local_video and os.path.exists(local_video)):
        fail(STAGE, "需提供 --video-url / --file / --parent 之一")

    item, out = scratch_record("frame", "png", parent=parent_id,
                               extra={"from_video": parent_id or a.video_url or a.file, "at": a.at})
    # 定位时间点
    if a.at == "last":
        dur = _probe_dur(local_video)
        ts = max(0.0, (dur - 0.05)) if dur else None
    else:
        try:
            ts = float(a.at)
        except ValueError:
            fail(STAGE, f"--at 非法：{a.at}（用 last 或秒数）")
    log(f"抽帧 {item['id']} @ {a.at} …")
    if ts is not None:
        r = _run(["ffmpeg", "-y", "-ss", f"{ts:.3f}", "-i", local_video,
                  "-frames:v", "1", out])
    else:  # 读不到时长，退而取靠后的一帧
        r = _run(["ffmpeg", "-y", "-sseof", "-0.1", "-i", local_video, "-frames:v", "1", out])
    if tmp:
        try: os.unlink(tmp.name)
        except OSError: pass
    if r.returncode != 0 or not os.path.exists(out):
        scratch_commit(item["id"], status="error")
        fail(STAGE, "抽帧失败：" + (r.stderr or "")[-500:])
    scratch_commit(item["id"], status="ok")
    log(f"  ✓ {out}")
    emit({"stage": STAGE,
          "produced": {"id": item["id"], "local": out,
                       "from_video": parent_id or a.video_url or a.file, "at": a.at},
          "note": "抽出的帧是本机文件：喂图片理解/图生视频需再经 OSS；喂图生图可直接 base64"})

if __name__ == "__main__":
    main()
