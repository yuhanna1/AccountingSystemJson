import json
import os
from datetime import datetime

DATA_DIR = "data"
FILE_PATH = os.path.join(DATA_DIR, "transactions.json")

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
