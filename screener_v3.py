#!/usr/bin/env python3
"""
股票筛选盯盘程序 V3 - 降噪优化版
优化点：
1. 提高入选门槛（评分≥40）
2. 增加趋势持续性检测
3. 强化强信号，弱化弱信号
4. 添加信号稳定性指标
5. 多日确认机制
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
    trend_strength: str  # 新增：趋势强度
    signal_quality: str  # 新增：信号质量
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


class StockScreenerV3:
    """股票筛选器V3 - 降噪优化版"""
    
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
            # 基本筛选参数
            'min_price': 5.0,
            'max_price': 1000.0,
            'min_volume': 500000,
            'min_avg_volume': 1000000,  # 新增：最低日均成交量
            
            # 降噪参数
            'min_score': 40,            # 最低入选分数（提高门槛）
            'volume_surge_ratio': 1.8,  # 成交量放大倍数（提高阈值）
            'trend_confirm_days': 3,    # 趋势确认天数
            
            # 技术指标参数
            'ma_short': 20,
            'ma_long': 50,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            
            # 评分权重（强化强信号）
            'weights': {
                'ma_golden_cross': 30,       # 金叉权重提高
                'macd_golden_cross': 25,     # MACD金叉权重提高
                'rsi_reversal': 20,          # RSI反转（从超卖区）
                'volume_surge': 15,          # 成交量放大
                'price_breakout_52w': 20,    # 52周新高突破
                'price_breakout_20d': 10,    # 20日新高
                'trend_continuation': 15,    # 趋势延续
                'obv_confirm': 10            # OBV确认
            },
            
            # 弱信号权重（降低或移除）
            'weak_signals': {
                'rsi_healthy': 0,            # 移除"RSI健康"这种弱信号
                'price_above_ma': 5,         # 降低"价格在MA上方"权重
                'volume_mild': 0,            # 移除"成交量温和放大"
            }
        }
    
    def get_stock_data(self, symbol: str) -> Optional[Dict]:
        """获取股票历史数据"""
        try:
            response = self.client.call_api('YahooFinance/get_stock_chart', query={
                'symbol': symbol,
                'region': 'US',
                'interval': '1d',
                'range': '6mo',  # 获取更多数据用于趋势分析
                'includeAdjustedClose': True
            })
            if response and 'chart' in response and 'result' in response['chart']:
                return response['chart']['result'][0]
            return None
        except Exception as e:
            return None
    
    def check_trend_strength(self, closes: List[float], days: int = 5) -> Tuple[str, int]:
        """
        检查趋势强度
        返回: (趋势描述, 额外分数)
        """
        if len(closes) < days + 1:
            return "数据不足", 0
        
        recent = closes[-(days+1):]
        up_days = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i-1])
        
        # 计算涨幅
        total_change = (recent[-1] - recent[0]) / recent[0] * 100 if recent[0] > 0 else 0
        
        if up_days >= days - 1 and total_change > 3:
            return "强势上涨", 15
        elif up_days >= days - 1 and total_change > 0:
            return "稳步上涨", 10
        elif up_days >= days // 2 + 1:
            return "温和上涨", 5
        elif up_days <= 1:
            return "持续下跌", -10
        else:
            return "震荡", 0
    
    def check_signal_quality(self, signals: List[str], score: int) -> str:
        """评估信号质量"""
        strong_signals = ['金叉', '52周新高', '成交量放大']
        strong_count = sum(1 for s in signals if any(ss in s for ss in strong_signals))
        
        if strong_count >= 2 and score >= 70:
            return "A级（强烈）"
        elif strong_count >= 1 and score >= 50:
            return "B级（较强）"
        elif score >= 40:
            return "C级（一般）"
        else:
            return "D级（弱）"
    
    def analyze_stock(self, symbol: str) -> Optional[StockSignal]:
        """分析单只股票（降噪版）"""
        data = self.get_stock_data(symbol)
        if not data:
            return None
        
        try:
            meta = data.get('meta', {})
            quotes = data.get('indicators', {}).get('quote', [{}])[0]
            
            closes = [c for c in quotes.get('close', []) if c is not None]
            volumes = [v for v in quotes.get('volume', []) if v is not None]
            highs = [h for h in quotes.get('high', []) if h is not None]
            
            if len(closes) < 60:  # 需要更多数据
                return None
            
            current_price = meta.get('regularMarketPrice', closes[-1])
            name = meta.get('shortName', meta.get('longName', symbol))
            
            # 基本筛选
            if current_price < self.config['min_price'] or current_price > self.config['max_price']:
                return None
            
            avg_volume = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else sum(volumes) / len(volumes)
            if avg_volume < self.config['min_avg_volume']:
                return None
            
            # 计算技术指标
            signals = []
            score = 0
            
            # 1. 移动平均线金叉检测（强信号）
            ma_short = self.indicators.calculate_sma(closes, self.config['ma_short'])
            ma_long = self.indicators.calculate_sma(closes, self.config['ma_long'])
            
            if ma_short and ma_long and len(ma_short) >= 3 and len(ma_long) >= 3:
                offset = len(ma_short) - len(ma_long)
                ma_short_aligned = ma_short[offset:] if offset > 0 else ma_short
                ma_long_aligned = ma_long[-len(ma_short_aligned):] if offset < 0 else ma_long
                
                if len(ma_short_aligned) >= 3 and len(ma_long_aligned) >= 3:
                    # 金叉：短期上穿长期（需要确认）
                    if (ma_short_aligned[-1] > ma_long_aligned[-1] and 
                        ma_short_aligned[-2] <= ma_long_aligned[-2]):
                        # 确认：金叉后价格继续上涨
                        if closes[-1] > closes[-2]:
                            signals.append(f"🔥 MA{self.config['ma_short']}/{self.config['ma_long']}金叉确认")
                            score += self.config['weights']['ma_golden_cross']
                    
                    # 趋势延续：短期在长期上方且持续上升
                    elif (ma_short_aligned[-1] > ma_long_aligned[-1] and 
                          ma_short_aligned[-1] > ma_short_aligned[-2] > ma_short_aligned[-3]):
                        signals.append(f"📈 均线多头排列")
                        score += self.config['weights']['trend_continuation']
            
            # 2. MACD金叉检测（强信号）
            macd_line, signal_line, histogram = self.indicators.calculate_macd(closes)
            if macd_line and signal_line and len(macd_line) >= 3:
                # MACD金叉（需要确认）
                if (macd_line[-1] > signal_line[-1] and 
                    macd_line[-2] <= signal_line[-2] and
                    macd_line[-1] > macd_line[-2]):  # 确认MACD继续上升
                    signals.append("🔥 MACD金叉确认")
                    score += self.config['weights']['macd_golden_cross']
                
                # MACD零轴上方且柱状图放大
                elif (macd_line[-1] > 0 and 
                      histogram and len(histogram) >= 2 and
                      histogram[-1] > histogram[-2] > 0):
                    signals.append("📊 MACD多头加速")
                    score += self.config['weights']['macd_golden_cross'] // 2
            
            # 3. RSI反转（从超卖区反弹 - 强信号）
            rsi = self.indicators.calculate_rsi(closes)
            if rsi and len(rsi) >= 3:
                current_rsi = rsi[-1]
                
                # 从超卖区反弹（强信号）
                if (min(rsi[-5:-1]) < self.config['rsi_oversold'] and 
                    current_rsi > self.config['rsi_oversold'] and
                    current_rsi > rsi[-2]):
                    signals.append(f"🔥 RSI超卖反弹 ({current_rsi:.0f})")
                    score += self.config['weights']['rsi_reversal']
                
                # RSI突破50（中等信号，需要确认）
                elif (rsi[-2] < 50 and current_rsi > 50 and 
                      current_rsi > rsi[-2] > rsi[-3]):
                    signals.append(f"📈 RSI突破50并上升 ({current_rsi:.0f})")
                    score += self.config['weights']['rsi_reversal'] // 2
            
            # 4. 成交量放大（需要显著放大）
            if volumes and len(volumes) >= 2:
                current_volume = volumes[-1]
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
                
                # 只有显著放大才计分
                if volume_ratio >= self.config['volume_surge_ratio']:
                    signals.append(f"🔥 成交量放大 {volume_ratio:.1f}倍")
                    score += self.config['weights']['volume_surge']
            
            # 5. 价格突破（强信号）
            if highs and len(highs) >= 20:
                # 52周新高（强信号）
                if len(highs) >= 250:
                    high_52w = max(highs[-250:])
                else:
                    high_52w = max(highs)
                
                ratio_52w = current_price / high_52w if high_52w > 0 else 0
                
                if ratio_52w >= 0.98:  # 接近或突破52周新高
                    signals.append(f"🔥 突破52周新高 ({ratio_52w*100:.1f}%)")
                    score += self.config['weights']['price_breakout_52w']
                elif ratio_52w >= 0.92:
                    signals.append(f"📈 接近52周新高 ({ratio_52w*100:.1f}%)")
                    score += self.config['weights']['price_breakout_52w'] // 2
                
                # 20日新高
                high_20d = max(highs[-20:])
                if current_price >= high_20d * 0.99:
                    signals.append("📈 突破20日高点")
                    score += self.config['weights']['price_breakout_20d']
            
            # 6. OBV确认
            obv = self.indicators.calculate_obv(closes, volumes)
            if obv and len(obv) >= 10:
                obv_sma = sum(obv[-10:]) / 10
                # OBV需要明显上升
                if obv[-1] > obv_sma * 1.05 and obv[-1] > obv[-2] > obv[-3]:
                    signals.append("📊 OBV持续上升")
                    score += self.config['weights']['obv_confirm']
            
            # 7. 趋势强度检查
            trend_desc, trend_score = self.check_trend_strength(closes, self.config['trend_confirm_days'])
            if trend_score > 0:
                signals.append(f"📈 {trend_desc}")
            score += trend_score
            
            # 只返回达到门槛的股票
            if signals and score >= self.config['min_score']:
                prev_close = closes[-2] if len(closes) >= 2 else current_price
                change_percent = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
                
                signal_quality = self.check_signal_quality(signals, score)
                
                return StockSignal(
                    symbol=symbol,
                    name=name[:30] if name else symbol,
                    current_price=current_price,
                    change_percent=change_percent,
                    volume=volumes[-1] if volumes else 0,
                    avg_volume=avg_volume,
                    signals=signals,
                    score=score,
                    trend_strength=trend_desc,
                    signal_quality=signal_quality,
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
        """批量筛选股票"""
        self.stats = RunTimeStats(
            start_time=datetime.now(),
            total_stocks=len(symbols)
        )
        self._processed_count = 0
        self._failed_count = 0
        
        results = []
        start_time = time.time()
        
        logger.info(f"开始筛选 {len(symbols)} 只股票（降噪模式）...")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._analyze_with_tracking, symbol): symbol 
                      for symbol in symbols}
            
            for i, future in enumerate(as_completed(futures)):
                symbol = futures[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        logger.info(f"✅ {result.symbol} [{result.signal_quality}] 评分:{result.score} {result.trend_strength}")
                except Exception as e:
                    pass
                
                if (i + 1) % 100 == 0 or i == len(symbols) - 1:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    remaining = (len(symbols) - i - 1) / rate if rate > 0 else 0
                    logger.info(f"进度: {i+1}/{len(symbols)} ({(i+1)/len(symbols)*100:.1f}%) "
                               f"| 发现: {len(results)} | 预计剩余: {remaining:.0f}秒")
        
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


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='股票筛选程序V3（降噪版）')
    parser.add_argument('--symbols', nargs='+', help='指定股票代码')
    parser.add_argument('--watchlist', type=str, help='股票列表文件')
    parser.add_argument('--workers', type=int, default=15, help='并行线程数')
    parser.add_argument('--limit', type=int, help='限制筛选数量')
    
    args = parser.parse_args()
    
    # 确定股票列表
    if args.symbols:
        symbols = [s.upper() for s in args.symbols]
    elif args.watchlist:
        symbols = load_stock_list(args.watchlist)
    else:
        symbols = load_stock_list('/home/ubuntu/stock_screener/all_priority_stocks.txt')
        if not symbols:
            symbols = load_stock_list('/home/ubuntu/stock_screener/priority_stocks.txt')
    
    if args.limit:
        symbols = symbols[:args.limit]
    
    logger.info(f"准备筛选 {len(symbols)} 只股票（降噪模式）")
    
    # 创建筛选器
    screener = StockScreenerV3(max_workers=args.workers)
    
    # 执行筛选
    results, stats = screener.screen_stocks(symbols)
    
    # 打印结果
    print("\n" + "=" * 60)
    print(f"⏱️ 耗时: {stats.total_runtime_seconds:.1f}秒")
    print(f"📊 筛选: {stats.total_stocks} 只 → 发现: {len(results)} 只")
    print(f"🔥 高分(≥70): {stats.high_score_count} 只")
    print("=" * 60)
    
    if results:
        print(f"\n🎯 发现 {len(results)} 只潜力股:\n")
        for i, r in enumerate(results[:15], 1):
            print(f"{i}. {r.symbol} ({r.name})")
            print(f"   评分: {r.score} | 质量: {r.signal_quality} | 趋势: {r.trend_strength}")
            print(f"   价格: ${r.current_price:.2f} ({r.change_percent:+.2f}%)")
            print(f"   信号: {' | '.join(r.signals[:3])}")
            print()
    
    # 保存报告
    report_path = '/home/ubuntu/stock_screener/report_v3.json'
    with open(report_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'version': 'v3_denoise',
            'stats': stats.to_dict(),
            'results': [asdict(r) for r in results]
        }, f, indent=2, default=str)
    
    # 发送Telegram
    config = load_config()
    tg_config = config.get('notification', {}).get('telegram', {})
    
    if tg_config.get('enabled') and tg_config.get('bot_token') and results:
        notifier = TelegramNotifier(tg_config['bot_token'], tg_config['chat_id'])
        
        msg_lines = [
            f"📊 <b>股票筛选完成（降噪版）</b>",
            f"⏱️ 耗时: {stats.total_runtime_seconds:.1f}秒",
            f"📈 筛选: {stats.total_stocks} → 发现: {len(results)} 只",
            ""
        ]
        
        # 按质量分组
        a_grade = [r for r in results if 'A级' in r.signal_quality]
        b_grade = [r for r in results if 'B级' in r.signal_quality]
        
        if a_grade:
            msg_lines.append(f"🔥 <b>A级信号 ({len(a_grade)}只)</b>")
            for r in a_grade[:5]:
                msg_lines.append(f"  <b>{r.symbol}</b> {r.score}分 ${r.current_price:.2f}")
                msg_lines.append(f"    {r.signals[0] if r.signals else ''}")
            msg_lines.append("")
        
        if b_grade:
            msg_lines.append(f"⭐ <b>B级信号 ({len(b_grade)}只)</b>")
            for r in b_grade[:3]:
                msg_lines.append(f"  {r.symbol} {r.score}分 ${r.current_price:.2f}")
            msg_lines.append("")
        
        notifier.send_message("\n".join(msg_lines))
    
    return results, stats


if __name__ == '__main__':
    main()
