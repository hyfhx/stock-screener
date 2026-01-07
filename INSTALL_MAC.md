# 📊 股票筛选系统 - Mac 安装指南

## 一键安装

### 方法1：下载安装包

1. 下载 `stock-screener-mac.zip` 并解压
2. 打开终端，进入解压目录
3. 运行安装脚本：

```bash
chmod +x install_mac.sh
./install_mac.sh
```

### 方法2：从GitHub安装

```bash
git clone https://github.com/hyfhx/stock-screener.git
cd stock-screener
chmod +x install_mac.sh
./install_mac.sh
```

## 安装过程

安装脚本会自动：
1. ✅ 检查Python环境
2. ✅ 安装Python依赖（yfinance, pandas, numpy）
3. ✅ 创建安装目录 `~/stock-screener`
4. ✅ 复制程序文件
5. ✅ 配置Telegram通知（可选）
6. ✅ 创建全局命令 `screener`

## 使用方法

### 常用命令

```bash
# 立即运行一次筛选
screener run

# 设置每日运行时间
screener schedule

# 启动定时任务服务
screener start

# 停止定时任务服务
screener stop

# 查看状态
screener status

# 查看日志
screener logs

# 编辑配置
screener config
```

### 设置运行时间

```bash
screener schedule
```

系统会提示输入运行时间（24小时制，美东时间），例如：
- `06:00` - 每天早上6点运行
- `09:30` - 每天开盘时运行
- `16:00` - 每天收盘后运行

### 立即测试

```bash
screener run
```

## 配置文件

配置文件位于 `~/stock-screener/config.json`

### 筛选参数

```json
{
  "screening": {
    "min_price": 5.0,        // 最低价格
    "max_price": 1000.0,     // 最高价格
    "min_volume": 500000,    // 最低成交量
    "min_score": 40          // 最低评分
  }
}
```

### 信号权重

```json
{
  "weights": {
    "ma_golden_cross": 30,     // MA金叉
    "macd_golden_cross": 25,   // MACD金叉
    "rsi_reversal": 20,        // RSI反弹
    "volume_surge": 15,        // 成交量放大
    "price_breakout_52w": 20,  // 52周高点突破
    "price_breakout_20d": 10,  // 20日高点突破
    "trend_continuation": 15,  // 趋势持续
    "obv_confirm": 10          // OBV确认
  }
}
```

### Telegram通知

```json
{
  "notification": {
    "telegram": {
      "enabled": true,
      "bot_token": "YOUR_BOT_TOKEN",
      "chat_id": "YOUR_CHAT_ID"
    }
  }
}
```

## 自定义股票池

编辑 `~/stock-screener/priority_stocks.txt`，每行一个股票代码：

```
# 科技股
AAPL
MSFT
GOOGL

# 半导体
NVDA
AMD
MU
```

## 文件目录

```
~/stock-screener/
├── screener_local.py      # 筛选程序
├── config.json            # 配置文件
├── priority_stocks.txt    # 股票列表
├── screener               # 控制脚本
├── run_daily.sh           # 每日运行脚本
├── data/                  # 数据库
├── logs/                  # 日志
└── reports/               # 报告
    └── daily/
```

## 查看结果

### 查看日志

```bash
screener logs
```

### 查看报告

报告保存在 `~/stock-screener/reports/` 目录，格式为 JSON。

## 卸载

```bash
screener uninstall
```

## 常见问题

### Q: 提示"未找到Python3"

安装Python：
```bash
brew install python3
```

### Q: 提示权限不足

```bash
chmod +x install_mac.sh
chmod +x ~/stock-screener/screener
```

### Q: 定时任务不运行

检查launchd服务状态：
```bash
launchctl list | grep stockscreener
```

重新加载服务：
```bash
screener stop
screener start
```

### Q: 如何更新程序

```bash
cd ~/stock-screener
git pull origin main
```

## 技术支持

- GitHub: https://github.com/hyfhx/stock-screener
- Issues: https://github.com/hyfhx/stock-screener/issues
