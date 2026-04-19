import difflib

# 货品排除项与规则
MATCH_RULES = {
    "skip_keywords": ["客户自己的机器", "维修"],
    "synonyms": {
        "X5白单": "X5白色单屏（3代I5+4+64+WiFi+喇叭）",
        "58TS": "XP-58TS",
        "C503": "TX-C503（新）",
        "JY335C": "JY-335C",
        "不干胶": "40*30*800张三防不干胶"
    }
}

def find_best_match(query, choices, threshold=0.1):
    """
    模糊匹配货品名称
    """
    if not query: return None
    query = str(query).upper().strip()
    
    # 0. 特殊处理 (预定义别名)
    for alias, formal in MATCH_RULES["synonyms"].items():
        if alias in query:
            # 如果别名在库里，直接返回
            if formal in choices: return formal

    # 1. 精确匹配
    if query in choices: return query
    
    # 2. 包含匹配 (优先处理)
    potential_matches = [c for c in choices if query in str(c).upper()]
    if potential_matches:
        return min(potential_matches, key=len) # 选名字最短的那个，通常是基准型号

    # 3. 模糊匹配 (difflib)
    matches = difflib.get_close_matches(query, choices, n=1, cutoff=threshold)
    return matches[0] if matches else None

def get_product_details(matched_name, inventory_list):
    """
    从库存列表获取详细信息 (条码, 编号, 重量等)
    """
    if not matched_name: return {}
    for item in inventory_list:
        if item.get("货品名称") == matched_name:
            return item
    return {}
