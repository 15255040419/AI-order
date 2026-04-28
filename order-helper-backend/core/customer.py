import logging

logger = logging.getLogger(__name__)

def find_customer_profile(text, customer_index):
    """
    根据原文中的手机号、姓名或账号在索引中查找客户
    """
    if not text or not customer_index:
        return None

    # 1. 尝试库中关键词拦截 (根据 配置规则 中的 客户对应关系)
    # 这部分逻辑在 processor.py 中有体现，但在档案搜索时也可以作为参考
    
    # 2. 这里的搜索逻辑应与 loader.py 建立的索引匹配
    # 简单实现：遍历索引 key
    for key in customer_index:
        if key in text:
            return customer_index[key]
            
    return None

def apply_customer_rules(result, profile):
    """
    应用基于客户档案的业务规则
    """
    if not profile:
        return result
    
    # 规则1：如果档案里有默认业务员，且当前未指派，则回馈
    if not result.get('salesman'):
        result['salesman'] = profile.get('业务员', '')
        
    # 备注逻辑已迁移至 core/processor.py，此处不再干预备注内容
    return result
