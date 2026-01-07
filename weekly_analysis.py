#!/usr/bin/env python3
"""
每周分析和模型优化模块
- 分析过去一周的筛选准确性
- 检测过拟合问题
- 自动调整模型参数
- 生成分析报告并发送Telegram通知
"""

import sys
sys.path.append('/opt/.manus/.sandbox-runtime')

import json
import smtplib
import requests
import logging
import statistics
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from data_store import DataStore, PerformanceTracker

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


class WeeklyAnalyzer:
    """每周分析器"""
    
    def __init__(self, config_path: str = '/home/ubuntu/stock_screener/config.json'):
        self.store = DataStore()
        self.tracker = PerformanceTracker()
        self.config = self._load_config(config_path)
        self.config_path = config_path
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def _save_config(self):
        """保存配置"""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def update_tracking_data(self):
        """更新所有追踪数据"""
        logger.info("开始更新追踪数据...")
        self.tracker.update_all_tracking()
        logger.info("追踪数据更新完成")
    
    def analyze_week(self, week_end: datetime.date = None) -> Dict:
        """分析一周的表现"""
        week_end = week_end or datetime.now().date()
        week_start = week_end - timedelta(days=7)
        
        logger.info(f"分析周期: {week_start} 至 {week_end}")
        
        # 获取统计数据
        stats = self.store.get_tracking_stats(days=14)
        
        # 获取本周的详细数据
        results = self.store.get_results_by_date_range(week_start, week_end)
        
        # 分析各类信号的表现
        signal_performance = self._analyze_signal_performance(week_start, week_end)
        
        # 检测过拟合
        overfitting_analysis = self._detect_overfitting(stats)
        
        # 生成优化建议
        optimization_suggestions = self._generate_optimization_suggestions(
            stats, signal_performance, overfitting_analysis
        )
        
        # 汇总分析结果
        analysis = {
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'total_signals': stats['total_signals'],
            'successful_signals': stats['successful_signals'],
            'accuracy_rate': stats['accuracy_rate'],
            'avg_return': stats['avg_return'],
            'avg_max_gain': stats['avg_max_gain'],
            'avg_max_loss': stats['avg_max_loss'],
            'by_score': stats['by_score'],
            'signal_performance': signal_performance,
            'overfitting_analysis': overfitting_analysis,
            'optimization_suggestions': optimization_suggestions,
            'best_performer': self._find_best_performer(week_start, week_end),
            'worst_performer': self._find_worst_performer(week_start, week_end)
        }
        
        # 保存分析结果
        self.store.save_weekly_analysis(analysis)
        
        return analysis
    
    def _analyze_signal_performance(self, week_start: datetime.date, week_end: datetime.date) -> Dict:
        """分析各类信号的表现"""
        import sqlite3
        conn = sqlite3.connect(self.store.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sr.signals, pt.day7_change, pt.is_successful, sr.score
            FROM screening_results sr
            JOIN performance_tracking pt ON sr.id = pt.screening_id
            WHERE DATE(sr.scan_time) BETWEEN ? AND ?
            AND pt.day7_change IS NOT NULL
        ''', (week_start.isoformat(), week_end.isoformat()))
        
        signal_stats = defaultdict(lambda: {'count': 0, 'successful': 0, 'returns': []})
        
        for row in cursor.fetchall():
            signals = json.loads(row[0]) if row[0] else []
            day7_change = row[1]
            is_successful = row[2]
            
            for signal in signals:
                signal_type = self._extract_signal_type(signal)
                signal_stats[signal_type]['count'] += 1
                if is_successful:
                    signal_stats[signal_type]['successful'] += 1
                signal_stats[signal_type]['returns'].append(day7_change)
        
        conn.close()
        
        performance = {}
        for signal_type, data in signal_stats.items():
            if data['count'] > 0:
                performance[signal_type] = {
                    'count': data['count'],
                    'accuracy': (data['successful'] / data['count']) * 100,
                    'avg_return': statistics.mean(data['returns']) if data['returns'] else 0,
                    'std_return': statistics.stdev(data['returns']) if len(data['returns']) > 1 else 0
                }
        
        return performance
    
    def _extract_signal_type(self, signal: str) -> str:
        """从信号文本中提取类型"""
        if 'MA' in signal and '金叉' in signal:
            return 'MA金叉'
        elif 'MACD' in signal and '金叉' in signal:
            return 'MACD金叉'
        elif 'MACD' in signal and '多头' in signal:
            return 'MACD多头'
        elif 'RSI' in signal and '反弹' in signal:
            return 'RSI反弹'
        elif 'RSI' in signal and '健康' in signal:
            return 'RSI健康'
        elif '成交量' in signal and '放大' in signal:
            return '成交量放大'
        elif '52周' in signal or '新高' in signal:
            return '接近新高'
        elif '突破' in signal:
            return '价格突破'
        elif 'OBV' in signal:
            return 'OBV确认'
        else:
            return '其他'
    
    def _detect_overfitting(self, stats: Dict) -> Dict:
        """检测过拟合"""
        analysis = {
            'is_overfitting': False,
            'concerns': [],
            'severity': 'low'
        }
        
        by_score = stats.get('by_score', {})
        
        high_acc = by_score.get('high', {}).get('accuracy', 0)
        low_acc = by_score.get('low', {}).get('accuracy', 0)
        
        if high_acc > 0 and low_acc > 0:
            if high_acc < low_acc + 10:
                analysis['concerns'].append("高分股票准确率未显著高于低分，评分系统可能需要调整")
                analysis['is_overfitting'] = True
        
        overall_acc = stats.get('accuracy_rate', 0)
        if overall_acc > 80:
            analysis['concerns'].append(f"准确率过高 ({overall_acc:.1f}%)，可能存在过拟合或样本偏差")
            analysis['is_overfitting'] = True
            analysis['severity'] = 'medium'
        elif overall_acc < 30:
            analysis['concerns'].append(f"准确率过低 ({overall_acc:.1f}%)，模型需要重新校准")
            analysis['severity'] = 'high'
        
        avg_return = stats.get('avg_return', 0)
        avg_max_loss = stats.get('avg_max_loss', 0)
        
        if avg_max_loss < -10 and avg_return < 3:
            analysis['concerns'].append(f"风险收益比不佳: 平均收益 {avg_return:.1f}%, 平均最大亏损 {avg_max_loss:.1f}%")
            analysis['severity'] = 'medium'
        
        total = stats.get('total_signals', 0)
        if total < 20:
            analysis['concerns'].append(f"样本量不足 ({total}个)，分析结果可能不可靠")
        
        return analysis
    
    def _generate_optimization_suggestions(self, stats: Dict, signal_perf: Dict, overfitting: Dict) -> List[Dict]:
        """生成优化建议"""
        suggestions = []
        
        for signal_type, perf in signal_perf.items():
            if perf['count'] >= 5:
                if perf['accuracy'] < 30:
                    suggestions.append({
                        'type': 'reduce_weight',
                        'target': signal_type,
                        'reason': f"准确率过低 ({perf['accuracy']:.1f}%)",
                        'action': f"建议降低 {signal_type} 的权重",
                        'priority': 'high'
                    })
                elif perf['accuracy'] > 70 and perf['avg_return'] > 5:
                    suggestions.append({
                        'type': 'increase_weight',
                        'target': signal_type,
                        'reason': f"表现优异: 准确率 {perf['accuracy']:.1f}%, 平均收益 {perf['avg_return']:.1f}%",
                        'action': f"建议提高 {signal_type} 的权重",
                        'priority': 'medium'
                    })
        
        by_score = stats.get('by_score', {})
        high_perf = by_score.get('high', {})
        
        if high_perf.get('accuracy', 0) < 50:
            suggestions.append({
                'type': 'adjust_threshold',
                'target': 'high_score_threshold',
                'reason': f"高分股票准确率不足 ({high_perf.get('accuracy', 0):.1f}%)",
                'action': "建议提高高分阈值或调整评分权重",
                'priority': 'high'
            })
        
        if overfitting['is_overfitting']:
            for concern in overfitting['concerns']:
                suggestions.append({
                    'type': 'review',
                    'target': 'model',
                    'reason': concern,
                    'action': "需要人工审查模型参数",
                    'priority': overfitting['severity']
                })
        
        return suggestions
    
    def _find_best_performer(self, week_start: datetime.date, week_end: datetime.date) -> Optional[Dict]:
        """找出表现最好的股票"""
        import sqlite3
        conn = sqlite3.connect(self.store.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sr.symbol, sr.name, sr.price as signal_price, sr.score,
                   pt.day7_change, pt.max_gain
            FROM screening_results sr
            JOIN performance_tracking pt ON sr.id = pt.screening_id
            WHERE DATE(sr.scan_time) BETWEEN ? AND ?
            AND pt.day7_change IS NOT NULL
            ORDER BY pt.day7_change DESC
            LIMIT 1
        ''', (week_start.isoformat(), week_end.isoformat()))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'symbol': row[0],
                'name': row[1],
                'signal_price': row[2],
                'score': row[3],
                'day7_change': row[4],
                'max_gain': row[5]
            }
        return None
    
    def _find_worst_performer(self, week_start: datetime.date, week_end: datetime.date) -> Optional[Dict]:
        """找出表现最差的股票"""
        import sqlite3
        conn = sqlite3.connect(self.store.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sr.symbol, sr.name, sr.price as signal_price, sr.score,
                   pt.day7_change, pt.max_loss
            FROM screening_results sr
            JOIN performance_tracking pt ON sr.id = pt.screening_id
            WHERE DATE(sr.scan_time) BETWEEN ? AND ?
            AND pt.day7_change IS NOT NULL
            ORDER BY pt.day7_change ASC
            LIMIT 1
        ''', (week_start.isoformat(), week_end.isoformat()))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'symbol': row[0],
                'name': row[1],
                'signal_price': row[2],
                'score': row[3],
                'day7_change': row[4],
                'max_loss': row[5]
            }
        return None
    
    def auto_optimize_model(self, analysis: Dict) -> Dict:
        """自动优化模型参数"""
        suggestions = analysis.get('optimization_suggestions', [])
        adjustments = {'applied': [], 'skipped': []}
        
        current_weights = self.config.get('weights', {
            'ma_golden_cross': 25,
            'macd_golden_cross': 20,
            'rsi_bullish': 15,
            'volume_surge': 15,
            'price_breakout': 15,
            'obv_confirm': 10
        })
        
        signal_to_weight = {
            'MA金叉': 'ma_golden_cross',
            'MACD金叉': 'macd_golden_cross',
            'MACD多头': 'macd_golden_cross',
            'RSI反弹': 'rsi_bullish',
            'RSI健康': 'rsi_bullish',
            '成交量放大': 'volume_surge',
            '接近新高': 'price_breakout',
            '价格突破': 'price_breakout',
            'OBV确认': 'obv_confirm'
        }
        
        new_weights = current_weights.copy()
        
        for suggestion in suggestions:
            if suggestion['type'] == 'reduce_weight':
                weight_key = signal_to_weight.get(suggestion['target'])
                if weight_key and weight_key in new_weights:
                    old_value = new_weights[weight_key]
                    new_value = max(5, old_value - 5)
                    new_weights[weight_key] = new_value
                    adjustments['applied'].append({
                        'param': weight_key,
                        'old': old_value,
                        'new': new_value,
                        'reason': suggestion['reason']
                    })
            
            elif suggestion['type'] == 'increase_weight':
                weight_key = signal_to_weight.get(suggestion['target'])
                if weight_key and weight_key in new_weights:
                    old_value = new_weights[weight_key]
                    new_value = min(35, old_value + 5)
                    new_weights[weight_key] = new_value
                    adjustments['applied'].append({
                        'param': weight_key,
                        'old': old_value,
                        'new': new_value,
                        'reason': suggestion['reason']
                    })
            
            elif suggestion['type'] == 'review':
                adjustments['skipped'].append({
                    'suggestion': suggestion['action'],
                    'reason': '需要人工审查'
                })
        
        if adjustments['applied']:
            self.config['weights'] = new_weights
            self._save_config()
            
            self.store.save_model_params(
                new_weights,
                analysis.get('accuracy_rate'),
                f"自动优化: {len(adjustments['applied'])} 项调整"
            )
            
            logger.info(f"模型参数已更新: {len(adjustments['applied'])} 项调整")
        
        return adjustments
    
    def format_telegram_message(self, analysis: Dict, adjustments: Dict = None) -> str:
        """生成Telegram格式消息"""
        accuracy = analysis.get('accuracy_rate', 0)
        status_icon = "✅" if accuracy >= 50 else ("⚠️" if accuracy >= 30 else "🔴")
        
        lines = [
            f"📈 <b>每周分析报告</b>",
            f"📅 {analysis['week_start']} ~ {analysis['week_end']}",
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "<b>📊 整体表现</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            f"总信号数: <b>{analysis['total_signals']}</b>",
            f"成功信号: <b>{analysis['successful_signals']}</b>",
            f"准确率: {status_icon} <b>{accuracy:.1f}%</b>",
            f"平均收益: <b>{analysis['avg_return']:.2f}%</b>",
            f"平均最大涨幅: <b>{analysis['avg_max_gain']:.2f}%</b>",
            f"平均最大跌幅: <b>{analysis['avg_max_loss']:.2f}%</b>",
            "",
        ]
        
        # 按评分分组
        by_score = analysis.get('by_score', {})
        if by_score:
            lines.append("<b>📈 按评分分组</b>")
            for group, data in by_score.items():
                group_name = {'high': '高分(≥70)', 'medium': '中分(40-69)', 'low': '低分(<40)'}.get(group, group)
                lines.append(f"  {group_name}: {data['total']}个, 准确率 {data['accuracy']:.1f}%")
            lines.append("")
        
        # 最佳/最差表现
        best = analysis.get('best_performer')
        worst = analysis.get('worst_performer')
        if best:
            lines.append(f"🏆 <b>最佳</b>: {best['symbol']} +{best['day7_change']:.1f}%")
        if worst:
            lines.append(f"💔 <b>最差</b>: {worst['symbol']} {worst['day7_change']:.1f}%")
        lines.append("")
        
        # 过拟合警告
        overfitting = analysis.get('overfitting_analysis', {})
        if overfitting.get('concerns'):
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("⚠️ <b>风险提示</b>")
            for concern in overfitting['concerns'][:3]:
                lines.append(f"• {concern}")
            lines.append("")
        
        # 模型调整
        if adjustments and adjustments.get('applied'):
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("🔧 <b>模型已自动调整</b>")
            for adj in adjustments['applied'][:5]:
                lines.append(f"• {adj['param']}: {adj['old']} → {adj['new']}")
            lines.append("")
        
        return "\n".join(lines)
    
    def format_analysis_report(self, analysis: Dict, adjustments: Dict = None) -> str:
        """生成完整分析报告"""
        lines = [
            "=" * 70,
            f"📊 每周分析报告",
            f"分析周期: {analysis['week_start']} 至 {analysis['week_end']}",
            "=" * 70,
            "",
            "【整体表现】",
            f"  总信号数: {analysis['total_signals']}",
            f"  成功信号: {analysis['successful_signals']}",
            f"  准确率: {analysis['accuracy_rate']:.1f}%",
            f"  平均收益: {analysis['avg_return']:.2f}%",
            f"  平均最大涨幅: {analysis['avg_max_gain']:.2f}%",
            f"  平均最大跌幅: {analysis['avg_max_loss']:.2f}%",
            ""
        ]
        
        lines.append("【按评分分组】")
        for group, data in analysis.get('by_score', {}).items():
            group_name = {'high': '高分(≥70)', 'medium': '中分(40-69)', 'low': '低分(<40)'}.get(group, group)
            lines.append(f"  {group_name}: {data['total']}个, 准确率 {data['accuracy']:.1f}%, 平均收益 {data['avg_return']:.2f}%")
        lines.append("")
        
        lines.append("【各类信号表现】")
        for signal, perf in sorted(analysis.get('signal_performance', {}).items(), 
                                   key=lambda x: x[1]['accuracy'], reverse=True):
            lines.append(f"  {signal}: {perf['count']}次, 准确率 {perf['accuracy']:.1f}%, 平均收益 {perf['avg_return']:.2f}%")
        lines.append("")
        
        best = analysis.get('best_performer')
        worst = analysis.get('worst_performer')
        if best:
            lines.append(f"【最佳表现】{best['symbol']} ({best['name']})")
            lines.append(f"  信号评分: {best['score']}, 7日收益: {best['day7_change']:.2f}%")
        if worst:
            lines.append(f"【最差表现】{worst['symbol']} ({worst['name']})")
            lines.append(f"  信号评分: {worst['score']}, 7日收益: {worst['day7_change']:.2f}%")
        lines.append("")
        
        overfitting = analysis.get('overfitting_analysis', {})
        if overfitting.get('concerns'):
            lines.append("【⚠️ 风险提示】")
            for concern in overfitting['concerns']:
                lines.append(f"  • {concern}")
            lines.append("")
        
        suggestions = analysis.get('optimization_suggestions', [])
        if suggestions:
            lines.append("【优化建议】")
            for i, sug in enumerate(suggestions, 1):
                priority_icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(sug['priority'], '⚪')
                lines.append(f"  {i}. {priority_icon} {sug['action']}")
                lines.append(f"     原因: {sug['reason']}")
            lines.append("")
        
        if adjustments:
            if adjustments.get('applied'):
                lines.append("【已应用的模型调整】")
                for adj in adjustments['applied']:
                    lines.append(f"  • {adj['param']}: {adj['old']} → {adj['new']}")
                lines.append("")
            
            if adjustments.get('skipped'):
                lines.append("【需人工处理】")
                for skip in adjustments['skipped']:
                    lines.append(f"  • {skip['suggestion']}")
                lines.append("")
        
        lines.extend([
            "=" * 70,
            f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 70
        ])
        
        return "\n".join(lines)
    
    def send_telegram(self, analysis: Dict, adjustments: Dict = None) -> bool:
        """发送Telegram通知"""
        tg_config = self.config.get('notification', {}).get('telegram', {})
        
        if not tg_config.get('enabled') or not tg_config.get('bot_token'):
            logger.info("Telegram通知未启用")
            return False
        
        notifier = TelegramNotifier(tg_config['bot_token'], tg_config['chat_id'])
        message = self.format_telegram_message(analysis, adjustments)
        return notifier.send_message(message)
    
    def run(self, auto_optimize: bool = True):
        """运行每周分析"""
        logger.info("开始每周分析...")
        
        # 1. 更新追踪数据
        self.update_tracking_data()
        
        # 2. 分析本周表现
        analysis = self.analyze_week()
        
        # 3. 自动优化模型
        adjustments = {}
        if auto_optimize:
            adjustments = self.auto_optimize_model(analysis)
        
        # 4. 生成报告
        report = self.format_analysis_report(analysis, adjustments)
        print(report)
        
        # 5. 保存报告
        report_dir = Path('/home/ubuntu/stock_screener/reports/weekly')
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_path = report_dir / f"weekly_analysis_{analysis['week_end']}.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"报告已保存: {report_path}")
        
        # 6. 发送Telegram通知
        self.send_telegram(analysis, adjustments)
        
        return analysis, adjustments


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='每周分析和模型优化')
    parser.add_argument('--no-optimize', action='store_true', help='不自动优化模型')
    parser.add_argument('--update-tracking', action='store_true', help='仅更新追踪数据')
    
    args = parser.parse_args()
    
    analyzer = WeeklyAnalyzer()
    
    if args.update_tracking:
        analyzer.update_tracking_data()
    else:
        analyzer.run(auto_optimize=not args.no_optimize)


if __name__ == '__main__':
    main()
