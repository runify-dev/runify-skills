#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
image_to_image — 图生图：基于一张图按提示词转换/重塑。落 scratch（版本化+血缘）。
图源：--image-url（公网或已生成的图）或 --file（本机图，走 base64，不上传 OSS）；
      或 --parent <scratch_id>（基于之前生成的某个产物继续做，自动接血缘）。

用法:
  python image_to_image.py --image-url https://x/y.png --prompt "改成赛博朋克雨夜，保留原构图"
  python image_to_image.py --file ./in.png --prompt "..." --intent remix1
  python image_to_image.py --parent img_20260611_153012_a1b2 --prompt "再暗一点"

返回 RESULT_JSON: produced{id,url,local,version,parent}
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (save_path_for, gen_image, scratch_record, scratch_commit, scratch_get,
                     resolve_image_for_image_model, STYLE_SUFFIX,
                     emit, fail, require_api_key, log)

STAGE = "image_to_image"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image-url", default=None)
    ap.add_argument("--file", default=None)
    ap.add_argument("--parent", default=None, help="基于之前 scratch 产物的 id 继续做")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--intent", default=None)
    ap.add_argument("--no-style", action="store_true")
    ap.add_argument("--save", action="store_true", help="把生成的产物下载到本地（默认只记 URL，不下载）")
    a = ap.parse_args()
    require_api_key(STAGE)

    parent_id = None
    src = resolve_image_for_image_model(a.image_url, a.file)
    if not src and a.parent:
        p = scratch_get(a.parent)
        if not p or not p.get("url"):
            fail(STAGE, f"找不到父产物或其无 url：{a.parent}")
        src = p["url"]; parent_id = a.parent
    if not src:
        fail(STAGE, "需提供 --image-url / --file / --parent 之一")

    prompt = a.prompt if a.no_style else f"{a.prompt}。{STYLE_SUFFIX}"
    intent = a.intent or (scratch_get(parent_id)["intent"] if parent_id else None)
    item, local = scratch_record("img", "png", prompt=prompt, parent=parent_id, intent=intent)
    if a.save:
        local = save_path_for(item, "png")
    log(f"图生图 {item['id']} …")
    try:
        url, _ = gen_image(prompt, ref_urls=[src], out_path=local)
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
