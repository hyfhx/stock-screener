#!/usr/bin/env python3
"""
获取主要指数成分股
- 标普500 (S&P 500)
- 纳斯达克100 (NASDAQ 100)
- 道琼斯30 (Dow Jones 30)
"""

import sys
sys.path.append('/opt/.manus/.sandbox-runtime')

import requests
import json
import logging
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
LISTS_DIR = PROJECT_DIR / 'lists'
LISTS_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 标普500成分股 (2024年最新)
SP500_SYMBOLS = [
    # 信息技术
    'AAPL', 'MSFT', 'NVDA', 'AVGO', 'ORCL', 'CRM', 'AMD', 'ADBE', 'ACN', 'CSCO',
    'INTC', 'IBM', 'INTU', 'TXN', 'QCOM', 'NOW', 'AMAT', 'ADI', 'LRCX', 'MU',
    'KLAC', 'SNPS', 'CDNS', 'MCHP', 'FTNT', 'PANW', 'CRWD', 'MSI', 'APH', 'TEL',
    'NXPI', 'MPWR', 'ON', 'KEYS', 'ANSS', 'FSLR', 'HPQ', 'HPE', 'NTAP', 'WDC',
    'STX', 'JNPR', 'GEN', 'FFIV', 'AKAM', 'EPAM', 'IT', 'CTSH', 'GDDY', 'PTC',
    
    # 通信服务
    'GOOGL', 'GOOG', 'META', 'NFLX', 'DIS', 'CMCSA', 'VZ', 'T', 'TMUS', 'CHTR',
    'EA', 'TTWO', 'WBD', 'PARA', 'FOX', 'FOXA', 'NWS', 'NWSA', 'LYV', 'MTCH',
    'OMC', 'IPG',
    
    # 非必需消费品
    'AMZN', 'TSLA', 'HD', 'MCD', 'NKE', 'LOW', 'SBUX', 'TJX', 'BKNG', 'ORLY',
    'AZO', 'CMG', 'MAR', 'HLT', 'YUM', 'DHI', 'LEN', 'GM', 'F', 'ROST',
    'EBAY', 'ETSY', 'ULTA', 'BBY', 'DRI', 'WYNN', 'LVS', 'MGM', 'CZR', 'RCL',
    'CCL', 'NCLH', 'EXPE', 'ABNB', 'APTV', 'BWA', 'GRMN', 'POOL', 'PHM', 'NVR',
    'TPR', 'RL', 'HAS', 'DPZ', 'DECK', 'LULU',
    
    # 医疗保健
    'UNH', 'JNJ', 'LLY', 'ABBV', 'MRK', 'PFE', 'TMO', 'ABT', 'DHR', 'BMY',
    'AMGN', 'GILD', 'ISRG', 'VRTX', 'MDT', 'SYK', 'REGN', 'BSX', 'ELV', 'CI',
    'CVS', 'MCK', 'HUM', 'CNC', 'ZTS', 'BDX', 'EW', 'IDXX', 'IQV', 'MTD',
    'A', 'DXCM', 'ALGN', 'HOLX', 'COO', 'RMD', 'BAX', 'BIIB', 'MRNA', 'ILMN',
    'TECH', 'MOH', 'HCA', 'CAH', 'COR', 'GEHC', 'PODD', 'RVTY', 'VTRS', 'LH',
    'DGX', 'WST', 'ZBH', 'STE', 'INCY',
    
    # 金融
    'BRK.B', 'JPM', 'V', 'MA', 'BAC', 'WFC', 'GS', 'MS', 'SPGI', 'BLK',
    'C', 'AXP', 'SCHW', 'CB', 'PGR', 'MMC', 'ICE', 'CME', 'AON', 'USB',
    'PNC', 'TFC', 'AIG', 'MET', 'PRU', 'AFL', 'TRV', 'ALL', 'AJG', 'MSCI',
    'MCO', 'FIS', 'COF', 'BK', 'STT', 'FITB', 'NDAQ', 'TROW', 'CINF', 'RJF',
    'WRB', 'HBAN', 'RF', 'CFG', 'KEY', 'NTRS', 'MTB', 'CBOE', 'FRC', 'SBNY',
    'L', 'BRO', 'EG', 'RE', 'GL', 'AIZ', 'LNC', 'IVZ', 'BEN', 'ZION',
    
    # 工业
    'CAT', 'GE', 'RTX', 'HON', 'UNP', 'UPS', 'BA', 'DE', 'LMT', 'ADP',
    'ETN', 'ITW', 'EMR', 'NOC', 'GD', 'WM', 'CSX', 'NSC', 'MMM', 'FDX',
    'TT', 'PH', 'CTAS', 'CARR', 'JCI', 'PCAR', 'CMI', 'OTIS', 'AME', 'ROK',
    'FAST', 'VRSK', 'GWW', 'CPRT', 'RSG', 'PWR', 'IR', 'ODFL', 'PAYX', 'EFX',
    'XYL', 'DOV', 'WAB', 'SWK', 'HWM', 'HUBB', 'J', 'IEX', 'NDSN', 'ROP',
    'TDG', 'LHX', 'AXON', 'DAL', 'UAL', 'LUV', 'AAL', 'JBHT', 'EXPD', 'CHRW',
    
    # 必需消费品
    'PG', 'KO', 'PEP', 'COST', 'WMT', 'PM', 'MO', 'MDLZ', 'CL', 'KMB',
    'GIS', 'KHC', 'SYY', 'STZ', 'ADM', 'HSY', 'KR', 'MKC', 'K', 'CAG',
    'TSN', 'HRL', 'SJM', 'CPB', 'CLX', 'CHD', 'EL', 'KDP', 'MNST', 'TAP',
    'BG', 'LW', 'WBA', 'DG', 'DLTR',
    
    # 能源
    'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'OXY', 'PXD',
    'WMB', 'KMI', 'HAL', 'DVN', 'HES', 'FANG', 'BKR', 'TRGP', 'OKE', 'CTRA',
    'MRO', 'APA',
    
    # 公用事业
    'NEE', 'SO', 'DUK', 'SRE', 'AEP', 'D', 'EXC', 'XEL', 'PCG', 'ED',
    'WEC', 'AWK', 'ES', 'EIX', 'DTE', 'PPL', 'FE', 'ETR', 'AEE', 'CMS',
    'CEG', 'CNP', 'EVRG', 'ATO', 'NI', 'PNW', 'NRG', 'LNT', 'AES', 'PEG',
    
    # 房地产
    'PLD', 'AMT', 'EQIX', 'CCI', 'PSA', 'WELL', 'DLR', 'O', 'SPG', 'VICI',
    'AVB', 'EQR', 'SBAC', 'WY', 'VTR', 'ARE', 'EXR', 'MAA', 'IRM', 'ESS',
    'INVH', 'UDR', 'KIM', 'REG', 'CPT', 'HST', 'BXP', 'PEAK', 'FRT',
    
    # 材料
    'LIN', 'APD', 'SHW', 'ECL', 'FCX', 'NEM', 'NUE', 'DOW', 'DD', 'PPG',
    'VMC', 'MLM', 'CTVA', 'ALB', 'IFF', 'CE', 'EMN', 'FMC', 'CF', 'MOS',
    'PKG', 'IP', 'AVY', 'BALL', 'SEE', 'AMCR', 'WRK',
]

