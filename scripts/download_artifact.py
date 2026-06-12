#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_artifact — 按需把产物（图片/视频）从公网 URL 下载到本地。
默认流程不下载（只在 manifest 记 URL）；当用户/agent 明确要把某个产物落地、导出、归档时用本工具。

下载直接传 URL（产物的 produced.url，或 manifest 里记的 url）。
带流式下载 + 总时长上限 + 停滞检测 + 重试（与生成时同一套，稳）。

用法:
  python3 download_artifact.py --url https://storage.googleapis.com/.../video.mp4
  python3 download_artifact.py --url https://.../img.png --out ./keep/cover.png
  python3 download_artifact.py --url https://.../v.mp4 --item-id vid_xxx   # 顺便把本地路径回填进 manifest

返回 RESULT_JSON: saved{url, local, bytes, item_id?}
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (_download_to, scratch_dir, scratch_get, scratch_commit,
                     emit, fail, log)

STAGE = "download_artifact"


def _guess_ext(url, default=".bin"):
    path = url.split("?", 1)[0]
    for e in (".mp4", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mov", ".webm"):
        if path.lower().endswith(e):
            return e
    return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="产物的公网 URL（直接下载它）")
    ap.add_argument("--out", default=None, help="保存路径；不给则放到 scratch 目录、按 URL 后缀命名")
    ap.add_argument("--item-id", default=None,
                    help="可选：对应 manifest 产物 id，下载后把 local 回填进 manifest")
    a = ap.parse_args()

    url = a.url.strip()
    if not url.lower().startswith(("http://", "https://")):
        fail(STAGE, f"--url 必须是公网 http(s) 链接，收到：{url[:120]}")

    # 决定保存路径
    out_path = a.out
    if not out_path:
        # 若给了 item-id 且 manifest 有记录，用 id 命名；否则用时间无关的 URL 文件名兜底
        if a.item_id:
            out_path = os.path.join(scratch_dir(), f"{a.item_id}{_guess_ext(url)}")
        else:
            base = os.path.basename(url.split("?", 1)[0]) or "artifact"
            if "." not in base:
                base += _guess_ext(url)
            out_path = os.path.join(scratch_dir(), base)

    log(f"按需下载 → {out_path}")
    try:
        _download_to(url, out_path)
    except Exception as e:
        fail(STAGE, f"下载失败：{e}")

    nbytes = os.path.getsize(out_path) if os.path.exists(out_path) else 0

    # 可选：把本地路径回填进 manifest（不改 url、不改版本，只补 local）
    item_id = a.item_id
    if item_id:
        if scratch_get(item_id):
            scratch_commit(item_id, local=out_path)
        else:
            log(f"  ⚠ manifest 中找不到 {item_id}，跳过回填（文件已下载）")

    log(f"  ✓ 已保存 {nbytes} 字节")
    emit({"stage": STAGE,
          "saved": {"url": url, "local": out_path, "bytes": nbytes, "item_id": item_id}})


if __name__ == "__main__":
    main()
