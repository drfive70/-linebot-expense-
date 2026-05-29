import os
import json
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, FlexMessage, FlexContainer
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

    # 取得聊天室 ID
    source = event.source
    if source.type == 'group':
        room_id = source.group_id
    elif source.type == 'room':
        room_id = source.room_id
    else:
        room_id = source.user_id

    messages = process_command(text)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages
            )
        )


def process_command(text):
    """回傳 LINE Message 物件列表"""

    # ── 銷帳確認中，只接受「確認」或「取消」 ──
    if expense_manager.is_pending_clear():
        if text in ['確認', '確定']:
            return [TextMessage(text=expense_manager.confirm_clear())]
        elif text in ['取消', '算了']:
            return [TextMessage(text=expense_manager.cancel_clear())]
        else:
            return [TextMessage(text="⚠️ 請輸入「確認」完成銷帳，或「取消」保留帳目。")]

    # ── 記帳解析：格式 心怡:麥當勞120 ──
    parsed = expense_manager.parse_expense(text)
    if parsed:
        debtor, description, amount = parsed
        reply = expense_manager.add_expense(debtor, description, amount)
        return [TextMessage(text=reply)]

    cmd = text.strip()

    # ── 結算 ──
    if cmd == '結算':
        summary, detail_text = expense_manager.get_balance()
        if detail_text is None:
            return [TextMessage(text=summary)]
        return [build_balance_flex(summary, detail_text)]

    # ── 消費紀錄 ──
    elif cmd == '消費紀錄':
        return [TextMessage(text=expense_manager.get_history())]

    # ── 銷帳 ──
    elif cmd == '銷帳':
        msg, need_flex = expense_manager.request_clear()
        if not need_flex:
            return [TextMessage(text=msg)]
        return [build_clear_confirm_flex()]

    # ── 歷史訊息 ──
    elif cmd == '歷史訊息':
        return [TextMessage(text=expense_manager.get_history_log())]

    # ── 幫助 ──
    elif cmd in ['幫助', 'help', '？', '?']:
        return [TextMessage(text=(
            "📒 記帳Bot 使用說明\n"
            "──────────────────\n"
            "➕ 記錄欠款：\n"
            "  [欠款方]:[說明][金額]\n"
            "  例：心怡:麥當勞120\n"
            "  例：70:早餐200\n\n"
            "💰 查看結算：\n"
            "  結算\n\n"
            "📋 查看消費紀錄：\n"
            "  消費紀錄\n\n"
            "🗑️ 銷帳（清空所有帳目）：\n"
            "  銷帳\n\n"
            "📂 查看歷史銷帳紀錄：\n"
            "  歷史訊息"
        ))]

    else:
        return [TextMessage(text="不認識這個指令 😅\n輸入「幫助」查看所有指令")]


# ────────────────────────────────────────────
# Flex Message 建構函式
# ────────────────────────────────────────────

def build_balance_flex(summary, detail_text):
    """結算 Flex Message：摘要 + 可展開明細"""
    detail_lines = detail_text.split('\n')
    detail_body_contents = [
        {
            "type": "text",
            "text": line,
            "size": "sm",
            "color": "#555555",
            "wrap": True
        }
        for line in detail_lines
    ]

    flex_content = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "💰 結算",
                    "weight": "bold",
                    "size": "md",
                    "color": "#ffffff"
                }
            ],
            "backgroundColor": "#27AE60",
            "paddingAll": "12px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": summary,
                    "weight": "bold",
                    "size": "lg",
                    "wrap": True,
                    "color": "#1a1a1a"
                },
                {
                    "type": "separator"
                },
                {
                    "type": "text",
                    "text": "▼ 明細",
                    "size": "sm",
                    "color": "#888888",
                    "margin": "sm"
                },
                *detail_body_contents
            ]
        }
    }

    return FlexMessage(
        alt_text=summary,
        contents=FlexContainer.from_dict(flex_content)
    )


def build_clear_confirm_flex():
    """銷帳確認 Flex Message"""
    flex_content = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "⚠️ 確認銷帳",
                    "weight": "bold",
                    "size": "md",
                    "color": "#ffffff"
                }
            ],
            "backgroundColor": "#E74C3C",
            "paddingAll": "12px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "餐費是否結清？",
                    "weight": "bold",
                    "size": "md",
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": "銷帳後所有明細將會消失，此操作無法復原。",
                    "size": "sm",
                    "color": "#888888",
                    "wrap": True
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "message",
                        "label": "取消",
                        "text": "取消"
                    }
                },
                {
                    "type": "button",
                    "style": "primary",
                    "height": "sm",
                    "color": "#E74C3C",
                    "action": {
                        "type": "message",
                        "label": "確認銷帳",
                        "text": "確認"
                    }
                }
            ]
        }
    }

    return FlexMessage(
        alt_text="⚠️ 餐費是否結清？銷帳後明細會消失",
        contents=FlexContainer.from_dict(flex_content)
    )


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
