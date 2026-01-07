#!/usr/bin/env python3
"""
股票筛选系统 - 本地独立运行版本
无需依赖外部API，使用yfinance获取数据

使用方法:
    python3 screener_local.py                    # 运行筛选
    python3 screener_local.py --config config.json  # 指定配置文件
"""

import os
import sys
import json
import argparse
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time

# 尝试导入依赖
try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
except ImportError as e:
    print(f"缺少依赖: {e}")
    print("请运行: pip3 install yfinance pandas numpy")
    sys.exit(1)

try:
    import requests
except ImportError:
    requests = None


class StockScreener:
    """股票筛选器"""
    
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.weights = self.config.get('weights', {})
        self.screening = self.config.get('screening', {})
        
        # 默认参数
        self.min_score = self.screening.get('min_score', 40)
        self.min_price = self.screening.get('min_price', 5.0)
        self.max_price = self.screening.get('max_price', 1000.0)
        self.min_volume = self.screening.get('min_volume', 500000)
        
        # 结果存储
        self.results = []
        self.failed = []
        self.start_time = None
        
    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        default_config = {
            "screening": {
                "min_price": 5.0,
                "max_price": 1000.0,
                "min_volume": 500000,
                "min_score": 40
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
                    "enabled": False,
                    "bot_token": "",
                    "chat_id": ""
                }
            }
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    # 合并配置
                    for key in user_config:
                        if key in default_config and isinstance(default_config[key], dict):
                            default_config[key].update(user_config[key])
                        else:
                            default_config[key] = user_config[key]
            except Exception as e:
                print(f"⚠ 加载配置文件失败: {e}")
        
        return default_config
    
    def get_stock_data(self, symbol: str, period: str = "6mo") -> Optional[pd.DataFrame]:
        """获取股票数据"""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)
            if df.empty or len(df) < 50:
                return None
            return df
        except Exception as e:
            return None
    
    def calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """计算技术指标"""
        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume']
        
        # 移动平均线
        ma20 = close.rolling(window=20).mean()
        ma50 = close.rolling(window=50).mean()
        
        # MACD
        exp12 = close.ewm(span=12, adjust=False).mean()
        exp26 = close.ewm(span=26, adjust=False).mean()
        macd = exp12 - exp26
        signal = macd.ewm(span=9, adjust=False).mean()
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # 成交量均值
        vol_ma20 = volume.rolling(window=20).mean()
        
        # OBV
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        obv_ma20 = obv.rolling(window=20).mean()
        
        # 52周高点
        high_52w = high.rolling(window=252, min_periods=50).max()
        
        # 20日高点
        high_20d = high.rolling(window=20).max()
        
        return {
            'close': close.iloc[-1],
            'ma20': ma20.iloc[-1],
            'ma50': ma50.iloc[-1],
            'ma20_prev': ma20.iloc[-2] if len(ma20) > 1 else ma20.iloc[-1],
            'ma50_prev': ma50.iloc[-2] if len(ma50) > 1 else ma50.iloc[-1],
            'macd': macd.iloc[-1],
            'macd_signal': signal.iloc[-1],
            'macd_prev': macd.iloc[-2] if len(macd) > 1 else macd.iloc[-1],
            'macd_signal_prev': signal.iloc[-2] if len(signal) > 1 else signal.iloc[-1],
            'rsi': rsi.iloc[-1],
            'rsi_prev': rsi.iloc[-2] if len(rsi) > 1 else rsi.iloc[-1],
            'volume': volume.iloc[-1],
            'vol_ma20': vol_ma20.iloc[-1],
            'obv': obv.iloc[-1],
            'obv_ma20': obv_ma20.iloc[-1],
            'high_52w': high_52w.iloc[-1],
            'high_20d': high_20d.iloc[-1],
            'change_pct': (close.iloc[-1] / close.iloc[-2] - 1) * 100 if len(close) > 1 else 0,
            # 趋势判断
            'trend_up_3d': all(close.iloc[-i] > close.iloc[-i-1] for i in range(1, min(4, len(close)))),
        }
    
    def analyze_stock(self, symbol: str) -> Optional[Dict]:
        """分析单只股票"""
        df = self.get_stock_data(symbol)
        if df is None:
            return None
        
        try:
            indicators = self.calculate_indicators(df)
        except Exception as e:
            return None
        
        close = indicators['close']
        
        # 基本过滤
        if close < self.min_price or close > self.max_price:
            return None
        if indicators['volume'] < self.min_volume:
            return None
        
        # 计算信号和评分
        signals = []
        score = 0
        
        # 1. MA金叉
        if (indicators['ma20'] > indicators['ma50'] and 
            indicators['ma20_prev'] <= indicators['ma50_prev']):
            signals.append("MA金叉")
            score += self.weights.get('ma_golden_cross', 30)
        elif indicators['ma20'] > indicators['ma50']:
            signals.append("MA多头")
            score += self.weights.get('ma_golden_cross', 30) // 2
        
        # 2. MACD金叉
        if (indicators['macd'] > indicators['macd_signal'] and 
            indicators['macd_prev'] <= indicators['macd_signal_prev']):
            signals.append("MACD金叉")
            score += self.weights.get('macd_golden_cross', 25)
        elif indicators['macd'] > indicators['macd_signal']:
            signals.append("MACD多头")
            score += self.weights.get('macd_golden_cross', 25) // 2
        
        # 3. RSI反弹
        if indicators['rsi_prev'] < 30 and indicators['rsi'] > 30:
            signals.append("RSI反弹")
            score += self.weights.get('rsi_reversal', 20)
        elif 30 <= indicators['rsi'] <= 70:
            score += 5  # RSI健康区间
        
        # 4. 成交量放大
        if indicators['vol_ma20'] > 0:
            vol_ratio = indicators['volume'] / indicators['vol_ma20']
            if vol_ratio > 1.8:
                signals.append(f"成交量放大{vol_ratio:.1f}倍")
                score += self.weights.get('volume_surge', 15)
        
        # 5. 52周高点突破
        if indicators['high_52w'] > 0:
            pct_of_52w = close / indicators['high_52w'] * 100
            if pct_of_52w >= 98:
                signals.append(f"接近52周新高({pct_of_52w:.1f}%)")
                score += self.weights.get('price_breakout_52w', 20)
        
        # 6. 20日高点突破
        if close >= indicators['high_20d'] * 0.98:
            signals.append("突破20日高点")
            score += self.weights.get('price_breakout_20d', 10)
        
        # 7. 趋势持续
        if indicators['trend_up_3d']:
            signals.append("连续上涨")
            score += self.weights.get('trend_continuation', 15)
        
        # 8. OBV确认
        if indicators['obv'] > indicators['obv_ma20']:
            signals.append("OBV确认")
            score += self.weights.get('obv_confirm', 10)
        
        # 过滤低分
        if score < self.min_score:
            return None
        
        # 信号质量分级
        if score >= 70:
            quality = "A"
        elif score >= 50:
            quality = "B"
        else:
            quality = "C"
        
        return {
            'symbol': symbol,
            'price': round(close, 2),
            'change_pct': round(indicators['change_pct'], 2),
            'score': score,
            'quality': quality,
            'signals': signals,
            'rsi': round(indicators['rsi'], 1),
            'volume_ratio': round(indicators['volume'] / indicators['vol_ma20'], 2) if indicators['vol_ma20'] > 0 else 0,
        }
    
    def load_stock_list(self, file_path: str = None) -> List[str]:
        """加载股票列表"""
        # 默认股票列表
        default_stocks = [
            # 科技巨头
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
            # 半导体
            "AVGO", "QCOM", "AMD", "INTC", "MU", "MRVL", "AMAT", "LRCX", "TSM", "ARM",
            # 软件/云
            "CRM", "NOW", "PANW", "CRWD", "NET", "DDOG", "SNOW", "ADBE", "ORCL",
            # AI相关
            "SMCI", "DELL", "IBM", "PLTR",
            # 金融
            "JPM", "BAC", "GS", "V", "MA", "BLK",
            # 医疗
            "UNH", "JNJ", "LLY", "ABBV", "MRK", "AMGN",
            # 消费
            "WMT", "COST", "HD", "NKE", "SBUX", "MCD", "DIS", "NFLX",
            # 工业
            "CAT", "BA", "HON", "UPS", "GE",
            # 能源
            "XOM", "CVX", "COP",
            # 热门成长股
            "COIN", "SQ", "SHOP", "ROKU", "UBER", "ABNB"
        ]
        
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    stocks = []
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            stocks.append(line.upper())
                    if stocks:
                        return stocks
            except Exception as e:
                print(f"⚠ 加载股票列表失败: {e}")
        
        return default_stocks
    
    def run(self, stock_list: List[str] = None) -> List[Dict]:
        """运行筛选"""
        self.start_time = time.time()
        
        if stock_list is None:
            stock_list = self.load_stock_list()
        
        print(f"\n📊 开始筛选 {len(stock_list)} 只股票...")
        print("=" * 50)
        
        self.results = []
        self.failed = []
        
        for i, symbol in enumerate(stock_list, 1):
            if i % 10 == 0:
                print(f"进度: {i}/{len(stock_list)} ({i*100//len(stock_list)}%)")
            
            result = self.analyze_stock(symbol)
            if result:
                self.results.append(result)
            else:
                self.failed.append(symbol)
            
            # 避免请求过快
            time.sleep(0.1)
        
        # 按评分排序
        self.results.sort(key=lambda x: x['score'], reverse=True)
        
        elapsed = time.time() - self.start_time
        print("=" * 50)
        print(f"✓ 筛选完成! 耗时: {elapsed:.1f}秒")
        print(f"  发现潜力股: {len(self.results)} 只")
        print(f"  数据获取失败: {len(self.failed)} 只")
        
        return self.results
    
    def print_results(self):
        """打印结果"""
        if not self.results:
            print("\n未发现符合条件的股票")
            return
        
        print("\n" + "=" * 70)
        print("📈 筛选结果")
        print("=" * 70)
        
        # 高分股票
        high_score = [r for r in self.results if r['score'] >= 70]
        if high_score:
            print(f"\n🔥 高分股票 (评分≥70): {len(high_score)} 只")
            print("-" * 70)
            print(f"{'股票':<8} {'价格':>10} {'涨跌':>8} {'评分':>6} {'质量':>4} {'信号'}")
            print("-" * 70)
            for r in high_score:
                signals_str = ", ".join(r['signals'][:3])
                print(f"{r['symbol']:<8} ${r['price']:>8.2f} {r['change_pct']:>+7.2f}% {r['score']:>5} {r['quality']:>4} {signals_str}")
        
        # 中分股票
        mid_score = [r for r in self.results if 50 <= r['score'] < 70]
        if mid_score:
            print(f"\n⭐ 中分股票 (50-69): {len(mid_score)} 只")
            print("-" * 70)
            for r in mid_score[:10]:  # 最多显示10只
                signals_str = ", ".join(r['signals'][:2])
                print(f"{r['symbol']:<8} ${r['price']:>8.2f} {r['change_pct']:>+7.2f}% {r['score']:>5} {r['quality']:>4} {signals_str}")
        
        print("\n" + "=" * 70)
    
    def save_results(self, output_dir: str = None):
        """保存结果到文件"""
        if output_dir is None:
            output_dir = os.path.dirname(os.path.abspath(__file__))
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = output_dir / f"report_{timestamp}.json"
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_scanned': len(self.results) + len(self.failed),
            'found': len(self.results),
            'failed': len(self.failed),
            'elapsed_seconds': time.time() - self.start_time if self.start_time else 0,
            'results': self.results
        }
        
        with open(json_path, 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📁 报告已保存: {json_path}")
        
        return json_path
    
    def send_telegram(self, results: List[Dict] = None):
        """发送Telegram通知"""
        if requests is None:
            print("⚠ 未安装requests库，无法发送Telegram通知")
            return
        
        telegram_config = self.config.get('notification', {}).get('telegram', {})
        if not telegram_config.get('enabled'):
            return
        
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('chat_id')
        
        if not bot_token or not chat_id:
            print("⚠ Telegram配置不完整")
            return
        
        if results is None:
            results = self.results
        
        # 构建消息
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        msg = f"📊 *股票筛选报告*\n"
        msg += f"🕐 {now}\n\n"
        
        high_score = [r for r in results if r['score'] >= 70]
        if high_score:
            msg += f"🔥 *高分股票* ({len(high_score)}只)\n"
            for r in high_score[:5]:
                signals = ", ".join(r['signals'][:2])
                msg += f"• *{r['symbol']}* ${r['price']} ({r['change_pct']:+.1f}%) - {r['score']}分\n"
                msg += f"  {signals}\n"
        else:
            msg += "今日无高分股票\n"
        
        msg += f"\n共发现 {len(results)} 只潜力股"
        
        # 发送
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': msg,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                print("✓ Telegram通知已发送")
            else:
                print(f"⚠ Telegram发送失败: {response.text}")
        except Exception as e:
            print(f"⚠ Telegram发送异常: {e}")


def main():
    parser = argparse.ArgumentParser(description='股票筛选系统')
    parser.add_argument('--config', '-c', type=str, help='配置文件路径')
    parser.add_argument('--stocks', '-s', type=str, help='股票列表文件路径')
    parser.add_argument('--output', '-o', type=str, help='输出目录')
    parser.add_argument('--no-notify', action='store_true', help='不发送通知')
    
    args = parser.parse_args()
    
    # 创建筛选器
    screener = StockScreener(config_path=args.config)
    
    # 加载股票列表
    stock_list = None
    if args.stocks:
        stock_list = screener.load_stock_list(args.stocks)
    
    # 运行筛选
    results = screener.run(stock_list)
    
    # 打印结果
    screener.print_results()
    
    # 保存结果
    screener.save_results(args.output)
    
    # 发送通知
    if not args.no_notify:
        screener.send_telegram()


if __name__ == '__main__':
    main()