# 纳斯达克100成分股
NASDAQ100_SYMBOLS = [
    'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'GOOG', 'TSLA', 'AVGO', 'COST',
    'PEP', 'ADBE', 'CSCO', 'NFLX', 'AMD', 'TMUS', 'CMCSA', 'INTC', 'INTU', 'AMGN',
    'TXN', 'QCOM', 'HON', 'ISRG', 'SBUX', 'BKNG', 'AMAT', 'VRTX', 'MDLZ', 'GILD',
    'ADP', 'ADI', 'REGN', 'LRCX', 'PANW', 'MU', 'SNPS', 'KLAC', 'CDNS', 'PYPL',
    'MELI', 'MAR', 'ORLY', 'CTAS', 'ASML', 'MNST', 'ABNB', 'MCHP', 'FTNT', 'AEP',
    'CHTR', 'CSX', 'PCAR', 'PAYX', 'KDP', 'NXPI', 'AZN', 'CPRT', 'ADSK', 'MRNA',
    'CRWD', 'KHC', 'PDD', 'ROST', 'DXCM', 'MRVL', 'ODFL', 'WDAY', 'IDXX', 'LULU',
    'EXC', 'BIIB', 'CSGP', 'EA', 'FAST', 'VRSK', 'ILMN', 'XEL', 'CTSH', 'GEHC',
    'BKR', 'FANG', 'ZS', 'ANSS', 'TEAM', 'DDOG', 'WBD', 'DLTR', 'ALGN', 'EBAY',
    'GFS', 'TTWO', 'WBA', 'SIRI', 'LCID', 'JD', 'RIVN', 'ZM', 'ENPH', 'SPLK',
]

# 道琼斯30成分股
DOW30_SYMBOLS = [
    'AAPL', 'AMGN', 'AXP', 'BA', 'CAT', 'CRM', 'CSCO', 'CVX', 'DIS', 'DOW',
    'GS', 'HD', 'HON', 'IBM', 'INTC', 'JNJ', 'JPM', 'KO', 'MCD', 'MMM',
    'MRK', 'MSFT', 'NKE', 'PG', 'TRV', 'UNH', 'V', 'VZ', 'WBA', 'WMT',
]

