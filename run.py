#!/usr/bin/env python3
"""
股票筛选系统启动脚本
- 自动检查并创建必要目录
- 自动检查并创建必要文件
- 自动初始化数据库
- 然后运行筛选任务

敏感信息通过环境变量配置：
- TELEGRAM_BOT_TOKEN: Telegram Bot Token
- TELEGRAM_CHAT_ID: Telegram Chat ID
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# 项目根目录
PROJECT_DIR = Path('/home/ubuntu/stock_screener')

# 必要的目录
REQUIRED_DIRS = [
    PROJECT_DIR / 'data',
    PROJECT_DIR / 'reports',
    PROJECT_DIR / 'reports/hourly',
    PROJECT_DIR / 'reports/daily',
    PROJECT_DIR / 'reports/weekly',
]

def get_default_config():
    """获取默认配置，敏感信息从环境变量读取"""
    return {
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
        "notification": {
            "telegram": {
                "enabled": bool(os.environ.get('TELEGRAM_BOT_TOKEN')),
                "bot_token": os.environ.get('TELEGRAM_BOT_TOKEN', ''),
                "chat_id": os.environ.get('TELEGRAM_CHAT_ID', '')
            }
        }
    }

# 默认优先股票池（标普500+纳斯达克100核心股票）
DEFAULT_PRIORITY_STOCKS = """# 优先股票池 - 标普500 + 纳斯达克100 核心股票
# 科技巨头
AAPL
MSFT
GOOGL
GOOG
AMZN
META
NVDA
TSLA
# 半导体
AVGO
QCOM
AMD
INTC
MU
MRVL
AMAT
LRCX
KLAC
TSM
ARM
ASML
# 软件/云
CRM
NOW
PANW
CRWD
NET
DDOG
SNOW
ADBE
ORCL
# AI相关
SMCI
DELL
IBM
AI
PATH
PLTR
# 金融
JPM
BAC
GS
MS
WFC
C
V
MA
AXP
BLK
# 医疗
UNH
JNJ
PFE
LLY
ABBV
MRK
BMY
AMGN
GILD
BIIB
# 消费
WMT
COST
HD
LOW
NKE
SBUX
MCD
DIS
NFLX
# 工业
CAT
DE
BA
HON
UPS
FDX
GE
MMM
# 能源
XOM
CVX
COP
OXY
SLB
# 热门成长股
MSTR
HOOD
RIVN
LCID
NIO
SOFI
AFRM
COIN
SQ
SHOP
ROKU
SNAP
PINS
RBLX
U
TTD
DKNG
ABNB
UBER
LYFT
DASH
"""


def ensure_directories():
    """确保必要目录存在"""
    for dir_path in REQUIRED_DIRS:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✓ 目录已就绪: {dir_path}")


def ensure_config():
    """确保配置文件存在"""
    config_path = PROJECT_DIR / 'config.json'
    if not config_path.exists():
        config = get_default_config()
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"✓ 配置文件已创建: {config_path}")
    else:
        # 更新现有配置中的Telegram设置（从环境变量）
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # 如果环境变量有设置，更新配置
            if os.environ.get('TELEGRAM_BOT_TOKEN'):
                if 'notification' not in config:
                    config['notification'] = {}
                if 'telegram' not in config['notification']:
                    config['notification']['telegram'] = {}
                config['notification']['telegram']['enabled'] = True
                config['notification']['telegram']['bot_token'] = os.environ.get('TELEGRAM_BOT_TOKEN')
                config['notification']['telegram']['chat_id'] = os.environ.get('TELEGRAM_CHAT_ID', '')
                
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                print(f"✓ 配置文件已更新（使用环境变量）: {config_path}")
            else:
                print(f"✓ 配置文件已存在: {config_path}")
        except Exception as e:
            print(f"⚠ 配置文件读取失败: {e}")


def ensure_stock_list():
    """确保股票列表文件存在"""
    # 优先股票池
    priority_path = PROJECT_DIR / 'priority_stocks.txt'
    if not priority_path.exists():
        with open(priority_path, 'w') as f:
            f.write(DEFAULT_PRIORITY_STOCKS)
        print(f"✓ 股票列表已创建: {priority_path}")
    else:
        print(f"✓ 股票列表已存在: {priority_path}")
    
    # all_priority_stocks.txt（如果不存在，复制priority_stocks.txt）
    all_priority_path = PROJECT_DIR / 'all_priority_stocks.txt'
    if not all_priority_path.exists():
        with open(all_priority_path, 'w') as f:
            f.write(DEFAULT_PRIORITY_STOCKS)
        print(f"✓ 完整股票列表已创建: {all_priority_path}")


def ensure_data_api():
    """确保data_api模块可用"""
    # 添加sandbox-runtime到路径
    runtime_path = '/opt/.manus/.sandbox-runtime'
    if runtime_path not in sys.path:
        sys.path.insert(0, runtime_path)
    print(f"✓ API模块路径已添加")


def init_environment():
    """初始化环境"""
    print("=" * 50)
    print("初始化股票筛选系统环境...")
    print("=" * 50)
    
    # 切换到项目目录
    os.chdir(PROJECT_DIR)
    
    # 确保目录存在
    ensure_directories()
    
    # 确保配置文件存在
    ensure_config()
    
    # 确保股票列表存在
    ensure_stock_list()
    
    # 确保API模块可用
    ensure_data_api()
    
    print("=" * 50)
    print("环境初始化完成!")
    print("=" * 50)


def run_task(task: str):
    """运行指定任务"""
    init_environment()
    
    # 导入并运行调度器
    from scheduler import (
        run_priority_scan, 
        run_extended_scan, 
        run_daily_report, 
        run_weekly_analysis,
        run_update_tracking
    )
    
    if task == 'priority':
        return run_priority_scan()
    elif task == 'extended':
        return run_extended_scan()
    elif task == 'daily':
        return run_daily_report()
    elif task == 'weekly':
        return run_weekly_analysis()
    elif task == 'tracking':
        return run_update_tracking()
    else:
        print(f"未知任务: {task}")
        return None


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='股票筛选系统启动脚本')
    parser.add_argument('task', nargs='?', default='priority',
                        choices=['priority', 'extended', 'daily', 'weekly', 'tracking', 'init'],
                        help='要执行的任务 (默认: priority)')
    
    args = parser.parse_args()
    
    if args.task == 'init':
        # 只初始化环境，不运行任务
        init_environment()
        print("\n环境初始化完成，可以运行筛选任务了。")
    else:
        run_task(args.task)


if __name__ == '__main__':
    main()
