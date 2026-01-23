#!/bin/bash
#
# Stock Screener 控制脚本
# 直接在git目录运行，无需安装到系统目录
#

# 获取脚本所在目录（支持软链接）
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 自动检测Python版本
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v /opt/homebrew/bin/python3.11 &> /dev/null; then
    PYTHON_CMD="/opt/homebrew/bin/python3.11"
elif command -v /opt/homebrew/bin/python3 &> /dev/null; then
    PYTHON_CMD="/opt/homebrew/bin/python3"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo "❌ 未找到Python3，请先安装: brew install python@3.11"
    exit 1
fi

# launchd plist文件路径
PLIST_NAME="com.stockscreener.daily"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 显示帮助
show_help() {
    echo "Stock Screener 控制脚本"
    echo ""
    echo "用法: ./screener.sh <命令>"
    echo ""
    echo "命令:"
    echo "  run         立即运行一次筛选"
    echo "  start       启动定时任务（每日自动运行）"
    echo "  stop        停止定时任务"
    echo "  status      查看运行状态"
    echo "  logs        查看最近日志"
    echo "  schedule    设置运行时间"
    echo "  config      编辑配置文件"
    echo "  test        测试Telegram通知"
    echo "  help        显示此帮助"
}

# 立即运行筛选
run_now() {
    echo -e "${GREEN}开始运行股票筛选...${NC}"
    echo ""
    $PYTHON_CMD "$SCRIPT_DIR/screener_local.py"
}

# 创建launchd plist
create_plist() {
    local hour=$1
    local minute=$2
    
    mkdir -p "$HOME/Library/LaunchAgents"
    
    cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_CMD</string>
        <string>$SCRIPT_DIR/screener_local.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>$hour</integer>
        <key>Minute</key>
        <integer>$minute</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/logs/screener.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/logs/screener_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
EOF
}

# 启动定时任务
start_service() {
    # 读取配置的运行时间
    if [ -f "$SCRIPT_DIR/config.json" ]; then
        RUN_TIME=$($PYTHON_CMD -c "import json; c=json.load(open('config.json')); print(c.get('schedule',{}).get('run_time','06:00'))" 2>/dev/null || echo "06:00")
    else
        RUN_TIME="06:00"
    fi
    
    HOUR=$(echo $RUN_TIME | cut -d: -f1)
    MINUTE=$(echo $RUN_TIME | cut -d: -f2)
    
    # 创建日志目录
    mkdir -p "$SCRIPT_DIR/logs"
    
    # 创建plist
    create_plist $HOUR $MINUTE
    
    # 加载服务
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    launchctl load "$PLIST_PATH"
    
    echo -e "${GREEN}✓ 定时任务已启动${NC}"
    echo "  运行时间: 每天 $RUN_TIME"
    echo "  日志位置: $SCRIPT_DIR/logs/"
}

# 停止定时任务
stop_service() {
    if [ -f "$PLIST_PATH" ]; then
        launchctl unload "$PLIST_PATH" 2>/dev/null || true
        rm -f "$PLIST_PATH"
        echo -e "${GREEN}✓ 定时任务已停止${NC}"
    else
        echo -e "${YELLOW}定时任务未运行${NC}"
    fi
}

# 查看状态
show_status() {
    echo "======================================"
    echo "  Stock Screener 状态"
    echo "======================================"
    echo ""
    
    # 检查定时任务
    if launchctl list | grep -q "$PLIST_NAME"; then
        echo -e "定时任务: ${GREEN}运行中${NC}"
        if [ -f "$SCRIPT_DIR/config.json" ]; then
            RUN_TIME=$($PYTHON_CMD -c "import json; c=json.load(open('config.json')); print(c.get('schedule',{}).get('run_time','06:00'))" 2>/dev/null || echo "06:00")
            echo "运行时间: 每天 $RUN_TIME"
        fi
    else
        echo -e "定时任务: ${YELLOW}未运行${NC}"
    fi
    
    echo ""
    
    # 检查数据库
    if [ -f "$SCRIPT_DIR/data/screener.db" ]; then
        DB_SIZE=$(ls -lh "$SCRIPT_DIR/data/screener.db" | awk '{print $5}')
        echo "数据库: $SCRIPT_DIR/data/screener.db ($DB_SIZE)"
    else
        echo "数据库: 尚未创建"
    fi
    
    # 最近运行
    if [ -f "$SCRIPT_DIR/logs/screener.log" ]; then
        echo ""
        echo "最近运行:"
        tail -5 "$SCRIPT_DIR/logs/screener.log" 2>/dev/null | head -5
    fi
}

