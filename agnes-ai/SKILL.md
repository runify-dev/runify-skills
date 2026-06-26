---
name: 视频生成(agnes供应商)
description: 基于 agnes-ai 的图像与视频生成技能：文生图/图生图/图片润色/图片理解、文生视频/图生视频/多图关键帧动画/视频抽帧，并能把小说编排成短剧。当用户要生成或修改/润色图片、理解分析一张图、文生图/图生图、文生视频/图生视频、把图片做成视频或动画化、做短剧、小说转视频、视频续写接续，或提到 agnes-ai 时使用。
metadata:
  runify:
    primaryEnv: AGNES_API_KEY
    requires:
      - ffmpeg   # 视频抽帧（extract_video_frame）需要，含 ffprobe
    envVars:
      - name: AGNES_API_KEY
        type: PasswordInput
        required: true
      # —— 以下为可选：仅“图片理解/自检”需要把本地图临时传 OSS 换公网 URL 时才填 ——
      - name: provider
        type: SingleSelect
        required: false
      - name: ali_access_key_id
        type: TextInput
        required: false
      - name: ali_access_key_secret
        type: PasswordInput
        required: false
      - name: ali_bucket
        type: TextInput
        required: false
      - name: ali_region
        type: TextInput
        required: false
      - name: ali_endpoint
        type: TextInput
        required: false
      - name: tencent_secret_id
        type: TextInput
        required: false
      - name: tencent_secret_key
        type: PasswordInput
        required: false
      - name: tencent_bucket
        type: TextInput
        required: false
      - name: tencent_region
        type: TextInput
        required: false
      - name: tencent_endpoint
        type: TextInput
        required: false
      - name: volc_access_key
        type: TextInput
        required: false
      - name: volc_secret_key
        type: PasswordInput
        required: false
      - name: volc_bucket
        type: TextInput
        required: false
      - name: volc_region
        type: TextInput
        required: false
      - name: volc_endpoint
        type: TextInput
        required: false
    # ┌─ 字段 type 取自 dynamics-form-plus/field-value/impl 下的组件名：
    # │   下拉 -> SingleSelect（用 optionList + labelField + valueField），
    # │   文本 -> TextInput，密码 -> PasswordInput。
    # └─ showRules：从属字段跟着 provider 联动显隐，conditions 的值挂在 value 键下。
    skillParameterForm:
      - field: AGNES_API_KEY
        label:
          value: agnes的KEY
          tooltip: agnes-ai 的 API Key（sk- 开头），必填
          type: TooltipLabel
        required: true
        type: PasswordInput

      # ===== OSS 供应商（仅图片理解需要；不填则图片理解不可用，其余功能不受影响）=====
      - field: provider
        label:
          value: OSS供应商
          tooltip: 选择对象存储供应商。仅“图片理解/自检”会把本地图临时上传换公网URL时用到
          type: TooltipLabel
        required: false
        type: SingleSelect
        defaultValue: ""
        optionList:
          - { label: 阿里云, value: aliyun }
          - { label: 腾讯云, value: tencent }
          - { label: 火山引擎, value: volcengine }
        labelField: label
        valueField: value

      # ----- 阿里云 OSS（provider = aliyun 时显示）-----
      - field: ali_access_key_id
        label: { value: 阿里云AccessKeyId, tooltip: 阿里云 AccessKey ID, type: TooltipLabel }
        required: false
        type: TextInput
        showRules: { condition: and, conditions: [ { field: provider, compare: eq, value: aliyun } ] }
      - field: ali_access_key_secret
        label: { value: 阿里云AccessKeySecret, tooltip: 阿里云 AccessKey Secret（敏感）, type: TooltipLabel }
        required: false
        type: PasswordInput
        showRules: { condition: and, conditions: [ { field: provider, compare: eq, value: aliyun } ] }
      - field: ali_bucket
        label: { value: 阿里云Bucket, tooltip: OSS Bucket 名称, type: TooltipLabel }
        required: false
        type: TextInput
        showRules: { condition: and, conditions: [ { field: provider, compare: eq, value: aliyun } ] }
      - field: ali_region
        label: { value: 阿里云Region, tooltip: 如 cn-hangzhou, type: TooltipLabel }
        required: false
        type: TextInput
        showRules: { condition: and, conditions: [ { field: provider, compare: eq, value: aliyun } ] }
      - field: ali_endpoint
        label: { value: 阿里云Endpoint, tooltip: 公网域名，如 oss-cn-hangzhou.aliyuncs.com（勿用内网-internal）, type: TooltipLabel }
        required: false
        type: TextInput
        showRules: { condition: and, conditions: [ { field: provider, compare: eq, value: aliyun } ] }

      # ----- 腾讯云 COS（provider = tencent 时显示）-----
      - field: tencent_secret_id
        label: { value: 腾讯云SecretId, tooltip: 腾讯云 SecretId, type: TooltipLabel }
        required: false
        type: TextInput
        showRules: { condition: and, conditions: [ { field: provider, compare: eq, value: tencent } ] }
      - field: tencent_secret_key
        label: { value: 腾讯云SecretKey, tooltip: 腾讯云 SecretKey（敏感）, type: TooltipLabel }
        required: false
        type: PasswordInput
        showRules: { condition: and, conditions: [ { field: provider, compare: eq, value: tencent } ] }
      - field: tencent_bucket
        label: { value: 腾讯云Bucket, tooltip: COS Bucket，形如 name-1250000000, type: TooltipLabel }
        required: false
        type: TextInput
        showRules: { condition: and, conditions: [ { field: provider, compare: eq, value: tencent } ] }
      - field: tencent_region
        label: { value: 腾讯云Region, tooltip: 如 ap-guangzhou, type: TooltipLabel }
        required: false
        type: TextInput
        showRules: { condition: and, conditions: [ { field: provider, compare: eq, value: tencent } ] }
      - field: tencent_endpoint
        label: { value: 腾讯云Endpoint（可选）, tooltip: 留空则由 region 自动推导, type: TooltipLabel }
        required: false
        type: TextInput
        showRules: { condition: and, conditions: [ { field: provider, compare: eq, value: tencent } ] }

      # ----- 火山引擎 TOS（provider = volcengine 时显示）-----
      - field: volc_access_key
        label: { value: 火山AccessKey, tooltip: 火山引擎 AccessKey, type: TooltipLabel }
        required: false
        type: TextInput
        showRules: { condition: and, conditions: [ { field: provider, compare: eq, value: volcengine } ] }
      - field: volc_secret_key
        label: { value: 火山SecretKey, tooltip: 火山引擎 SecretKey（敏感）, type: TooltipLabel }
        required: false
        type: PasswordInput
        showRules: { condition: and, conditions: [ { field: provider, compare: eq, value: volcengine } ] }
      - field: volc_bucket
        label: { value: 火山Bucket, tooltip: TOS Bucket 名称, type: TooltipLabel }
        required: false
        type: TextInput
        showRules: { condition: and, conditions: [ { field: provider, compare: eq, value: volcengine } ] }
      - field: volc_region
        label: { value: 火山Region, tooltip: 如 cn-beijing, type: TooltipLabel }
        required: false
        type: TextInput
        showRules: { condition: and, conditions: [ { field: provider, compare: eq, value: volcengine } ] }
      - field: volc_endpoint
        label: { value: 火山Endpoint, tooltip: 公网域名，如 tos-cn-beijing.volces.com, type: TooltipLabel }
        required: false
        type: TextInput
        showRules: { condition: and, conditions: [ { field: provider, compare: eq, value: volcengine } ] }
