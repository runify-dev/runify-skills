---
name: 桌面控制(runctl)
description: 跨平台(macOS/Windows)桌面自动化 / 计算机使用技能，封装 runctl 命令行工具。能力：列出显示器；列出窗口及其 id(同名窗口按 id 精确定位)；截屏(整个虚拟桌面/某显示器/全部显示器/某窗口，即使被遮挡)；移动鼠标并点击/右键/双击；激活窗口置顶；滚轮滚动；按下-拖拽-释放；输入文字；按单键或组合键(enter/esc/tab/cmd+a/alt+f4 等)；用系统默认程序打开 URL/文件/应用；监视窗口或屏幕的像素变化，等到首次变化或限时退出(退出码区分)；检查并(在 macOS)申请屏幕录制与辅助功能权限。坐标做法：先用 `--json shot` 截图拿到图的宽高，视觉在图上定出目标像素后，点击/移动/滚动/拖拽时连同宽高一起传 --shot-w/--shot-h，runctl 按比例映射到窗口实时矩形(任意 DPI 都准，不用手算)。用法是 agent 自己跑一个 看→懂→定→做→验 的闭环：windows 锁定目标窗口 id、先建界面地图；之后反复 --json shot 截图 → 把截图连同"用户到底要干什么"交给图片理解技能(没有就给用户确认)，让它回 当前状态+下一步最优单动作+目标像素 → activate 后 click/type 执行那一步 → 再截图核对 → 没完成再来一轮。一次性操作直接这样转；只有"等窗口变化再处理"(如盯微信新消息回复)才在每轮"看"之前加一道 watch 门(--until-change，靠退出码分支)。当用户要：操作桌面或某个应用、点某个按钮、自动填表单、截图看屏幕上有什么、控制微信/某软件、监听窗口有没有新消息再处理、模拟鼠标键盘、自动化 GUI 操作，或提到 runctl 时，使用本技能。
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

1. **截图必须带 `--json`**，从输出读这张图的 `width` / `height`：
   ```
   runctl --json shot --window-id <ID> --out f.png
   → {"ok":true,"action":"shot","width":W,"height":H,"path":"f.png"}
   ```
2. **视觉在 f.png 上定出目标像素 `(x,y)`**（左上角为原点）。
3. **点击/移动/滚动/拖拽时，把这张图的 W、H 一起传 `--shot-w`/`--shot-h`**：
   ```
   runctl click --window-id <ID> --x <x> --y <y> --shot-w W --shot-h H
   ```
   runctl 自动把 (x,y) **按比例映射**到窗口实时矩形——**任何 DPI/缩放都准，不用你算**。

> ⚠ **永远成对传 `--shot-w --shot-h`**。不传时 x/y 被当成"窗口内未缩放的点"，几乎必偏。
> 窗口**一律用 id 锁定**：先 `runctl --json windows` 拿目标窗口 id，全程 `--window-id <ID>`（用名字会撞）。

---

## 干活的闭环：看 → 懂 → 定 → 做 → 验

**先建图（进窗口一次）**：`runctl --json windows` 选目标记下 id →
`runctl activate --window-id <ID>` 置顶 → `runctl --json shot --window-id <ID> --out ui.png` →
让视觉产出**界面地图**（有哪些控件、各管什么、像素位置），记住复用。

**然后反复走这五步，直到 `done`——别"截图就点"：**
1. **看**　`runctl --json shot --window-id <ID> --out now.png`　**（记下返回的 W、H）**
2. **懂**　把 now.png + **用户到底要干什么** + 已知地图，交给图片理解技能，要它结构化回
   　`{state, blockers, next_action, target_xy, text, reason, done}`（模板见下）。
   　**没有图片理解技能 → 把 now.png + 你的判断给用户，让其确认下一步与坐标。**
3. **定**　先清 `blockers`；选**一个**最优动作。不确定 / 有风险 → 先问用户。
4. **做**　`runctl activate --window-id <ID>`（确保焦点）再执行那**一步**：
   　`click/move --window-id <ID> --x <x> --y <y> --shot-w W --shot-h H` ／ `type "<text>"` ／ `key enter` ／ `scroll …`
5. **验**　再 `runctl --json shot --window-id <ID> --out after.png` 确认生效。
   　没生效 → 回第 2 步重新理解（**绝不盲点连击**）；`done=true` → 结束，否则回第 1 步。

> **一次性任务**（点个按钮、填个表、开个设置）就这样转，不需要 watch。

**只有当任务是"等窗口出现变化再处理"时**（如盯微信新消息回复），才在每轮的"看"之前加一道 `watch` 门：
```
runctl watch --window-id <ID> --until-change --background-only --duration 60
  exit 0  → 窗口变了，进入上面的 看→懂→定→做→验
  exit 124 → 这段时间没动，决定继续等还是收尾
```

### 给视觉的提问模板（套用，别只让它"描述图"）

```
这是 <应用> 窗口截图，尺寸 W×H。用户总目标：<原样填用户需求>。
已知布局：<填界面地图；首次没有就写"未知，请一并标出关键控件及像素">。
只看这张图，用 JSON 回答：
- state       当前相对目标的状态（一句话）
- blockers    需先处理的弹窗/登录/报错（无则 none）
- next_action click|double_click|right_click|type|key|scroll|wait|done 之一
- target_xy   该动作目标的像素 {x,y}（左上为原点；type/key/wait 可省）
- text        next_action=type 时要输入的文字；key 时填键名(如 enter)
- reason      为什么这是当前最优的一步
- done        总目标是否完成 true/false
```

---

## 命令速查（统一用 `runctl`）

| 命令 | 用途 | 关键参数 |
|---|---|---|
| `windows` | 列窗口 + id（开头锁定用） | `--json` |
| `shot` | 截图（**务必 `--json` 拿 W/H**） | `--window-id N`，`--out` |
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
