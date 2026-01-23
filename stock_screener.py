#!/usr/bin/env python3
"""
股票筛选盯盘程序 - Stock Screener & Alert System
功能：程序化发现有上涨潜力的股票并发送提醒

作者：Manus AI
版本：1.0
"""

import sys
sys.path.append('/opt/.manus/.sandbox-runtime')

import json
import time
import smtplib
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from data_api import ApiClient
import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent
LOG_DIR = PROJECT_DIR / 'logs'
REPORTS_DIR = PROJECT_DIR / 'reports'
LOG_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'screener.log'),
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
    score: int  # 综合评分
    timestamp: datetime


class TechnicalIndicators:
    """技术指标计算类"""
    
    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> List[float]:
        """计算简单移动平均线"""
        if len(prices) < period:
            return []
        sma = []
        for i in range(period - 1, len(prices)):
            avg = sum(prices[i - period + 1:i + 1]) / period
            sma.append(avg)
        return sma
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> List[float]:
        """计算指数移动平均线"""
        if len(prices) < period:
            return []
        
        multiplier = 2 / (period + 1)
        ema = [sum(prices[:period]) / period]  # 第一个EMA用SMA
        
        for price in prices[period:]:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
        
        return ema
    
    @staticmethod
    def calculate_macd(prices: List[float]) -> Tuple[List[float], List[float], List[float]]:
        """
        计算MACD指标
        返回: (MACD线, 信号线, 柱状图)
        """
        if len(prices) < 26:
            return [], [], []
        
        ema12 = TechnicalIndicators.calculate_ema(prices, 12)
        ema26 = TechnicalIndicators.calculate_ema(prices, 26)
        
        # 对齐长度
        diff = len(ema12) - len(ema26)
        ema12 = ema12[diff:]
        
        # MACD线 = EMA12 - EMA26
        macd_line = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
        
        # 信号线 = MACD的9日EMA
        if len(macd_line) >= 9:
            signal_line = TechnicalIndicators.calculate_ema(macd_line, 9)
            # 对齐
            macd_line = macd_line[-(len(signal_line)):]
            # 柱状图
            histogram = [m - s for m, s in zip(macd_line, signal_line)]
        else:
            signal_line = []
            histogram = []
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
        """计算RSI指标"""
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
        """计算OBV能量潮"""
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


