---
name: 桌面控制(runctl)
description: 跨平台(macOS/Windows)桌面自动化/计算机使用技能，封装 runctl 命令行用截图+视觉来操作桌面应用。当用户要操作桌面或某个应用——点按钮、填表单、控制微信/某软件、截图看屏幕上有什么、监听窗口有没有新消息再处理、模拟鼠标键盘、自动化 GUI 操作——或提到 runctl 时使用。
metadata:
  runify:
    requires:
      - runctl   # 单文件二进制；缺失时可用 `./desk setup` 自动安装（cargo 或 macOS install.sh）
    envVars:
      - name: RUNCTL_VERSION
        type: TextInput
        required: false
      - name: RUNCTL_INSTALL_DIR
        type: TextInput
        required: false
    skillParameterForm:
      - field: RUNCTL_VERSION
        label:
          value: runctl 版本(可选)
          tooltip: 安装时固定到某个 tag，如 v0.1.0；留空装最新。仅 `./desk setup` 用到
          type: TooltipLabel
        required: false
        type: TextInput
      - field: RUNCTL_INSTALL_DIR
        label:
          value: 安装目录(可选)
          tooltip: 自定义 runctl 安装目录；留空用默认(~/.cargo/bin 或 /usr/local/bin)。仅 macOS install.sh 路径用到
          type: TooltipLabel
        required: false
        type: TextInput
# 说明：
#   - runctl 必须装在【运行本技能的那台机器】上（它直接操作那台机器的桌面）。
#   - 真正的桌面操作都由 runctl 完成；本技能只做"定位/安装 runctl + 原样转发 + 保留退出码"。
#   - macOS 受 TCC 管控：必须由用户在系统设置里授予 屏幕录制 + 辅助功能，agent 无法代授。
---

# 桌面控制（runctl）

runctl 是单文件桌面控制二进制，提供 截图 / 点击 / 输入 / 等变化 等**单步原语**。
**循环由 agent 自己跑**：调一步 → 看结果 → 决定下一步，本技能不写脚本、不起常驻进程。
每条命令加 `--json` 给机器读，**退出码 0=成功 / 1=错 / 2=参数错 / 124=watch 超时无变化**。

**怎么调**：直接 `runctl <子命令>`（已装在 PATH）。**下文命令一律用 `runctl`，照抄即可。**
> 仅当没装 runctl 时：本技能附带 `./desk` 入口，跑一次 `./desk setup` 自动安装，装好后照常用 `runctl`。
> （`./desk <子命令>` 与 `runctl <子命令>` 完全等价，二选一，别混着用。）

---

## ⭐ 铁律：坐标只有一种正确传法（最容易错，先记死）

**三步，缺一不可：**

1. **截图带 `--json` + `--grid`**，从输出读这张图的 `width` / `height`：
   ```
   runctl --json shot --window-id <ID> --grid --out "$RUNIFY_OUTPUT_DIR/now.png"
   → {"ok":true,"action":"shot","width":W,"height":H,"path":".../now.png"}
   ```
   ⛔ **任何 `shot` 都必须带 `--grid`，没有例外**（核对那张也带）——`--grid` 叠一层**带刻度的坐标网格**，
   刻度即截图像素坐标，视觉照格线读 (x,y) 才准；不带网格 = 让模型凭空猜坐标，必偏。
   （太密可 `--grid edge` 只标边缘刻度、`--grid-step 50` 调间距。）
   （**截图一律写进 `$RUNIFY_OUTPUT_DIR`**，见下《截图落盘》。）
2. **视觉在这张带网格的图上定出目标像素 `(x,y)`**（左上角为原点，照最近格线刻度估）。
3. **点击/移动/滚动/拖拽时，把这张图的 W、H 一起传 `--shot-w`/`--shot-h`**：
   ```
   runctl click --window-id <ID> --x <x> --y <y> --shot-w W --shot-h H
   ```
   runctl 自动把 (x,y) **按比例映射**到窗口实时矩形——**任何 DPI/缩放都准，不用你算**。

> ⚠ **永远成对传 `--shot-w --shot-h`**。不传时 x/y 被当成"窗口内未缩放的点"，几乎必偏。
> 窗口**一律用 id 锁定**：先 `runctl --json windows` 拿目标窗口 id，全程 `--window-id <ID>`（用名字会撞）。

