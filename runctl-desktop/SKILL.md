---
name: 桌面控制(runctl)
description: 跨平台(macOS/Windows)桌面自动化 / 计算机使用技能，封装 runctl 命令行工具。能力：列出显示器；列出窗口及其 id(多个同名窗口时按 id 精确定位)；截屏(整个虚拟桌面/某个显示器/全部显示器/某个窗口，即使被遮挡)；移动鼠标并点击/右键/双击；激活窗口置顶；滚轮滚动；按下-拖拽-释放；输入文字；按单键或组合键(enter/esc/tab/cmd+a/ctrl+shift+t/alt+f4 等)；用系统默认程序打开 URL/文件/应用；监视某个窗口或屏幕的像素变化，等到首次变化或限时退出(退出码区分)；检查并(在 macOS)申请屏幕录制与辅助功能权限。坐标全程用"对着某窗口截图量出来的像素"(自动套用该窗的偏移与 DPI)。用法是 agent 在自己的工具调用循环里跑一个"感知→理解→决策→执行→核对"的闭环：开头 windows 锁定目标窗口 id、先截图建立「界面地图」(各区域/控件的功能与像素位置)；之后反复地 watch 等窗口变化 → 变化后 shot 截图 → 把截图连同"用户到底要干什么"一起交给图片理解技能(没有就给用户看图确认)，让它回出当前状态+下一步最优单动作+目标像素 → activate 置顶后 click/move/type 执行那一步 → 再截图核对是否生效 → 没完成回到 watch。强调先看懂界面再操作、围绕用户目标想出最优一步、一次只动一步并核对。当用户要：操作桌面或某个应用、点某个按钮、自动填表单、截图看屏幕上有什么、控制微信/某个软件、监听窗口有没有新消息再处理、模拟鼠标键盘、自动化 GUI 操作、把窗口置顶后操作，或提到 runctl 时，使用本技能。
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

runctl 是个单文件桌面控制二进制，暴露一组**"计算机使用"单步原语**（截窗口 / 点击 / 输入 / 等窗口变化 …）。
每条命令是**一次独立的工具调用**：打印一行人类摘要，或加 `--json` 给机器读，
**退出码 0=成功 / 1=错误 / 2=参数错 / 124=watch 超时未变化**。

**循环不在本技能里，在 agent 自己身上。** 本技能不写脚本循环、不起常驻进程——
而是 **agent 在它自己的工具调用循环里**：调一个命令 → 看返回（图/退出码）→ 决定下一个调用，
如此反复，自然转起来。下面《主循环》就是这套要 agent 自己驱动的节奏。

## 核心心法（关键在"脑子"，别只会截图就点）

这些命令只是手脚；干得好不好取决于**每动一步前有没有看懂界面、有没有围绕用户目标想出最优的那一步**。

1. **先看懂界面，再谈操作。** 第一次进入目标窗口，先截整窗，让图片理解产出一张**「界面地图」**：
   有哪些区域/控件、各自什么功能、在图里的像素位置（如微信：左侧会话列表 / 右侧消息区 / 底部输入框 /
   发送按钮，各自范围与中心点）。记下来本会话复用，别每步都从零重认。
2. **图片理解要"带着任务问"，不是泛泛描述。** 把**"用户到底要我干什么"写进提示词**，让模型围绕目标回答：
   现在处于什么状态、下一步最优单动作是什么、目标元素精确像素、有无弹窗异常要先处理。
   （提示词模板见下方《图片理解该怎么问》。）
3. **先想出最优解，再动手。** 拿到理解结果后，选**一个最优动作**，不是一串盲操作。
   不确定 / 有风险 / 没有图片理解技能 → 把截图 + 你的候选判断给**用户确认**再动。
4. **一次一步，动完必核对。** 每次只做一个动作，做完**再截一张图看是否生效**；没生效就重新理解再试，
   绝不盲点连击（坐标错了连点只会越错越远）。
5. **锁定一个窗口 id，全程只盯它。** `windows` 拿 **id**（别用名字，会撞）→ 全程 `--window-id N`，
   坐标统一窗口坐标系。`shot --window-id` 与 `click --window-id` 共用同一坐标空间，截图上得到的像素直接能点。
6. **循环由 agent 自己驱动，靠 watch 退出码分支**（0=变化去处理 / 124=超时再决定 / 1\|2=出错）。

