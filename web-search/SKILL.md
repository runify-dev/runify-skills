---
name: 浏览器检索
description: 联网检索与网页正文抽取技能：搜索网页、抓取某网页抽正文(可转 markdown)、或搜了直接读前几条。当用户要联网搜索、查资料、找最新信息、读取或总结某个网页、把网页转成文字/markdown，或说"上网查/搜一下"时使用。
metadata:
  runify:
    requires: []          # 仅依赖 Python>=3.6 与 requests，无系统级依赖、无需浏览器
    envVars:
      - name: WEB_SEARCH_PROVIDER
        type: SingleSelect
        required: false
      - name: SERPER_API_KEY
        type: PasswordInput
        required: false
      - name: TAVILY_API_KEY
        type: PasswordInput
        required: false
      - name: WEB_HTTP_PROXY
        type: TextInput
        required: false
    # ┌─ type 取自 dynamics-form-plus 组件名：下拉 -> SingleSelect，文本 -> TextInput，密码 -> PasswordInput。
    # └─ showRules：API key 字段跟随 provider 联动显隐。
    skillParameterForm:
      - field: WEB_SEARCH_PROVIDER
        label:
          value: 搜索后端
          tooltip: 默认 duckduckgo（免 key、开箱即用）。需要更高质量/稳定性可选 serper 或 tavily，并在下方填对应 key。
          type: TooltipLabel
        required: false
        type: SingleSelect
        defaultValue: duckduckgo
        optionList:
          - { label: DuckDuckGo（免key，默认）, value: duckduckgo }
          - { label: Serper（需Key）, value: serper }
          - { label: Tavily（需Key）, value: tavily }
        labelField: label
        valueField: value

      - field: SERPER_API_KEY
        label: { value: Serper API Key, tooltip: serper.dev 的 API Key（敏感）；仅搜索后端选 serper 时需要, type: TooltipLabel }
        required: false
        type: PasswordInput
        showRules: { condition: and, conditions: [ { field: WEB_SEARCH_PROVIDER, compare: eq, value: serper } ] }

      - field: TAVILY_API_KEY
        label: { value: Tavily API Key, tooltip: tavily.com 的 API Key（敏感）；仅搜索后端选 tavily 时需要, type: TooltipLabel }
        required: false
        type: PasswordInput
        showRules: { condition: and, conditions: [ { field: WEB_SEARCH_PROVIDER, compare: eq, value: tavily } ] }

      - field: WEB_HTTP_PROXY
        label: { value: HTTP 代理（可选）, tooltip: 形如 http://host:port；服务器需经代理上网时填，留空则直连, type: TooltipLabel }
        required: false
        type: TextInput
# 说明：
#   - 不填任何配置即可用：默认走 DuckDuckGo，免 API key。
#   - 仅当把"搜索后端"切到 serper/tavily 时才需要对应的 API key。
#   - 纯 HTTP 抓取，不渲染 JavaScript：强 JS 单页应用可能取不到正文（这类站点需另配无头浏览器，不在本技能范围）。
---

# 浏览器检索（联网搜索 + 网页正文抽取）

一组**自由原子工具**（互不依赖、随调随用），让 agent 能上网查资料、读网页：

- **`search`** —— 给关键词/问题，返回若干条结果（标题 / 链接 / 摘要），不抓正文。
- **`fetch`** —— 抓取一个网页并抽取正文（去掉脚本/导航/页脚），输出纯文本或 markdown。
- **`search_read`** —— 一步到位：先搜索，再自动抓取并抽取前 N 条结果的正文。

纯 HTTP 抓取 + 标准库解析，**不渲染 JavaScript、无需安装浏览器**。默认搜索后端是
DuckDuckGo（免 key），可在技能设置里切到 Serper / Tavily。

## 先判意图，再选工具

| 用户想要的 | 用哪个 |
|---|---|
| 只想拿到一批相关链接/出处 | `search` |
| 已有某个 URL，想读它的正文 | `fetch` |
| "帮我查 X 并把要点读出来/总结" | `search_read`（搜+读一步到位） |
| 先搜，再挑其中几条细读 | `search` → 对选中的 url 逐个 `fetch` |

## 统一入口

所有工具都通过 `./web <命令> [参数]` 调用，无需写解释器/路径/后缀。
**Linux、macOS、Windows 都用 `./web <命令>`**（类 Unix 走 `web`，Windows 走 `web.cmd`）。
不带命令时列出全部。

- Linux/mac 若提示无权限：先 `chmod +x web`。
- 备用（要绝对确定性）：`python3 web.py <命令> ...`（Windows 无 python3 时用 `py -3 web.py ...`）。

约定：结果走 stdout 的最后一行 `RESULT_JSON: {...}`；进度走 stderr；退出码恒 0，
成功/失败/needs_config 都在 RESULT_JSON 里按 `status` 区分。

## 原子工具与参数

**`./web search`** 网络搜索
- 必填：`--query/-q "关键词或问题"`
- 可选：`--max/-n 条数`（默认 8）
- 返回：`results[]`，每条含 `title / url / snippet`

**`./web fetch`** 抓取网页并抽取正文
- 必填：`--url/-u https://...`
- 可选：`--format/-f text|markdown`（默认 text；markdown 保留标题层级/链接/列表）、
  `--max-chars/-m N`（正文最多保留 N 字符，0=不限）
- 返回：`title / url / content / length / truncated`

**`./web search_read`** 搜索 + 自动读取前 N 条正文
- 必填：`--query/-q "..."`
- 可选：`--top/-t N`（抓前 N 篇正文，默认 3）、`--max/-n 条数`（搜索结果数，默认 8）、
  `--format/-f text|markdown`、`--max-chars/-m N`（每篇正文上限，默认 4000）
- 返回：`results[]`（全部命中）+ `pages[]`（前 N 篇的正文）

## 使用要点

- **引用出处**：把结果/正文转述给用户时，带上对应 `url` 作为来源，便于核实。
- **正文为空怎么办**：目标多半是强 JS 站点（内容靠浏览器跑 JS 才出来），本技能不渲染 JS。
  可换一个信息源、或改用 `search_read` 读其它命中页。
- **needs_config**：把搜索后端切成 serper/tavily 但没填对应 key 时，工具返回
  `status=needs_config`（退出码 0）。读到后停下，转达用户去技能设置填 key，或把后端改回 duckduckgo。
- **截断**：`fetch`/`search_read` 默认对正文有字符上限（避免一次塞爆上下文）；要全文加大或去掉 `--max-chars`。
