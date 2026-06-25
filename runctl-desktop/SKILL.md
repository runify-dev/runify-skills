---
name: 桌面控制(runctl)
description: 跨平台(macOS/Windows)桌面自动化 / 计算机使用技能，封装 runctl 命令行工具。能力：列出显示器；列出窗口及其 id(多个同名窗口时按 id 精确定位)；截屏(整个虚拟桌面/某个显示器/全部显示器/某个窗口，即使被遮挡)；移动鼠标并点击/右键/双击；激活窗口置顶；滚轮滚动；按下-拖拽-释放；输入文字；按单键或组合键(enter/esc/tab/cmd+a/ctrl+shift+t/alt+f4 等)；用系统默认程序打开 URL/文件/应用；监视某个窗口或屏幕的像素变化，变化时输出事件/执行命令/POST webhook(可附截图)，支持等到首次变化或限时退出；检查并(在 macOS)申请屏幕录制与辅助功能权限。坐标支持全局坐标，或"对着某显示器/某窗口的截图量出来的像素"(自动套用该屏/该窗的偏移与 DPI)。典型回路：截屏→视觉模型判断目标位置→激活窗口→点击输入框→输入文字→回车发送；或：监视窗口→等到有变化→截屏→判断→回复。当用户要：操作桌面或某个应用、点某个按钮、自动填表单、截图看屏幕上有什么、控制微信/某个软件、监听窗口有没有新消息再处理、模拟鼠标键盘、自动化 GUI 操作、把窗口置顶后操作，或提到 runctl 时，使用本技能。
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

把 runctl 这个单文件桌面控制二进制包成技能。runctl 暴露一组"计算机使用"原语
（截屏 / 点击 / 输入 / 监视窗口 …），每条命令是一次独立进程调用，打印一行人类摘要，
或加 `--json` 给机器读，**退出码 0=成功 / 1=错误 / 2=参数错 / 124=watch 超时未变化**。

## 统一入口 `./desk`（= runctl）

在本技能目录用 **`./desk <子命令> [参数]`** 调用，等价于 README 里的 `runctl <子命令>`。
封装层会自动定位 runctl，并**原样保留它的退出码与输出**（这点对 `watch` 的 124 很关键）。

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

## 坐标模型（点错位置基本都栽在这）

两种给坐标的方式，**强烈推荐第二种**：

1. **全局坐标**（不带 `--screen`）：整个多显示器是一个虚拟坐标系，左/上方的显示器偏移为负，正常。
   注意 HiDPI：截图是物理像素，要自己 ÷ 该屏 scale。
2. **按截图量像素**（带 `--screen N` 或 `--window <子串>` / `--window-id N`）：直接用你在
   `shot --screen N` / `shot --window 子串` / `shot --window-id N` 那张 PNG 上数出来的像素坐标，
   runctl 自动按该屏/该窗的实时偏移 + DPI 换算成真实点击位置。**截图→在图里找目标→用同样的数字点它。**

**窗口怎么指定**：`--window <子串>`（按标题/应用名子串匹配，方便）或 `--window-id N`（精确）。
**多个同名窗口**（如开了两个微信窗口）易选错——先 `./desk windows` 拿到目标窗口的 id，
之后全程用 `--window-id N` 驱动（`shot`/`click`/`activate` 都支持），避免误点到另一个。

习惯动作：点之前先 `move` 同样坐标，肉眼确认落点再 `click`。

## 命令清单（都用 `./desk` 调；完整示例见 README）

| 子命令 | 作用 | 关键参数 |
|---|---|---|
| `list` | 列显示器（index/偏移/尺寸/scale/主屏） | `--json` |
| `windows` | 列窗口及其 **id**（多个同名窗口时用来精确定位） | `--json` |
| `shot` | 截屏到 PNG | `--out`，`--screen N\|all\|full`，`--window 子串`/`--window-id N` |
| `move` / `click` | 移动 / 点击 | `--x --y`，`--screen N`/`--window 子串`/`--window-id N`，`--button right`，`--double` |
| `activate` | 窗口置顶（点击/输入前必做） | `activate 子串` 或 `activate --window-id N` |
| `scroll` | 滚轮 | `--dir up\|down --amount N`，可带 `--screen/--x/--y` |
| `drag` | 按下→拖→释放 | `--from-x --from-y --to-x --to-y`，`--screen N` |
| `open` | 用默认程序打开 | `open <url\|文件\|app>` |
| `type` | 在当前焦点输入文字 | `type "文本"` |
| `key` | 单键/组合键 | `key enter` / `key cmd+a` / `key ctrl+shift+t` |
| `watch` | 监视窗口/屏幕像素变化 | 见下 |
| `check` | 报告（macOS 可申请）权限 | `--request` |

## 两个标准回路

**A. 看屏幕 → 点击/输入（截图驱动）**
```sh
./desk --json windows                          # 0. 先拿目标窗口 id（如 51234），后续全程用它，杜绝选错
./desk shot --window-id 51234 --out wx.png      # 1. 截目标窗口
# 2. 视觉模型读 wx.png，定出"输入框/按钮"在图里的像素 (x,y)
./desk activate --window-id 51234               # 3. 置顶（type 去的是当前焦点，必须先置顶并点进输入框）
./desk click --window-id 51234 --x 440 --y 600  # 4. 点输入框（坐标就是步骤2在图上量的像素）
./desk type "你好，稍后回复"                     # 5. 输入
./desk key enter                               # 6. 发送
```
`shot --window-id` 和 `click --window-id` 用同一套坐标空间，所以步骤2量的像素步骤4直接能用。
（只有一个目标窗口、不怕选错时，也可省掉步骤0，直接用 `--window 微信`。）

**B. 监视窗口 → 等到变化 → 处理**
```sh
if ./desk watch --window-id 51234 --until-change --duration 60; then
    ./desk shot --window-id 51234 --out msg.png  # 退出码 0：有变化 → 截图交给视觉模型判断
else
    echo "60s 无变化"                             # 退出码 124：超时未变化
fi
```

## watch 用法要点

- 选**且仅选**一个目标：`--window <子串>`（每次重新解析标题，关了再开也不丢）或
  `--screen <N|primary|full>`。
- 调参：`--interval`(轮询毫秒) `--threshold`(变化像素占比阈值) `--cooldown`(触发后静默毫秒)。
- 限时：`--duration <秒>`(到点退出) / `--until-change`(首次变化即退出)；
  二者合用 = "最多等 N 秒等一次变化"，用退出码分支（0=变了 / 124=超时 / 1\|2=出错）。
- 通知三选/可叠加：stdout 的 NDJSON（默认）、`--exec '<命令>'`（事件进环境变量
  `RUNCTL_EVENT/TARGET/RATIO/TS`）、`--webhook <url>`（POST 事件 JSON，加 `--post-image` 附 base64 截图）。
- **它只认像素变化、不认语义**：分不清"新消息"还是"你在打字/滚动/时间戳跳动"。要逼近"新消息"信号：
  开 `--background-only`（你自己的操作发生在窗口聚焦时）、调高 `--threshold` 滤掉小抖动、用 `--cooldown` 去抖。

## 安全与边界

- 能截全屏、能点任意位置 = 很大的权限面。在 agent 环境里应**约束何时能截、能点哪里**，
  不要把整机控制权无限制交给模型。
- runctl 操作的是**运行它的那台机器**的真实桌面；务必确认是在用户期望的机器上跑。
- 涉及发送消息、提交表单、关闭窗口（`key alt+f4`/`cmd+w`）等不可逆/外发动作，先确认再执行。
