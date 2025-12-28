import re
from urllib.parse import parse_qsl
from datetime import datetime
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    TextMessage, ImageMessage, MessagingApiBlob,
    QuickReply, QuickReplyItem, MessageAction,
    FlexMessage, FlexContainer, ConfirmTemplate,
    TemplateMessage, PostbackAction
)

from services.json_store import (
    add_transaction, 
    get_user_transactions, 
    set_budget, 
    get_user_budgets, 
    get_monthly_summary,
    delete_transaction
)

from services.chart import generate_expense_pie_chart
import flex_templates as flex

CATEGORIES = ["飲食", "娛樂", "運動", "交通", "健康", "其他"]

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

def handle_text_logic(api, event):
    user_id = event.source.user_id
    text = event.message.text.strip()

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
        api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=messages))
        return
    
    # 2. 功能：使用教學 (點擊 Rich Menu 或輸入觸發)
    elif text == "使用教學":
        api.reply_message(ReplyMessageRequest(
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
            api.reply_message(ReplyMessageRequest(
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
                        "action": {
                            "type": "postback",
                            "label": "刪除",
                            "data": f"action=ask_delete&id={r['id']}&desc={r['category']}${r['amount']}",
                            "displayText": f"想刪除 {r['category']} ${r['amount']}" # 讓使用者知道自己點了哪個
                        }
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

        api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[FlexMessage(alt_text="本月消費明細", contents=FlexContainer.from_dict(flex_bubble))]
        ))
        return
    
    if text == "設定額度":
        budgets = get_user_budgets(user_id) # 呼叫匯入的函式
        bubble = flex.budget_setup_guide(CATEGORIES, budgets)
        api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[FlexMessage(alt_text="快速預算設定", contents=FlexContainer.from_dict(bubble))]
        ))
        return

    # 功能：預算設定執行
    elif text.startswith("設定"):
        parts = text.split()
        if len(parts) == 2:
            cat = parts[1]
            qr = QuickReply(items=[
                QuickReplyItem(action=MessageAction(label=p, text=f"設定 {cat} {p}")) for p in ["3000", "5000", "10000"]
            ])
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"請選擇【{cat}】的每月預算：", quick_reply=qr)]
            ))
        elif len(parts) >= 3:
            try:
                cat, amount = parts[1], int(parts[2])
                set_budget(user_id, cat, amount)
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"✅ 【{cat}】額度已設為 ${amount}")]
                ))
            except:
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="❌ 格式錯誤。範例：設定 飲食 5000")]
                ))
        return
    
    # 4. 功能：刪除與預算設定邏輯
    elif text.startswith("刪除"):
        parts = text.split()
        if len(parts) == 2:
            res_text = "✅ 紀錄已成功刪除！" if delete_transaction(user_id, parts[1]) else "❌ 刪除失敗。"
        else:
            res_text = "⚠️ 格式：刪除 [ID]"
        api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=res_text)]))
        return
    
    elif text == "設定額度":
        budgets = get_user_budgets(user_id)
        guide_contents = []

        guide_contents.append({
            "type": "text", "text": "🎯 預算初始化設定", "weight": "bold", "size": "lg", "margin": "md"
        })
        guide_contents.append({
            "type": "text", "text": "請點擊下方類別設定每月額度：", "size": "xs", "color": "#aaaaaa", "margin": "sm"
        })
        guide_contents.append({"type": "separator", "margin": "md"})
        
        for cat in CATEGORIES:
            current_limit = budgets.get(cat)
            is_set = current_limit is not None and int(current_limit) > 0
            
            status_text = f"目前：${current_limit}" if is_set else "🔴 尚未設定"
            btn_label = "修改" if is_set else "設定"
            
            item_box = {
                "type": "box", "layout": "horizontal", "margin": "lg", "spacing": "sm",
                "contents": [
                    {
                        "type": "box", "layout": "vertical", "flex": 3,
                        "contents": [
                            {"type": "text", "text": cat, "weight": "bold", "size": "sm"},
                            {"type": "text", "text": status_text, "size": "xs", "color": "#888888"}
                        ]
                    },
                    {
                        "type": "button", "style": "primary" if not is_set else "secondary",
                        "height": "sm", "flex": 2, "color": "#1DB446" if not is_set else "#eeeeee",
                        "action": {
                            "type": "message", "label": btn_label, "text": f"設定 {cat} "
                        }
                    }
                ]
            }
            guide_contents.append(item_box)

        # 發送 Flex Message
        api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[
                FlexMessage(
                    alt_text="快速預算設定導引",
                    contents=FlexContainer.from_dict({
                        "type": "bubble",
                        "body": {"type": "box", "layout": "vertical", "contents": guide_contents}
                    })
                )
            ]
        ))
        return
    
    elif text.startswith("設定"):
            parts = text.split()

            # 如果只有「設定 類別」，彈出 Quick Reply 選金額
            if len(parts) == 2:
                category = parts[1]
                reply_text = f"請選擇【{category}】的每月預算金額，或直接輸入數字："
                
                quick_set_qr = QuickReply(items=[
                    QuickReplyItem(action=MessageAction(label="3000", text=f"設定 {category} 3000")),
                    QuickReplyItem(action=MessageAction(label="5000", text=f"設定 {category} 5000")),
                    QuickReplyItem(action=MessageAction(label="8000", text=f"設定 {category} 8000")),
                    QuickReplyItem(action=MessageAction(label="10000", text=f"設定 {category} 10000")),
                    QuickReplyItem(action=MessageAction(label="自定義", text=f"設定 {category} "))
                ])

                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text, quick_reply=quick_set_qr)]
                ))
                return
            
            # 如果已經有金額了 (parts 長度為 3)，則正常執行設定
            try:
                if len(parts) < 3:
                    raise ValueError("缺少金額")
                
                category, amount = parts[1], int(parts[2])
                set_budget(user_id, category, amount)
                reply_text = f"✅ 【{category}】額度設定成功！\n每月預算為：${amount}"
            except:
                reply_text = "❌ 設定格式：設定 類別 金額\n例如：設定 飲食 5000"
            
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply_text)]))
            return
    

    # 5. 核心：金額輸入觸發 Quick Reply
    else:
        match = re.search(r"(\d+)", text)
        
        if not match:
            # 如果不是數字，也不是預設指令，就不回應或給予教學提示
            return 
        
        amount = match.group(1)
        remaining_text = text.replace(amount, "").strip()

        found_category = None
        for cat in CATEGORIES:
            if cat in remaining_text:
                found_category = cat
                break

        # A. 找不到類別 -> 彈出 Quick Reply
        if not found_category:
            memo = remaining_text
            quick_reply_items = [
                QuickReplyItem(action=MessageAction(label=cat, text=f"{cat} {amount} {memo}".strip())) 
                for cat in CATEGORIES
            ]
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(
                    text=f"💵 金額：${amount}\n這是屬於哪個類別的支出？",
                    quick_reply=QuickReply(items=quick_reply_items)
                )]
            ))
            return
        
        # B. 已有類別 -> 存檔並檢查預算
        else:
            category = found_category
            memo = remaining_text.replace(category, "").strip()
            budgets = get_user_budgets(user_id)
            limit = budgets.get(category)

            # 未設預算時的處理
            if limit is None or int(limit) <= 0:
                qr = QuickReply(items=[
                    QuickReplyItem(action=MessageAction(label=p, text=f"設定 {category} {p}")) for p in ["3000", "5000", "8000"]
                ])
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"⚠️ 請先設定【{category}】的預算額度：", quick_reply=qr)]
                ))
                return

            # 已有預算，正常存檔
            add_transaction(user_id, {"category": category, "amount": int(amount), "type": "expense", "memo": memo})
            
            # 計算預算進度百分比
            summary = get_monthly_summary(user_id)
            curr_total = summary.get(category, 0)
            limit = int(limit)
            percent = min(100, int((curr_total / limit) * 100)) if limit > 0 else 0
            color = "#FF334B" if percent >= 100 else ("#F7AF1D" if percent >= 80 else "#1DB446")
            
            # 呼叫 Flex 模板產生成功卡片
            success_bubble = flex.record_success_card(category, amount, memo, percent, color)
            
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(alt_text="記帳成功", contents=FlexContainer.from_dict(success_bubble))]
            ))

def handle_postback_logic(api, event):
    data = event.postback.data
    params = dict(parse_qsl(data))
    user_id = event.source.user_id

    # 1. 第一步：詢問是否確定刪除
    if params.get('action') == 'ask_delete':
        transaction_id = params.get('id')
        desc = params.get('desc')

        confirm_template = ConfirmTemplate(
            text=f"確定要刪除這筆紀錄嗎？\n({desc})",
            actions=[
                PostbackAction(label="確定刪除", data=f"action=confirm_delete&id={transaction_id}"),
                PostbackAction(label="取消", data="action=cancel")
            ]
        )
        api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TemplateMessage(alt_text="確認刪除", template=confirm_template)]
        ))

    # 2. 第二步：使用者點擊「確定刪除」
    elif params.get('action') == 'confirm_delete':
        success = delete_transaction(user_id, params.get('id'))

        msg = "✅ 已成功刪除紀錄！" if success else "❌ 刪除失敗。"
        api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=msg)]
        ))