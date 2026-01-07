#!/bin/bash
#
# 股票筛选系统 - Mac 一键安装脚本
# 
# 使用方法：
#   chmod +x install_mac.sh
#   ./install_mac.sh
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
INSTALL_DIR="$HOME/stock-screener"
PLIST_NAME="com.stockscreener.daily"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
CONFIG_FILE="$INSTALL_DIR/config.json"
LOG_FILE="$INSTALL_DIR/logs/install.log"

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║         📊 股票筛选系统 - Mac 一键安装程序                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 检查Python
echo -e "${YELLOW}[1/6] 检查Python环境...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓ Python已安装: $PYTHON_VERSION${NC}"
else
    echo -e "${RED}✗ 未找到Python3，请先安装Python3${NC}"
    echo "  安装方法: brew install python3"
    exit 1
fi

# 检查pip
echo -e "${YELLOW}[2/6] 检查pip...${NC}"
if command -v pip3 &> /dev/null; then
    echo -e "${GREEN}✓ pip3已安装${NC}"
else
    echo -e "${RED}✗ 未找到pip3，正在安装...${NC}"
    python3 -m ensurepip --upgrade
fi

# 创建安装目录
echo -e "${YELLOW}[3/6] 创建安装目录...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/reports/daily"
mkdir -p "$INSTALL_DIR/reports/weekly"
echo -e "${GREEN}✓ 目录已创建: $INSTALL_DIR${NC}"

