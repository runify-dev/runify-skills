#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
浏览器检索 · 公共模块
所有原子工具（search / fetch / search_read）共用：配置、HTTP 客户端、
搜索后端、HTML 正文抽取、统一 RESULT_JSON 输出。

契约（与 agnes-ai 一致，便于同一 agent 复用）：
- 进度/日志走 stderr；最后一行 stdout 打印 `RESULT_JSON: {...}` 供 agent 解析。
- 退出码恒 0：成功/失败/needs_config 都在 RESULT_JSON 里，调用方按 status 区分。
- 配置从环境变量读（见 SKILL.md 的 envVars）；只依赖标准库 + requests，无浏览器。
"""
import os
import re
import sys
import json
import time
import html as _html
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs, unquote, urljoin

import requests

# ======================= 配置（可被 env 覆盖） =======================
# 搜索后端：duckduckgo（默认，免 key）| serper（需 SERPER_API_KEY）| tavily（需 TAVILY_API_KEY）
PROVIDER        = (os.environ.get("WEB_SEARCH_PROVIDER") or "duckduckgo").strip().lower()
SERPER_API_KEY  = os.environ.get("SERPER_API_KEY", "").strip()
TAVILY_API_KEY  = os.environ.get("TAVILY_API_KEY", "").strip()

HTTP_TIMEOUT = int(os.environ.get("WEB_HTTP_TIMEOUT", "30"))
RETRY_MAX     = 2
RETRY_BACKOFF = 1.5
USER_AGENT = os.environ.get(
    "WEB_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
)
# 可选代理：WEB_HTTP_PROXY=http://host:port（同时用于 http/https）
_PROXY = os.environ.get("WEB_HTTP_PROXY", "").strip()
PROXIES = {"http": _PROXY, "https": _PROXY} if _PROXY else None


# ======================= 统一输出 =======================
def log(*a):
    print(*a, file=sys.stderr, flush=True)

def emit(result: dict, code: int = 0):
    result.setdefault("status", "ok")
    print("RESULT_JSON: " + json.dumps(result, ensure_ascii=False), flush=True)
    sys.exit(code)

def fail(stage: str, message: str, **extra):
    payload = {"status": "error", "stage": stage, "error": message}
    payload.update(extra)
    print("RESULT_JSON: " + json.dumps(payload, ensure_ascii=False), flush=True)
    sys.exit(0)

def needs_config(stage: str, message: str, **extra):
    """缺配置时走成功通道（退出码 0），把指引透传给 agent 转达用户。"""
    payload = {"status": "needs_config", "stage": stage, "message": message,
               "where": "Runify 技能设置界面 → 本技能参数配置"}
    payload.update(extra)
    print("RESULT_JSON: " + json.dumps(payload, ensure_ascii=False), flush=True)
    sys.exit(0)


# ======================= HTTP 客户端（带重试） =======================
def _request(method, url, **kwargs):
    kwargs.setdefault("timeout", HTTP_TIMEOUT)
    if PROXIES:
        kwargs.setdefault("proxies", PROXIES)
    headers = kwargs.pop("headers", {}) or {}
    headers.setdefault("User-Agent", USER_AGENT)
    last = None
    for attempt in range(RETRY_MAX + 1):
        try:
            if attempt > 0:
                wait = RETRY_BACKOFF * (2 ** (attempt - 1))
                log(f"  ↻ 第 {attempt}/{RETRY_MAX} 次重试 {method} {url.split('?')[0]} …")
                time.sleep(wait)
            r = requests.request(method, url, headers=headers, **kwargs)
            if r.status_code >= 500 or r.status_code == 429:
                raise requests.HTTPError(f"HTTP {r.status_code}")
            return r
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.HTTPError) as e:
            last = e
    raise RuntimeError(f"请求失败（重试 {RETRY_MAX} 次）：{last}")

def http_get(url, **kw):  return _request("GET", url, **kw)
def http_post(url, **kw): return _request("POST", url, **kw)


# ======================= 搜索后端 =======================
def _ddg_unwrap(href):
    """DuckDuckGo 结果链接常是 //duckduckgo.com/l/?uddg=<编码后的真实URL> 的跳转，解出真实 URL。"""
    if href.startswith("//"):
        href = "https:" + href
    try:
        q = parse_qs(urlparse(href).query)
        if "uddg" in q:
            return unquote(q["uddg"][0])
    except Exception:
        pass
    return href

