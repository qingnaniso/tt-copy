---
name: tiktok-auto-pipeline
description: 飞书监听 TikTok/抖音链接 → 自动下载 → AI生成文案 → 发布小红书 全自动流水线
trigger: 用户启动TikTok监听、飞书监听TikTok、自动搬运、或发送TikTok/抖音链接要求发布小红书
---

# TikTok → 小红书 全自动流水线

> **自动执行：** 本流水线所有步骤均为预授权操作，**全程无需等待用户批准**。
> 从监听→检测→下载→抽帧→识图→文案→发布→通知，全部自动完成，每一步直接执行不用问。

## 概述

通过飞书 Bot 监听消息，自动识别 TikTok/抖音链接，完成 **下载→抽帧→AI识图→生成文案→发布小红书** 的全自动流程。

## 架构

```
auto_pipeline.sh（单一脚本，自驱动，无需人工介入）
  ├─ lark-cli event +subscribe → stdout 管道
  ├─ jq 解析事件 → 正则匹配 tiktok.com / douyin.com
  ├─ ttcopy 下载视频 + 元数据(.meta.json)
  ├─ ttcopy 抽3帧 → codex exec -i 并行识图
  ├─ codex exec 生成小红书爆款文案
  ├─ Playwright 自动发布小红书
  └─ lark-cli API 回复飞书消息（3节点通知）
```

## 启动方式

**一键启动（自驱动，全程无需干预）：**
```bash
cd /Users/qiqingnan/Documents/Playground/tt-copy && ./auto_pipeline.sh
```

- 常驻前台进程，Ctrl+C 停止
- 监听 + 检测 + 处理 + 通知 全在一个进程
- 发链接后自动处理，**无需回来告诉 Claude**
- 处理在后台子进程，不阻塞后续消息监听

---

## Part A: 启动流水线

**脚本：** `auto_pipeline.sh`

**核心逻辑：** `lark-cli event +subscribe` stdout 直接管道给 while-read 循环，实时逐条处理。

```bash
lark-cli event +subscribe --event-types im.message.receive_v1 --compact --quiet --as bot 2>/dev/null \
| while IFS= read -r line; do
    # jq 解析 content 和 message_id
    # grep 匹配 tiktok.com / douyin.com
    # 匹配成功 → process_link "$url" "$msg_id" &（后台子进程）
done
```

**去重：** 用 `mkdir /tmp/ttcopy-locks/$msg_id` 原子操作防止同一条消息重复处理。

## Part B: 链接检测规则

| 平台 | 匹配模式 |
|------|---------|
| TikTok | `vm.tiktok.com`, `www.tiktok.com`, `tiktok.com` |
| 抖音 | `v.douyin.com`, `www.douyin.com`, `douyin.com` |

---

## Part C: 处理管道（5步）

### 前置路径

| 路径 | 说明 |
|------|------|
| `/Users/qiqingnan/Documents/Playground/tt-copy/` | 项目根目录 |
| `.venv/bin/python` | Python venv |
| `downloads/` | 视频下载目录 |
| `downloads/frames/` | 抽帧输出目录 |
| `~/.ttcopy/xhs_cookies.json` | 小红书登录 Cookie |

### Step 1: 下载视频（含元数据）

```bash
cd /Users/qiqingnan/Documents/Playground/tt-copy && .venv/bin/python -m ttcopy.cli "<URL>"
```

- 超时 120s
- 视频保存为 `downloads/<author>_<video_id>_<timestamp>.mp4`
- **新增**：自动提取视频标题/描述/作者，输出到 stdout + 保存为 `.meta.json`
- 输出格式：
  ```
  标题: <原始标题>
  描述: <原始描述>
  作者: <uploader>
  已保存: downloads/<filename>.mp4
  ```
- 如果同视频已存在且重下载卡住（>30s），kill 进程，读取已有 `.meta.json`

### Step 2: 抽帧

