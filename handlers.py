import re
from urllib.parse import parse_qsl
from datetime import datetime
from linebot.v3.messaging import (
    ReplyMessageRequest, TextMessage, FlexMessage, FlexContainer,
    QuickReply, QuickReplyItem, MessageAction, ConfirmTemplate, 
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
import flex_templates as flex

CATEGORIES = ["飲食", "娛樂", "運動", "交通", "健康", "其他"]

def handle_text_logic(api, event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 功能：圖表、教學、花費明細
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

    # 功能：記帳邏輯
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
    """處理刪除確認的 Postback 事件"""
    data = event.postback.data
    params = dict(parse_qsl(data))
    user_id = event.source.user_id

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

    elif params.get('action') == 'confirm_delete':
        success = delete_transaction(user_id, params.get('id'))
        msg = "✅ 已成功刪除紀錄！" if success else "❌ 刪除失敗。"
        api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=msg)]
        ))