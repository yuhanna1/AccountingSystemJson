def budget_setup_guide(categories, budgets):
    guide_contents = [
        {"type": "text", "text": "🎯 預算初始化設定", "weight": "bold", "size": "lg", "margin": "md"},
        {"type": "text", "text": "請點擊下方類別設定每月額度：", "size": "xs", "color": "#aaaaaa", "margin": "sm"},
        {"type": "separator", "margin": "md"}
    ]
    
    for cat in categories:
        current_limit = budgets.get(cat, 0)
        is_set = current_limit is not None and int(current_limit) > 0
        status_text = f"目前：${current_limit}" if is_set else "🔴 尚未設定"
        
        guide_contents.append({
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
                    "type": "button", 
                    "style": "primary" if not is_set else "secondary",
                    "height": "sm", 
                    "flex": 2, 
                    "color": "#1DB446" if not is_set else "#eeeeee",
                    "action": {
                        "type": "message", 
                        "label": "設定" if not is_set else "修改", 
                        "text": f"設定 {cat} "
                    }
                }
            ]
        })
        
    return {
        "type": "bubble", 
        "body": {"type": "box", "layout": "vertical", "contents": guide_contents}
    }

def record_success_card(category, amount, memo, percent, color):
    display_percent = min(100, max(0, percent))
    
    return {
        "type": "bubble", 
        "size": "sm",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "md",
            "contents": [
                {"type": "text", "text": "✅ 記錄成功", "weight": "bold", "size": "md", "color": "#1DB446"},
                {
                    "type": "box", "layout": "vertical", 
                    "contents": [
                        {"type": "text", "text": f"{category}：${amount}", "size": "xl", "weight": "bold"},
                        {"type": "text", "text": f"備註：{memo if memo else '無'}", "size": "xs", "color": "#aaaaaa"}
                    ]
                },
                {"type": "separator"},
                {
                    "type": "box", "layout": "vertical", "spacing": "xs", 
                    "contents": [
                        {
                            "type": "box", "layout": "horizontal", 
                            "contents": [
                                {"type": "text", "text": f"{category}預算進度", "size": "xs", "color": "#888888"},
                                {"type": "text", "text": f"{percent}%", "size": "xs", "align": "end", "color": color, "weight": "bold"}
                            ]
                        },
                        {
                            "type": "box", "layout": "vertical", "backgroundColor": "#eeeeee", "height": "6px", "cornerRadius": "3px",
                            "contents": [
                                {
                                    "type": "box", "layout": "vertical", 
                                    "width": f"{display_percent}%", 
                                    "backgroundColor": color, "height": "6px", "cornerRadius": "3px"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    }