## 主循环（agent 自己一圈圈转，不是脚本）：感知 → 理解(带任务) → 决策 → 执行 → 核对

```
# ── 进入目标窗口：先建立「界面地图」（一次） ──
windows                                   → 选目标窗口，记 id（如 51234）
activate --window-id 51234                → 置顶
shot --window-id 51234 --out ui.png
〈图片理解·建图〉给模型：ui.png +「这是<什么应用>，用户总目标是<…>」
        → 产出界面地图（区域/控件 + 功能 + 像素位置），存为本会话「布局认知」复用

# ── 之后每推进一步，都走完整闭环 ──
loop:
  watch --window-id 51234 --until-change --background-only --duration 60
        exit 124 → 本轮无变化，决定继续等还是收尾
        exit 0   → 有变化，继续↓
  shot --window-id 51234 --out now.png                      # 感知
  〈图片理解·带任务〉给模型：now.png + 用户目标 + 已知布局，要它结构化返回：
        { state, blockers, next_action, target_xy, text, reason, done }
        没有图片理解技能 → 把 now.png + 你的判断给用户，让其确认下一步与坐标   # 理解
  〈决策〉据返回选这一步最优动作；blockers 非空先处理；不确定/有风险先问用户      # 决策
  activate --window-id 51234                                                  # 执行前确保置顶
  click/move --window-id 51234 --x <target_xy> ; type "<text>" ; key enter ; scroll …
  shot --window-id 51234 --out after.png                                     # 核对
  〈核对〉对比 after：动作生效了吗？没生效→重新理解再试；done=true→结束，否则回 loop
```

## 图片理解该怎么问（提示词模板，套用即可）

无论调图片理解技能还是让用户确认，**都要把"用户目标 + 已知布局"喂进去**，让它回**可执行的单步**，而不是泛泛描述：

```
你看到的是 <应用名> 窗口的截图。用户的总目标：<把用户原始需求原样填这>。
已知界面布局：<填上面建好的界面地图；首次没有就写"未知，请一并标出关键控件及其像素位置">。
只依据这张图，用 JSON 回答：
- state:       当前屏幕相对目标处于什么状态（一句话）
- blockers:    有没有弹窗/登录/报错等必须先处理的（没有写 none）
- next_action: 为推进目标，下一步该做的【单个】动作，取值之一：
               click | double_click | right_click | type | key | scroll | wait | done
- target_xy:   该动作目标控件的像素坐标 {x,y}（原点左上角；type/key/wait 可省）
- text:        若 next_action=type 要输入的文字；若 key 则填键名(如 enter)
- reason:      为什么这是当前最优的一步
- done:        总目标是否已完成（true/false）
```

拿到结构化结果后：**先看 blockers**（有就先清）→ 按 `target_xy` 执行**那一个** `next_action` →
截图核对 → `done` 为真则收尾，否则带最新截图再问一轮。

## 统一入口 `./desk`（= runctl）

在本技能目录用 **`./desk <子命令> [参数]`** 调用，等价于 README 里的 `runctl <子命令>`。
封装层自动定位 runctl，并**原样保留它的退出码与输出**（对 `watch` 的 124 很关键）。

- Linux/mac 若提示无权限：先 `chmod +x desk`。
- 备用写法：`python3 desk.py <子命令> ...`（Windows 无 python3 用 `py -3 desk.py ...`）。
- 若 runctl 已在 PATH，直接用 `runctl <子命令>` 也行。

## 第一步：确保安装 + 权限（务必先做）

```sh
./desk setup     # 没装就自动装（cargo 或 macOS install.sh），并跑一遍 runctl check
```

- 返回 `status=needs_setup`/`needs_config` → 把指引转达用户，让其安装 runctl。
- **macOS 必须授权**（agent 代授不了，必须让用户去系统设置点）：
  - **屏幕录制** → `shot` / `watch` 需要（系统设置 › 隐私与安全性 › 屏幕录制）
  - **辅助功能** → `click` / `move` / `type` / `key` 需要（隐私与安全性 › 辅助功能）
  - `./desk check --request` 可触发屏幕录制授权弹窗。
  - 注意：重新编译会重置授权（TCC 绑定签名）；Sequoia 每月左右会重新弹屏幕录制。
