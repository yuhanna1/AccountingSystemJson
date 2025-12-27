from flask import Flask, request, abort
import requests
import json
import os
from datetime import datetime

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    TextMessage, ImageMessage, MessagingApiBlob,
    QuickReply, QuickReplyItem, MessageAction,
    FlexMessage, FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

# 匯入自定義服務模組
from services.json_store import (
    add_transaction, 
    get_user_transactions, 
    set_budget, 
    get_user_budgets, 
    get_monthly_summary,
    delete_transaction
)
from services.chart import generate_expense_pie_chart

app = Flask(__name__)

# --- 配置資訊 ---
CHANNEL_ACCESS_TOKEN = 'LAU/pl0+Tk9yP0KOr4u4AVE6bAf/xJRGsx8zTCzYj6JwsOjgzdvx964IvNZS6cpCEsxJeR/kaGJDVJsEEd9m6TVZZvotBYbB+8V75nw1alI1CMqYiZgkLRG6lLDk3Wa/IIIQTxPtoQRnhutopzppcQdB04t89/1O/w1cDnyilFU='
CHANNEL_SECRET = '7d9c922a4e31502546357a3109a4d6e4'

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

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
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        welcome_text = (
            "🌟 您好！歡迎使用「記帳助手」🌟\n\n"
            "🚀 快速上手指南：\n"
            "1.【直接記帳】：輸入「金額 備註」，例如「100 宵夜」\n"
            "2.【選擇類別】：輸入金額後點選彈出的按鈕\n"
            "3.【設定預算】：輸入「設定 類別 金額」，例如「設定 飲食 5000」\n"
            "4.【查看報告】：點擊下方選單按鈕\n\n"
            "💡 現在就輸入一個數字試試看吧！"
        )
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=welcome_text)]
            )
        )

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        categories = ["飲食", "娛樂", "運動", "交通", "健康", "其他"]

        # 1. 功能：生成圓餅圖
        if text == "圖表":
            records = get_user_transactions(user_id)
            chart_url = generate_expense_pie_chart(records)
            if chart_url:
                messages = [
                    TextMessage(text="📊 這是您的消費分析圓餅圖："),
                    ImageMessage(original_content_url=chart_url, preview_image_url=chart_url)
                ]
            else:
                messages = [TextMessage(text="查無紀錄，請先開始記帳喔！")]
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=messages))
            return
        
        # 2. 功能：本月花費明細 (Flex Message)
        elif text == "本月花費":
            records = get_user_transactions(user_id)
            this_month = datetime.now().strftime("%Y-%m")
            monthly_records = [r for r in records if r["time"].startswith(this_month) and r["type"] == "expense"]
            monthly_records.reverse()
            
            if not monthly_records:
                line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="本月目前沒有消費紀錄喔！")]
                ))
                return

            contents = []
            for r in monthly_records:
                display_date = r['time'][5:10]
                item_box = {
                    "type": "box", "layout": "horizontal", "margin": "md", "spacing": "sm",
                    "contents": [
                        # 日期
                        {"type": "text", "text": display_date, "size": "xs", "color": "#aaaaaa", "flex": 2, "gravity": "center"},
                        # 類別
                        {"type": "text", "text": r['category'], "size": "sm", "flex": 2, "gravity": "center"},
                        # 金額
                        {"type": "text", "text": f"${r['amount']}", "size": "sm", "weight": "bold", "flex": 2, "align": "end", "gravity": "center"},
                        {
                            "type": "text",
                            "text": "🗑️",
                            "size": "lg",
                            "flex": 1,
                            "align": "center",
                            "gravity": "center",
                            "action": {
                                "type": "message",
                                "label": "刪除",
                                "text": f"刪除 {r['id']}"
                            }
                        }
                    ]
                }
                contents.append(item_box)
                contents.append({"type": "separator", "margin": "md"})

            # 定義 Flex Bubble 結構
            flex_bubble = {
                "type": "bubble",
                "header": {
                    "type": "box", "layout": "vertical",
                    "contents": [{"type": "text", "text": "📅 本月消費明細", "weight": "bold", "size": "xl", "color": "#1DB446"}]
                },
                "body": {"type": "box", "layout": "vertical", "contents": contents[:-1]}
            }

            # 使用 FlexMessage 與 FlexContainer 包裝 ---
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    FlexMessage(
                        alt_text="本月消費明細",
                        contents=FlexContainer.from_dict(flex_bubble)
                    )
                ]
            ))
            return
        
        # 3. 功能：刪除指令
        elif text.startswith("刪除"):
            parts = text.split()
            if len(parts) == 2:
                record_id = parts[1]
                if delete_transaction(user_id, record_id):
                    res_text = "✅ 紀錄已成功刪除！"
                else:
                    res_text = "❌ 刪除失敗，找不到該筆紀錄。"
            else:
                res_text = "⚠️ 請輸入正確格式：刪除 [ID]"
                
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=res_text)]
            ))
            return
        
        # 4. 功能：設定預算
        elif text == "設定額度":
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="💰 欲設定每月預算，請輸入「設定 類別 金額」\n例如：設定 飲食 5000")]
            ))
            return
        
        elif text.startswith("設定"):
            try:
                parts = text.split()
                category, amount = parts[1], int(parts[2])
                set_budget(user_id, category, amount)
                reply_text = f"✅ 已將【{category}】的每月額度設為 ${amount}"
            except:
                reply_text = "❌ 格式錯誤。範例：設定 飲食 5000"
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply_text)]))
            return

        # 5. 核心功能：金額輸入觸發 Quick Reply 或 完整記帳
        else:
            parts = text.split()
            if not parts: return

            # A. 判斷是否為純數字 (啟動快速類別選單)
            if parts[0].isdigit():
                amount = parts[0]
                memo = " ".join(parts[1:]) if len(parts) > 1 else ""
                
                quick_reply_items = [
                    QuickReplyItem(
                        action=MessageAction(label=cat, text=f"{cat} {amount} {memo}".strip())
                    ) for cat in categories
                ]
                
                line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(
                        text=f"💵 已輸入金額 ${amount}，請選擇類別：",
                        quick_reply=QuickReply(items=quick_reply_items)
                    )]
                ))
                return

            # B. 處理「類別 金額 備註」完整記帳格式
            try:
                if len(parts) < 2: raise ValueError()
                category, amount = parts[0], int(parts[1])
                memo = " ".join(parts[2:]) if len(parts) > 2 else ""

                add_transaction(user_id, {"category": category, "amount": amount, "type": "expense", "memo": memo})

                # 預算警示檢查
                summary = get_monthly_summary(user_id)
                budgets = get_user_budgets(user_id)
                curr_total = summary.get(category, 0)
                limit = budgets.get(category)
                
                warning = ""
                if limit:
                    limit = int(limit)
                    if curr_total >= limit:
                        warning = f"\n\n⚠️ 警告：{category}已達額度！(${curr_total}/${limit})"
                    elif curr_total >= limit * 0.8:
                        warning = f"\n\n🔔 提醒：{category}已達 80%！"

                reply_text = f"✅ 已記錄\n類別：{category}\n金額：{amount}\n備註：{memo if memo else '無'}" + warning

            except:
                reply_text = "❌ 格式錯誤\n請輸入「金額 備註」或點選選單功能。"

            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            ))

