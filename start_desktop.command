#!/bin/zsh
cd "$(dirname "$0")"

echo ""
echo " =========================================="
echo "   TT-Copy Desktop Shell"
echo "   Playwright + Chromium + Qt Shell"
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
    echo " [1/3] 正在创建虚拟环境..."
    $PYTHON -m venv .venv
    PYTHON=".venv/bin/python"
    echo " [1/3] 虚拟环境          OK"
else
    echo " [1/3] 虚拟环境          OK"
    PYTHON=".venv/bin/python"
fi

# ---- Step 3: 装依赖 ----
if ! .venv/bin/python -c "import PyQt6" &>/dev/null; then
    echo " [2/3] 正在安装依赖库 (PyQt6 + Playwright)..."
    .venv/bin/pip install -r requirements.txt -q
    echo " [2/3] 依赖库            OK"
else
    echo " [2/3] 依赖库            OK"
fi

# ---- Step 4: 检查 Chromium ----
if ! .venv/bin/python -c "from playwright.sync_api import sync_playwright; sync_playwright().chromium" &>/dev/null; then
    echo " [3/3] 正在下载 Chromium..."
    .venv/bin/python -m playwright install chromium
    echo " [3/3] Chromium          OK"
else
    echo " [3/3] Chromium          OK"
fi

echo ""
echo " =========================================="
echo "   正在启动 TT-Copy Desktop Shell..."
echo ""
echo "   浏览器: 系统 Chromium (视频播放正常)"
echo "   外壳:   PyQt6 控制面板"
echo " =========================================="
echo ""

.venv/bin/python -m ttcopy.desktop_shell "$@"
