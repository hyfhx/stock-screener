#!/bin/bash
#
# Stock Screener - 简化安装脚本
# 只安装Python依赖，所有文件直接在git目录运行
#

set -e

echo "======================================"
echo "  Stock Screener 环境配置"
echo "======================================"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 检查Python
echo "检查Python环境..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    echo "✓ 找到Python: $PYTHON_VERSION"
else
    echo "✗ 未找到Python3，请先安装Python"
    echo "  Mac: brew install python3"
    exit 1
fi

# 检查pip
echo ""
echo "检查pip..."
if $PYTHON_CMD -m pip --version &> /dev/null; then
    echo "✓ pip已安装"
else
    echo "✗ pip未安装，正在安装..."
    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    $PYTHON_CMD get-pip.py --user
    rm get-pip.py
fi

# 安装依赖
echo ""
echo "安装Python依赖..."
$PYTHON_CMD -m pip install --user -q yfinance pandas numpy requests

echo "✓ 依赖安装完成"

# 创建数据目录
echo ""
echo "创建数据目录..."
mkdir -p "$SCRIPT_DIR/data"
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$SCRIPT_DIR/reports"
echo "✓ 目录创建完成"

# 创建配置文件（如果不存在）
if [ ! -f "$SCRIPT_DIR/config.json" ]; then
    echo ""
    echo "创建配置文件..."
    cat > "$SCRIPT_DIR/config.json" << 'EOF'
{
    "telegram": {
        "enabled": false,
        "bot_token": "YOUR_BOT_TOKEN_HERE",
        "chat_id": "YOUR_CHAT_ID_HERE"
    },
    "schedule": {
        "enabled": true,
        "run_time": "06:00"
    },
    "screener": {
        "min_score": 40,
        "top_n": 20
    }
}
EOF
    echo "✓ 配置文件已创建: config.json"
    echo "  请编辑 config.json 配置Telegram通知"
fi

# 设置执行权限
chmod +x "$SCRIPT_DIR/screener.sh"

echo ""
echo "======================================"
echo "  安装完成！"
echo "======================================"
echo ""
echo "使用方法（在此目录下运行）："
echo ""
echo "  ./screener.sh run        # 立即运行筛选"
echo "  ./screener.sh start      # 启动定时任务"
echo "  ./screener.sh stop       # 停止定时任务"
echo "  ./screener.sh status     # 查看状态"
echo "  ./screener.sh logs       # 查看日志"
echo ""
echo "配置Telegram通知："
echo "  编辑 config.json 文件"
echo ""
