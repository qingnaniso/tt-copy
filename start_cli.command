#!/bin/zsh
cd "$(dirname "$0")"

echo ""
echo " =========================================="
echo "   TT-Copy CLI - 链接直接下载"
echo " =========================================="
echo ""

# ---- Step 1: 找 Python ----
PYTHON=""
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    echo " [错误] 找不到 Python，请先安装："
    echo "        brew install python"
    echo ""
    read -n 1 -s -r -p " 按任意键退出..."
    exit 1
fi

# ---- Step 2: 建虚拟环境 ----
if [ ! -f ".venv/bin/python" ]; then
    echo " [1/2] 正在创建虚拟环境..."
    $PYTHON -m venv .venv
    PYTHON=".venv/bin/python"
    echo " [1/2] 虚拟环境          OK"
else
    echo " [1/2] 虚拟环境          OK"
    PYTHON=".venv/bin/python"
fi

# ---- Step 3: 装依赖 ----
MISSING=""
if ! .venv/bin/python -c "import yt_dlp" &>/dev/null; then
    MISSING="$MISSING yt-dlp"
fi
if ! .venv/bin/python -c "import playwright" &>/dev/null; then
    MISSING="$MISSING playwright"
fi

if [ -n "$MISSING" ]; then
    echo " [2/2] 正在安装依赖库:$MISSING ..."
    .venv/bin/pip install $MISSING -q
    echo " [2/2] 依赖库            OK"
else
    echo " [2/2] 依赖库            OK"
fi

echo ""
echo " =========================================="
echo "   粘贴 TikTok 链接，回车即可下载"
echo "   下载完成后可选择发布到小红书"
echo "   输入 q 退出"
echo " =========================================="
echo ""

while true; do
    read "url? 链接: "
    [ -z "$url" ] && continue
    [ "$url" = "q" ] || [ "$url" = "Q" ] && break

    # 清理 URL：只提取 http(s):// 开头的有效链接
    url=$(echo "$url" | grep -oE 'https?://[^ ]+')
    if [ -z "$url" ]; then
        echo " [错误] 未检测到有效链接，请粘贴 https:// 开头的链接"
        echo ""
        continue
    fi

    echo ""
    echo " [1] 仅下载"
    echo " [2] 下载并发布到小红书"
    read "choice? 选择 (1/2): "

    echo ""
    if [ "$choice" = "2" ]; then
        .venv/bin/python -m ttcopy.cli "$url" --publish
    else
        .venv/bin/python -m ttcopy.cli "$url"
    fi
    echo ""
done
