# Flask 入口與 Webhook 設定
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    TextMessage, ImageMessage, MessagingApiBlob,
    QuickReply, QuickReplyItem, MessageAction,
    FlexMessage, FlexContainer, ConfirmTemplate,
    TemplateMessage, PostbackAction
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent, PostbackEvent
import handlers
import requests
import json

app = Flask(__name__)

# --- 配置資訊 ---
CHANNEL_ACCESS_TOKEN = 'LAU/pl0+Tk9yP0KOr4u4AVE6bAf/xJRGsx8zTCzYj6JwsOjgzdvx964IvNZS6cpCEsxJeR/kaGJDVJsEEd9m6TVZZvotBYbB+8V75nw1alI1CMqYiZgkLRG6lLDk3Wa/IIIQTxPtoQRnhutopzppcQdB04t89/1O/w1cDnyilFU='
CHANNEL_SECRET = '7d9c922a4e31502546357a3109a4d6e4'

config = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# 定義重複使用的教學訊息
WELCOME_TEXT = (
    "🌟 您好！歡迎使用「記帳助手」🌟\n\n"
    "🚀 快速上手指南：\n"
    "1.【直接記帳】：輸入「金額 備註」，例如「100 宵夜」\n"
    "2.【選擇類別】：輸入金額後點選彈出的按鈕\n"
    "3.【設定預算】：輸入「設定 類別 金額」，例如「設定 飲食 5000」\n"
    "4.【查看報告】：點擊下方選單按鈕\n\n"
    "💡 現在就輸入一個數字試試看吧！"
)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 加入好友事件：發送教學訊息
@handler.add(FollowEvent)
def handle_follow(event):
    with ApiClient(config) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=WELCOME_TEXT)]
            )
        )

@handler.add(MessageEvent, message=TextMessageContent)
def handle_msg(event):
    with ApiClient(config) as api_client:
        line_bot_api = MessagingApi(api_client)
        handlers.handle_text_logic(line_bot_api, event)

@handler.add(PostbackEvent)
def handle_post(event):
    with ApiClient(config) as api_client:
        line_bot_api = MessagingApi(api_client)
        handlers.handle_postback_logic(line_bot_api, event)

# --- 圖文選單建立 ---
def create_rich_menu():
    with ApiClient(config) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_blob_api = MessagingApiBlob(api_client)
        headers = {'Authorization': 'Bearer ' + CHANNEL_ACCESS_TOKEN, 'Content-Type': 'application/json'}
        body = {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "記帳選單",
            "chatBarText": "點我開始記帳",
            "areas": [
                {"bounds": {"x": 0, "y": 0, "width": 2500, "height": 845}, "action": {"type": "message", "text": "使用教學"}},
                {"bounds": {"x": 0, "y": 845, "width": 849, "height": 841}, "action": {"type": "message", "text": "設定額度"}},
                {"bounds": {"x": 840, "y": 845, "width": 824, "height": 836}, "action": {"type": "message", "text": "本月花費"}},
                {"bounds": {"x": 1663, "y": 845, "width": 837, "height": 841}, "action": {"type": "message", "text": "圖表"}}
            ]
        }
        try:
            res = requests.post('https://api.line.me/v2/bot/richmenu', headers=headers, data=json.dumps(body).encode('utf-8'))
            rid = res.json()['richMenuId']
            with open('static/richmenu-1.png', 'rb') as img:
                line_bot_blob_api.set_rich_menu_image(rich_menu_id=rid, body=bytearray(img.read()), _headers={'Content-Type': 'image/png'})
            line_bot_api.set_default_rich_menu(rid)
        except:
            print("Rich Menu 處理跳過")

if __name__ == "__main__":
    # create_rich_menu() # 需要更新選單時再拿掉註解
    app.run(port=5000)