# 说明：
#   - RUNIFY_OUTPUT_DIR 由运行时注入（会话挂载目录），不作为配置项暴露给用户。
#   - API 地址/模型名写死在 scripts/_common.py：换 agnes-ai 之外的 api 应另写 skill。
#   - OSS 字段仅“图片理解/自检”用到（agnes 图片理解只吃公网 URL、不支持 base64）；
#     不配则图片理解不可用，图生图/润色/图生视频不受影响。凭据由 `./agnes oss_upload` 使用。
---

# 短剧 / 图像视频生成（agnes 供应商）

这是一套**图像与视频生成能力**，核心是一组自由原子工具：

- **自由原子工具**（互不依赖、随调随用，产物落 `scratch/` 版本化）——
  文生图、图生图、润色、图片理解、文生视频、单图生视频、视频抽帧。
- **做短剧/小说转视频** 时，由 agent 用这些原子工具**自行编排**（见《做短剧：推荐编排》），
  不依赖固定流水线脚本。

每个脚本只做**产出一个产物 + 落盘 + 返回 RESULT_JSON**，自己不持有剧情、不跨步攒上下文。

## 先判意图，再选路由（agent 第一步）

**先判意图，别急着出活。** 先看用户给了什么 + 想要什么：

| 用户给的 / 想要的 | 走哪条 | 用什么 |
|---|---|---|
| 一句话想要一张图 | 单步 | `text_to_image` |
| 给一张图，想改/转换 | 单步 | `image_to_image`（基于单张底图改，非多图融合） |
| 给一张图，想润色增强 | 单步 | `polish_image` |
| 给一张图，想看懂它讲什么 | 单步 | `understand_image` |
| 一句话想要一个短视频 | 简单出片 | `text_to_video` |
| 给一张图想动起来/出视频 | 简单出片 | `image_to_video` |
| 给多张图想做过渡/保持一致/关键帧动画 | 多图出片 | `image_to_video --images ...`（加 `--keyframes` 走关键帧） |
| 拿上一个视频接着做下一个 | 组合 | `extract_video_frame` → understand/再生成 |
| 一整本/一章小说，想做成有剧情的短剧 | 组合编排 | 见下《做短剧：推荐编排》——AI 用原子工具自行编排 |