---

## ⭐ 能按键就别找按钮（键盘优先，最省事最可靠）

定位按钮再点，又慢又易点偏。**凡是有键盘途径的，一律 `key`/`type`，别截图找按钮：**

- **发消息 / 提交 / 搜索**（微信、聊天、搜索框、表单）：`type "内容"` 后**直接 `runctl key enter` 发送**——**绝不去找"发送"按钮**。
- **找具名目标**（联系人/会话/文件/设置项）：**优先用应用的搜索框**——`click 搜索框 → type "名字" → key enter`，别让视觉去聊天列表里**扫/滚动找坐标**（人不在可视区就找不到）。
- 关弹窗/取消：`key esc`；换输入框/字段：`key tab`；全选/复制粘贴：`cmd+a`(Win `ctrl+a`) 等。
- **只有没有键盘等价**的目标（某个图标、链接、菜单项）才走"截图→读坐标→`click`"。

## 干活的节奏：看清 → 成批做完一段 → 核对（**别一步一截图**）

**能预判的连续动作一口气做完，做完一"段"再截图核对。** 截图只在两种时刻发生：
**① 需要看清状态/定位某控件时；② 做完一段要确认结果时。** 中间可预判的动作（尤其键盘）别拆开、别逐个截图。

**开头**：`runctl --json windows` 选目标、记下 id，之后全程 `--window-id <ID>`。然后循环（直到 `done`）：
1. **看清**（仅当需要）：`runctl --json shot --window-id <ID> --grid --out "$RUNIFY_OUTPUT_DIR/now.png"`（记 W、H）。
   位置已知（上一段刚确认过、或搜索框/输入框这类固定控件）就别重复截图。
2. **想清这一段**：带着**具体目标**问视觉（模板见下），让它回 `{state, plan, done}`——
   `plan` 是**接下来能一口气做的几步**（每步 `{action, xy?, text?}`）。位置未知才让它给 `xy`。
3. **成批做完这一段**：`activate` 确保焦点后，**连着执行 plan 里的几步、中间不截图**。例：
   `click 搜索框 → type "张少虎" → key enter`；或进会话后 `click 输入框 → type "消息" → key enter`。
   （位置已知的 click 直接做；位置未知才回第 1 步截图定位，别瞎点。键盘优先见上节。）
4. **核对**：这一段做完再 `runctl --json shot --window-id <ID> --grid --out "$RUNIFY_OUTPUT_DIR/after.png"` 看结果。
   符合预期 → 继续下一段 / `done` 收尾；不符 → 回第 1 步看清再调整。

> **一次性任务**（点个按钮、填个表、开个设置）就这样转，不需要 watch。

**只有当任务是"等窗口出现变化再处理"时**（如盯微信新消息回复），才在每轮的"看清"之前加一道 `watch` 门：
```
runctl watch --window-id <ID> --until-change --background-only --duration 60
  exit 0  → 窗口变了，进入上面的循环
  exit 124 → 这段时间没动，决定继续等还是收尾
```

### 给视觉的提问：目标性提问，让它回"一段动作"

**把具体目标带进去**，并让它回**接下来能一口气做的几步（`plan`）**，而不是只回一步：

```
这是 <应用> 窗口截图（已叠坐标网格，刻度=图像像素），尺寸 W×H。
我的目标：<具体目标，如"跟张少虎发一条消息：晚上一起吃饭吗">。
为达成目标，只看这张图，用 JSON 回答：
- state    当前图片什么状态、相对目标到哪一步了（一句话）
- plan     接下来能一口气做的连续动作数组，每项 {action, xy?, text?}：
           action ∈ click|double_click|type|key|scroll|done
           xy 仅当该步要点且位置能从图上读出时给（照网格刻度，左上原点）
           text：type 的文字 / key 的键名(如 enter)
           （键盘优先：发送/提交用 key enter，别在 plan 里塞"点发送按钮"）
- blockers 有弹窗/登录/报错要先处理吗（无则 none）
- done     目标是否已完成 true/false
```

**例：跟张少虎聊天**（成批做，不一步一截图）——
1. 截一张 → 问上面模板 → 视觉回 `plan = [click 搜索框, type "张少虎", key enter]`
   → **连着做完这三步**（不中途截图）。