# --- 圖文選單建立 (執行一次即可) ---
def create_rich_menu():
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_blob_api = MessagingApiBlob(api_client)

        headers = {'Authorization': 'Bearer ' + CHANNEL_ACCESS_TOKEN, 'Content-Type': 'application/json'}
        body = {
            "size": {"width": 2500, "height": 843},
            "selected": True,
            "name": "記帳小幫手選單",
            "chatBarText": "點我開始記帳",
            "areas": [
                {"bounds": {"x": 0, "y": 0, "width": 841, "height": 843}, "action": {"type": "message", "text": "設定額度"}},
                {"bounds": {"x": 836, "y": 0, "width": 832, "height": 843}, "action": {"type": "message", "text": "本月花費"}},
                {"bounds": {"x": 1664, "y": 0, "width": 836, "height": 843}, "action": {"type": "message", "text": "圖表"}}
            ]
        }

        try:
            res = requests.post('https://api.line.me/v2/bot/richmenu', headers=headers, data=json.dumps(body).encode('utf-8'))
            rid = res.json()['richMenuId']
            with open('static/richmenu-1.png', 'rb') as img:
                line_bot_blob_api.set_rich_menu_image(rich_menu_id=rid, body=bytearray(img.read()), _headers={'Content-Type': 'image/png'})
            line_bot_api.set_default_rich_menu(rid)
            print("Rich Menu 建立成功")
        except:
            print("Rich Menu 可能已存在")

if __name__ == "__main__":
    # create_rich_menu() # 第一次執行後可註解掉
    app.run(port=5000)