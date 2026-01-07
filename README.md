# 📊 股票筛选盯盘系统 V3

一个自动化的股票筛选和盯盘系统，支持全美股筛选，能够程序化发现有上涨潜力的股票，并通过Telegram发送提醒。

## ✨ 功能特点

### 🔍 分级筛选
- **优先筛选**：标普500 + 纳斯达克100 + 热门成长股（约500只）
- **扩展筛选**：全美股（约11000只）
- **自定义筛选**：支持自定义股票池

### 📈 技术指标
- **移动平均线金叉检测** (MA20/MA50)
- **MACD金叉/多头排列**
- **RSI动量分析**
- **成交量异动检测**
- **52周高点突破检测**
- **OBV趋势确认**
- **趋势持续性检测**（V3新增）
- **信号质量分级**（V3新增：A/B/C级）

### 🔇 降噪优化（V3）
- 提高入选门槛（评分≥40）
- 强化金叉等强信号权重
- 移除弱信号干扰
- 信号质量分级（A/B/C）

### ⏱️ 运行时间追踪
- 每次筛选记录运行时间
- 自动监控性能
- 超时自动告警

### 📱 自动通知
- **Telegram实时推送**
- 高分股票即时提醒
- 每日汇总报告
- 每周分析报告

### 📊 智能追踪
- **结果持久化存储** (SQLite数据库)
- **7日表现追踪**
- **准确性统计分析**
- **自动模型优化**

## 🔐 安全配置

**重要**：敏感信息通过环境变量配置，不要将凭证提交到代码库！

### 环境变量

```bash
# Telegram通知配置
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"
```

### 配置文件

复制模板文件并填入您的配置：

```bash
cp config.json.example config.json
# 编辑 config.json 填入您的配置
```

**注意**：`config.json` 已被 `.gitignore` 忽略，不会被提交到仓库。

## 📁 文件结构

```
stock_screener/
├── run.py                 # 启动脚本（推荐使用）
├── screener_v3.py         # V3核心筛选程序（降噪版）
├── screener_v2.py         # V2筛选程序
├── stock_screener.py      # V1筛选程序
├── scheduler.py           # 调度运行脚本
├── data_store.py          # 数据持久化模块
├── daily_report.py        # 每日汇总报告
├── weekly_analysis.py     # 每周分析和模型优化
├── fetch_index_stocks.py  # 获取指数成分股
├── fetch_all_stocks.py    # 获取全美股列表
│
├── config.json.example    # 配置文件模板
├── config.json            # 配置文件（不提交到Git）
├── .gitignore             # Git忽略文件
│
├── 股票池文件
│   ├── priority_stocks.txt    # 优先股票池（标普500+纳斯达克100）
│   ├── all_priority_stocks.txt # 全部优先（含热门成长股）
│   ├── all_us_stocks.txt      # 全美股列表
│   ├── sp500.txt              # 标普500
│   ├── nasdaq100.txt          # 纳斯达克100
│   └── hot_growth.txt         # 热门成长股
│
├── data/                  # 数据库目录（不提交到Git）
│   └── screener.db        # SQLite数据库
│
└── reports/               # 报告目录（不提交到Git）
    ├── hourly/            # 每小时筛选报告
    ├── daily/             # 每日汇总报告
    └── weekly/            # 每周分析报告
```

## 🚀 快速开始

### 1. 设置环境变量

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

### 2. 运行优先筛选（推荐）

```bash
cd /home/ubuntu/stock_screener

# 使用启动脚本（自动初始化环境）
python3 run.py priority

# 或直接使用调度器
python3 scheduler.py priority
```

### 3. 运行扩展筛选（全美股）

```bash
python3 run.py extended
```

### 4. 生成日报

```bash
python3 run.py daily
```

### 5. 运行周分析

```bash
python3 run.py weekly
```

## ⏰ 定时任务

系统已配置以下定时任务：

| 任务 | 时间 | 说明 |
|------|------|------|
| 优先筛选 | 周一至周五 9:30-15:30 每小时 | 筛选标普500+纳斯达克100 |
| 每日汇总 | 每天早上 6:00 | 汇总前一天结果并发送Telegram |
| 每周分析 | 每周五 20:00 | 分析准确性并优化模型 |

## 📊 股票池统计

| 股票池 | 数量 | 说明 |
|--------|------|------|
| 标普500 | 436只 | 美国500强上市公司 |
| 纳斯达克100 | 100只 | 纳斯达克最大100家非金融公司 |
| 道琼斯30 | 30只 | 美国30家大型蓝筹股 |
| 热门成长股 | 50只 | AI、电动车、Meme股等 |
| 优先股票池 | 504只 | 以上去重合并 |
| 全美股 | 11650只 | 纳斯达克+纽交所+AMEX |

## ⚙️ 配置说明

### config.json.example

```json
{
  "screening": {
    "min_price": 5.0,
    "max_price": 500.0,
    "min_volume": 500000,
    "volume_surge_ratio": 1.5
  },
  "weights": {
    "ma_golden_cross": 25,
    "macd_golden_cross": 20,
    "rsi_bullish": 15,
    "volume_surge": 15,
    "price_breakout": 15,
    "obv_confirm": 10
  },
  "notification": {
    "telegram": {
      "enabled": true,
      "bot_token": "YOUR_BOT_TOKEN_HERE",
      "chat_id": "YOUR_CHAT_ID_HERE"
    }
  }
}
```

## 📈 评分系统

| 评分范围 | 等级 | 信号质量 | 说明 |
|---------|------|---------|------|
| ≥70 | 🔥 高分 | A级 | 多个强势信号叠加，重点关注 |
| 50-69 | ⭐ 中分 | B级 | 有上涨迹象，可以跟踪 |
| 40-49 | 普通 | C级 | 信号较弱，谨慎对待 |

## ⏱️ 运行时间参考

| 股票池 | 数量 | 预计耗时 |
|--------|------|---------|
| 优先股票池 | 504只 | ~25秒 |
| 全美股 | 11650只 | ~10-15分钟 |

## 🔧 模型自动优化

每周五系统会：
1. 统计各类信号的准确率
2. 检测是否存在过拟合
3. 根据表现自动调整权重
4. 生成详细分析报告

## ⚠️ 风险提示

**本系统仅供技术分析参考，不构成任何投资建议。**

- 股市有风险，投资需谨慎
- 历史表现不代表未来收益
- 请结合基本面分析做出投资决策
- 建议设置止损，控制风险

## 📝 更新日志

### v3.0.0 (2026-01-07)
- 🔇 降噪优化：减少35%噪声信号
- 📊 信号质量分级（A/B/C）
- 🔐 安全更新：敏感信息改为环境变量配置
- 📁 添加 `.gitignore` 和配置模板
- 🔄 趋势持续性检测

### v2.0.0 (2026-01-07)
- 支持全美股筛选（11000+只）
- 分级筛选策略（优先/扩展）
- 运行时间追踪和监控
- 性能优化（并行处理）
- 超时自动告警

### v1.0.0 (2026-01-07)
- 初始版本发布
- 支持6种技术指标筛选
- Telegram通知功能

## 🤝 贡献指南

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📄 License

MIT License
