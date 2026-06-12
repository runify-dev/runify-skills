#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
polish_image — 润色/增强一张图：在【保留原构图、主体、视角】前提下提升质量。
本质是 image_to_image 的“保留式编辑”模板。落 scratch（版本化+血缘）。
图源同 image_to_image：--image-url / --file（本机走 base64）/ --parent。

用法:
  python polish_image.py --file ./in.png
  python polish_image.py --image-url https://x.png --instruction "提升清晰度，柔化光影，增强细节"
  python polish_image.py --parent img_xxx --instruction "色调更暖"

返回 RESULT_JSON: produced{id,url,local,version,parent}
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (save_path_for, gen_image, scratch_record, scratch_commit, scratch_get,
                     resolve_image_for_image_model, STYLE_SUFFIX,
                     emit, fail, require_api_key, log)

STAGE = "polish_image"

POLISH_BASE = ("在严格保留原图构图、主体结构、视角与整体内容的前提下进行润色增强："
               "提升清晰度与细节、优化光影与色彩、修正瑕疵，不改变画面内容与布局。")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image-url", default=None)
    ap.add_argument("--file", default=None)
    ap.add_argument("--parent", default=None)
    ap.add_argument("--instruction", default=None, help="额外润色要求（中文）")
    ap.add_argument("--intent", default=None)
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

    prompt = POLISH_BASE + (("额外要求：" + a.instruction) if a.instruction else "") + f"。{STYLE_SUFFIX}"
    intent = a.intent or (scratch_get(parent_id)["intent"] if parent_id else None)
    item, local = scratch_record("img", "png", prompt=prompt, parent=parent_id, intent=intent)
    if a.save:
        local = save_path_for(item, "png")
    log(f"润色 {item['id']} …")
    try:
        url, _ = gen_image(prompt, ref_urls=[src], out_path=local)
    except Exception as e:
        scratch_commit(item["id"], status="error")
        fail(STAGE, f"润色失败：{e}", item_id=item["id"])
    scratch_commit(item["id"], url=url, local=local)
    log(f"  ✓ {url}")
    emit({"stage": STAGE,
          "produced": {"id": item["id"], "url": url, "local": local,
                       "intent": item["intent"], "version": item["version"],
                       "parent": parent_id}})

if __name__ == "__main__":
    main()
