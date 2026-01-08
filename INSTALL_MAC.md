# 📊 股票筛选系统 - Mac 安装指南

## 快速安装

```bash
# 1. 克隆代码
git clone https://github.com/hyfhx/stock-screener.git
cd stock-screener

# 2. 运行安装脚本（只安装Python依赖）
chmod +x setup.sh
./setup.sh
```

就这么简单！所有文件都在 `stock-screener` 目录里，不需要安装到系统目录。

## 使用方法

进入 `stock-screener` 目录后：

```bash
# 立即运行一次筛选
./screener.sh run

# 启动每日定时任务
./screener.sh start

# 停止定时任务
./screener.sh stop

# 查看状态
./screener.sh status

# 查看日志
./screener.sh logs

# 设置运行时间
./screener.sh schedule

# 编辑配置文件
./screener.sh config

# 测试Telegram通知
./screener.sh test
```

## 配置Telegram通知

运行 `./screener.sh config` 或直接编辑 `config.json`：

```json
{
    "telegram": {
        "enabled": true,
        "bot_token": "YOUR_BOT_TOKEN_HERE",
        "chat_id": "YOUR_CHAT_ID_HERE"
    },
    "schedule": {
        "enabled": true,
        "run_time": "06:00"
    },
    "screener": {
        "min_score": 40,
        "top_n": 20
    }
}
```

## 设置运行时间

```bash
./screener.sh schedule
```

输入时间（24小时制），例如：
- `06:00` - 每天早上6点
- `09:30` - 每天开盘时
- `16:00` - 每天收盘后

## 文件结构

```
stock-screener/
├── setup.sh              # 安装脚本（只需运行一次）
├── screener.sh           # 控制脚本（日常使用）
├── screener_local.py     # 筛选程序
├── config.json           # 配置文件（自动创建）
├── priority_stocks.txt   # 股票列表
├── data/                 # 数据目录（自动创建）
│   └── screener.db       # SQLite数据库
├── logs/                 # 日志目录（自动创建）
└── reports/              # 报告目录（自动创建）
```

## 更新程序

```bash
cd stock-screener
git pull
```

## 卸载

```bash
# 停止定时任务
./screener.sh stop

# 删除目录
cd ..
rm -rf stock-screener
```

## 常见问题

### Q: 提示 "python3: command not found"

安装Python：
```bash
brew install python3
```

### Q: 定时任务没有运行

检查状态：
```bash
./screener.sh status
```

重新启动：
```bash
./screener.sh stop
./screener.sh start
```

### Q: 如何修改运行时间？

```bash
./screener.sh schedule
```

## 技术支持

- GitHub: https://github.com/hyfhx/stock-screener
- Issues: https://github.com/hyfhx/stock-screener/issues
