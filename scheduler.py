#!/usr/bin/env python3
"""
股票筛选系统调度器 V3
- 使用降噪版筛选器
- 分级筛选：优先筛选标普500+纳斯达克100，扩展筛选全美股
- 运行时间追踪和监控
- 每小时运行筛选 (交易时间)
- 每天早上6点发送日报
- 每周五晚上进行分析和优化
"""

import sys
sys.path.append('/opt/.manus/.sandbox-runtime')

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import asdict

# 导入V3降噪版筛选器
from screener_v3 import StockScreenerV3, TelegramNotifier, load_stock_list, RunTimeStats
from data_store import DataStore, PerformanceTracker
from daily_report import DailyReporter
from weekly_analysis import WeeklyAnalyzer

PROJECT_DIR = Path(__file__).resolve().parent
LOG_DIR = PROJECT_DIR / 'logs'
LISTS_DIR = PROJECT_DIR / 'lists'
DATA_DIR = PROJECT_DIR / 'data'
REPORTS_DIR = PROJECT_DIR / 'reports'
LOG_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CONFIG_PATH = str(PROJECT_DIR / 'config.json')
PRIORITY_STOCKS_PATH = str(LISTS_DIR / 'priority_stocks.txt')
ALL_PRIORITY_STOCKS_PATH = str(LISTS_DIR / 'all_priority_stocks.txt')
ALL_US_STOCKS_PATH = str(LISTS_DIR / 'all_us_stocks.txt')


def load_config() -> dict:
    """加载配置"""
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except:
        return {}


def send_telegram_notification(message: str, config: dict = None) -> bool:
    """发送Telegram通知"""
    config = config or load_config()
    tg_config = config.get('notification', {}).get('telegram', {})
    
    if not tg_config.get('enabled') or not tg_config.get('bot_token'):
        return False
    
    notifier = TelegramNotifier(tg_config['bot_token'], tg_config['chat_id'])
    return notifier.send_message(message)


def format_results_message(results, stats: RunTimeStats, scan_type: str = "优先") -> str:
    """格式化筛选结果消息（V3版）"""
    # 按质量分组
    a_grade = [r for r in results if 'A级' in r.signal_quality]
    b_grade = [r for r in results if 'B级' in r.signal_quality]
    c_grade = [r for r in results if 'C级' in r.signal_quality]
    
    lines = [
        f"📊 <b>股票筛选完成 ({scan_type})</b>",
        f"⏱️ 耗时: {stats.total_runtime_seconds:.1f}秒",
        f"📈 筛选: {stats.total_stocks} 只 → 发现: {len(results)} 只",
        f"🔥 高分(≥70): {stats.high_score_count} 只",
        ""
    ]
    
    if a_grade:
        lines.append(f"🔥 <b>A级信号 ({len(a_grade)}只)</b>")
        for r in a_grade[:5]:
            lines.append(f"  <b>{r.symbol}</b> {r.score}分 ${r.current_price:.2f} ({r.change_percent:+.2f}%)")
            lines.append(f"    📈 {r.trend_strength}")
            if r.signals:
                lines.append(f"    📌 {r.signals[0]}")
        if len(a_grade) > 5:
            lines.append(f"  ... 还有 {len(a_grade)-5} 只")
        lines.append("")
    
    if b_grade:
        lines.append(f"⭐ <b>B级信号 ({len(b_grade)}只)</b>")
        for r in b_grade[:3]:
            lines.append(f"  {r.symbol} {r.score}分 ${r.current_price:.2f} | {r.trend_strength}")
        if len(b_grade) > 3:
            lines.append(f"  ... 还有 {len(b_grade)-3} 只")
        lines.append("")
    
    if c_grade and len(a_grade) + len(b_grade) < 5:
        lines.append(f"📋 <b>C级信号 ({len(c_grade)}只)</b>")
        for r in c_grade[:2]:
            lines.append(f"  {r.symbol} {r.score}分 ${r.current_price:.2f}")
    
    return "\n".join(lines)


