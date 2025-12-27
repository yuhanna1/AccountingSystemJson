from flask import Flask, request, abort
import requests
import json
import urllib.parse

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    TextMessage, ImageMessage, MessagingApiBlob
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

# 匯入你的服務模組
from services.json_store import add_transaction, get_user_transactions
from services.chart import generate_expense_pie_chart

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = 'LAU/pl0+Tk9yP0KOr4u4AVE6bAf/xJRGsx8zTCzYj6JwsOjgzdvx964IvNZS6cpCEsxJeR/kaGJDVJsEEd9m6TVZZvotBYbB+8V75nw1alI1CMqYiZgkLRG6lLDk3Wa/IIIQTxPtoQRnhutopzppcQdB04t89/1O/w1cDnyilFU='
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler('7d9c922a4e31502546357a3109a4d6e4')

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(FollowEvent)
def handle_follow(event):
    print(f'Got {event.type} event')

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        # --- A. 處理「圖表」按鈕點擊 ---
        if text == "圖表":
            records = get_user_transactions(user_id)
            chart_url = generate_expense_pie_chart(records)
            
            if chart_url:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            TextMessage(text="📊 這是您的消費分析圓餅圖："),
                            ImageMessage(original_content_url=chart_url, preview_image_url=chart_url)
                        ]
                    )
                )
            else:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="查無消費紀錄，請先開始記帳喔！")]
                    )
                )
            return

        # --- B. 原有的記帳功能邏輯 ---
        try:
            parts = text.split()
            if len(parts) < 2:
                raise ValueError("格式錯誤")

            category = parts[0]
            amount = int(parts[1])
            memo = " ".join(parts[2:]) if len(parts) > 2 else ""

            data = {
                "category": category,
                "amount": amount,
                "type": "expense",
                "memo": memo
            }

            add_transaction(user_id, data)
            reply_text = f"✅ 已記錄\n類別：{category}\n金額：{amount}\n備註：{memo if memo else '無'}"

        except Exception as e:
            # 如果不是符合記帳格式，也不是「圖表」，才噴錯誤訊息
            reply_text = "❌ 輸入格式錯誤\n請輸入：餐飲 120 炒飯\n或點選選單中的「圖表」按鈕"

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

# Rich Menu 建立程式碼 (保留你原本的邏輯)
def create_rich_menu():
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_blob_api = MessagingApiBlob(api_client)

        headers = {
            'Authorization': 'Bearer ' + CHANNEL_ACCESS_TOKEN,
            'Content-Type': 'application/json'
        }
        body = {
            "size": {"width": 2500, "height": 843},
            "selected": True,
            "name": "圖文選單 1",
            "chatBarText": "查看更多資訊",
            "areas": [
                {"bounds": {"x": 0, "y": 0, "width": 841, "height": 843}, "action": {"type": "message", "text": "設定額度"}},
                {"bounds": {"x": 836, "y": 0, "width": 832, "height": 843}, "action": {"type": "message", "text": "本月花費"}},
                {"bounds": {"x": 1664, "y": 0, "width": 836, "height": 843}, "action": {"type": "message", "text": "圖表"}}
            ]
        }

        try:
            response = requests.post('https://api.line.me/v2/bot/richmenu', headers=headers, data=json.dumps(body).encode('utf-8'))
            rich_menu_id = response.json()['richMenuId']
            with open('static/richmenu-1.png', 'rb') as image:
                line_bot_blob_api.set_rich_menu_image(
                    rich_menu_id=rich_menu_id,
                    body=bytearray(image.read()),
                    _headers={'Content-Type': 'image/png'}
                )
            line_bot_api.set_default_rich_menu(rich_menu_id)
        except Exception as e:
            print(f"Rich Menu Set Error or Already Exists: {e}")

if __name__ == "__main__":
    create_rich_menu() # 如果選單已設定好可註解掉
    app.run()