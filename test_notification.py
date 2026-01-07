#!/usr/bin/env python3
"""
通知功能测试脚本
"""

import sys
sys.path.append('/opt/.manus/.sandbox-runtime')

import json
import requests
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path


def load_config():
    """加载配置"""
    config_path = Path('/home/ubuntu/stock_screener/config.json')
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}


def test_telegram():
    """测试Telegram通知"""
    config = load_config()
    tg_config = config.get('notification', {}).get('telegram', {})
    
    if not tg_config.get('bot_token') or not tg_config.get('chat_id'):
        print("❌ Telegram配置不完整，请先在config.json中配置bot_token和chat_id")
        return False
    
    bot_token = tg_config['bot_token']
    chat_id = tg_config['chat_id']
    
    test_message = f"""
📊 <b>股票筛选系统测试</b>

🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
✅ Telegram通知配置成功！

这是一条测试消息，如果你收到了，说明通知功能正常工作。
"""
    
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                'chat_id': chat_id,
                'text': test_message,
                'parse_mode': 'HTML'
            }
        )
        
        if response.status_code == 200:
            print("✅ Telegram测试消息发送成功！")
            return True
        else:
            print(f"❌ Telegram发送失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Telegram发送异常: {e}")
        return False


def test_email():
    """测试邮件通知"""
    config = load_config()
    email_config = config.get('notification', {}).get('email', {})
    
    required = ['smtp_server', 'smtp_port', 'sender', 'password', 'recipients']
    missing = [k for k in required if not email_config.get(k)]
    
    if missing:
        print(f"❌ 邮件配置不完整，缺少: {', '.join(missing)}")
        return False
    
    test_message = f"""
股票筛选系统测试

时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
状态: 邮件通知配置成功！

这是一条测试邮件，如果你收到了，说明邮件通知功能正常工作。
"""
    
    try:
        msg = MIMEMultipart()
        msg['From'] = email_config['sender']
        msg['To'] = ', '.join(email_config['recipients'])
        msg['Subject'] = f"📈 股票筛选系统测试 - {datetime.now().strftime('%Y-%m-%d')}"
        
        msg.attach(MIMEText(test_message, 'plain', 'utf-8'))
        
        with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
            server.starttls()
            server.login(email_config['sender'], email_config['password'])
            server.send_message(msg)
        
        print("✅ 测试邮件发送成功！")
        return True
        
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='测试通知功能')
    parser.add_argument('--telegram', action='store_true', help='测试Telegram通知')
    parser.add_argument('--email', action='store_true', help='测试邮件通知')
    parser.add_argument('--all', action='store_true', help='测试所有通知方式')
    
    args = parser.parse_args()
    
    if args.all or (not args.telegram and not args.email):
        print("=" * 40)
        print("测试所有通知方式")
        print("=" * 40)
        test_telegram()
        print()
        test_email()
    else:
        if args.telegram:
            test_telegram()
        if args.email:
            test_email()


if __name__ == '__main__':
    main()
