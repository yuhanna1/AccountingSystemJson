#json_store.py
import json
import os
from datetime import datetime

DATA_DIR = "data"
FILE_PATH = os.path.join(DATA_DIR, "transactions.json")
BUDGET_FILE = os.path.join(DATA_DIR, "budgets.json") # 新增額度檔案路徑

def add_transaction(user_id, data):
    # 確保資料夾存在
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    # 讀取舊資料
    if os.path.exists(FILE_PATH):
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)
    else:
        records = []

    # 新增一筆記帳
    record = {
        "user_id": user_id,
        "category": data["category"],
        "amount": data["amount"],
        "type": data["type"],
        "memo": data.get("memo", ""),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    records.append(record)

    # 寫回 JSON
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    return {"status": True}
# services/json_store.py 底部新增

def get_user_transactions(user_id):
    if os.path.exists(FILE_PATH):
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            all_records = json.load(f)
            # 過濾出屬於該 user_id 的紀錄
            user_records = [r for r in all_records if r["user_id"] == user_id]
            return user_records
    return []

def set_budget(user_id, category, amount):
    """設定使用者的類別額度"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    budgets = {}
    if os.path.exists(BUDGET_FILE):
        with open(BUDGET_FILE, "r", encoding="utf-8") as f:
            budgets = json.load(f)
    
    if user_id not in budgets:
        budgets[user_id] = {}
    
    budgets[user_id][category] = amount
    
    with open(BUDGET_FILE, "w", encoding="utf-8") as f:
        json.dump(budgets, f, ensure_ascii=False, indent=2)

def get_user_budgets(user_id):
    """取得使用者的所有額度設定"""
    if os.path.exists(BUDGET_FILE):
        with open(BUDGET_FILE, "r", encoding="utf-8") as f:
            budgets = json.load(f)
            return budgets.get(user_id, {})
    return {}

def get_monthly_summary(user_id):
    """計算本月各類別的支出總和"""
    records = get_user_transactions(user_id)
    this_month = datetime.now().strftime("%Y-%m") # 取得目前年份-月份 (如 2025-12)
    
    summary = {}
    for r in records:
        # 檢查紀錄的時間是否屬於本月，且類型為支出
        if r["time"].startswith(this_month) and r["type"] == "expense":
            cat = r["category"]
            summary[cat] = summary.get(cat, 0) + r["amount"]
    return summary