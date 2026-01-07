#!/usr/bin/env python3
"""
股票筛选盯盘程序 V2 - 支持全美股和运行时间追踪
功能：
- 支持11000+只美股筛选
- 运行时间追踪和监控
- 批量并行处理优化
- 自动性能报告
"""

import sys
sys.path.append('/opt/.manus/.sandbox-runtime')

import json
import time
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import threading

from data_api import ApiClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/stock_screener/screener.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class StockSignal:
    """股票信号数据类"""
    symbol: str
    name: str
    current_price: float
    change_percent: float
    volume: int
    avg_volume: float
    signals: List[str]
    score: int
    timestamp: datetime


@dataclass
class RunTimeStats:
    """运行时间统计"""
    start_time: datetime
    end_time: datetime = None
    total_stocks: int = 0
    processed_stocks: int = 0
    successful_stocks: int = 0
    failed_stocks: int = 0
    signals_found: int = 0
    high_score_count: int = 0
    avg_time_per_stock: float = 0
    total_runtime_seconds: float = 0
    
    def to_dict(self):
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'total_stocks': self.total_stocks,
            'processed_stocks': self.processed_stocks,
            'successful_stocks': self.successful_stocks,
            'failed_stocks': self.failed_stocks,
            'signals_found': self.signals_found,
            'high_score_count': self.high_score_count,
            'avg_time_per_stock_ms': round(self.avg_time_per_stock * 1000, 2),
            'total_runtime_seconds': round(self.total_runtime_seconds, 2),
            'total_runtime_minutes': round(self.total_runtime_seconds / 60, 2)
        }


