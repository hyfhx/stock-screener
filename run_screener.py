#!/usr/bin/env python3
"""
定时运行股票筛选程序
支持定时执行、市场时间检测、多种通知方式
"""

import sys
sys.path.append('/opt/.manus/.sandbox-runtime')

import json
import time
import schedule
import requests
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# 导入主筛选程序
from stock_screener import StockScreener, AlertNotifier, StockSignal, DEFAULT_WATCHLIST

PROJECT_DIR = Path(__file__).resolve().parent
LOG_DIR = PROJECT_DIR / 'logs'
LISTS_DIR = PROJECT_DIR / 'lists'
REPORTS_DIR = PROJECT_DIR / 'reports'
LOG_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)
LISTS_DIR.mkdir(exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Telegram通知类"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def send_message(self, text: str) -> bool:
        """发送Telegram消息"""
        try:
            # Telegram消息有长度限制，需要分段发送
            max_length = 4000
            messages = [text[i:i+max_length] for i in range(0, len(text), max_length)]
            
            for msg in messages:
                response = requests.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        'chat_id': self.chat_id,
                        'text': msg,
                        'parse_mode': 'HTML'
                    }
                )
                if response.status_code != 200:
                    logger.error(f"Telegram发送失败: {response.text}")
                    return False
                time.sleep(0.5)  # 避免频率限制
            
            logger.info("Telegram消息发送成功")
            return True
            
        except Exception as e:
            logger.error(f"Telegram发送异常: {e}")
            return False
    
    def format_alert(self, signals: List[StockSignal]) -> str:
        """格式化Telegram消息"""
        if not signals:
            return "📊 <b>股票筛选报告</b>\n\n未发现符合条件的股票"
        
        lines = [
            f"📊 <b>股票筛选报告</b>",
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"📈 发现 <b>{len(signals)}</b> 只潜力股票\n",
            "=" * 30
        ]
        
        for i, sig in enumerate(signals[:10], 1):  # 只显示前10只
            lines.append(f"\n<b>【{i}】{sig.symbol}</b> - {sig.name[:20]}")
            lines.append(f"💰 ${sig.current_price:.2f} ({sig.change_percent:+.2f}%)")
            lines.append(f"⭐ 评分: {sig.score}")
            lines.append("📌 " + " | ".join(sig.signals[:3]))  # 只显示前3个信号
        
        if len(signals) > 10:
            lines.append(f"\n... 还有 {len(signals) - 10} 只股票")
        
        lines.append("\n⚠️ 仅供参考，不构成投资建议")
        
        return "\n".join(lines)


def load_config() -> Dict:
    """加载配置文件"""
    config_path = PROJECT_DIR / 'config.json'
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}


def load_watchlist() -> List[str]:
    """加载股票池"""
    watchlist_path = LISTS_DIR / 'watchlist.txt'
    if watchlist_path.exists():
        with open(watchlist_path, 'r') as f:
            symbols = []
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    symbols.append(line.upper())
            return symbols if symbols else DEFAULT_WATCHLIST
    return DEFAULT_WATCHLIST


def is_market_open() -> bool:
    """检查美股市场是否开盘 (简化版本)"""
    from datetime import datetime
    import pytz
    
    try:
        et = pytz.timezone('America/New_York')
        now = datetime.now(et)
        
        # 周末不开盘
        if now.weekday() >= 5:
            return False
        
        # 交易时间 9:30 - 16:00 ET
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now <= market_close
    except:
        # 如果没有pytz，默认返回True
        return True


def run_screening():
    """执行一次筛选"""
    logger.info("=" * 50)
    logger.info("开始执行股票筛选...")
    
    config = load_config()
    symbols = load_watchlist()
    
    logger.info(f"股票池: {len(symbols)} 只股票")
    
    # 创建筛选器
    screener = StockScreener()
    notifier = AlertNotifier()
    
    # 执行筛选
    results = screener.screen_stocks(symbols)
    
    # 保存报告
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = str(REPORTS_DIR / f'report_{timestamp}.txt')
    notifier.save_report(results, report_path)
    
    # 控制台输出
    notifier.print_console(results)
    
    # 发送通知
    if results:  # 只有发现股票才发送通知
        # Telegram通知
        tg_config = config.get('notification', {}).get('telegram', {})
        if tg_config.get('enabled') and tg_config.get('bot_token') and tg_config.get('chat_id'):
            tg = TelegramNotifier(tg_config['bot_token'], tg_config['chat_id'])
            tg.send_message(tg.format_alert(results))
        
        # 邮件通知
        email_config = config.get('notification', {}).get('email', {})
        if email_config.get('enabled'):
            notifier.send_email(
                results,
                email_config['smtp_server'],
                email_config['smtp_port'],
                email_config['sender'],
                email_config['password'],
                email_config['recipients']
            )
    
    logger.info(f"筛选完成! 发现 {len(results)} 只潜力股票")
    logger.info("=" * 50)
    
    return results


def run_scheduled():
    """定时运行模式"""
    config = load_config()
    schedule_config = config.get('schedule', {})
    
    interval = schedule_config.get('interval_minutes', 60)
    market_hours_only = schedule_config.get('market_hours_only', True)
    
    logger.info(f"定时模式启动: 每 {interval} 分钟执行一次")
    if market_hours_only:
        logger.info("仅在美股交易时间运行")
    
    def job():
        if market_hours_only and not is_market_open():
            logger.info("当前非交易时间，跳过筛选")
            return
        run_screening()
    
    # 立即执行一次
    job()
    
    # 设置定时任务
    schedule.every(interval).minutes.do(job)
    
    logger.info("定时任务已启动，按 Ctrl+C 退出")
    
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='股票筛选定时运行程序')
    parser.add_argument('--once', action='store_true', help='只运行一次')
    parser.add_argument('--scheduled', action='store_true', help='定时运行模式')
    
    args = parser.parse_args()
    
    if args.scheduled:
        run_scheduled()
    else:
        run_screening()
