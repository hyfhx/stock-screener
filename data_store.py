#!/usr/bin/env python3
"""
数据持久化存储模块
- 存储每次筛选结果
- 追踪股票后续表现
- 支持历史查询和分析
"""

import sys
sys.path.append('/opt/.manus/.sandbox-runtime')

import json
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from data_api import ApiClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = '/home/ubuntu/stock_screener/data/screener.db'


class DataStore:
    """数据存储类"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 筛选结果表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS screening_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_time TIMESTAMP NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                price REAL,
                change_percent REAL,
                volume INTEGER,
                avg_volume REAL,
                signals TEXT,
                score INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 股票后续表现追踪表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                screening_id INTEGER,
                symbol TEXT NOT NULL,
                signal_date DATE NOT NULL,
                signal_price REAL,
                signal_score INTEGER,
                day1_price REAL,
                day1_change REAL,
                day3_price REAL,
                day3_change REAL,
                day5_price REAL,
                day5_change REAL,
                day7_price REAL,
                day7_change REAL,
                max_gain REAL,
                max_loss REAL,
                is_successful INTEGER,
                updated_at TIMESTAMP,
                FOREIGN KEY (screening_id) REFERENCES screening_results(id)
            )
        ''')
        
        # 每日汇总表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_date DATE UNIQUE NOT NULL,
                total_scans INTEGER,
                total_signals INTEGER,
                top_stocks TEXT,
                avg_score REAL,
                sent_email INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 模型参数历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_params_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                effective_date DATE NOT NULL,
                params TEXT NOT NULL,
                accuracy_rate REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 周分析报告表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weekly_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start DATE NOT NULL,
                week_end DATE NOT NULL,
                total_signals INTEGER,
                successful_signals INTEGER,
                accuracy_rate REAL,
                avg_return REAL,
                best_performer TEXT,
                worst_performer TEXT,
                analysis_notes TEXT,
                model_adjustments TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"数据库初始化完成: {self.db_path}")
    
    def save_screening_results(self, results: List[Dict], scan_time: datetime = None) -> int:
        """保存筛选结果"""
        if not results:
            return 0
        
        scan_time = scan_time or datetime.now()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved_count = 0
        for result in results:
            cursor.execute('''
                INSERT INTO screening_results 
                (scan_time, symbol, name, price, change_percent, volume, avg_volume, signals, score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                scan_time.isoformat(),
                result['symbol'],
                result.get('name', ''),
                result.get('price', 0),
                result.get('change_percent', 0),
                result.get('volume', 0),
                result.get('avg_volume', 0),
                json.dumps(result.get('signals', []), ensure_ascii=False),
                result.get('score', 0)
            ))
            
            # 同时创建追踪记录
            screening_id = cursor.lastrowid
            cursor.execute('''
                INSERT INTO performance_tracking 
                (screening_id, symbol, signal_date, signal_price, signal_score)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                screening_id,
                result['symbol'],
                scan_time.date().isoformat(),
                result.get('price', 0),
                result.get('score', 0)
            ))
            
            saved_count += 1
        
        conn.commit()
        conn.close()
        logger.info(f"保存了 {saved_count} 条筛选结果")
        return saved_count
    
    def get_results_by_date(self, date: datetime.date) -> List[Dict]:
        """获取指定日期的筛选结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT symbol, name, price, change_percent, volume, avg_volume, 
                   signals, MAX(score) as score, scan_time
            FROM screening_results 
            WHERE DATE(scan_time) = ?
            GROUP BY symbol
            ORDER BY score DESC
        ''', (date.isoformat(),))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'symbol': row[0],
                'name': row[1],
                'price': row[2],
                'change_percent': row[3],
                'volume': row[4],
                'avg_volume': row[5],
                'signals': json.loads(row[6]) if row[6] else [],
                'score': row[7],
                'scan_time': row[8]
            })
        
        conn.close()
        return results
    
    def get_results_by_date_range(self, start_date: datetime.date, end_date: datetime.date) -> List[Dict]:
        """获取日期范围内的筛选结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT symbol, name, price, change_percent, volume, avg_volume, 
                   signals, score, scan_time
            FROM screening_results 
            WHERE DATE(scan_time) BETWEEN ? AND ?
            ORDER BY scan_time DESC, score DESC
        ''', (start_date.isoformat(), end_date.isoformat()))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'symbol': row[0],
                'name': row[1],
                'price': row[2],
                'change_percent': row[3],
                'volume': row[4],
                'avg_volume': row[5],
                'signals': json.loads(row[6]) if row[6] else [],
                'score': row[7],
                'scan_time': row[8]
            })
        
        conn.close()
        return results
    
    def get_pending_tracking(self, days_ago: int = 7) -> List[Dict]:
        """获取需要更新追踪数据的记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days_ago)).date()
        
        cursor.execute('''
            SELECT id, symbol, signal_date, signal_price, signal_score
            FROM performance_tracking 
            WHERE signal_date >= ? AND (day7_price IS NULL OR updated_at < DATE('now', '-1 day'))
        ''', (cutoff_date.isoformat(),))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'symbol': row[1],
                'signal_date': row[2],
                'signal_price': row[3],
                'signal_score': row[4]
            })
        
        conn.close()
        return results
    
    def update_tracking(self, tracking_id: int, data: Dict):
        """更新追踪数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE performance_tracking SET
                day1_price = COALESCE(?, day1_price),
                day1_change = COALESCE(?, day1_change),
                day3_price = COALESCE(?, day3_price),
                day3_change = COALESCE(?, day3_change),
                day5_price = COALESCE(?, day5_price),
                day5_change = COALESCE(?, day5_change),
                day7_price = COALESCE(?, day7_price),
                day7_change = COALESCE(?, day7_change),
                max_gain = COALESCE(?, max_gain),
                max_loss = COALESCE(?, max_loss),
                is_successful = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            data.get('day1_price'),
            data.get('day1_change'),
            data.get('day3_price'),
            data.get('day3_change'),
            data.get('day5_price'),
            data.get('day5_change'),
            data.get('day7_price'),
            data.get('day7_change'),
            data.get('max_gain'),
            data.get('max_loss'),
            data.get('is_successful'),
            tracking_id
        ))
        
        conn.commit()
        conn.close()
    
    def save_daily_summary(self, summary_date: datetime.date, data: Dict):
        """保存每日汇总"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO daily_summary 
            (summary_date, total_scans, total_signals, top_stocks, avg_score, sent_email)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            summary_date.isoformat(),
            data.get('total_scans', 0),
            data.get('total_signals', 0),
            json.dumps(data.get('top_stocks', []), ensure_ascii=False),
            data.get('avg_score', 0),
            data.get('sent_email', 0)
        ))
        
        conn.commit()
        conn.close()
    
    def mark_email_sent(self, summary_date: datetime.date):
        """标记邮件已发送"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE daily_summary SET sent_email = 1 WHERE summary_date = ?
        ''', (summary_date.isoformat(),))
        
        conn.commit()
        conn.close()
    
    def save_weekly_analysis(self, data: Dict):
        """保存周分析报告"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO weekly_analysis 
            (week_start, week_end, total_signals, successful_signals, accuracy_rate,
             avg_return, best_performer, worst_performer, analysis_notes, model_adjustments)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['week_start'],
            data['week_end'],
            data.get('total_signals', 0),
            data.get('successful_signals', 0),
            data.get('accuracy_rate', 0),
            data.get('avg_return', 0),
            json.dumps(data.get('best_performer', {}), ensure_ascii=False),
            json.dumps(data.get('worst_performer', {}), ensure_ascii=False),
            data.get('analysis_notes', ''),
            json.dumps(data.get('model_adjustments', {}), ensure_ascii=False)
        ))
        
        conn.commit()
        conn.close()
    
    def save_model_params(self, params: Dict, accuracy_rate: float = None, notes: str = ''):
        """保存模型参数"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO model_params_history 
            (effective_date, params, accuracy_rate, notes)
            VALUES (?, ?, ?, ?)
        ''', (
            datetime.now().date().isoformat(),
            json.dumps(params, ensure_ascii=False),
            accuracy_rate,
            notes
        ))
        
        conn.commit()
        conn.close()
    
    def get_latest_model_params(self) -> Optional[Dict]:
        """获取最新模型参数"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT params FROM model_params_history 
            ORDER BY effective_date DESC, id DESC LIMIT 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None
    
    def get_tracking_stats(self, days: int = 30) -> Dict:
        """获取追踪统计数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).date()
        
        # 总体统计
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN is_successful = 1 THEN 1 ELSE 0 END) as successful,
                AVG(day7_change) as avg_return,
                AVG(max_gain) as avg_max_gain,
                AVG(max_loss) as avg_max_loss
            FROM performance_tracking 
            WHERE signal_date >= ? AND day7_change IS NOT NULL
        ''', (cutoff_date.isoformat(),))
        
        row = cursor.fetchone()
        
        stats = {
            'total_signals': row[0] or 0,
            'successful_signals': row[1] or 0,
            'accuracy_rate': (row[1] / row[0] * 100) if row[0] else 0,
            'avg_return': row[2] or 0,
            'avg_max_gain': row[3] or 0,
            'avg_max_loss': row[4] or 0
        }
        
        # 按评分分组统计
        cursor.execute('''
            SELECT 
                CASE 
                    WHEN signal_score >= 70 THEN 'high'
                    WHEN signal_score >= 40 THEN 'medium'
                    ELSE 'low'
                END as score_group,
                COUNT(*) as total,
                SUM(CASE WHEN is_successful = 1 THEN 1 ELSE 0 END) as successful,
                AVG(day7_change) as avg_return
            FROM performance_tracking 
            WHERE signal_date >= ? AND day7_change IS NOT NULL
            GROUP BY score_group
        ''', (cutoff_date.isoformat(),))
        
        stats['by_score'] = {}
        for row in cursor.fetchall():
            stats['by_score'][row[0]] = {
                'total': row[1],
                'successful': row[2],
                'accuracy': (row[2] / row[1] * 100) if row[1] else 0,
                'avg_return': row[3] or 0
            }
        
        conn.close()
        return stats


class PerformanceTracker:
    """股票表现追踪器"""
    
    def __init__(self):
        self.client = ApiClient()
        self.store = DataStore()
    
    def update_all_tracking(self):
        """更新所有待追踪的记录"""
        pending = self.store.get_pending_tracking(days_ago=14)
        logger.info(f"需要更新 {len(pending)} 条追踪记录")
        
        for record in pending:
            try:
                self._update_single_tracking(record)
            except Exception as e:
                logger.error(f"更新 {record['symbol']} 追踪数据失败: {e}")
    
    def _update_single_tracking(self, record: Dict):
        """更新单条追踪记录"""
        symbol = record['symbol']
        signal_date = datetime.strptime(record['signal_date'], '%Y-%m-%d').date()
        signal_price = record['signal_price']
        
        # 获取历史数据
        response = self.client.call_api('YahooFinance/get_stock_chart', query={
            'symbol': symbol,
            'region': 'US',
            'interval': '1d',
            'range': '1mo',
            'includeAdjustedClose': True
        })
        
        if not response or 'chart' not in response:
            return
        
        result = response['chart']['result'][0]
        timestamps = result.get('timestamp', [])
        quotes = result.get('indicators', {}).get('quote', [{}])[0]
        closes = quotes.get('close', [])
        highs = quotes.get('high', [])
        lows = quotes.get('low', [])
        
        if not timestamps or not closes:
            return
        
        # 转换时间戳为日期
        dates = [datetime.fromtimestamp(ts).date() for ts in timestamps]
        
        # 找到信号日期的索引
        signal_idx = None
        for i, d in enumerate(dates):
            if d >= signal_date:
                signal_idx = i
                break
        
        if signal_idx is None:
            return
        
        # 计算各天的表现
        data = {}
        
        # Day 1
        if signal_idx + 1 < len(closes) and closes[signal_idx + 1]:
            data['day1_price'] = closes[signal_idx + 1]
            data['day1_change'] = ((closes[signal_idx + 1] - signal_price) / signal_price) * 100
        
        # Day 3
        if signal_idx + 3 < len(closes) and closes[signal_idx + 3]:
            data['day3_price'] = closes[signal_idx + 3]
            data['day3_change'] = ((closes[signal_idx + 3] - signal_price) / signal_price) * 100
        
        # Day 5
        if signal_idx + 5 < len(closes) and closes[signal_idx + 5]:
            data['day5_price'] = closes[signal_idx + 5]
            data['day5_change'] = ((closes[signal_idx + 5] - signal_price) / signal_price) * 100
        
        # Day 7
        if signal_idx + 7 < len(closes) and closes[signal_idx + 7]:
            data['day7_price'] = closes[signal_idx + 7]
            data['day7_change'] = ((closes[signal_idx + 7] - signal_price) / signal_price) * 100
        
        # 计算最大涨幅和最大跌幅 (7天内)
        end_idx = min(signal_idx + 8, len(closes))
        period_highs = [h for h in highs[signal_idx:end_idx] if h]
        period_lows = [l for l in lows[signal_idx:end_idx] if l]
        
        if period_highs:
            max_high = max(period_highs)
            data['max_gain'] = ((max_high - signal_price) / signal_price) * 100
        
        if period_lows:
            min_low = min(period_lows)
            data['max_loss'] = ((min_low - signal_price) / signal_price) * 100
        
        # 判断是否成功 (7天内涨幅超过3%视为成功)
        if 'day7_change' in data:
            data['is_successful'] = 1 if data['day7_change'] >= 3 else 0
        elif 'max_gain' in data:
            data['is_successful'] = 1 if data['max_gain'] >= 5 else 0
        
        # 更新数据库
        self.store.update_tracking(record['id'], data)
        logger.info(f"更新 {symbol} 追踪数据: day7_change={data.get('day7_change', 'N/A'):.2f}%")


if __name__ == '__main__':
    # 测试
    store = DataStore()
    print("数据库初始化完成")
    
    # 测试保存结果
    test_results = [
        {
            'symbol': 'TEST',
            'name': 'Test Stock',
            'price': 100.0,
            'change_percent': 2.5,
            'volume': 1000000,
            'avg_volume': 800000,
            'signals': ['测试信号1', '测试信号2'],
            'score': 75
        }
    ]
    store.save_screening_results(test_results)
    print("测试数据保存成功")