# 查看日志
show_logs() {
    LOG_FILE="$SCRIPT_DIR/logs/screener.log"
    if [ -f "$LOG_FILE" ]; then
        echo "======================================"
        echo "  最近日志 (最后50行)"
        echo "======================================"
        tail -50 "$LOG_FILE"
    else
        echo -e "${YELLOW}暂无日志${NC}"
    fi
}

# 设置运行时间
set_schedule() {
    echo "当前运行时间设置:"
    if [ -f "$SCRIPT_DIR/config.json" ]; then
        RUN_TIME=$($PYTHON_CMD -c "import json; c=json.load(open('config.json')); print(c.get('schedule',{}).get('run_time','06:00'))" 2>/dev/null || echo "06:00")
        echo "  $RUN_TIME"
    else
        echo "  06:00 (默认)"
    fi
    
    echo ""
    read -p "请输入新的运行时间 (格式 HH:MM，如 06:00): " NEW_TIME
    
    if [[ $NEW_TIME =~ ^[0-2][0-9]:[0-5][0-9]$ ]]; then
        # 更新配置文件
        $PYTHON_CMD << EOF
import json
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
except:
    config = {}

if 'schedule' not in config:
    config['schedule'] = {}
config['schedule']['run_time'] = '$NEW_TIME'

with open('config.json', 'w') as f:
    json.dump(config, f, indent=4)
print('✓ 运行时间已更新为: $NEW_TIME')
EOF
        
        # 如果服务正在运行，重启它
        if launchctl list | grep -q "$PLIST_NAME"; then
            echo "重启定时任务..."
            start_service
        fi
    else
        echo -e "${RED}✗ 时间格式错误，请使用 HH:MM 格式${NC}"
    fi
}

# 编辑配置
edit_config() {
    CONFIG_FILE="$SCRIPT_DIR/config.json"
    
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "创建默认配置文件..."
        cat > "$CONFIG_FILE" << 'EOF'
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
    fi
    
    # 使用默认编辑器打开
    if [ -n "$EDITOR" ]; then
        $EDITOR "$CONFIG_FILE"
    elif command -v nano &> /dev/null; then
        nano "$CONFIG_FILE"
    elif command -v vim &> /dev/null; then
        vim "$CONFIG_FILE"
    else
        open -e "$CONFIG_FILE"  # Mac默认文本编辑器
    fi
}

# 测试Telegram通知
test_telegram() {
    echo "测试Telegram通知..."
    $PYTHON_CMD << 'EOF'
import json
import requests

try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    telegram = config.get('telegram', {})
    if not telegram.get('enabled'):
        print('✗ Telegram未启用，请先编辑 config.json')
        exit(1)
    
    bot_token = telegram.get('bot_token', '')
    chat_id = telegram.get('chat_id', '')
    
    if 'YOUR_' in bot_token or 'YOUR_' in chat_id:
        print('✗ 请先配置 bot_token 和 chat_id')
        exit(1)
    
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    data = {
        'chat_id': chat_id,
        'text': '🔔 Stock Screener 测试消息\n\n如果您收到此消息，说明Telegram通知配置成功！',
        'parse_mode': 'HTML'
    }
    
    response = requests.post(url, data=data, timeout=10)
    if response.status_code == 200:
        print('✓ 测试消息已发送，请检查Telegram')
    else:
        print(f'✗ 发送失败: {response.text}')
except Exception as e:
    print(f'✗ 错误: {e}')
EOF
}

# 主逻辑
case "$1" in
    run)
        run_now
        ;;
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    schedule)
        set_schedule
        ;;
    config)
        edit_config
        ;;
    test)
        test_telegram
        ;;
    help|--help|-h|"")
        show_help
        ;;
    *)
        echo -e "${RED}未知命令: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