# 复制文件
echo -e "${YELLOW}[4/6] 复制程序文件...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 复制所有Python文件
cp "$SCRIPT_DIR"/*.py "$INSTALL_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR"/*.txt "$INSTALL_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR"/*.json "$INSTALL_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR"/*.md "$INSTALL_DIR/" 2>/dev/null || true

echo -e "${GREEN}✓ 程序文件已复制${NC}"

# 安装Python依赖
echo -e "${YELLOW}[5/6] 安装Python依赖...${NC}"
pip3 install --user yfinance pandas numpy requests schedule pytz --quiet
echo -e "${GREEN}✓ Python依赖已安装${NC}"

# 配置Telegram
echo -e "${YELLOW}[6/6] 配置Telegram通知...${NC}"

if [ -f "$CONFIG_FILE" ]; then
    echo -e "${GREEN}✓ 配置文件已存在${NC}"
else
    echo ""
    echo -e "${BLUE}请输入Telegram配置（直接回车跳过）:${NC}"
    
    read -p "Telegram Bot Token: " BOT_TOKEN
    read -p "Telegram Chat ID: " CHAT_ID
    
    # 创建配置文件
    cat > "$CONFIG_FILE" << EOF
{
  "screening": {
    "min_price": 5.0,
    "max_price": 1000.0,
    "min_volume": 500000,
    "min_avg_volume": 1000000,
    "min_score": 40,
    "volume_surge_ratio": 1.8,
    "trend_confirm_days": 3
  },
  "weights": {
    "ma_golden_cross": 30,
    "macd_golden_cross": 25,
    "rsi_reversal": 20,
    "volume_surge": 15,
    "price_breakout_52w": 20,
    "price_breakout_20d": 10,
    "trend_continuation": 15,
    "obv_confirm": 10
  },
  "schedule": {
    "run_time": "06:00",
    "timezone": "America/New_York"
  },
  "notification": {
    "telegram": {
      "enabled": ${BOT_TOKEN:+true}${BOT_TOKEN:-false},
      "bot_token": "${BOT_TOKEN:-}",
      "chat_id": "${CHAT_ID:-}"
    }
  }
}
EOF
    echo -e "${GREEN}✓ 配置文件已创建${NC}"
fi

# 创建启动脚本
cat > "$INSTALL_DIR/run_daily.sh" << 'EOF'
#!/bin/bash
# 每日运行脚本

INSTALL_DIR="$HOME/stock-screener"
LOG_FILE="$INSTALL_DIR/logs/screener_$(date +%Y%m%d).log"

cd "$INSTALL_DIR"

echo "========================================" >> "$LOG_FILE"
echo "开始运行: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# 运行筛选
python3 "$INSTALL_DIR/screener_v3.py" --config "$INSTALL_DIR/config.json" >> "$LOG_FILE" 2>&1

echo "运行完成: $(date)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
EOF

chmod +x "$INSTALL_DIR/run_daily.sh"

# 创建控制脚本
cat > "$INSTALL_DIR/screener" << 'CONTROL_SCRIPT'
#!/bin/bash
#
# 股票筛选系统控制脚本
#

INSTALL_DIR="$HOME/stock-screener"
PLIST_NAME="com.stockscreener.daily"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

show_help() {
    echo -e "${BLUE}股票筛选系统控制面板${NC}"
    echo ""
    echo "用法: screener <命令>"
    echo ""
    echo "命令:"
    echo "  run         立即运行一次筛选"
    echo "  start       启动定时任务服务"
    echo "  stop        停止定时任务服务"
    echo "  status      查看服务状态"
    echo "  logs        查看最近的日志"
    echo "  config      编辑配置文件"
    echo "  schedule    设置运行时间"
    echo "  uninstall   卸载程序"
    echo ""
}

run_now() {
    echo -e "${YELLOW}正在运行股票筛选...${NC}"
    cd "$INSTALL_DIR"
    python3 "$INSTALL_DIR/screener_v3.py" --config "$INSTALL_DIR/config.json"
    echo -e "${GREEN}✓ 运行完成${NC}"
}

start_service() {
    if [ -f "$PLIST_PATH" ]; then
        launchctl load "$PLIST_PATH" 2>/dev/null
        echo -e "${GREEN}✓ 定时任务服务已启动${NC}"
    else
        echo -e "${RED}✗ 未找到服务配置，请先运行 'screener schedule' 设置运行时间${NC}"
    fi
}

stop_service() {
    if [ -f "$PLIST_PATH" ]; then
        launchctl unload "$PLIST_PATH" 2>/dev/null
        echo -e "${GREEN}✓ 定时任务服务已停止${NC}"
    else
        echo -e "${YELLOW}服务未安装${NC}"
    fi
}

show_status() {
    echo -e "${BLUE}=== 股票筛选系统状态 ===${NC}"
    echo ""
    
    # 检查服务状态
    if launchctl list | grep -q "$PLIST_NAME"; then
        echo -e "服务状态: ${GREEN}运行中${NC}"
    else
        echo -e "服务状态: ${YELLOW}未运行${NC}"
    fi
    
    # 显示配置的运行时间
    if [ -f "$INSTALL_DIR/config.json" ]; then
        RUN_TIME=$(python3 -c "import json; print(json.load(open('$INSTALL_DIR/config.json')).get('schedule', {}).get('run_time', '未设置'))" 2>/dev/null || echo "未设置")
        echo "运行时间: $RUN_TIME"
    fi
    
    # 显示最近运行
    LATEST_LOG=$(ls -t "$INSTALL_DIR/logs/"*.log 2>/dev/null | head -1)
    if [ -n "$LATEST_LOG" ]; then
        LAST_RUN=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$LATEST_LOG" 2>/dev/null || echo "未知")
        echo "最近运行: $LAST_RUN"
    fi
    
    echo ""
}

show_logs() {
    LATEST_LOG=$(ls -t "$INSTALL_DIR/logs/"*.log 2>/dev/null | head -1)
    if [ -n "$LATEST_LOG" ]; then
        echo -e "${BLUE}=== 最近日志 ===${NC}"
        tail -50 "$LATEST_LOG"
    else
        echo -e "${YELLOW}暂无日志${NC}"
    fi
}

edit_config() {
    if command -v code &> /dev/null; then
        code "$INSTALL_DIR/config.json"
    elif command -v nano &> /dev/null; then
        nano "$INSTALL_DIR/config.json"
    else
        open -e "$INSTALL_DIR/config.json"
    fi
}

set_schedule() {
    echo -e "${BLUE}设置运行时间${NC}"
    echo ""
    echo "当前时间格式: HH:MM (24小时制，美东时间)"
    echo "例如: 06:00 表示每天早上6点运行"
    echo ""
    
    read -p "请输入运行时间 [默认 06:00]: " RUN_TIME
    RUN_TIME=${RUN_TIME:-06:00}
    
    # 解析时间
    HOUR=$(echo "$RUN_TIME" | cut -d: -f1)
    MINUTE=$(echo "$RUN_TIME" | cut -d: -f2)
    
    # 更新配置文件
    python3 << EOF
import json
config_path = "$INSTALL_DIR/config.json"
with open(config_path, 'r') as f:
    config = json.load(f)
if 'schedule' not in config:
    config['schedule'] = {}
config['schedule']['run_time'] = "$RUN_TIME"
with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)
print("配置已更新")
EOF
    
    # 创建launchd plist
    cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$INSTALL_DIR/run_daily.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>$HOUR</integer>
        <key>Minute</key>
        <integer>$MINUTE</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/logs/launchd_error.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST
    
    # 重新加载服务
    launchctl unload "$PLIST_PATH" 2>/dev/null
    launchctl load "$PLIST_PATH"
    
    echo -e "${GREEN}✓ 定时任务已设置: 每天 $RUN_TIME 运行${NC}"
}

uninstall() {
    echo -e "${RED}确定要卸载股票筛选系统吗？${NC}"
    read -p "输入 'yes' 确认: " CONFIRM
    
    if [ "$CONFIRM" = "yes" ]; then
        # 停止服务
        launchctl unload "$PLIST_PATH" 2>/dev/null
        rm -f "$PLIST_PATH"
        
        # 删除文件
        rm -rf "$INSTALL_DIR"
        rm -f "/usr/local/bin/screener"
        
        echo -e "${GREEN}✓ 卸载完成${NC}"
    else
        echo "取消卸载"
    fi
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
    config)
        edit_config
        ;;
    schedule)
        set_schedule
        ;;
    uninstall)
        uninstall
        ;;
    *)
        show_help
        ;;
esac
CONTROL_SCRIPT

chmod +x "$INSTALL_DIR/screener"

# 创建全局命令链接
echo ""
echo -e "${YELLOW}是否创建全局命令 'screener'？(需要管理员权限)${NC}"
read -p "输入 y 确认 [y/N]: " CREATE_LINK

if [ "$CREATE_LINK" = "y" ] || [ "$CREATE_LINK" = "Y" ]; then
    sudo ln -sf "$INSTALL_DIR/screener" /usr/local/bin/screener
    echo -e "${GREEN}✓ 全局命令已创建，可以在任意位置使用 'screener' 命令${NC}"
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    ✓ 安装完成！                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "安装目录: ${BLUE}$INSTALL_DIR${NC}"
echo ""
echo -e "${YELLOW}下一步操作:${NC}"
echo ""
echo "  1. 设置运行时间:"
echo -e "     ${BLUE}screener schedule${NC}"
echo ""
echo "  2. 立即运行一次测试:"
echo -e "     ${BLUE}screener run${NC}"
echo ""
echo "  3. 查看状态:"
echo -e "     ${BLUE}screener status${NC}"
echo ""
echo -e "更多命令请运行: ${BLUE}screener${NC}"
echo ""
