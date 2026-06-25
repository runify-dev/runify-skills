---
name: 桌面控制(runctl)
description: 跨平台(macOS/Windows)桌面自动化 / 计算机使用技能，封装 runctl 命令行工具。能力：列出显示器；列出窗口及其 id(多个同名窗口时按 id 精确定位)；截屏(整个虚拟桌面/某个显示器/全部显示器/某个窗口，即使被遮挡)；移动鼠标并点击/右键/双击；激活窗口置顶；滚轮滚动；按下-拖拽-释放；输入文字；按单键或组合键(enter/esc/tab/cmd+a/ctrl+shift+t/alt+f4 等)；用系统默认程序打开 URL/文件/应用；监视某个窗口或屏幕的像素变化，等到首次变化或限时退出(退出码区分)；检查并(在 macOS)申请屏幕录制与辅助功能权限。坐标全程用"对着某窗口截图量出来的像素"(自动套用该窗的偏移与 DPI)。用法是 agent 在自己的工具调用循环里一个个调这些命令：开头 windows 锁定目标窗口 id → 反复地 watch 等窗口变化 → 变化后 activate 置顶并 shot 截图 → 把截图交给图片理解技能(没有就给用户看图让其确认点哪) → click/move/type 操作 → 回到 watch。当用户要：操作桌面或某个应用、点某个按钮、自动填表单、截图看屏幕上有什么、控制微信/某个软件、监听窗口有没有新消息再处理、模拟鼠标键盘、自动化 GUI 操作、把窗口置顶后操作，或提到 runctl 时，使用本技能。
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

## 四条心法（先记牢，再看命令）

1. **锁定一个窗口 id，全程只盯它。** 开头 `windows` 拿到目标窗口的 **id**（别用名字，会撞），
   之后每个 `shot / move / click / activate / watch` 都带 `--window-id N`，坐标统一在该窗口坐标系。
2. **循环由 agent 自己用工具调用驱动**，不是脚本、不是常驻 watch+回调。每步一次调用，看结果再走下一步。
3. **截图后必须先"理解"再动手**，而且 agent 不假定自己能直接看图——
   **有图片理解技能 → 调它**看懂截图、定出目标像素；**没有图片理解技能 → 把截图给用户，让用户确认点哪里**（给坐标或指出目标）。
4. **靠退出码分支。** `watch --until-change` 返回 0=有变化（去处理）/ 124=超时（再决定继续等还是收尾）/ 1\|2=出错。

## 主循环（agent 反复调这些工具，**不是 shell 脚本**）

```
# ── 开头一次：锁定目标窗口 ──
windows                              → 从列表里挑出目标窗口，记下它的 id（如 51234）

# ── 之后 agent 自己一圈圈转 ──
loop:
  watch --window-id 51234 --until-change --background-only --duration 60
        → exit 124（这一轮没变化）：agent 决定继续 loop 还是停
        → exit 0（窗口变了）：进入处理↓
  activate --window-id 51234         → 置顶（type/click 作用于当前焦点，必须先置顶）
  shot --window-id 51234 --out f.png → 截这个窗口（被遮挡也能截）
  〈理解 f.png〉
     有图片理解技能 → 调它读 f.png：屏幕上发生了什么 + 要点的目标在图里的像素 (x,y)
     没有          → 把 f.png 展示给用户，问"点哪里/做什么"，拿到用户确认的坐标或指令
  click --window-id 51234 --x <x> --y <y>   → 点击（坐标就是上一步在这张图上得到的像素）
  type "…"  /  key enter  /  scroll …       → 按任务干事
  → 回到 loop 顶部，再起一次 watch
```

要点：`shot --window-id` 与 `click --window-id` **共用同一套坐标空间**——你在截图上量到/得到的像素，
直接拿去 `click --window-id` 就能点中，runctl 自动按窗口实时位置 + DPI 换算。

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