def search_duckduckgo(query, max_results):
    """DuckDuckGo HTML 端点，免 API key。解析 result__a / result__snippet。"""
    r = http_post("https://html.duckduckgo.com/html/", data={"q": query},
                  headers={"Referer": "https://html.duckduckgo.com/"})
    body = r.text
    items = []
    # 每个结果含一个 result__a（标题+链接），随后一个 result__snippet（摘要）
    link_re = re.compile(
        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.S)
    snip_re = re.compile(
        r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', re.S)
    links = link_re.findall(body)
    snips = snip_re.findall(body)
    for i, (href, title) in enumerate(links):
        if len(items) >= max_results:
            break
        url = _ddg_unwrap(href)
        if not url.startswith("http"):
            continue
        snippet = snips[i] if i < len(snips) else ""
        items.append({
            "title": _strip_tags(title).strip(),
            "url": url,
            "snippet": _strip_tags(snippet).strip(),
        })
    return items

def search_serper(query, max_results):
    if not SERPER_API_KEY:
        needs_config("search", "已选 serper 后端但缺少 SERPER_API_KEY，请在技能设置里填写，"
                               "或把搜索后端改回 duckduckgo（免 key）。")
    r = http_post("https://google.serper.dev/search",
                  headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
                  json={"q": query, "num": max_results})
    r.raise_for_status()
    data = r.json()
    items = []
    for it in (data.get("organic") or [])[:max_results]:
        items.append({"title": it.get("title", ""), "url": it.get("link", ""),
                      "snippet": it.get("snippet", "")})
    return items

def search_tavily(query, max_results):
    if not TAVILY_API_KEY:
        needs_config("search", "已选 tavily 后端但缺少 TAVILY_API_KEY，请在技能设置里填写，"
                               "或把搜索后端改回 duckduckgo（免 key）。")
    r = http_post("https://api.tavily.com/search",
                  json={"api_key": TAVILY_API_KEY, "query": query,
                        "max_results": max_results})
    r.raise_for_status()
    data = r.json()
    items = []
    for it in (data.get("results") or [])[:max_results]:
        items.append({"title": it.get("title", ""), "url": it.get("url", ""),
                      "snippet": it.get("content", "")})
    return items

def web_search(query, max_results=8):
    if PROVIDER == "serper":
        return search_serper(query, max_results)
    if PROVIDER == "tavily":
        return search_tavily(query, max_results)
    return search_duckduckgo(query, max_results)


# ======================= HTML → 正文抽取 =======================
# 注意：不把 <head> 整段丢掉，否则读不到 <title>；噪声靠单独丢 script/style/noscript。
_DROP_TAGS = {"script", "style", "noscript", "header", "footer",
              "nav", "aside", "form", "svg", "iframe", "template"}
_BLOCK_TAGS = {"p", "div", "section", "article", "br", "li", "tr", "table",
               "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre"}
_HEADINGS = {"h1": "# ", "h2": "## ", "h3": "### ",
             "h4": "#### ", "h5": "##### ", "h6": "###### "}


class _Extractor(HTMLParser):
    """轻量正文抽取：丢弃脚本/导航等噪声标签，块级标签换行；
    markdown 模式额外保留标题层级、链接、列表项符号。仅用标准库，不渲染 JS。"""
    def __init__(self, base_url="", markdown=False):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.markdown = markdown
        self.out = []
        self._skip_depth = 0
        self._title = None
        self._in_title = False
        self._href = None

    def handle_starttag(self, tag, attrs):
        if tag in _DROP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = True
        if tag in _BLOCK_TAGS:
            self.out.append("\n")
        if self.markdown and tag in _HEADINGS:
            self.out.append(_HEADINGS[tag])
        if self.markdown and tag == "li":
            self.out.append("- ")
        if self.markdown and tag == "a":
            d = dict(attrs)
            self._href = d.get("href")
            if self._href:
                self.out.append("[")

    def handle_endtag(self, tag):
        if tag in _DROP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = False
        if self.markdown and tag == "a" and self._href is not None:
            full = urljoin(self.base_url, self._href) if self.base_url else self._href
            self.out.append(f"]({full})")
            self._href = None
        if tag in _BLOCK_TAGS:
            self.out.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title:
            if self._title is None:
                self._title = data.strip()
            return  # 标题只进 title 字段，不混进正文
        text = data.strip("\n")
        if text.strip():
            self.out.append(text)

    def text(self):
        raw = "".join(self.out)
        # 折叠多余空白：每行去首尾空格，合并 3+ 连续空行为 1 个空行
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in raw.splitlines()]
        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return cleaned


def fetch_extract(url, markdown=False, max_chars=0):
    """抓取 url 并抽取正文。返回 dict(title, url, content, truncated, length)。"""
    r = http_get(url)
    r.raise_for_status()
    ctype = (r.headers.get("Content-Type") or "").lower()
    if "html" not in ctype and "xml" not in ctype and "text" not in ctype:
        # 非文本（pdf/图片等）不解析，直接报类型
        return {"title": "", "url": r.url, "content": "",
                "content_type": ctype, "note": "非文本内容，未抽取正文",
                "length": 0, "truncated": False}
    # 让 requests 用响应声明的编码；缺省时按 apparent_encoding 兜底
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding or "utf-8"
    ex = _Extractor(base_url=r.url, markdown=markdown)
    ex.feed(r.text)
    content = ex.text()
    title = ex._title or ""
    truncated = False
    if max_chars and len(content) > max_chars:
        content = content[:max_chars]
        truncated = True
    return {"title": _html.unescape(title), "url": r.url, "content": content,
            "content_type": ctype, "length": len(content), "truncated": truncated}


def _strip_tags(s):
    return _html.unescape(re.sub(r"<[^>]+>", "", s or ""))


# ======================= 可选落盘（与 agnes 一致的根目录约定） =======================
def out_root():
    return os.environ.get("RUNIFY_OUTPUT_DIR") or os.path.join(os.getcwd(), "project")
