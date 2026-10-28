# stickers_manager.py
import os
import json
current_dir = os.path.dirname(os.path.abspath(__file__))
STICKERS_DIR = os.path.abspath(os.path.join(current_dir, "..", "stickers"))
INDEX_PATH = os.path.join(STICKERS_DIR, "stickers.json")

def sync_stickers():
    # 1. 读取现有索引
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {"stickers": []}

    indexed_files = {item['file'] for item in data['stickers']}
    
    # 2. 扫描文件夹中的图片 (1.jpg, 2.jpg ...)
    all_files = [f for f in os.listdir(STICKERS_DIR) if f.endswith(('.jpg', '.png', '.gif'))]
    
    # 3. 增量更新
    changed = False
    for f in all_files:
        if f not in indexed_files:
            data['stickers'].append({
                "id": f.split('.')[0], # 用数字文件名当 ID
                "file": f,
                "desc": "暂未存储"  # 默认特征
            })
            changed = True
            
    # 4. 写回 JSON
    if changed:
        with open(INDEX_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    return data