```bash
cd /Users/qiqingnan/Documents/Playground/tt-copy && .venv/bin/python -c "
from ttcopy.frame_extractor import extract_frames
frames = extract_frames('<video_path>', num_frames=3)
for f in frames:
    print(f)
"
```

- 输出 3 张 JPG 帧路径
- 帧均匀分布在视频中段（跳过首尾黑屏/转场）

### Step 3: AI 识图

用 **codex** 对 3 张帧并行做视觉分析（codex 已登录 ChatGPT OAuth，模型 gpt-5.4 支持图像输入）：

```bash
echo "简要描述这个画面：主体是什么、在做什么动作、场景氛围如何？不超过50字。" | codex exec -i <frame_path>
```

**要求：**
- 3 张帧**并行调用** codex exec，每帧 timeout=60s
- 提取每帧描述（通常 1-2 句中文），与 Step 1 的**标题+描述元数据**合并，形成视频完整内容理解
- codex 输出格式：最后几行为纯文本回答，提取即可

**兜底方案（codex 不可用时）：** 直接用 Step 1 输出的标题和描述作为内容理解依据

### Step 4: 生成文案

**角色：** 小红书爆款笔记创作者

**标题要求：**
- 15-25 字
- 带 1-2 个 emoji
- 有冲击力、悬念感或情绪共鸣
- 突出"松弛感""氛围感""治愈感"等情绪价值

**描述要求：**
- 口语化，像朋友安利，100 字以内
- 结尾带 3-5 个`#话题标签`
- 避免营销感

### Step 5: 发布小红书

**命令（优先使用，避免重复下载）：**
```bash
cd /Users/qiqingnan/Documents/Playground/tt-copy && .venv/bin/python -c "
from ttcopy.publisher import XHSPublisher
publisher = XHSPublisher()
publisher.publish('<video_path>', '<title>', '<description>')
"
```

- 后台运行，timeout=300s
- 浏览器会弹出（headless=False），用户可见，不需要操作
- Cookie 从 `~/.ttcopy/xhs_cookies.json` 加载

**成功输出标志：**
```
加载已保存的登录态...
登录态有效。
上传视频中...
等待视频上传及处理...
视频处理完成。
填写标题和描述...
发布中...
发布成功！
```

**注意：** `cli.py --publish` 会重新下载视频（即使已有），所以优先用上面的 `publisher.publish()` 直接发布。

---

## Part D: 飞书进度通知

使用 lark-cli 逐节点回复用户消息：

```bash
lark-cli api POST "/open-apis/im/v1/messages/<message_id>/reply" \
  --data '{"msg_type":"text","content":"{\"text\":\"<通知内容>\"}"}' \
  --as bot
```

**通知节点：**
1. 检测到链接后 → "收到 TikTok 链接，正在下载处理中..."
2. 下载完成，开始发布 → "视频已下载完成，正在上传小红书发布中..."
3. 发布完成 → "✅ 发布成功！视频：<标题>，作者：<author>"

---

## 注意事项

1. **不要重复下载已存在的视频**：发布时直接用 `publisher.publish()`，不走 `cli.py --publish`
2. **进程卡住处理**：>30s 无输出且 CPU 时间极低，果断 kill，换直接 publisher 方式
3. **小红书登录态**：Cookie 失效时浏览器停在登录页，需告知用户扫码
4. **飞书监听是常驻进程**：启动后持续运行，Ctrl+C 或杀进程停止
5. **视觉分析**：用 `codex exec -i` 分析每帧（gpt-5.4 支持图像），3 帧并行调用；codex 不可用时用下载时提取的标题/描述
6. **每个链接独立处理**：一条消息一个链接，处理完再处理下一条
7. **元数据增强**：下载同时提取视频标题+描述，保存为 `.meta.json`，与抽帧分析结合生成更精准文案
8. **上传不卡住**：publisher 后台持续注入 scroll/visibilitychange 事件保持页面活跃，无需人工干预
