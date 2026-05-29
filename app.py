import os
import json
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from expense_manager import ExpenseManager

app = Flask(__name__)

configuration = Configuration(access_token=os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.environ.get('LINE_CHANNEL_SECRET'))
expense_manager = ExpenseManager()

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id
    reply = process_command(text, user_id)
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )

def process_command(text, user_id):
    parts = text.split()
    cmd = parts[0].lower() if parts else ''

    # 幫助指令
    if cmd in ['幫助', 'help', '？', '?']:
        return (
            "📒 飯錢記帳Bot 使用說明\n"
            "──────────────────\n"
            "➕ 記錄付款：\n"
            "  付 [名字] [金額] [說明]\n"
            "  例：付 小明 350 午餐\n\n"
            "📊 查看帳目：\n"
            "  帳目\n\n"
            "💰 查看結算：\n"
            "  結算\n\n"
            "✅ 標記已還清：\n"
            "  還清 [名字]\n\n"
            "🗑️ 刪除最後一筆：\n"
            "  刪除\n\n"
            "📋 查看所有紀錄：\n"
            "  歷史\n"
        )

    # 記錄付款：付 小明 350 午餐
    elif cmd == '付':
        if len(parts) < 3:
            return "格式錯誤！\n請輸入：付 [名字] [金額] [說明]\n例：付 小明 350 午餐"
        payer = parts[1]
        try:
            amount = float(parts[2])
        except ValueError:
            return "金額格式錯誤，請輸入數字。"
        description = parts[3] if len(parts) > 3 else '未填說明'
        result = expense_manager.add_expense(payer, amount, description)
        return result

    # 查看帳目
    elif cmd == '帳目':
        return expense_manager.get_summary()

    # 結算（誰欠誰多少）
    elif cmd == '結算':
        return expense_manager.get_balance()

    # 還清
    elif cmd == '還清':
        if len(parts) < 2:
            return "請輸入要還清的名字。\n例：還清 小明"
        person = parts[1]
        return expense_manager.clear_balance(person)

    # 刪除最後一筆
    elif cmd == '刪除':
        return expense_manager.delete_last()

    # 歷史紀錄
    elif cmd == '歷史':
        return expense_manager.get_history()

    else:
        return "不認識這個指令 😅\n輸入「幫助」查看所有指令"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