def run_priority_scan():
    """运行优先筛选（标普500+纳斯达克100+热门成长股）- V3降噪版"""
    logger.info("=" * 50)
    logger.info("开始优先筛选（V3降噪版）...")
    
    config = load_config()
    
    # 加载优先股票池
    symbols = load_stock_list(ALL_PRIORITY_STOCKS_PATH)
    if not symbols:
        symbols = load_stock_list(PRIORITY_STOCKS_PATH)
    
    if not symbols:
        logger.error("无法加载股票列表")
        return [], None
    
    logger.info(f"准备筛选 {len(symbols)} 只股票")
    
    # 创建V3筛选器
    screener = StockScreenerV3(max_workers=15)
    store = DataStore()
    
    # 执行筛选
    results, stats = screener.screen_stocks(symbols)
    
    # 保存结果到数据库
    if results:
        result_dicts = [{
            'symbol': r.symbol,
            'name': r.name,
            'price': r.current_price,
            'change_percent': r.change_percent,
            'volume': r.volume,
            'avg_volume': r.avg_volume,
            'signals': r.signals,
            'score': r.score,
            'signal_quality': r.signal_quality,
            'trend_strength': r.trend_strength
        } for r in results]
        
        store.save_screening_results(result_dicts)
        
        # 保存报告文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        report_dir = REPORTS_DIR / 'hourly'
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_path = report_dir / f"priority_scan_{timestamp}.json"
        with open(report_path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'scan_type': 'priority_v3',
                'version': 'v3_denoise',
                'stats': stats.to_dict(),
                'results': [asdict(r) for r in results]
            }, f, indent=2, default=str)
    
    # 保存运行时间统计
    runtime_log_path = DATA_DIR / 'runtime_history.json'
    runtime_history = []
    if runtime_log_path.exists():
        try:
            with open(runtime_log_path, 'r') as f:
                runtime_history = json.load(f)
        except:
            pass
    
    runtime_history.append({
        'timestamp': datetime.now().isoformat(),
        'scan_type': 'priority_v3',
        **stats.to_dict()
    })
    
    # 只保留最近100条记录
    runtime_history = runtime_history[-100:]
    with open(runtime_log_path, 'w') as f:
        json.dump(runtime_history, f, indent=2)
    
    # 发送Telegram通知
    if results:
        message = format_results_message(results, stats, "优先-降噪版")
        send_telegram_notification(message, config)
    else:
        # 没有发现信号也通知
        message = f"""📊 <b>股票筛选完成（降噪版）</b>

⏱️ 耗时: {stats.total_runtime_seconds:.1f}秒
📈 筛选: {stats.total_stocks} 只
🔍 未发现符合条件的股票

（降噪模式下门槛较高，无信号属正常）"""
        send_telegram_notification(message, config)
    
    # 如果耗时过长，发送警告
    if stats.total_runtime_seconds > 300:  # 超过5分钟
        warning = f"""⚠️ <b>运行时间警告</b>

优先筛选耗时 <b>{stats.total_runtime_seconds/60:.1f}分钟</b>
建议检查网络或减少股票数量

股票数: {stats.total_stocks}
成功率: {stats.successful_stocks/stats.total_stocks*100:.1f}%"""
        send_telegram_notification(warning, config)
    
    logger.info(f"优先筛选完成: 发现 {len(results)} 只潜力股，耗时 {stats.total_runtime_seconds:.1f}秒")
    logger.info("=" * 50)
    
    return results, stats