# 热门成长股/Meme股
HOT_GROWTH_SYMBOLS = [
    'PLTR', 'SNOW', 'NET', 'COIN', 'HOOD', 'SOFI', 'AFRM', 'UPST', 'MSTR', 'SMCI',
    'ARM', 'AI', 'PATH', 'SOUN', 'IONQ', 'RGTI', 'QUBT', 'BBAI', 'RKLB', 'LUNR',
    'ASTS', 'RDW', 'JOBY', 'ACHR', 'LILM', 'EVTL', 'GME', 'AMC', 'BB', 'NOK',
    'SPCE', 'PLUG', 'FCEL', 'BE', 'CHPT', 'BLNK', 'EVGO', 'QS', 'LCID', 'RIVN',
    'NIO', 'XPEV', 'LI', 'GOEV', 'FSR', 'FFIE', 'MULN', 'WKHS', 'RIDE', 'NKLA',
]

def save_stock_lists():
    """保存各指数股票列表"""
    output_dir = LISTS_DIR
    
    # 去重并合并
    sp500_set = set(SP500_SYMBOLS)
    nasdaq100_set = set(NASDAQ100_SYMBOLS)
    dow30_set = set(DOW30_SYMBOLS)
    hot_growth_set = set(HOT_GROWTH_SYMBOLS)
    
    # 优先级股票池（标普500 + 纳斯达克100 去重）
    priority_stocks = list(sp500_set | nasdaq100_set | dow30_set)
    priority_stocks.sort()
    
    # 全部股票池（包含热门成长股）
    all_priority = list(sp500_set | nasdaq100_set | dow30_set | hot_growth_set)
    all_priority.sort()
    
    # 保存标普500
    with open(output_dir / 'sp500.txt', 'w') as f:
        f.write(f"# 标普500成分股 ({len(sp500_set)} 只)\n\n")
        for symbol in sorted(sp500_set):
            f.write(f"{symbol}\n")
    logger.info(f"标普500: {len(sp500_set)} 只股票")
    
    # 保存纳斯达克100
    with open(output_dir / 'nasdaq100.txt', 'w') as f:
        f.write(f"# 纳斯达克100成分股 ({len(nasdaq100_set)} 只)\n\n")
        for symbol in sorted(nasdaq100_set):
            f.write(f"{symbol}\n")
    logger.info(f"纳斯达克100: {len(nasdaq100_set)} 只股票")
    
    # 保存道琼斯30
    with open(output_dir / 'dow30.txt', 'w') as f:
        f.write(f"# 道琼斯30成分股 ({len(dow30_set)} 只)\n\n")
        for symbol in sorted(dow30_set):
            f.write(f"{symbol}\n")
    logger.info(f"道琼斯30: {len(dow30_set)} 只股票")
    
    # 保存热门成长股
    with open(output_dir / 'hot_growth.txt', 'w') as f:
        f.write(f"# 热门成长股/Meme股 ({len(hot_growth_set)} 只)\n\n")
        for symbol in sorted(hot_growth_set):
            f.write(f"{symbol}\n")
    logger.info(f"热门成长股: {len(hot_growth_set)} 只股票")
    
    # 保存优先股票池
    with open(output_dir / 'priority_stocks.txt', 'w') as f:
        f.write(f"# 优先筛选股票池 (标普500 + 纳斯达克100 + 道琼斯30)\n")
        f.write(f"# 共 {len(priority_stocks)} 只股票\n\n")
        for symbol in priority_stocks:
            f.write(f"{symbol}\n")
    logger.info(f"优先股票池: {len(priority_stocks)} 只股票")
    
    # 保存全部优先股票池（包含热门成长股）
    with open(output_dir / 'all_priority_stocks.txt', 'w') as f:
        f.write(f"# 全部优先筛选股票池\n")
        f.write(f"# 标普500 + 纳斯达克100 + 道琼斯30 + 热门成长股\n")
        f.write(f"# 共 {len(all_priority)} 只股票\n\n")
        for symbol in all_priority:
            f.write(f"{symbol}\n")
    logger.info(f"全部优先股票池: {len(all_priority)} 只股票")
    
    # 保存为JSON格式
    stock_data = {
        'sp500': sorted(list(sp500_set)),
        'nasdaq100': sorted(list(nasdaq100_set)),
        'dow30': sorted(list(dow30_set)),
        'hot_growth': sorted(list(hot_growth_set)),
        'priority': priority_stocks,
        'all_priority': all_priority
    }
    
    with open(output_dir / 'index_stocks.json', 'w') as f:
        json.dump(stock_data, f, indent=2)
    
    print("\n" + "=" * 50)
    print("股票池统计")
    print("=" * 50)
    print(f"  标普500: {len(sp500_set)} 只")
    print(f"  纳斯达克100: {len(nasdaq100_set)} 只")
    print(f"  道琼斯30: {len(dow30_set)} 只")
    print(f"  热门成长股: {len(hot_growth_set)} 只")
    print(f"  优先股票池(去重): {len(priority_stocks)} 只")
    print(f"  全部优先(含成长股): {len(all_priority)} 只")
    print("=" * 50)
    
    return stock_data


if __name__ == '__main__':
    save_stock_lists()