判断不了就问一句用户想要哪种。做短剧时按下方《做短剧：推荐编排》组织原子工具，不依赖任何固定流水线脚本。
> 上表只决定**选哪个工具**；每个工具的**完整入参**见下方《自由原子工具》里的参数清单。

## 交互策略（默认停、可切到不间断；逐个生成永不变）

适用于所有需要反复打磨的生成：

- **逐个生成永远开着**（质量铁律）：一个一个出，每镜视频看着上一镜接（续写时抽上一镜末帧作起点参考），
  **绝不一次性全出**——一次性全出会严重跳帧、不连贯。
- **确认默认开**：每产出一个就**展示实物**（按《产物展示规范》：统一用 table 放图/视频），
  然后停下等用户。用户会反复说“这里不行/重做/换个机位”，就重做那一个再展示，直到满意。
  **第一个产物**的打磨最关键，务必停够、交互充分。
- **用户说“后面不用确认了/你一路跑”→ 关闭确认**：之后连续逐个生成、**仍逐个展示**（让用户能
  看到进度、随时喊停），但不再每个都停。用户再说“停”就切回默认。
- 用户随时可回头改某一个（用 `--parent` 接血缘重做某个产物）。

> 一句话：**逐个生成 ≠ 逐个确认。** 前者为质量、恒开；后者为打磨、默认开但用户可一句话关。

## 产物展示规范（agent 拼 md 时照此，保持一致）

工具只返回数据 `produced{url,local,version,intent,parent}`，**怎么渲染由 agent 决定**。
**统一用 table 展示**（图片和视频都放进表格单元格）：

- **单个产物**（一张图 / 一个视频）：
  ```markdown
  | 预览 | 信息 |
  |---|---|
  | ![](图url) | 风格：皮克斯<br>[📥 下载](图url) |
  ```
  视频用 `<video>` 放进单元格：
  ```markdown
  | 预览 | 信息 |
  |---|---|
  | <video src="视频url" controls width="360"></video> | 时长：5s<br>[📥 下载](视频url) |
  ```
- **同一 intent 的多个版本**（反复重做后对比）→ 每版一行，标出当前选中：
  ```markdown
  | 版本 | 预览 | 操作 |
  |---|---|---|
  | v1 | ![](url1) | [下载](url1) |
  | v2 ✅当前 | ![](url2) | [下载](url2) |
  ```
- **url 取值**：优先 `produced.url`（agnes 公网直链）；展示本地产物则用平台把 `produced.local`
  转成的可访问路径（如 `./api/storage/file/<id>`）。
- 视频是异步生成、耗时数十秒~数分钟：生成期间工具会持续输出进度日志（提交即报、每次报
  `进度% / 已等 Ns`、单次查询失败自动重试续查），**把这些进度透传给用户**，不要让界面看起来卡死。
- 展示 ≠ 确认：展示是每个产物都做的机械动作；是否停下等确认看《交互策略》。

## 自由原子工具（manifest 版本化+血缘）

**统一入口 `agnes`**：所有工具都通过 `./agnes <命令> [参数]` 调用，无需写解释器/路径/后缀。
**Linux、macOS、Windows(PowerShell/cmd) 都用 `./agnes <命令>`**——各平台自动命中对应入口
（类 Unix 走 `agnes`，Windows 走 `agnes.cmd`），命令写法一致。不带命令时列出全部。
例：`./agnes image_to_video --images a,b --keyframes --prompt "..."`。
- 如 Linux/mac 提示无权限：先 `chmod +x agnes`。
- 备用（执行器若想要绝对确定性）：`python3 agnes.py <命令> ...`（两平台字面一致；Windows 无 python3 时用 `py -3 agnes.py ...`）。
> 视频抽帧（extract_video_frame）依赖本机 **ffmpeg/ffprobe** 在 PATH 中；Windows 需自行安装并加入 PATH。

