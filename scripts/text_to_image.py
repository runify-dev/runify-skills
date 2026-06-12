#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
text_to_image — 文生图。独立能力，落 scratch 自由工作区（版本化，反复重做不丢历史）。

用法:
  python text_to_image.py --prompt "一只猫在沙滩看日落，电影感"
  python text_to_image.py --prompt "..." --intent cat_beach   # 同一意图多次尝试归一组，便于回退/对比

返回 RESULT_JSON: produced{id,url,local,version} —— version 是该 intent 下第几次尝试
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (save_path_for, gen_image, scratch_record, scratch_commit, STYLE_SUFFIX,
                     emit, fail, require_api_key, log)

STAGE = "text_to_image"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--intent", default=None, help="同一创作意图的分组键，用于版本计数/回退")
    ap.add_argument("--no-style", action="store_true", help="不追加默认动漫风格后缀")
    ap.add_argument("--save", action="store_true", help="把生成的产物下载到本地（默认只记 URL，不下载）")
    a = ap.parse_args()
    require_api_key(STAGE)

    prompt = a.prompt if a.no_style else f"{a.prompt}。{STYLE_SUFFIX}"
    item, local = scratch_record("img", "png", prompt=prompt, intent=a.intent)
    if a.save:
        local = save_path_for(item, "png")
    log(f"文生图 {item['id']} …")
    try:
        url, _ = gen_image(prompt, out_path=local)
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
