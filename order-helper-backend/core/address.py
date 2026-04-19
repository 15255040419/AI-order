import re

PROVINCES = [
    "北京","天津","河北","山西","内蒙古","辽宁","吉林","黑龙江","上海","江苏","浙江","安徽","福建","江西","山东","河南","湖北","湖南","广东","广西","海南","重庆","四川","贵州","云南","西藏","陕西","甘肃","青海","新疆"
]

def clean_address(text):
    """
    清洗地址字符串，去除干扰项
    """
    if not text: return ""
    # 去除两端的特殊符号
    text = re.sub(r'^[\s,，。\.；;]+|[\s,，。\.；;]+$', '', text)
    return text.strip()

def get_province(text, ai_suggested=""):
    """
    从地址或 AI 建议中确定省份
    """
    # 1. 优先从 AI 提取的省份里找
    if ai_suggested:
        for p in PROVINCES:
            if p in ai_suggested:
                return p
    
    # 2. 如果没有 AI 建议或不匹配，直接从地址正文里找
    if text:
        for p in PROVINCES:
            if p in text:
                return p
                
    return None
