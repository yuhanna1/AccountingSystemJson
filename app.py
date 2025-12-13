#app.py
from flask import Flask, request, abort

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    TemplateMessage,
    ButtonsTemplate,
    PostbackAction,
    MulticastRequest,
    PushMessageRequest
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    FollowEvent,
    PostbackEvent
)

from services.json_store import add_transaction

app = Flask(__name__)

configuration = Configuration(access_token='LAU/pl0+Tk9yP0KOr4u4AVE6bAf/xJRGsx8zTCzYj6JwsOjgzdvx964IvNZS6cpCEsxJeR/kaGJDVJsEEd9m6TVZZvotBYbB+8V75nw1alI1CMqYiZgkLRG6lLDk3Wa/IIIQTxPtoQRnhutopzppcQdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('7d9c922a4e31502546357a3109a4d6e4')


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

#加入好友事件
@handler.add(FollowEvent)
def handle_follow(event):
    print(f'Got {event.type} event')

#訊息事件
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    print("👉 收到訊息：", text)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

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

            reply_text = (
                f"✅ 已記錄\n"
                f"類別：{category}\n"
                f"金額：{amount}\n"
                f"備註：{memo if memo else '無'}"
            )

        except Exception as e:
            print("❌ 錯誤：", e)
            reply_text = (
                "❌ 輸入格式錯誤\n"
                "請輸入：餐飲 120 炒飯"
            )

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )


'''@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=event.message.text)]
            )
        )'''
if __name__ == "__main__":
    app.run()