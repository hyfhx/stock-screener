# Telegram Bot 设置指南

## 创建 Telegram Bot

### 步骤 1: 创建 Bot
1. 在 Telegram 中搜索 `@BotFather`
2. 发送 `/newbot` 命令
3. 按提示输入 Bot 名称（如：Stock Alert Bot）
4. 输入 Bot 用户名（必须以 `bot` 结尾，如：`my_stock_alert_bot`）
5. 创建成功后，BotFather 会返回一个 **Bot Token**，格式类似：
   ```
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
6. **保存这个 Token**

### 步骤 2: 获取 Chat ID
1. 在 Telegram 中搜索你刚创建的 Bot
2. 向 Bot 发送任意消息（如 `/start`）
3. 在浏览器中访问：
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
   将 `<YOUR_BOT_TOKEN>` 替换为你的 Token
4. 在返回的 JSON 中找到 `"chat":{"id":XXXXXXXX}`
5. 这个数字就是你的 **Chat ID**

### 步骤 3: 配置程序
编辑 `config.json` 文件，修改 Telegram 配置：

```json
{
  "notification": {
    "telegram": {
      "enabled": true,
      "bot_token": "你的Bot Token",
      "chat_id": "你的Chat ID"
    }
  }
}
```

## 测试通知

运行以下命令测试 Telegram 通知：

```bash
cd /home/ubuntu/stock_screener
python3 test_notification.py --telegram
```

## 群组通知

如果想在群组中接收通知：
1. 将 Bot 添加到群组
2. 在群组中发送任意消息
3. 使用 `getUpdates` API 获取群组的 Chat ID（通常是负数）
4. 将群组 Chat ID 填入配置

## 常见问题

**Q: 收不到消息？**
- 确保已向 Bot 发送过消息（激活对话）
- 检查 Bot Token 和 Chat ID 是否正确
- 确保 `enabled` 设置为 `true`

**Q: 如何获取群组 Chat ID？**
- 群组 Chat ID 通常是负数，如 `-123456789`
- 可以通过 `getUpdates` API 获取