- Windows 一般无需授权；要操作"以管理员运行"的窗口，runctl 也需以管理员运行。

## 窗口与坐标

- **怎么指定窗口**：`--window-id N`（精确，**首选**，来自 `windows`）或 `--window <子串>`（按标题/应用名匹配，方便但同名会撞）。
  多个同名窗口（如两个微信窗口）极易选错 → 一律先 `windows` 拿 id，全程 `--window-id`。
- **坐标只用窗口相对像素**：你在 `shot --window-id N` 那张 PNG 上得到的 (x,y)，直接喂 `click/move --window-id N`，
  runctl 自动套该窗口的偏移 + DPI。**不要去算全局坐标**（除非确有跨窗口需求）。
- 习惯动作：拿不准时点之前先 `move` 同样坐标，确认落点再 `click`。

## 命令清单（都用 `./desk` 调；完整示例见 README）

| 子命令 | 作用 | 关键参数 |
|---|---|---|
| `windows` | 列窗口及其 **id**（循环开头用它锁定目标） | `--json` |
| `list` | 列显示器（index/偏移/尺寸/scale/主屏） | `--json` |
| `shot` | 截屏到 PNG | `--out`，`--window-id N`/`--window 子串`（也支持 `--screen N\|all\|full`） |
| `activate` | 窗口置顶（点击/输入前必做） | `activate --window-id N` 或 `activate 子串` |
| `move` / `click` | 移动 / 点击 | `--window-id N`（或 `--window 子串`）+ `--x --y`，`--button right`，`--double` |
| `type` | 在当前焦点输入文字（先 activate 置顶并点进输入框） | `type "文本"` |
| `key` | 单键/组合键 | `key enter` / `key cmd+a` / `key ctrl+shift+t` |
| `scroll` | 滚轮 | `--dir up\|down --amount N`，可带 `--window-id/--x/--y` |
| `drag` | 按下→拖→释放 | `--from-x --from-y --to-x --to-y`（可带 `--window-id`） |
| `watch` | 监视窗口像素变化（循环的"等事件"那步） | 见下 |
| `open` | 用默认程序打开 | `open <url\|文件\|app>` |
| `check` | 报告（macOS 可申请）权限 | `--request` |

## watch 用法要点（循环里"等窗口变化"那步）

- 目标用 `--window-id N`（每轮重新解析，关了再开也不丢）。也可 `--window <子串>` / `--screen <N|primary|full>`。
- **限时 + 等一次变化**：`--until-change --duration <秒>` = "最多等 N 秒等一次变化"，
  用退出码分支（**0=变了 / 124=超时 / 1\|2=出错**）。这是 agent 循环最顺手的形态：一调一返，不挂死。
- **建议加 `--background-only`**：只在窗口**没被聚焦**时才算变化——这样 agent 自己 activate/click/type 的操作
  不会被误判成"窗口变了"，更接近"外部来了新东西（如新消息）"的信号。
- 调灵敏度：`--threshold`(变化像素占比阈值，调高滤掉小抖动) `--cooldown`(触发后静默毫秒，去抖) `--interval`(轮询毫秒)。
- **它只认像素变化、不认语义**：分不清"新消息"还是滚动/时间戳跳动。靠 `--background-only` + 调高 `--threshold` + `--cooldown` 逼近"新消息"信号；要更准就把截图交给图片理解技能去判断这次变化是不是要处理的事。
- 进阶通知（一般用不上）：长驻 watch 可用 `--exec '<命令>'`（事件进 `RUNCTL_EVENT/TARGET/RATIO/TS` 环境变量）或
  `--webhook <url>`（POST 事件 JSON，加 `--post-image` 附 base64 截图）。但 agent 自循环里**优先用 `--until-change` + 退出码**，更可控。

## 安全与边界

- 能截窗口、能点任意位置 = 很大的权限面。在 agent 环境里应**约束何时能截、能点哪里**，不要把整机控制权无限制交给模型。
- runctl 操作的是**运行它的那台机器**的真实桌面；务必确认是在用户期望的机器上跑。
- **没有图片理解技能时，点击位置一定要让用户确认**（给用户看截图再点），不要凭猜点。
- 涉及发送消息、提交表单、关闭窗口（`key alt+f4`/`cmd+w`）等不可逆/外发动作，先确认再执行。