class StockScreener:
    """股票筛选器主类"""
    
    def __init__(self, config: Dict = None):
        self.client = ApiClient()
        self.indicators = TechnicalIndicators()
        self.config = config or self._default_config()
        
    def _default_config(self) -> Dict:
        """默认配置"""
        return {
            # 筛选参数
            'min_price': 5.0,           # 最低股价
            'max_price': 500.0,         # 最高股价
            'min_volume': 500000,       # 最低日均成交量
            'volume_surge_ratio': 1.5,  # 成交量放大倍数
            
            # 技术指标参数
            'ma_short': 20,             # 短期均线
            'ma_long': 50,              # 长期均线
            'rsi_oversold': 30,         # RSI超卖线
            'rsi_overbought': 70,       # RSI超买线
            
            # 评分权重
            'weights': {
                'ma_golden_cross': 25,
                'macd_golden_cross': 20,
                'rsi_bullish': 15,
                'volume_surge': 15,
                'price_breakout': 15,
                'obv_confirm': 10
            }
        }
    
    def get_stock_data(self, symbol: str, days: int = 100) -> Optional[Dict]:
        """获取股票历史数据"""
        try:
            # 根据天数选择合适的range
            if days <= 30:
                range_param = '1mo'
            elif days <= 90:
                range_param = '3mo'
            elif days <= 180:
                range_param = '6mo'
            else:
                range_param = '1y'
            
            response = self.client.call_api('YahooFinance/get_stock_chart', query={
                'symbol': symbol,
                'region': 'US',
                'interval': '1d',
                'range': range_param,
                'includeAdjustedClose': True
            })
            
            if response and 'chart' in response and 'result' in response['chart']:
                result = response['chart']['result'][0]
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"获取 {symbol} 数据失败: {e}")
            return None
    
    def analyze_stock(self, symbol: str) -> Optional[StockSignal]:
        """分析单只股票"""
        data = self.get_stock_data(symbol)
        if not data:
            return None
        
        try:
            meta = data.get('meta', {})
            quotes = data.get('indicators', {}).get('quote', [{}])[0]
            
            # 提取价格和成交量数据
            closes = [c for c in quotes.get('close', []) if c is not None]
            volumes = [v for v in quotes.get('volume', []) if v is not None]
            highs = [h for h in quotes.get('high', []) if h is not None]
            lows = [l for l in quotes.get('low', []) if l is not None]
            
            if len(closes) < 50:
                logger.debug(f"{symbol}: 数据不足")
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
            
            # 1. 移动平均线金叉检测
            ma_short = self.indicators.calculate_sma(closes, self.config['ma_short'])
            ma_long = self.indicators.calculate_sma(closes, self.config['ma_long'])
            
            if ma_short and ma_long:
                # 检测金叉 (短期均线上穿长期均线)
                if len(ma_short) >= 2 and len(ma_long) >= 2:
                    # 对齐
                    offset = len(ma_short) - len(ma_long)
                    ma_short_aligned = ma_short[offset:] if offset > 0 else ma_short
                    ma_long_aligned = ma_long[-len(ma_short_aligned):] if offset < 0 else ma_long
                    
                    if len(ma_short_aligned) >= 2 and len(ma_long_aligned) >= 2:
                        # 今天短期在长期上方，昨天短期在长期下方 = 金叉
                        if (ma_short_aligned[-1] > ma_long_aligned[-1] and 
                            ma_short_aligned[-2] <= ma_long_aligned[-2]):
                            signals.append(f"🔥 MA{self.config['ma_short']}/MA{self.config['ma_long']}金叉")
                            score += self.config['weights']['ma_golden_cross']
                        # 短期均线在长期均线上方且上升
                        elif (ma_short_aligned[-1] > ma_long_aligned[-1] and 
                              ma_short_aligned[-1] > ma_short_aligned[-2]):
                            signals.append(f"📈 价格在MA{self.config['ma_long']}上方运行")
                            score += self.config['weights']['ma_golden_cross'] // 2
            
            # 2. MACD金叉检测
            macd_line, signal_line, histogram = self.indicators.calculate_macd(closes)
            if macd_line and signal_line and len(macd_line) >= 2:
                # MACD金叉
                if macd_line[-1] > signal_line[-1] and macd_line[-2] <= signal_line[-2]:
                    signals.append("🔥 MACD金叉")
                    score += self.config['weights']['macd_golden_cross']
                # MACD在零轴上方
                elif macd_line[-1] > 0 and macd_line[-1] > signal_line[-1]:
                    signals.append("📊 MACD多头排列")
                    score += self.config['weights']['macd_golden_cross'] // 2
                # 柱状图由负转正
                if histogram and len(histogram) >= 2:
                    if histogram[-1] > 0 and histogram[-2] <= 0:
                        signals.append("📈 MACD柱状图转正")
                        score += 5
            
            # 3. RSI分析
            rsi = self.indicators.calculate_rsi(closes)
            if rsi:
                current_rsi = rsi[-1]
                # RSI从超卖区反弹
                if len(rsi) >= 3:
                    if (current_rsi > self.config['rsi_oversold'] and 
                        min(rsi[-5:]) < self.config['rsi_oversold']):
                        signals.append(f"📈 RSI从超卖区反弹 ({current_rsi:.1f})")
                        score += self.config['weights']['rsi_bullish']
                    # RSI突破50
                    elif current_rsi > 50 and rsi[-2] <= 50:
                        signals.append(f"📊 RSI突破50 ({current_rsi:.1f})")
                        score += self.config['weights']['rsi_bullish'] // 2
                    # RSI在健康区间
                    elif 50 < current_rsi < 70:
                        signals.append(f"✅ RSI健康 ({current_rsi:.1f})")
                        score += 5
            
            # 4. 成交量分析
            if len(volumes) >= 20:
                recent_volume = volumes[-1]
                avg_vol_20 = sum(volumes[-20:]) / 20
                volume_ratio = recent_volume / avg_vol_20 if avg_vol_20 > 0 else 0
                
                if volume_ratio >= self.config['volume_surge_ratio']:
                    signals.append(f"🔥 成交量放大 {volume_ratio:.1f}倍")
                    score += self.config['weights']['volume_surge']
                elif volume_ratio >= 1.2:
                    signals.append(f"📊 成交量温和放大 {volume_ratio:.1f}倍")
                    score += self.config['weights']['volume_surge'] // 2
            
            # 5. 价格突破检测
            if len(highs) >= 20:
                high_20 = max(highs[-20:])
                if current_price >= high_20 * 0.98:  # 接近或突破20日高点
                    signals.append(f"🚀 接近/突破20日高点")
                    score += self.config['weights']['price_breakout']
            
            # 6. 52周高点检测
            week_52_high = meta.get('fiftyTwoWeekHigh', 0)
            week_52_low = meta.get('fiftyTwoWeekLow', 0)
            if week_52_high > 0:
                pct_from_high = (current_price / week_52_high) * 100
                if pct_from_high >= 95:
                    signals.append(f"🔥 接近52周新高 ({pct_from_high:.1f}%)")
                    score += 10
                elif pct_from_high >= 80:
                    signals.append(f"📈 距52周高点 {100-pct_from_high:.1f}%")
                    score += 5
            
            # 7. OBV确认
            obv = self.indicators.calculate_obv(closes, volumes)
            if len(obv) >= 10:
                obv_ma = sum(obv[-10:]) / 10
                if obv[-1] > obv_ma and obv[-1] > obv[-2]:
                    signals.append("📊 OBV上升确认")
                    score += self.config['weights']['obv_confirm']
            
            # 计算涨跌幅
            if len(closes) >= 2:
                change_percent = ((closes[-1] - closes[-2]) / closes[-2]) * 100
            else:
                change_percent = 0
            
            # 只返回有信号的股票
            if signals and score >= 20:
                return StockSignal(
                    symbol=symbol,
                    name=name,
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
            logger.error(f"分析 {symbol} 时出错: {e}")
            return None
    
    def screen_stocks(self, symbols: List[str]) -> List[StockSignal]:
        """批量筛选股票"""
        results = []
        total = len(symbols)
        
        for i, symbol in enumerate(symbols):
            logger.info(f"正在分析 [{i+1}/{total}]: {symbol}")
            
            signal = self.analyze_stock(symbol)
            if signal:
                results.append(signal)
                logger.info(f"✅ {symbol} 发现信号! 评分: {signal.score}")
            
            # 避免API限制
            time.sleep(0.5)
        
        # 按评分排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results


class AlertNotifier:
    """提醒通知类"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
    
    def format_alert(self, signals: List[StockSignal]) -> str:
        """格式化提醒消息"""
        if not signals:
            return "未发现符合条件的股票"
        
        lines = [
            "=" * 50,
            f"📊 股票筛选报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "=" * 50,
            f"共发现 {len(signals)} 只潜力股票\n"
        ]
        
        for i, sig in enumerate(signals, 1):
            lines.append(f"【{i}】{sig.symbol} - {sig.name}")
            lines.append(f"    💰 价格: ${sig.current_price:.2f} ({sig.change_percent:+.2f}%)")
            lines.append(f"    📊 成交量: {sig.volume:,} (均量: {sig.avg_volume:,.0f})")
            lines.append(f"    ⭐ 综合评分: {sig.score}")
            lines.append(f"    📌 信号:")
            for signal in sig.signals:
                lines.append(f"       • {signal}")
            lines.append("")
        
        lines.append("=" * 50)
        lines.append("⚠️ 以上仅为技术分析参考，不构成投资建议")
        lines.append("=" * 50)
        
        return "\n".join(lines)
    
    def send_email(self, signals: List[StockSignal], 
                   smtp_server: str, smtp_port: int,
                   sender: str, password: str, 
                   recipients: List[str]) -> bool:
        """发送邮件提醒"""
        try:
            content = self.format_alert(signals)
            
            msg = MIMEMultipart()
            msg['From'] = sender
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"📈 股票筛选报告 - {datetime.now().strftime('%Y-%m-%d')} - 发现{len(signals)}只潜力股"
            
            msg.attach(MIMEText(content, 'plain', 'utf-8'))
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender, password)
                server.send_message(msg)
            
            logger.info(f"邮件发送成功: {recipients}")
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False
    
    def print_console(self, signals: List[StockSignal]):
        """控制台输出"""
        print(self.format_alert(signals))
    
    def save_report(self, signals: List[StockSignal], filepath: str):
        """保存报告到文件"""
        content = self.format_alert(signals)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"报告已保存: {filepath}")
        
        # 同时保存JSON格式
        json_path = filepath.replace('.txt', '.json')
        data = [{
            'symbol': s.symbol,
            'name': s.name,
            'price': s.current_price,
            'change_percent': s.change_percent,
            'volume': s.volume,
            'avg_volume': s.avg_volume,
            'signals': s.signals,
            'score': s.score,
            'timestamp': s.timestamp.isoformat()
        } for s in signals]
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"JSON报告已保存: {json_path}")


# 预设股票池 - 美股热门股票
DEFAULT_WATCHLIST = [
    # 科技股
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD', 'INTC', 'CRM',
    'ADBE', 'NFLX', 'PYPL', 'SQ', 'SHOP', 'SNOW', 'PLTR', 'UBER', 'ABNB', 'COIN',
    # 半导体
    'AVGO', 'QCOM', 'MU', 'MRVL', 'AMAT', 'LRCX', 'KLAC', 'ASML', 'TSM', 'ARM',
    # 软件/云
    'NOW', 'PANW', 'CRWD', 'ZS', 'DDOG', 'NET', 'MDB', 'TEAM', 'OKTA', 'WDAY',
    # AI相关
    'SMCI', 'DELL', 'HPE', 'ORCL', 'IBM', 'AI', 'PATH', 'UPST', 'SOUN', 'BBAI',
    # 金融
    'JPM', 'BAC', 'WFC', 'GS', 'MS', 'V', 'MA', 'AXP', 'BLK', 'SCHW',
    # 医疗
    'UNH', 'JNJ', 'PFE', 'ABBV', 'MRK', 'LLY', 'TMO', 'ABT', 'BMY', 'AMGN',
    # 消费
    'WMT', 'COST', 'HD', 'NKE', 'SBUX', 'MCD', 'DIS', 'CMCSA', 'PEP', 'KO',
    # 能源
    'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'OXY', 'MPC', 'VLO', 'PSX', 'HAL',
    # 热门成长股
    'MSTR', 'HOOD', 'RBLX', 'RIVN', 'LCID', 'NIO', 'XPEV', 'LI', 'SOFI', 'AFRM'
]


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='股票筛选盯盘程序')
    parser.add_argument('--symbols', nargs='+', help='要筛选的股票代码列表')
    parser.add_argument('--watchlist', type=str, help='股票代码文件路径')
    parser.add_argument('--output', type=str, default=str(REPORTS_DIR / 'report.txt'),
                        help='报告输出路径')
    parser.add_argument('--email', action='store_true', help='是否发送邮件')
    parser.add_argument('--smtp-server', type=str, default='smtp.gmail.com')
    parser.add_argument('--smtp-port', type=int, default=587)
    parser.add_argument('--sender', type=str, help='发件人邮箱')
    parser.add_argument('--password', type=str, help='邮箱密码/应用密码')
    parser.add_argument('--recipients', nargs='+', help='收件人邮箱列表')
    
    args = parser.parse_args()
    
    # 确定股票列表
    if args.symbols:
        symbols = args.symbols
    elif args.watchlist:
        with open(args.watchlist, 'r') as f:
            symbols = [line.strip() for line in f if line.strip()]
    else:
        symbols = DEFAULT_WATCHLIST
    
    logger.info(f"开始筛选 {len(symbols)} 只股票...")
    
    # 创建筛选器和通知器
    screener = StockScreener()
    notifier = AlertNotifier()
    
    # 执行筛选
    results = screener.screen_stocks(symbols)
    
    # 输出结果
    notifier.print_console(results)
    notifier.save_report(results, args.output)
    
    # 发送邮件
    if args.email and args.sender and args.password and args.recipients:
        notifier.send_email(
            results,
            args.smtp_server, args.smtp_port,
            args.sender, args.password, args.recipients
        )
    
    logger.info(f"筛选完成! 发现 {len(results)} 只潜力股票")
    return results


if __name__ == '__main__':
    main()
