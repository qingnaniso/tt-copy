#!/bin/zsh
cd "$(dirname "$0")"

echo ""
echo " =========================================="
echo "   TT-Copy Desktop - TikTok 桌面下载器"
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
    echo " [2/3] 正在安装依赖库 (含 PyQt6，约需 2-3 分钟)..."
    .venv/bin/pip install -r requirements.txt -q
    echo " [2/3] 依赖库            OK"
else
    echo " [2/3] 依赖库            OK"
fi

echo ""
echo " =========================================="
echo "   正在启动桌面版 TT-Copy..."
echo " =========================================="
echo ""

.venv/bin/python -m ttcopy.desktop "$@"
