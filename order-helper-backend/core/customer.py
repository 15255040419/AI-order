import logging

logger = logging.getLogger(__name__)

def find_customer_profile(text, customer_index):
    """
    在识别出的订单文本中寻找匹配的客户档案
    返回匹配到的第一个客户完整信息
    """
    if not text or not customer_index:
        return None

    # 1. 尝试从文本中寻找已知名字
    for name, profile in customer_index.items():
        if name in text:
            return profile

    # 2. 尝试从文本中寻找已知手机号
    # 手机号通常是 11 位数字
    import re
    phones = re.findall(r'1[3-9]\d{9}', text)
    for p in phones:
        if p in customer_index:
            return customer_index[p]
            
    return None

def apply_customer_rules(result, profile):
    """
    将查到的客户档案应用到解析结果中
    """
    if not profile:
        return result

    # 自动补充字段
    if not result.get('customer_account'):
        result['customer_account'] = profile.get('客户账号', '')
    
    if not result.get('salesman'):
        result['salesman'] = profile.get('业务员', '')
        
    # 如果找到了客户，备注里记载一下
    if profile.get('客户名称'):
        result['note'] = f"系统识别客户: {profile['客户名称']} | {result.get('note', '')}"
        
    return result
