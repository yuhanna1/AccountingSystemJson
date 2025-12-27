import json
import urllib.parse

def generate_expense_pie_chart(records):
    """
    輸入紀錄列表，回傳 QuickChart 圓餅圖 URL
    """
    if not records:
        return None

    # 1. 統計資料
    summary = {}
    for r in records:
        cat = r.get('category', '未分類')
        amt = r.get('amount', 0)
        summary[cat] = summary.get(cat, 0) + amt

    labels = list(summary.keys())
    values = list(summary.values())
    
    # 2. 建立 QuickChart 配置
    chart_config = {
        "type": "pie",
        "data": {
            "labels": labels,
            "datasets": [{
                "data": values,
                "backgroundColor": [
                    "#FF6384", "#36A2EB", "#FFCE56", 
                    "#4BC0C0", "#9966FF", "#FF9F40", "#C9CBCF"
                ]
            }]
        },
        "options": {
            "plugins": {
                # 顯示標籤與數值
                "datalabels": {
                    "display": True,
                    "color": "#fff",
                    "font": {"size": 16, "weight": "bold"}
                },
                # 圖例位置
                "legend": {
                    "position": "bottom"
                }
            }
        }
    }

    # 3. 轉成 URL
    config_str = json.dumps(chart_config)
    encoded_config = urllib.parse.quote(config_str)
    
    return f"https://quickchart.io/chart?c={encoded_config}"