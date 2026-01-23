#!/usr/bin/env python3
"""
每日汇总报告模块
- 汇总当天所有筛选结果
- 生成专业报告
- 发送Telegram/邮件通知
"""

import sys
sys.path.append('/opt/.manus/.sandbox-runtime')

import json
import smtplib
import requests
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import List, Dict, Optional
from collections import Counter

from data_store import DataStore

PROJECT_DIR = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_DIR / 'reports'
DAILY_REPORT_DIR = REPORTS_DIR / 'daily'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Telegram通知类"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
    
    def send_message(self, text: str, parse_mode: str = 'HTML') -> bool:
        """发送Telegram消息"""
        try:
            # Telegram消息有长度限制，需要分段发送
            max_length = 4000
            messages = [text[i:i+max_length] for i in range(0, len(text), max_length)]
            
            for msg in messages:
                response = requests.post(
                    f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    json={
                        'chat_id': self.chat_id,
                        'text': msg,
                        'parse_mode': parse_mode
                    }
                )
                if response.status_code != 200:
                    logger.error(f"Telegram发送失败: {response.text}")
                    return False
            
            logger.info("Telegram消息发送成功")
            return True
            
        except Exception as e:
            logger.error(f"Telegram发送异常: {e}")
            return False


class DailyReporter:
    """每日报告生成器"""
    
    def __init__(self, config_path: str = None):
        config_path = config_path or str(PROJECT_DIR / 'config.json')
        self.store = DataStore()
        self.config = self._load_config(config_path)
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def generate_daily_summary(self, target_date: datetime.date = None) -> Dict:
        """生成每日汇总"""
        target_date = target_date or (datetime.now() - timedelta(days=1)).date()
        
        # 获取当天所有结果
        results = self.store.get_results_by_date(target_date)
        
        if not results:
            return {
                'date': target_date.isoformat(),
                'total_signals': 0,
                'top_stocks': [],
                'message': '当天无筛选结果'
            }
        
        # 统计信号出现次数
        symbol_counts = Counter(r['symbol'] for r in results)
        
        # 获取每只股票的最高评分
        best_scores = {}
        for r in results:
            symbol = r['symbol']
            if symbol not in best_scores or r['score'] > best_scores[symbol]['score']:
                best_scores[symbol] = r
        
        # 按评分排序
        sorted_stocks = sorted(best_scores.values(), key=lambda x: x['score'], reverse=True)
        
        # 生成汇总
        summary = {
            'date': target_date.isoformat(),
            'total_signals': len(results),
            'unique_stocks': len(best_scores),
            'top_stocks': sorted_stocks[:20],  # Top 20
            'avg_score': sum(s['score'] for s in sorted_stocks) / len(sorted_stocks) if sorted_stocks else 0,
            'high_score_count': len([s for s in sorted_stocks if s['score'] >= 70]),
            'medium_score_count': len([s for s in sorted_stocks if 40 <= s['score'] < 70]),
            'low_score_count': len([s for s in sorted_stocks if s['score'] < 40]),
            'most_frequent': symbol_counts.most_common(5)
        }
        
        # 保存汇总到数据库
        self.store.save_daily_summary(target_date, {
            'total_scans': len(results),
            'total_signals': summary['unique_stocks'],
            'top_stocks': [s['symbol'] for s in sorted_stocks[:10]],
            'avg_score': summary['avg_score']
        })
        
        return summary
    
    def format_telegram_message(self, summary: Dict) -> str:
        """生成Telegram格式消息"""
        top_stocks = summary.get('top_stocks', [])
        
        lines = [
            f"📊 <b>股票筛选日报 - {summary['date']}</b>",
            "",
            f"📈 发现潜力股: <b>{summary.get('unique_stocks', 0)}</b> 只",
            f"🔥 高分股票(≥70): <b>{summary.get('high_score_count', 0)}</b> 只",
            f"📊 平均评分: <b>{summary.get('avg_score', 0):.1f}</b>",
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "🏆 <b>今日Top 10</b>",
            "━━━━━━━━━━━━━━━━━━━━",
        ]
        
        for i, stock in enumerate(top_stocks[:10], 1):
            score = stock.get('score', 0)
            change = stock.get('change_percent', 0)
            change_icon = "🟢" if change >= 0 else "🔴"
            score_icon = "🔥" if score >= 70 else ("⭐" if score >= 40 else "")
            
            lines.append(f"{i}. <b>{stock.get('symbol', '')}</b> {score_icon}")
            lines.append(f"   💰 ${stock.get('price', 0):.2f} {change_icon} {change:+.2f}%")
            lines.append(f"   📊 评分: {score}")
            
            # 显示前2个信号
            signals = stock.get('signals', [])[:2]
            if signals:
                lines.append(f"   📌 {' | '.join(signals)}")
            lines.append("")
        
        if len(top_stocks) > 10:
            lines.append(f"... 还有 {len(top_stocks) - 10} 只股票")
        
        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "⚠️ 仅供参考，不构成投资建议",
        ])
        
        return "\n".join(lines)
    
    def format_email_html(self, summary: Dict) -> str:
        """生成HTML格式邮件"""
        top_stocks = summary.get('top_stocks', [])
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .summary-box {{ background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0; }}
        .stat {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #3498db; }}
        .stat-label {{ font-size: 12px; color: #666; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #3498db; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f5f5f5; }}
        .score-high {{ color: #27ae60; font-weight: bold; }}
        .score-medium {{ color: #f39c12; font-weight: bold; }}
        .score-low {{ color: #95a5a6; }}
        .change-positive {{ color: #27ae60; }}
        .change-negative {{ color: #e74c3c; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
        .warning {{ background: #fff3cd; border: 1px solid #ffc107; padding: 10px; border-radius: 4px; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>📊 股票筛选日报 - {summary['date']}</h1>
    
    <div class="summary-box">
        <div class="stat">
            <div class="stat-value">{summary.get('unique_stocks', 0)}</div>
            <div class="stat-label">发现潜力股</div>
        </div>
        <div class="stat">
            <div class="stat-value">{summary.get('high_score_count', 0)}</div>
            <div class="stat-label">高分股票 (≥70)</div>
        </div>
        <div class="stat">
            <div class="stat-value">{summary.get('avg_score', 0):.1f}</div>
            <div class="stat-label">平均评分</div>
        </div>
    </div>
"""
        
        if top_stocks:
            html += """
    <h2>🏆 今日潜力股 Top 20</h2>
    <table>
        <tr>
            <th>排名</th>
            <th>股票</th>
            <th>价格</th>
            <th>涨跌</th>
            <th>评分</th>
            <th>信号</th>
        </tr>
"""
            for i, stock in enumerate(top_stocks[:20], 1):
                score = stock.get('score', 0)
                score_class = 'score-high' if score >= 70 else ('score-medium' if score >= 40 else 'score-low')
                change = stock.get('change_percent', 0)
                change_class = 'change-positive' if change >= 0 else 'change-negative'
                
                signals_html = ' | '.join(stock.get('signals', [])[:3])
                
                html += f"""
        <tr>
            <td>{i}</td>
            <td><strong>{stock.get('symbol', '')}</strong><br><small>{stock.get('name', '')[:25]}</small></td>
            <td>${stock.get('price', 0):.2f}</td>
            <td class="{change_class}">{change:+.2f}%</td>
            <td class="{score_class}">{score}</td>
            <td><small>{signals_html}</small></td>
        </tr>
"""
            
            html += """
    </table>
"""
        
        html += f"""
    <div class="warning">
        ⚠️ <strong>风险提示</strong>：以上内容仅为技术分析参考，不构成投资建议。
    </div>
    
    <div class="footer">
        <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
</body>
</html>
"""
        return html
    
    def send_telegram(self, summary: Dict) -> bool:
        """发送Telegram通知"""
        tg_config = self.config.get('notification', {}).get('telegram', {})
        
        if not tg_config.get('enabled') or not tg_config.get('bot_token'):
            logger.info("Telegram通知未启用")
            return False
        
        notifier = TelegramNotifier(tg_config['bot_token'], tg_config['chat_id'])
        message = self.format_telegram_message(summary)
        return notifier.send_message(message)
    
    def send_email(self, summary: Dict, recipient: str = None) -> bool:
        """发送邮件通知"""
        email_config = self.config.get('notification', {}).get('email', {})
        
        if not email_config.get('enabled') or not email_config.get('smtp_server'):
            logger.info("邮件通知未启用")
            return False
        
        recipient = recipient or email_config.get('recipients', [None])[0]
        if not recipient:
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = email_config['sender']
            msg['To'] = recipient
            
            high_count = summary.get('high_score_count', 0)
            total = summary.get('unique_stocks', 0)
            msg['Subject'] = f"📊 股票日报 {summary['date']} - 发现{total}只潜力股 ({high_count}只高分)"
            
            html_part = MIMEText(self.format_email_html(summary), 'html', 'utf-8')
            msg.attach(html_part)
            
            with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                server.starttls()
                server.login(email_config['sender'], email_config['password'])
                server.send_message(msg)
            
            logger.info(f"邮件发送成功: {recipient}")
            self.store.mark_email_sent(datetime.strptime(summary['date'], '%Y-%m-%d').date())
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False
    
    def run(self, target_date: datetime.date = None):
        """运行每日报告"""
        # 生成汇总
        summary = self.generate_daily_summary(target_date)
        
        if summary.get('unique_stocks', 0) == 0:
            logger.info(f"日期 {summary['date']} 无筛选结果，跳过发送")
            return summary
        
        # 保存报告文件
        DAILY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = DAILY_REPORT_DIR / f"daily_report_{summary['date']}.html"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(self.format_email_html(summary))
        logger.info(f"报告已保存: {report_path}")
        
        # 发送Telegram通知
        self.send_telegram(summary)
        
        # 发送邮件通知
        self.send_email(summary)
        
        return summary


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='生成每日汇总报告')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)，默认为昨天')
    parser.add_argument('--today', action='store_true', help='汇总今天的数据')
    
    args = parser.parse_args()
    
    target_date = None
    if args.date:
        target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    elif args.today:
        target_date = datetime.now().date()
    
    reporter = DailyReporter()
    summary = reporter.run(target_date)
    
    print(f"\n汇总完成: {summary['date']}")
    print(f"发现 {summary.get('unique_stocks', 0)} 只潜力股")
    print(f"高分股票: {summary.get('high_score_count', 0)} 只")


if __name__ == '__main__':
    main()
