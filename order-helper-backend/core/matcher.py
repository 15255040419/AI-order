import difflib
import re

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

def find_best_match(query, choices, data_loader=None, threshold=0.1):
    """
    模糊匹配货品名称，优先使用数据索引进行精确匹配
    """
    if not query: return None
    query = str(query).upper().strip()
    
    # 0. 特殊处理 (预定义别名)
    for alias, formal in MATCH_RULES["synonyms"].items():
        if alias in query:
            return formal

    # 1. 尝试从 DataLoader 的索引中直接查找 (极其快速)
    if data_loader:
        # 1.1 精确匹配规格编号 (Item No)
        if query in data_loader.item_no_index:
            return data_loader.item_no_index[query].get('货品名称')
        
        # 1.2 精确匹配货品名称
        if query in data_loader.product_name_index:
            return query

    # 2. 精确匹配 choices 列表
    if query in choices: return query
    
    # 3. 包含匹配 (优先处理)
    # 过滤掉一些太短的 query，防止误伤 (比如 "1" 匹配到所有带 1 的产品)
    if len(query) >= 2:
        potential_matches = [c for c in choices if query in str(c).upper()]
        if potential_matches:
            return min(potential_matches, key=len) # 选名字最短的那个，通常是基准型号

    # 4. 模糊匹配 (difflib)
    matches = difflib.get_close_matches(query, choices, n=1, cutoff=threshold)
    return matches[0] if matches else None

def get_product_details(matched_name, data_loader):
    """
    从 DataLoader 索引获取详细信息
    """
    if not matched_name or not data_loader: return {}
    
    # 优先从货品名称索引取
    if matched_name in data_loader.product_name_index:
        return data_loader.product_name_index[matched_name]
        
    return {}