class TechnicalIndicators:
    """技术指标计算类"""
    
    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> List[float]:
        if len(prices) < period:
            return []
        sma = []
        for i in range(period - 1, len(prices)):
            avg = sum(prices[i - period + 1:i + 1]) / period
            sma.append(avg)
        return sma
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> List[float]:
        if len(prices) < period:
            return []
        multiplier = 2 / (period + 1)
        ema = [sum(prices[:period]) / period]
        for price in prices[period:]:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
        return ema
    
    @staticmethod
    def calculate_macd(prices: List[float]) -> Tuple[List[float], List[float], List[float]]:
        if len(prices) < 26:
            return [], [], []
        ema12 = TechnicalIndicators.calculate_ema(prices, 12)
        ema26 = TechnicalIndicators.calculate_ema(prices, 26)
        diff = len(ema12) - len(ema26)
        ema12 = ema12[diff:]
        macd_line = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
        if len(macd_line) >= 9:
            signal_line = TechnicalIndicators.calculate_ema(macd_line, 9)
            macd_line = macd_line[-(len(signal_line)):]
            histogram = [m - s for m, s in zip(macd_line, signal_line)]
        else:
            signal_line = []
            histogram = []
        return macd_line, signal_line, histogram
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
        if len(prices) < period + 1:
            return []
        rsi_values = []
        for i in range(period, len(prices)):
            gains = []
            losses = []
            for j in range(i - period + 1, i + 1):
                change = prices[j] - prices[j - 1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            avg_gain = sum(gains) / period
            avg_loss = sum(losses) / period
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            rsi_values.append(rsi)
        return rsi_values
    
    @staticmethod
    def calculate_obv(prices: List[float], volumes: List[int]) -> List[float]:
        if len(prices) != len(volumes) or len(prices) < 2:
            return []
        obv = [0]
        for i in range(1, len(prices)):
            if prices[i] > prices[i - 1]:
                obv.append(obv[-1] + volumes[i])
            elif prices[i] < prices[i - 1]:
                obv.append(obv[-1] - volumes[i])
            else:
                obv.append(obv[-1])
        return obv


class StockScreenerV2:
    """股票筛选器V2 - 支持大规模筛选和时间追踪"""
    
    def __init__(self, config: Dict = None, max_workers: int = 10):
        self.client = ApiClient()
        self.indicators = TechnicalIndicators()
        self.config = config or self._default_config()
        self.max_workers = max_workers
        self.stats = None
        self._lock = threading.Lock()
        self._processed_count = 0
        self._failed_count = 0
    
    def _default_config(self) -> Dict:
        return {
            'min_price': 5.0,
            'max_price': 500.0,
            'min_volume': 500000,
            'volume_surge_ratio': 1.5,
            'ma_short': 20,
            'ma_long': 50,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'weights': {
                'ma_golden_cross': 25,
                'macd_golden_cross': 20,
                'rsi_bullish': 15,
                'volume_surge': 15,
                'price_breakout': 15,
                'obv_confirm': 10
            }
        }
    
    def get_stock_data(self, symbol: str) -> Optional[Dict]:
        """获取股票历史数据"""
        try:
            response = self.client.call_api('YahooFinance/get_stock_chart', query={
                'symbol': symbol,
                'region': 'US',
                'interval': '1d',
                'range': '3mo',
                'includeAdjustedClose': True
            })
            if response and 'chart' in response and 'result' in response['chart']:
                return response['chart']['result'][0]
            return None
        except Exception as e:
            return None
    
    def analyze_stock(self, symbol: str) -> Optional[StockSignal]:
        """分析单只股票"""
        data = self.get_stock_data(symbol)
        if not data:
            return None
        
        try:
            meta = data.get('meta', {})
            quotes = data.get('indicators', {}).get('quote', [{}])[0]
            
            closes = [c for c in quotes.get('close', []) if c is not None]
            volumes = [v for v in quotes.get('volume', []) if v is not None]
            highs = [h for h in quotes.get('high', []) if h is not None]
            
            if len(closes) < 50:
                return None
            
            current_price = meta.get('regularMarketPrice', closes[-1])
            name = meta.get('shortName', meta.get('longName', symbol))
            
            # 基本筛选
            if current_price < self.config['min_price'] or current_price > self.config['max_price']:
                return None
            
            avg_volume = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else sum(volumes) / len(volumes)
            if avg_volume < self.config['min_volume']:
                return None
            
            # 计算技术指标
            signals = []
            score = 0
            
            # 1. 移动平均线
            ma_short = self.indicators.calculate_sma(closes, self.config['ma_short'])
            ma_long = self.indicators.calculate_sma(closes, self.config['ma_long'])
            
            if ma_short and ma_long and len(ma_short) >= 2 and len(ma_long) >= 2:
                offset = len(ma_short) - len(ma_long)
                ma_short_aligned = ma_short[offset:] if offset > 0 else ma_short
                ma_long_aligned = ma_long[-len(ma_short_aligned):] if offset < 0 else ma_long
                
                if len(ma_short_aligned) >= 2 and len(ma_long_aligned) >= 2:
                    if (ma_short_aligned[-1] > ma_long_aligned[-1] and 
                        ma_short_aligned[-2] <= ma_long_aligned[-2]):
                        signals.append(f"🔥 MA金叉")
                        score += self.config['weights']['ma_golden_cross']
                    elif (ma_short_aligned[-1] > ma_long_aligned[-1] and 
                          ma_short_aligned[-1] > ma_short_aligned[-2]):
                        signals.append(f"📈 价格在MA{self.config['ma_long']}上方")
                        score += self.config['weights']['ma_golden_cross'] // 2
            
            # 2. MACD
            macd_line, signal_line, histogram = self.indicators.calculate_macd(closes)
            if macd_line and signal_line and len(macd_line) >= 2:
                if macd_line[-1] > signal_line[-1] and macd_line[-2] <= signal_line[-2]:
                    signals.append("🔥 MACD金叉")
                    score += self.config['weights']['macd_golden_cross']
                elif macd_line[-1] > 0 and macd_line[-1] > signal_line[-1]:
                    signals.append("📊 MACD多头排列")
                    score += self.config['weights']['macd_golden_cross'] // 2
            
            # 3. RSI
            rsi = self.indicators.calculate_rsi(closes)
            if rsi and len(rsi) >= 2:
                current_rsi = rsi[-1]
                prev_rsi = rsi[-2]
                if prev_rsi < self.config['rsi_oversold'] and current_rsi > prev_rsi:
                    signals.append(f"📈 RSI从超卖区反弹 ({current_rsi:.1f})")
                    score += self.config['weights']['rsi_bullish']
                elif 40 < current_rsi < 60 and current_rsi > prev_rsi:
                    signals.append(f"📊 RSI突破50 ({current_rsi:.1f})")
                    score += self.config['weights']['rsi_bullish'] // 2
                elif 50 <= current_rsi <= 70:
                    signals.append(f"✅ RSI健康 ({current_rsi:.1f})")
                    score += 5
            
            # 4. 成交量
            if volumes:
                current_volume = volumes[-1]
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
                if volume_ratio >= self.config['volume_surge_ratio']:
                    signals.append(f"🔥 成交量放大 {volume_ratio:.1f}倍")
                    score += self.config['weights']['volume_surge']
                elif volume_ratio >= 1.2:
                    signals.append(f"📊 成交量温和放大 {volume_ratio:.1f}倍")
                    score += self.config['weights']['volume_surge'] // 2
            
            # 5. 价格突破
            if highs and len(highs) >= 20:
                high_20d = max(highs[-20:])
                if current_price >= high_20d * 0.98:
                    signals.append("🔥 突破/接近20日高点")
                    score += self.config['weights']['price_breakout']
                
                # 52周新高
                if len(highs) >= 250:
                    high_52w = max(highs[-250:])
                else:
                    high_52w = max(highs)
                
                ratio_52w = current_price / high_52w if high_52w > 0 else 0
                if ratio_52w >= 0.95:
                    signals.append(f"🔥 接近52周新高 ({ratio_52w*100:.1f}%)")
                    score += 10
                elif ratio_52w >= 0.85:
                    signals.append(f"📈 距52周高点 {(1-ratio_52w)*100:.1f}%")
            
            # 6. OBV
            obv = self.indicators.calculate_obv(closes, volumes)
            if obv and len(obv) >= 10:
                obv_sma = sum(obv[-10:]) / 10
                if obv[-1] > obv_sma and obv[-1] > obv[-2]:
                    signals.append("📊 OBV上升确认")
                    score += self.config['weights']['obv_confirm']
            
            # 只返回有信号的股票
            if signals and score >= 20:
                prev_close = closes[-2] if len(closes) >= 2 else current_price
                change_percent = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
                
                return StockSignal(
                    symbol=symbol,
                    name=name[:30] if name else symbol,
                    current_price=current_price,
                    change_percent=change_percent,
                    volume=volumes[-1] if volumes else 0,
                    avg_volume=avg_volume,
                    signals=signals,
                    score=score,
                    timestamp=datetime.now()
                )
            
            return None
            
        except Exception as e:
            return None
    
    def _analyze_with_tracking(self, symbol: str) -> Optional[StockSignal]:
        """带追踪的分析"""
        result = self.analyze_stock(symbol)
        with self._lock:
            self._processed_count += 1
            if result is None:
                self._failed_count += 1
        return result
    
    def screen_stocks(self, symbols: List[str], progress_callback=None) -> Tuple[List[StockSignal], RunTimeStats]:
        """批量筛选股票（带时间追踪）"""
        self.stats = RunTimeStats(
            start_time=datetime.now(),
            total_stocks=len(symbols)
        )
        self._processed_count = 0
        self._failed_count = 0
        
        results = []
        start_time = time.time()
        
        logger.info(f"开始筛选 {len(symbols)} 只股票...")
        
        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._analyze_with_tracking, symbol): symbol 
                      for symbol in symbols}
            
            for i, future in enumerate(as_completed(futures)):
                symbol = futures[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        logger.info(f"✅ {result.symbol} 发现信号! 评分: {result.score}")
                except Exception as e:
                    logger.error(f"处理 {symbol} 时出错: {e}")
                
                # 进度报告
                if (i + 1) % 100 == 0 or i == len(symbols) - 1:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    remaining = (len(symbols) - i - 1) / rate if rate > 0 else 0
                    logger.info(f"进度: {i+1}/{len(symbols)} ({(i+1)/len(symbols)*100:.1f}%) "
                               f"| 速度: {rate:.1f}只/秒 | 预计剩余: {remaining:.0f}秒")
                    
                    if progress_callback:
                        progress_callback(i + 1, len(symbols), len(results))
        
        # 更新统计
        end_time = time.time()
        self.stats.end_time = datetime.now()
        self.stats.processed_stocks = self._processed_count
        self.stats.successful_stocks = self._processed_count - self._failed_count
        self.stats.failed_stocks = self._failed_count
        self.stats.signals_found = len(results)
        self.stats.high_score_count = len([r for r in results if r.score >= 70])
        self.stats.total_runtime_seconds = end_time - start_time
        self.stats.avg_time_per_stock = self.stats.total_runtime_seconds / len(symbols) if symbols else 0
        
        # 按评分排序
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results, self.stats


class TelegramNotifier:
    """Telegram通知"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
    
    def send_message(self, text: str) -> bool:
        try:
            max_length = 4000
            messages = [text[i:i+max_length] for i in range(0, len(text), max_length)]
            for msg in messages:
                response = requests.post(
                    f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    json={'chat_id': self.chat_id, 'text': msg, 'parse_mode': 'HTML'}
                )
                if response.status_code != 200:
                    return False
            return True
        except:
            return False


def load_stock_list(path: str) -> List[str]:
    """加载股票列表"""
    symbols = []
    try:
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    symbols.append(line.upper())
    except:
        pass
    return symbols


def load_config() -> Dict:
    """加载配置"""
    try:
        with open('/home/ubuntu/stock_screener/config.json', 'r') as f:
            return json.load(f)
    except:
        return {}


def format_runtime_report(stats: RunTimeStats) -> str:
    """格式化运行时间报告"""
    lines = [
        "=" * 50,
        "⏱️ 运行时间报告",
        "=" * 50,
        f"开始时间: {stats.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"结束时间: {stats.end_time.strftime('%Y-%m-%d %H:%M:%S') if stats.end_time else 'N/A'}",
        f"总耗时: {stats.total_runtime_seconds:.1f}秒 ({stats.total_runtime_seconds/60:.1f}分钟)",
        "",
        f"总股票数: {stats.total_stocks}",
        f"成功处理: {stats.successful_stocks}",
        f"处理失败: {stats.failed_stocks}",
        f"平均每只: {stats.avg_time_per_stock*1000:.0f}ms",
        "",
        f"发现信号: {stats.signals_found} 只",
        f"高分股票(≥70): {stats.high_score_count} 只",
        "=" * 50
    ]
    return "\n".join(lines)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='股票筛选程序V2')
    parser.add_argument('--all', action='store_true', help='筛选全美股')
    parser.add_argument('--symbols', nargs='+', help='指定股票代码')
    parser.add_argument('--watchlist', type=str, help='股票列表文件')
    parser.add_argument('--workers', type=int, default=10, help='并行线程数')
    parser.add_argument('--limit', type=int, help='限制筛选数量（测试用）')
    
    args = parser.parse_args()
    
    # 确定股票列表
    if args.symbols:
        symbols = [s.upper() for s in args.symbols]
    elif args.all:
        symbols = load_stock_list('/home/ubuntu/stock_screener/all_us_stocks.txt')
    elif args.watchlist:
        symbols = load_stock_list(args.watchlist)
    else:
        # 默认使用全美股
        symbols = load_stock_list('/home/ubuntu/stock_screener/all_us_stocks.txt')
        if not symbols:
            # 回退到默认列表
            symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'AMD', 'MU', 'QCOM']
    
    if args.limit:
        symbols = symbols[:args.limit]
    
    logger.info(f"准备筛选 {len(symbols)} 只股票")
    
    # 创建筛选器
    screener = StockScreenerV2(max_workers=args.workers)
    
    # 执行筛选
    results, stats = screener.screen_stocks(symbols)
    
    # 打印运行时间报告
    print(format_runtime_report(stats))
    
    # 保存运行时间统计
    stats_path = '/home/ubuntu/stock_screener/runtime_stats.json'
    with open(stats_path, 'w') as f:
        json.dump(stats.to_dict(), f, indent=2)
    logger.info(f"运行时间统计已保存: {stats_path}")
    
    # 打印结果
    if results:
        print(f"\n发现 {len(results)} 只潜力股:\n")
        for i, r in enumerate(results[:20], 1):
            print(f"{i}. {r.symbol} ({r.name}) - 评分: {r.score}")
            print(f"   价格: ${r.current_price:.2f} ({r.change_percent:+.2f}%)")
            print(f"   信号: {' | '.join(r.signals[:3])}")
            print()
    
    # 保存完整报告
    report_path = '/home/ubuntu/stock_screener/report_v2.json'
    with open(report_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'stats': stats.to_dict(),
            'results': [asdict(r) for r in results]
        }, f, indent=2, default=str)
    logger.info(f"完整报告已保存: {report_path}")
    
    # 发送Telegram通知（如果耗时过长）
    config = load_config()
    tg_config = config.get('notification', {}).get('telegram', {})
    
    if tg_config.get('enabled') and tg_config.get('bot_token'):
        notifier = TelegramNotifier(tg_config['bot_token'], tg_config['chat_id'])
        
        # 如果耗时超过30分钟，发送警告
        if stats.total_runtime_seconds > 1800:
            warning_msg = f"""⚠️ <b>运行时间警告</b>

筛选 {stats.total_stocks} 只股票耗时 <b>{stats.total_runtime_seconds/60:.1f}分钟</b>

建议考虑缩小股票池或增加筛选间隔。

发现信号: {stats.signals_found} 只
高分股票: {stats.high_score_count} 只"""
            notifier.send_message(warning_msg)
        
        # 发送高分股票通知
        high_score = [r for r in results if r.score >= 70]
        if high_score:
            msg_lines = [f"🔥 <b>发现 {len(high_score)} 只高分股票</b>\n"]
            for r in high_score[:10]:
                msg_lines.append(f"<b>{r.symbol}</b> - 评分: {r.score}")
                msg_lines.append(f"💰 ${r.current_price:.2f} ({r.change_percent:+.2f}%)")
                msg_lines.append(f"📌 {r.signals[0] if r.signals else ''}\n")
            
            msg_lines.append(f"\n⏱️ 筛选耗时: {stats.total_runtime_seconds/60:.1f}分钟")
            notifier.send_message("\n".join(msg_lines))
    
    return results, stats


if __name__ == '__main__':
    main()
