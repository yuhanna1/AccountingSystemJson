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
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=WELCOME_TEXT)]
            )
        )

# 訊息事件
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
        
        # 2. 功能：使用教學 (點擊 Rich Menu 或輸入觸發)
        elif text == "使用教學":
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=WELCOME_TEXT)]
            ))
            return

        # 3. 功能：本月花費明細 (Flex Message)
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
                        {"type": "text", "text": display_date, "size": "xs", "color": "#aaaaaa", "flex": 2, "gravity": "center"},
                        {"type": "text", "text": r['category'], "size": "sm", "flex": 2, "gravity": "center"},
                        {"type": "text", "text": f"${r['amount']}", "size": "sm", "weight": "bold", "flex": 2, "align": "end", "gravity": "center"},
                        {
                            "type": "text", "text": "🗑️", "size": "lg", "flex": 1, "align": "center", "gravity": "center",
                            "action": {"type": "message", "label": "刪除", "text": f"刪除 {r['id']}"}
                        }
                    ]
                }
                contents.append(item_box)
                contents.append({"type": "separator", "margin": "md"})

            flex_bubble = {
                "type": "bubble",
                "header": {
                    "type": "box", "layout": "vertical",
                    "contents": [{"type": "text", "text": "📅 本月消費明細", "weight": "bold", "size": "xl", "color": "#1DB446"}]
                },
                "body": {"type": "box", "layout": "vertical", "contents": contents[:-1]}
            }

            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(alt_text="本月消費明細", contents=FlexContainer.from_dict(flex_bubble))]
            ))
            return
        
        # 4. 功能：刪除與預算設定邏輯 (保持不變)
        elif text.startswith("刪除"):
            parts = text.split()
            if len(parts) == 2:
                res_text = "✅ 紀錄已成功刪除！" if delete_transaction(user_id, parts[1]) else "❌ 刪除失敗。"
            else:
                res_text = "⚠️ 格式：刪除 [ID]"
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=res_text)]))
            return
        
        elif text == "設定額度":
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="💰 請輸入「設定 類別 金額」\n例如：設定 飲食 5000")]))
            return
        
        elif text.startswith("設定"):
            try:
                parts = text.split()

                if len(parts) < 3:
                    raise ValueError("缺少金額")

                category, amount = parts[1], int(parts[2])
                set_budget(user_id, category, amount)

                reply_text = f"✅ 【{category}】額度設定成功！\n現在您可以開始記錄這筆花費了。"
            except:
                reply_text = "❌ 設定格式：設定 類別 金額\n例如：設定 飲食 5000"
            
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply_text)]))
            return

        # 5. 核心：金額輸入觸發 Quick Reply
        else:
            import re
            # 智慧拆解：找出金額 (\d+)
            match = re.search(r"(\d+)", text)
            
            if not match:
                line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="❌ 沒看到金額喔！\n請輸入例如：100 或 飲食 100")]
                ))
                return

            amount = match.group(1)
            remaining_text = text.replace(amount, "").strip()

            # 檢查剩下的文字裡有沒有包含「已知類別」
            found_category = None
            for cat in categories:
                if cat in remaining_text:
                    found_category = cat
                    break
            
            # A. 如果「找不到明確類別」：不管他輸入什麼，只要有錢，就彈選單
            if not found_category:
                # 把剩下的文字當作備註
                memo = remaining_text
                quick_reply_items = [
                    QuickReplyItem(
                        action=MessageAction(label=cat, text=f"{cat} {amount} {memo}".strip())
                    ) for cat in categories
                ]
                line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(
                        text=f"💵 金額：${amount}\n這是屬於哪個類別的支出？",
                        quick_reply=QuickReply(items=quick_reply_items)
                    )]
                ))
                return

            # B. 如果「有明確類別」 (例如點了按鈕或是輸入 "飲食 100")
            else:
                category = found_category
                # 備註就是剩下的文字扣除類別
                memo = remaining_text.replace(category, "").strip()

                # 檢查預算限制
                budgets = get_user_budgets(user_id)
                limit = budgets.get(category)

                if limit is None or int(limit) <= 0:
                    reply_text = f"⚠️ 記帳失敗！\n您尚未設定【{category}】的每月額度。"
                    quick_set_qr = QuickReply(items=[
                        QuickReplyItem(action=MessageAction(label="3000", text=f"設定 {category} 3000")),
                        QuickReplyItem(action=MessageAction(label="5000", text=f"設定 {category} 5000")),
                        QuickReplyItem(action=MessageAction(label="8000", text=f"設定 {category} 8000")),
                        QuickReplyItem(action=MessageAction(label="10000", text=f"設定 {category} 10000")),
                        QuickReplyItem(action=MessageAction(label="自定義", text=f"設定 {category} "))
                    ])

                    line_bot_api.reply_message(ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text, quick_reply=quick_set_qr)]
                    ))
                    return

                # 存檔
                add_transaction(user_id, {"category": category, "amount": int(amount), "type": "expense", "memo": memo})

                # 預算警示檢查
                summary = get_monthly_summary(user_id)
                curr_total = summary.get(category, 0)
                limit = int(limit)
                
                status_icon = "✅"
                warning = ""
                if curr_total > limit:
                    status_icon = "🚨"
                    warning = f"\n\n🚫 警告：{category}已爆表！\n(${curr_total}/${limit})"
                elif curr_total >= limit * 0.8:
                    status_icon = "⚠️"
                    warning = f"\n\n🔔 提醒：{category}已達 80%！"

                reply_text = f"{status_icon} 已記錄\n類別：{category}\n金額：${amount}\n備註：{memo if memo else '無'}" + warning
            
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            ))

# --- 圖文選單建立 ---
def create_rich_menu():
    with ApiClient(configuration) as api_client:
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