**默认不把产物文件下载到本地**——agnes 生成的图/视频自带公网 URL，直接用 URL 即可。
`$RUNIFY_OUTPUT_DIR/scratch/manifest.json` 只维护**历史元数据**：每个产物的
`url`（公网直链）、`prompt`（用哪段话生成的）、`intent`（同一意图分组）、`version`（第几次尝试，
反复试不丢历史、可回退/对比）、`parent`（基于哪个产物做的，血缘）。
这样能完整追溯"哪段提示词 → 生成了哪个产物 → 第几版 → 从哪个产物续来"，而不占服务器存储。
**随时用 `./agnes history` 查看这些历史**（列全部 / 按类型或意图筛 / `--id` 看某产物的血缘链）。
返回 `produced{id,url,local,intent,version,parent}`，其中 **`local` 默认为 null**（未下载）。
> **要把产物落到本地**有两种方式：① 生成时加 `--save`（顺便下载，仅图/视频生成工具支持）；
> ② 事后用 `./agnes download_artifact --url <URL>` 按需下载（可选 `--item-id` 把本地路径回填进 manifest）。
> 或设环境变量 `KEEP_LOCAL=1` 让所有生成默认落本地。

每个工具的参数如下（`[]` 为可选；图源类 `--image-url/--file/--parent` 三选一）：

**`./agnes text_to_image`** 文生图
- 必填：`--prompt "画面描述"`
- 可选：`--intent k`（同一创作意图分组，用于版本计数/回退）、`--no-style`（不加默认动漫风格后缀）、`--save`（下载到本地）

**`./agnes image_to_image`** 图生图（基于「一张」底图做转换/编辑/重打光/风格迁移，保持原构图；**非多图融合**）
- 图源：`--image-url URL` | `--file 本机路径` | `--parent 产物id`（三选一）
- 必填：`--prompt "改成什么、保留什么"`
- 可选：`--intent k`、`--no-style`、`--save`
- 要"用多张参考图"做画面：图像模型没有此能力，改用 `image_to_video --images ...`。

**`./agnes polish_image`** 润色/增强（保留构图）
- 图源：`--image-url` | `--file` | `--parent`（三选一）
- 可选：`--instruction "额外润色要求"`、`--intent k`、`--save`

**`./agnes understand_image`** 图片理解/自检（只吃公网 URL，本机图自动走 OSS）
- 图源：`--image-url` | `--file`
- 可选：`--question "想问什么"`；或 `--check --expect "这图本应呈现什么"`（自检图文是否相符）

**`./agnes text_to_video`** 文生视频
- 必填：`--prompt "画面+动作+运镜"`
- 可选：`--duration 秒数`（默认5）、`--intent k`、`--audio "声音描述"`（不传=默认中文配音；可写"只有背景音乐，人物不说话"/"无声"/"人物说中文，有环境声"等）、`--save`

**`./agnes image_to_video`** 图生视频（单图/多图/关键帧）
- 单图：`--image-url` | `--file` | `--parent`（三选一）
- 多图：`--images a,b[,...]`（逗号分隔；每项可为 URL/本机路径/scratch产物id），或多次 `--image x` 逐张传
- 关键帧：在多图基础上加 `--keyframes`（在关键帧间生成平滑过渡）
- 必填：`--prompt "..."`
- 可选：`--duration 秒数`（默认5）、`--intent k`、`--audio "声音描述"`（不传=默认中文配音；可写"只有背景音乐，人物不说话"/"无声"/"人物说中文，有环境声"等）、`--save`

**`./agnes extract_video_frame`** 视频抽帧
- 视频源：`--video-url URL` | `--file 本机路径` | `--parent 视频产物id`（三选一）
- 可选：`--at last`（末帧，默认）或 `--at 2.5`（第2.5秒）

**`./agnes download_artifact`** 按需把产物下载到本地（默认不下载；用户要导出/归档时才调）
- 必填：`--url 产物URL`
- 可选：`--out 保存路径`、`--item-id 产物id`（把本地路径回填进 manifest）

**`./agnes history`** 查看产物历史（从 manifest 读，不下载文件）
- 无参数：按时间倒序列出全部产物（类型/id/版本/血缘/prompt/url）
- 可选：`--kind img|vid|frame`（按类型筛）、`--intent k`（看某意图的 v1→v2→…）、
  `--id 产物id`（看详情 + 血缘链，即"它基于哪个产物做的"）、`--limit N`、`--json`（给程序用）

