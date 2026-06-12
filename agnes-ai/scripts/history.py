#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
history — 查看产物历史（从 scratch/manifest.json 读，不下载任何文件）。
能回答："生成过哪些产物 / 用哪段 prompt / 第几版 / 谁基于谁（血缘）/ URL 是什么"。

用法:
  ./agnes history                       列出全部产物（按时间倒序，最新在前）
  ./agnes history --kind vid            只看视频（img/vid/frame）
  ./agnes history --intent cat_shot     看某创作意图下的所有版本（v1, v2, ...）
  ./agnes history --id vid_xxx          看某个产物的详情 + 它的血缘链（从根到它）
  ./agnes history --limit 20            最多显示多少条（默认 50）
  ./agnes history --json                输出原始 JSON（给程序/agent 用）

返回 RESULT_JSON: history{count, items:[...]}
"""
import os, sys, json, argparse, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import scratch_mf_path, load_json, emit, fail, log

STAGE = "history"


def _fmt_ts(ts):
    try:
        return datetime.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


def _short(s, n=60):
    s = (s or "").replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def _chain(items_by_id, item):
    """从根产物到当前产物的血缘链（id 列表，按从祖先到自身顺序）。"""
    chain = []
    seen = set()
    cur = item
    while cur:
        if cur["id"] in seen:   # 防环
            break
        seen.add(cur["id"])
        chain.append(cur["id"])
        pid = cur.get("parent")
        cur = items_by_id.get(pid) if pid else None
    return list(reversed(chain))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default=None, help="只看某类型：img / vid / frame")
    ap.add_argument("--intent", default=None, help="只看某创作意图分组下的所有版本")
    ap.add_argument("--id", default=None, help="看某个产物详情 + 血缘链")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--json", action="store_true", help="输出原始 JSON")
    a = ap.parse_args()

    mf = load_json(scratch_mf_path(), default={"items": []}) or {"items": []}
    items = mf.get("items", [])
    by_id = {it["id"]: it for it in items}

    # ---- 单个产物详情 + 血缘 ----
    if a.id:
        it = by_id.get(a.id)
        if not it:
            fail(STAGE, f"找不到产物：{a.id}")
        chain = _chain(by_id, it)
        log(f"产物 {it['id']}（{it.get('kind')}，v{it.get('version')}，{it.get('status')}）")
        log(f"  prompt: {it.get('prompt')}")
        log(f"  url   : {it.get('url')}")
        log(f"  local : {it.get('local')}")
        log(f"  intent: {it.get('intent')}   time: {_fmt_ts(it.get('ts'))}")
        if len(chain) > 1:
            log("  血缘链（祖先→自身）: " + " → ".join(chain))
        else:
            log("  血缘链: （无父产物，是根）")
        emit({"stage": STAGE, "history": {"count": 1, "items": [it], "chain": chain}})
        return

    # ---- 列表 / 过滤 ----
    sel = items
    if a.kind:
        sel = [it for it in sel if it.get("kind") == a.kind]
    if a.intent:
        sel = [it for it in sel if it.get("intent") == a.intent]

    if a.intent:
        # 同一 intent：按 version 升序，方便看 v1→v2→...
        sel = sorted(sel, key=lambda it: it.get("version", 0))
    else:
        # 默认：按时间倒序，最新在前
        sel = sorted(sel, key=lambda it: it.get("ts", 0), reverse=True)

    total = len(sel)
    sel = sel[:a.limit]

    if a.json:
        print(json.dumps({"count": total, "items": sel}, ensure_ascii=False, indent=2))
    else:
        if not sel:
            log("（暂无产物历史）")
        for it in sel:
            tag = f"v{it.get('version')}"
            par = f" ←{it['parent']}" if it.get("parent") else ""
            log(f"[{it.get('kind')}] {it['id']} {tag}{par}  {it.get('status')}  {_fmt_ts(it.get('ts'))}")
            log(f"    “{_short(it.get('prompt'))}”")
            log(f"    {it.get('url') or '(无url)'}")
        if total > len(sel):
            log(f"… 共 {total} 条，仅显示前 {len(sel)} 条（用 --limit 调整）")

    emit({"stage": STAGE, "history": {"count": total, "items": sel}})


if __name__ == "__main__":
    main()
