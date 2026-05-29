#!/bin/bash
# tt-copy 一键安装脚本
# 用法: chmod +x install.sh && ./install.sh

set -e
cd "$(dirname "$0")"
TTCOPY_DIR="$(pwd)"

# === 颜色输出 ===
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[!!]${NC} $1"; }
err()  { echo -e "${RED}[错误]${NC} $1"; exit 1; }
step() { echo ""; echo -e "${GREEN}==>${NC} $1"; }

echo ""
echo "=========================================="
echo "  tt-copy 安装程序"
echo "=========================================="

# =========================================
# Step 1: Homebrew
# =========================================
step "检测 Homebrew..."

# 根据芯片架构确定 brew 路径
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    BREW_BIN="/opt/homebrew/bin/brew"
else
    BREW_BIN="/usr/local/bin/brew"
fi

if [ -f "$BREW_BIN" ]; then
    eval "$($BREW_BIN shellenv)"
    ok "Homebrew 已安装"
elif command -v brew &>/dev/null; then
    ok "Homebrew 已安装"
else
    warn "未检测到 Homebrew，开始安装（需要输入密码）..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # 安装后加入当前 session 的 PATH
    if [ -f "/opt/homebrew/bin/brew" ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -f "/usr/local/bin/brew" ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
    ok "Homebrew 安装完成"
fi

# =========================================
# Step 2: 系统依赖 (Python / ffmpeg / jq)
# =========================================
step "检测系统依赖..."

# Python: 要求 >= 3.8
if command -v python3 &>/dev/null \
   && python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
    ok "Python $(python3 --version 2>&1 | awk '{print $2}')"
else
    warn "Python 3.8+ 未找到，正在安装..."
    brew install python
    ok "Python $(python3 --version 2>&1 | awk '{print $2}')"
fi

if command -v ffmpeg &>/dev/null; then
    ok "ffmpeg"
else
    warn "ffmpeg 未找到，正在安装..."
    brew install ffmpeg
    ok "ffmpeg"
fi

if command -v jq &>/dev/null; then
    ok "jq"
else
    warn "jq 未找到，正在安装..."
    brew install jq
    ok "jq"
fi

# =========================================
# Step 3: Python 虚拟环境 & 依赖
# =========================================
step "配置 Python 环境..."

if [ ! -f ".venv/bin/python" ]; then
    python3 -m venv .venv
    ok "虚拟环境创建完成"
else
    ok "虚拟环境已存在"
fi

echo "  安装 Python 依赖（yt-dlp, playwright）..."
.venv/bin/pip install -r requirements.txt -q
ok "Python 依赖"

if [ ! -f ".setup_done" ]; then
    echo "  下载 Chromium（首次约需 3-5 分钟）..."
    .venv/bin/python -m playwright install chromium
    touch .setup_done
    ok "Chromium"
else
    ok "Chromium 已安装"
fi

# =========================================
# Step 4: 生成 .env 配置文件
# =========================================
step "配置 .env 文件..."

if [ ! -f ".env" ]; then
    cp .env.example .env
    # 自动写入当前目录为 TTCOPY_DIR
    sed -i '' "s|^TTCOPY_DIR=.*|TTCOPY_DIR=$TTCOPY_DIR|" .env

    echo ""
    echo "  请输入 Kimi API Key（sk-kimi-... 格式）"
    echo "  没有的话直接回车跳过，之后手动编辑 .env"
    echo ""
    read -p "  KIMI_API_KEY: " kimi_key
    if [ -n "$kimi_key" ]; then
        sed -i '' "s|^KIMI_API_KEY=.*|KIMI_API_KEY=$kimi_key|" .env
        ok ".env 已生成并写入 API Key"
    else
        warn ".env 已生成，请手动编辑填写 KIMI_API_KEY"
    fi
else
    # 已存在则只更新 TTCOPY_DIR（路径可能变了）
    sed -i '' "s|^TTCOPY_DIR=.*|TTCOPY_DIR=$TTCOPY_DIR|" .env
    ok ".env 已存在，TTCOPY_DIR 已更新"
fi

# =========================================
# Step 5: 注册 Claude Code Skill
# =========================================
step "注册 Claude Code Skill..."

SKILL_DIR="$HOME/.claude/skills/tiktok-auto-pipeline"
mkdir -p "$SKILL_DIR"

# 将 SKILL.md 中的旧路径替换为当前安装路径后写入
sed "s|/Users/qiqingnan/Documents/Playground/tt-copy|$TTCOPY_DIR|g" \
    SKILL.md > "$SKILL_DIR/SKILL.md"

ok "Skill 已注册到 ~/.claude/skills/tiktok-auto-pipeline/"

# =========================================
# 完成
# =========================================
echo ""
echo "=========================================="
echo -e "  ${GREEN}安装完成！${NC}"
echo ""
echo "  使用方法："
echo "  打开 Claude Code，粘贴 TikTok 链接即可触发"
echo ""
echo "  首次发布小红书时会弹出浏览器扫码登录（仅一次）"
echo ""
if grep -q "^KIMI_API_KEY=sk-kimi-在这里填入你的Key" .env 2>/dev/null \
   || grep -q "^KIMI_API_KEY=$" .env 2>/dev/null; then
    warn "提醒：还未填写 KIMI_API_KEY，请编辑 .env 文件"
fi
echo "=========================================="
echo ""