2. 截一张核对"进了和张少虎的会话吗" → 回 `plan = [click 输入框, type "晚上一起吃饭吗", key enter]`
   → **连着做完**。
3. 截一张核对"消息发出了吗" → `done=true` 收尾。

→ 整个聊天就 **3 次截图**（每段做完核对一次），而不是七八次。

> 要点：**目标一字不改地带进每一轮提问**；每轮只问"为了这个目标、看这张图、现在做哪一步"，AI 自然给出"点张三 / 点输入框 / 打字回车"，不会跑偏去描述无关元素。

---

## 截图落盘：一律写进 `$RUNIFY_OUTPUT_DIR`

- **所有 `shot --out` 都写到 `$RUNIFY_OUTPUT_DIR` 下**（运行时注入的会话落盘目录），
  如 `--out "$RUNIFY_OUTPUT_DIR/now.png"`。好处：不污染工作目录；图在会话挂载目录里，
  **图片理解技能、展示给用户都能直接拿到**（如平台的 `./api/storage/file/...`）。
- 用固定几个名字（`ui/now/after`）**覆盖**即可，别按时间戳堆积——watch 可能跑很久，会塞满盘。
- 该变量是 env、每条命令都能直接引用。**未设置**（本地直跑）时退回临时目录：mac/Linux `/tmp`、Windows `%TEMP%`。

## 命令速查（统一用 `runctl`）

| 命令 | 用途 | 关键参数 |
|---|---|---|
| `windows` | 列窗口 + id（开头锁定用） | `--json` |
| `shot` | 截图（**一律 `--json --grid`**：拿 W/H + 叠坐标网格，无例外） | `--window-id N`，`--out`，`--grid`(**必带**；可 `edge` / `--grid-step N`) |
| `activate` | 置顶（做动作前必做） | `activate --window-id N` |
| `click` / `move` | 点击 / 移动 | `--window-id N --x --y --shot-w W --shot-h H`；`--button right`；`--double` |
| `type` | 输入到当前焦点（先 activate 并点进输入框） | `type "文本"` |
| `key` | 按键 / 组合键 | `key enter` / `key cmd+a`(Win 用 `ctrl+a`) / `key alt+f4` |
| `scroll` | 滚动 | `--window-id N --x --y --shot-w W --shot-h H --dir up\|down --amount N` |
| `drag` | 拖拽 | `--from-x --from-y --to-x --to-y`（可带 `--shot-w/--shot-h`） |
| `watch` | 等窗口变化（"等事件"那步） | `--window-id N --until-change --background-only --duration <秒>` |
| `open` | 系统默认程序打开 | `open <url\|文件\|app>` |
| `check` | 报告/申请权限 | `--request` |

## watch 要点（仅"等事件再处理"类任务才用）

- `--until-change --duration <秒>` = "最多等 N 秒等一次变化"，靠**退出码分支**（0 变 / 124 超时 / 1\|2 错）。
  一调一返、不挂死——需要等外部变化时用它当门，其余任务不用。
- `--background-only`：只在窗口**非聚焦**时算变化，避免把 agent 自己的 click/type 误判成"新变化"。
- 它只认像素变化、不认语义：用 `--threshold`（滤小抖动）`--cooldown`（去抖）逼近"有新东西"；
  要判断"是不是该处理的事"，靠把截图交给视觉。

## 安装 + 权限（首次）

`./desk setup`：没装就自动装（cargo 或 macOS install.sh），并跑一遍 `check`。
- **macOS 必须由用户去系统设置授权**（agent 代授不了）：**屏幕录制**（shot/watch）、**辅助功能**（click/move/type）。
  `./desk check --request` 可触发屏幕录制弹窗。重新编译会重置授权（TCC 绑签名）。
- Windows 一般无需授权；要操作"管理员窗口"，runctl 也要以管理员运行。

## 安全

- 能截能点 = 权限面很大：约束**何时截、点哪里**，别无限放权给模型。
- 操作的是**运行机的真实桌面**，确认是对的机器。
- **没有图片理解技能时，点击位置必须用户确认**，不许凭猜。
- 发消息 / 提交表单 / 关窗（`alt+f4`、`cmd+w`）等不可逆动作，先确认再做。