**`./agnes oss_upload`** 本机图传 OSS 换公网 URL（通常由其他工具自动调用，一般不手动用）
- `--file 本机路径`；`--expires 秒`；`--check-only`（只校验 OSS 配置是否齐全）

**怎么选**：纯文字出图 → `text_to_image`；改一张图 → `image_to_image`；只增强不改 → `polish_image`；
看懂一张图 → `understand_image`；纯文字出视频 → `text_to_video`；一张图动起来 → `image_to_video`；
多图过渡/关键帧 → `image_to_video --images`（加 `--keyframes`）。
视频异步生成、有进度反馈与重试，耐心等并把进度透传用户；本机图喂图生视频/图片理解需先 OSS（见下）。

**接力做下一个**：用 `--parent <上一个产物 id>` 即可基于它继续（自动接血缘、继承 intent）；
“拿上一个视频接着做”= `extract_video_frame --parent <视频id>` 抽帧 → 再喂 understand/image_to_*。

### 图源 → 要不要传 OSS（适用所有带图入参的工具）

只看**图从哪来 + 喂给哪个模型**：

- agnes 生成出来的图（任何工具产出）→ 自带公网 url → **直接用，永不传 OSS**。
- 用户本机图（`--file`）：
  - 喂**图生图/润色**（支持 base64）→ 自动转 data-uri，**不传 OSS**。
  - 喂**图片理解 / 图生视频**（agnes 这两处**只吃公网 URL、不支持 base64**）→ **必须先传 OSS**，
    工具会自动调 `./agnes oss_upload`；未配置 OSS 时，stdout 正常返回
    `RESULT_JSON: {"status":"needs_config", ...}`（**退出码 0、走成功通道**，指引在正常输出里，含 message/where/guidance）。
    agent **读到 `status` 为 `needs_config` 时必须停止当前步骤**，把 guidance 转达用户
    （去 Runify 技能设置界面选 OSS 供应商并填凭据），或让用户改用 `--image-url` 公网图。
    **切勿擅自改用别的工具绕过缺失的 OSS 配置**（如不要降级成 text_to_video 凭空描述）。

---

# 做短剧 / 小说转视频：推荐编排（提示词引导，非硬流程）

把"小说/剧情 → 有连贯画面的短剧"这件事，**交给 agent 用上面的原子工具自行编排**，
不依赖任何固定的流水线脚本。下面是推荐路径与要点，agent 可按场景灵活调整（镜数、是否配音、风格）。

## 推荐路径

1. **拆镜**：把正文按情节拆成若干"镜头"（一句话一镜或一动作一镜），每镜想清楚画面内容 + 运镜。
2. **逐镜出画**：每镜先用 `text_to_image`（或基于参考图用 `image_to_image`）出该镜的关键画面。
   - 想要全片角色/场景一致：先出一张"主角/主场景"参考图，后续各镜用 `image_to_image --file 参考图` 续画，保持形象统一。
3. **逐镜出视频**：用 `image_to_video --file 该镜关键画面 --prompt "本镜运镜/动作"` 把每镜动起来。
4. **镜间连贯（关键）**：生成第 N+1 镜前，**先抽第 N 镜视频的末帧**作下一镜的起点参考——
   `extract_video_frame --parent <第N镜视频id> --at last` 得到末帧图。两种接法：
   - **单图续接**（简单）：`image_to_video --file <末帧图> --prompt "延续上一镜：..."`，下一镜从这一帧长出。
   - **关键帧/多图过渡**（更稳，推荐用于画面变化大的衔接）：把"上一镜末帧 + 下一镜目标画面"两张一起给——
     `image_to_video --images <上一镜末帧>,<目标画面> --keyframes --prompt "在两帧间平滑过渡，保持角色一致"`，
     精确控制这一镜的起点和终点，接缝处用真实末帧，**避免跳脸/跳场/动作断裂**。
5. **合成**：把各镜视频按顺序拼接成成片（用系统 ffmpeg，例如 `ffmpeg -f concat` 拼接多段 mp4）。

## 编排要点

- **一次一个产物**：每调一个工具产出一个产物，逐个推进，便于流式展示、断点续跑、单点重做。
- **连贯靠"末帧续接"而非"凭空描述"**：续写下一镜务必带上一镜真实末帧；纯文字描述接续必然对不上。
- **本机图喂视频要走 OSS**：见上《图源→要不要传 OSS》。视频模型只吃公网 URL、不支持 base64。
- **风格统一**：把画风/色调/光线等写进每镜 prompt 的固定前缀，跨镜保持一致。
- **镜数与节奏由用户定**：不确定就问用户要几镜、要不要配音、多长，别擅自定。
