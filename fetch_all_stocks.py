#!/usr/bin/env python3
"""
获取全美股股票列表
- 纳斯达克 (NASDAQ)
- 纽约证券交易所 (NYSE)
- 美国证券交易所 (AMEX)
"""

import sys
sys.path.append('/opt/.manus/.sandbox-runtime')

import requests
import pandas as pd
import logging
from pathlib import Path
from typing import List, Dict
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def fetch_nasdaq_listed() -> List[Dict]:
    """从NASDAQ FTP获取股票列表"""
    stocks = []
    
    # NASDAQ Listed
    try:
        url = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
        response = requests.get(url, timeout=30)
        lines = response.text.strip().split('\n')
        
        for line in lines[1:-1]:  # 跳过header和footer
            parts = line.split('|')
            if len(parts) >= 2:
                symbol = parts[0].strip()
                name = parts[1].strip() if len(parts) > 1 else ''
                
                # 过滤掉测试股票和特殊符号
                if symbol and not symbol.endswith('$') and len(symbol) <= 5:
                    stocks.append({
                        'symbol': symbol,
                        'name': name,
                        'exchange': 'NASDAQ'
                    })
        
        logger.info(f"NASDAQ Listed: {len(stocks)} 只股票")
    except Exception as e:
        logger.error(f"获取NASDAQ列表失败: {e}")
    
    return stocks


def fetch_other_listed() -> List[Dict]:
    """获取NYSE/AMEX等其他交易所股票"""
    stocks = []
    
    try:
        url = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
        response = requests.get(url, timeout=30)
        lines = response.text.strip().split('\n')
        
        for line in lines[1:-1]:
            parts = line.split('|')
            if len(parts) >= 3:
                symbol = parts[0].strip()
                name = parts[1].strip() if len(parts) > 1 else ''
                exchange = parts[2].strip() if len(parts) > 2 else 'OTHER'
                
                # 映射交易所代码
                exchange_map = {'N': 'NYSE', 'A': 'AMEX', 'P': 'ARCA', 'Z': 'BATS'}
                exchange = exchange_map.get(exchange, exchange)
                
                if symbol and not symbol.endswith('$') and len(symbol) <= 5:
                    stocks.append({
                        'symbol': symbol,
                        'name': name,
                        'exchange': exchange
                    })
        
        logger.info(f"Other Listed (NYSE/AMEX等): {len(stocks)} 只股票")
    except Exception as e:
        logger.error(f"获取其他交易所列表失败: {e}")
    
    return stocks


def filter_tradable_stocks(stocks: List[Dict], min_price: float = 1.0) -> List[Dict]:
    """过滤可交易的股票"""
    filtered = []
    
    # 排除的后缀（优先股、权证等）
    exclude_suffixes = ['.W', '.U', '.R', '-W', '-U', '-R', '+', '^']
    
    for stock in stocks:
        symbol = stock['symbol']
        
        # 跳过带特殊后缀的
        skip = False
        for suffix in exclude_suffixes:
            if suffix in symbol:
                skip = True
                break
        
        if skip:
            continue
        
        # 只保留普通股票（1-5个字母）
        if symbol.isalpha() and 1 <= len(symbol) <= 5:
            filtered.append(stock)
    
    logger.info(f"过滤后: {len(filtered)} 只股票")
    return filtered


def save_stock_list(stocks: List[Dict], output_path: str):
    """保存股票列表"""
    # 保存为JSON
    json_path = output_path.replace('.txt', '.json')
    with open(json_path, 'w') as f:
        json.dump(stocks, f, indent=2)
    
    # 保存为TXT（仅代码）
    with open(output_path, 'w') as f:
        f.write("# 全美股股票池\n")
        f.write(f"# 共 {len(stocks)} 只股票\n")
        f.write(f"# 更新时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 按交易所分组
        by_exchange = {}
        for stock in stocks:
            ex = stock['exchange']
            if ex not in by_exchange:
                by_exchange[ex] = []
            by_exchange[ex].append(stock['symbol'])
        
        for exchange, symbols in sorted(by_exchange.items()):
            f.write(f"# {exchange} ({len(symbols)} 只)\n")
            for symbol in sorted(symbols):
                f.write(f"{symbol}\n")
            f.write("\n")
    
    logger.info(f"股票列表已保存: {output_path}")
    logger.info(f"JSON列表已保存: {json_path}")


def main():
    """主函数"""
    logger.info("开始获取全美股股票列表...")
    
    # 获取所有股票
    nasdaq_stocks = fetch_nasdaq_listed()
    other_stocks = fetch_other_listed()
    
    # 合并并去重
    all_stocks = nasdaq_stocks + other_stocks
    seen = set()
    unique_stocks = []
    for stock in all_stocks:
        if stock['symbol'] not in seen:
            seen.add(stock['symbol'])
            unique_stocks.append(stock)
    
    logger.info(f"合并后总计: {len(unique_stocks)} 只股票")
    
    # 过滤
    filtered_stocks = filter_tradable_stocks(unique_stocks)
    
    # 保存
    output_path = '/home/ubuntu/stock_screener/all_us_stocks.txt'
    save_stock_list(filtered_stocks, output_path)
    
    # 统计
    by_exchange = {}
    for stock in filtered_stocks:
        ex = stock['exchange']
        by_exchange[ex] = by_exchange.get(ex, 0) + 1
    
    print("\n" + "=" * 50)
    print("全美股股票池统计")
    print("=" * 50)
    for exchange, count in sorted(by_exchange.items(), key=lambda x: -x[1]):
        print(f"  {exchange}: {count} 只")
    print(f"  总计: {len(filtered_stocks)} 只")
    print("=" * 50)
    
    return filtered_stocks


if __name__ == '__main__':
    main()