def run_extended_scan():
    """运行扩展筛选（全美股）- V3降噪版"""
    logger.info("=" * 50)
    logger.info("开始扩展筛选（全美股-V3降噪版）...")
    
    config = load_config()
    
    # 加载全美股列表
    symbols = load_stock_list(ALL_US_STOCKS_PATH)
    
    if not symbols:
        logger.error("无法加载全美股列表")
        return [], None
    
    logger.info(f"准备筛选 {len(symbols)} 只股票")
    
    # 创建V3筛选器（使用更多线程）
    screener = StockScreenerV3(max_workers=20)
    store = DataStore()
    
    # 执行筛选
    start_time = time.time()
    results, stats = screener.screen_stocks(symbols)
    
    # 保存结果
    if results:
        result_dicts = [{
            'symbol': r.symbol,
            'name': r.name,
            'price': r.current_price,
            'change_percent': r.change_percent,
            'volume': r.volume,
            'avg_volume': r.avg_volume,
            'signals': r.signals,
            'score': r.score,
            'signal_quality': r.signal_quality,
            'trend_strength': r.trend_strength
        } for r in results]
        
        store.save_screening_results(result_dicts)
        
        # 保存报告
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        report_dir = REPORTS_DIR / 'daily'
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_path = report_dir / f"extended_scan_{timestamp}.json"
        with open(report_path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'scan_type': 'extended_v3',
                'version': 'v3_denoise',
                'stats': stats.to_dict(),
                'results': [asdict(r) for r in results]
            }, f, indent=2, default=str)
    
    # 发送通知
    a_grade = [r for r in results if 'A级' in r.signal_quality]
    b_grade = [r for r in results if 'B级' in r.signal_quality]
    
    message = f"""📊 <b>全美股扩展筛选完成（降噪版）</b>

⏱️ 耗时: {stats.total_runtime_seconds/60:.1f}分钟
📈 筛选: {stats.total_stocks} 只
✅ 成功: {stats.successful_stocks} 只
🎯 发现信号: {len(results)} 只
🔥 A级信号: {len(a_grade)} 只
⭐ B级信号: {len(b_grade)} 只"""
    
    if a_grade:
        message += "\n\n🔥 <b>A级信号</b>"
        for r in a_grade[:5]:
            message += f"\n  <b>{r.symbol}</b> {r.score}分 | {r.trend_strength}"
    
    send_telegram_notification(message, config)
    
    logger.info(f"扩展筛选完成: 发现 {len(results)} 只潜力股，耗时 {stats.total_runtime_seconds/60:.1f}分钟")
    logger.info("=" * 50)
    
    return results, stats


def run_daily_report():
    """每日汇总任务"""
    logger.info("=" * 50)
    logger.info("开始生成每日汇总报告...")
    
    reporter = DailyReporter(CONFIG_PATH)
    
    # 汇总昨天的结果
    yesterday = (datetime.now() - timedelta(days=1)).date()
    summary = reporter.run(yesterday)
    
    logger.info(f"日报生成完成: {summary.get('unique_stocks', 0)} 只潜力股")
    logger.info("=" * 50)
    
    return summary


def run_weekly_analysis(auto_optimize: bool = True):
    """每周分析任务"""
    logger.info("=" * 50)
    logger.info("开始每周分析...")
    
    analyzer = WeeklyAnalyzer(CONFIG_PATH)
    analysis, adjustments = analyzer.run(auto_optimize)
    
    logger.info(f"周分析完成: 准确率 {analysis.get('accuracy_rate', 0):.1f}%")
    if adjustments.get('applied'):
        logger.info(f"模型已调整: {len(adjustments['applied'])} 项")
    logger.info("=" * 50)
    
    return analysis, adjustments


def run_update_tracking():
    """更新追踪数据"""
    logger.info("更新追踪数据...")
    tracker = PerformanceTracker()
    tracker.update_all_tracking()
    logger.info("追踪数据更新完成")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='股票筛选系统调度器V3（降噪版）')
    parser.add_argument('task', choices=['priority', 'extended', 'daily', 'weekly', 'tracking', 'all'],
                        help='要执行的任务: priority=优先筛选, extended=全美股筛选, daily=日报, weekly=周分析')
    parser.add_argument('--no-notify', action='store_true', help='不发送通知')
    parser.add_argument('--no-optimize', action='store_true', help='不自动优化模型')
    
    args = parser.parse_args()
    
    if args.task == 'priority':
        run_priority_scan()
    
    elif args.task == 'extended':
        run_extended_scan()
    
    elif args.task == 'daily':
        run_daily_report()
    
    elif args.task == 'weekly':
        run_weekly_analysis(not args.no_optimize)
    
    elif args.task == 'tracking':
        run_update_tracking()
    
    elif args.task == 'all':
        # 运行所有任务
        run_priority_scan()
        run_update_tracking()
        run_daily_report()
        
        # 如果是周五，运行周分析
        if datetime.now().weekday() == 4:
            run_weekly_analysis(not args.no_optimize)


if __name__ == '__main__':
    main()
