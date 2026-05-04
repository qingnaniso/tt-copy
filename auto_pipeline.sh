#!/bin/bash
# TikTok → 小红书 全自动流水线（自驱动版）
# 监听飞书消息 → 检测链接 → 下载→抽帧→Kimi识图→Kimi文案→发布→通知
# 用法: ./auto_pipeline.sh

set -uo pipefail

TTCOPY_DIR="/Users/qiqingnan/Documents/Playground/tt-copy"
PYTHON="$TTCOPY_DIR/.venv/bin/python"
LOCK_DIR="/tmp/ttcopy-locks"

mkdir -p "$LOCK_DIR"

# === 工具函数 ===

# 回复飞书消息（用 jq 安全构造 JSON）
notify() {
    local msg_id="$1" text="$2"
    local payload
    payload=$(jq -n --arg t "$text" '{msg_type:"text", content:({text:$t}|tojson)}')
    lark-cli api POST "/open-apis/im/v1/messages/$msg_id/reply" \
      --data "$payload" --as bot 2>/dev/null
}

# 调用 Kimi Vision API（替代 codex）
kimi_vision() {
    local prompt="$1" image="${2:-}"
    if [ -n "$image" ] && [ -f "$image" ]; then
        "$PYTHON" -m ttcopy.vision -i "$image" -p "$prompt" 2>/dev/null
    else
        echo "$prompt" | "$PYTHON" -m ttcopy.vision 2>/dev/null
    fi
}

# === 核心处理函数 ===

process_link() {
    local url="$1" msg_id="$2"

    # 去重：同一条消息不重复处理
    local lock_id
    lock_id=$(echo "$msg_id" | md5)
    mkdir "$LOCK_DIR/$lock_id" 2>/dev/null || return 0

    echo ""
    echo "=========================================="
    echo "开始处理: $url"
    echo "=========================================="

    # --- Step 0: 通知 ---
    notify "$msg_id" "收到链接，开始处理..."

    # --- Step 1: 下载视频 ---
    echo "[Step 1] 下载视频..."
    cd "$TTCOPY_DIR"
    local dl_output video_path title desc author
    dl_output=$("$PYTHON" -m ttcopy.cli "$url" 2>&1)
    video_path=$(echo "$dl_output" | grep "^已保存:" | awk '{print $2}')
    title=$(echo "$dl_output" | grep "^标题:" | sed 's/^标题: //')
    desc=$(echo "$dl_output" | grep "^描述:" | sed 's/^描述: //')
    author=$(echo "$dl_output" | grep "^作者:" | sed 's/^作者: //')

    if [ -z "$video_path" ] || [ ! -f "$video_path" ]; then
        echo "ERROR: 下载失败"
        notify "$msg_id" "下载失败，请检查链接是否有效"
        rmdir "$LOCK_DIR/$lock_id" 2>/dev/null
        return 1
    fi
    echo "  视频: $video_path"
    echo "  标题: $title"
    echo "  作者: $author"

    # --- Step 2: 抽帧 ---
    echo "[Step 2] 抽帧..."
    local frames
    frames=$("$PYTHON" -c "
from ttcopy.frame_extractor import extract_frames
frames = extract_frames('$video_path', num_frames=3)
for f in frames:
    print(f)
" 2>&1)

    # --- Step 3: AI 识图 (codex) ---
    echo "[Step 3] AI 识图..."
    local frame_analysis=""
    local vision_prompt="简要描述这个画面：主体是什么、在做什么动作、场景氛围如何？不超过50字。"

    while IFS= read -r frame; do
        [ -z "$frame" ] && continue
        local result
        result=$(kimi_vision "$vision_prompt" "$frame")
        [ -n "$result" ] && frame_analysis="${frame_analysis}${result}"$'\n'
        echo "  帧分析 (Kimi): $result"
    done <<< "$frames"

    # --- Step 4: 生成文案（冷幽默/反幽默风格）---
    echo "[Step 4] 生成文案..."
    local caption_prompt caption_text xhs_title xhs_desc
    caption_prompt="你是一个面无表情的冷幽默段子手。根据以下信息生成小红书笔记文案：

视频原始标题：$title
视频帧画面分析：$frame_analysis

输出格式（严格两行）：
标题：<10到20字，不用emoji，冷静克制的事实陈述，带一点荒谬感或冷幽默>
描述：<冷幽默反幽默风格，50到80字，用平淡语气描述视频内容，不做任何煽情和安利，像在描述一件稀松平常但仔细一想有点好笑的事。不要用感叹号。结尾加2到3个话题标签>

风格参考：一本正经地描述无聊的事、过度认真分析日常片段、用新闻播报语气讲废话。不要典型小红书风格，不要治愈松弛氛围这些词。"

    caption_text=$(kimi_vision "$caption_prompt" "")

    # 尝试从 codex 输出中提取标题和描述
    xhs_title=$(echo "$caption_text" | grep "^标题：" | sed 's/^标题：//' | head -1)
    xhs_desc=$(echo "$caption_text" | grep "^描述：" | sed 's/^描述：//' | head -1)

    # 兜底文案
    [ -z "$xhs_title" ] && xhs_title="一段视频被上传到了互联网"
    [ -z "$xhs_desc" ] && xhs_desc="有人拍了这个视频，然后我看了，现在你也可以看了。事情就是这样。#日常观察 #互联网搬运"

    echo "  标题: $xhs_title"
    echo "  描述: $xhs_desc"

    # --- Step 5: 发布小红书 ---
    echo "[Step 5] 发布小红书..."
    notify "$msg_id" "内容分析完成，正在发布小红书..."

    local publish_result
    publish_result=$("$PYTHON" -c "
from ttcopy.publisher import XHSPublisher
publisher = XHSPublisher()
publisher.publish('$video_path', '''$xhs_title''', '''$xhs_desc''')
" 2>&1)

    echo "$publish_result"

    if echo "$publish_result" | grep -q "发布成功"; then
        notify "$msg_id" "✅ 发布成功！${xhs_title}"
        echo "===== 处理完成 ✅ ====="
    else
        notify "$msg_id" "发布完成，请检查浏览器确认"
        echo "===== 处理完成(请确认) ====="
    fi

    rmdir "$LOCK_DIR/$lock_id" 2>/dev/null
}

# === 主循环 ===

echo "==================================="
echo "TikTok → 小红书 自动搬运流水线"
echo "监听飞书消息中... (Ctrl+C 停止)"
echo "==================================="

lark-cli event +subscribe \
  --event-types im.message.receive_v1 \
  --compact --quiet --as bot 2>/dev/null \
| while IFS= read -r line; do
    content=$(echo "$line" | jq -r '.content // empty' 2>/dev/null)
    msg_id=$(echo "$line" | jq -r '.message_id // empty' 2>/dev/null)

    [ -z "$content" ] || [ -z "$msg_id" ] && continue

    # 检测 TikTok / 抖音链接
    if echo "$content" | grep -qE '(tiktok\.com|douyin\.com)'; then
        url=$(echo "$content" | grep -oE 'https?://[^ ]*(tiktok\.com|douyin\.com)[^ ]*' | head -1)
        [ -z "$url" ] && continue

        echo ">>> $(date '+%H:%M:%S') 检测到链接: $url"
        # 后台处理，断开管道stdin，输出到日志
        process_link "$url" "$msg_id" </dev/null >> /tmp/ttcopy-pipeline.log 2>&1 &
    fi
done
