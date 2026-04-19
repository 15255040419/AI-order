# 映射关系规则 (由 配置规则.json 彻底迁移至此)

SALESMAN_MAP = {
    "TX": "仝心科技(admin)",
    "L": "陆香(12)",
    "D": "王德龙(21)",
    "C": "王德成(31)",
    "W": "汪朋松(30)",
    "T": "胡正婷(16)",
    "H": "韩伟(13)",
    "F": "方同辉(14)"
}

RECEIPT_MAP = {
    "已付仝心农商": "仝心农商（公账）",
    "已付农商成": "农商银行（成）",
    "已付农商龙": "农商（龙）",
    "已付农商": "农商银行（成）",
    "已付财务微信": "财务微信",
    "已付安徽仝心": "仝心农商（公账）",
    "已付仝心": "仝心农商（公账）"
}

DEFAULT_SALESMAN = "仝心科技(admin)"

def get_salesman_by_code(code, default=DEFAULT_SALESMAN):
    """
    通过代码获取业务员全名
    """
    if not code: return default
    return SALESMAN_MAP.get(str(code).upper(), default)

def find_receipt_account(text):
    """
    从文本中匹配收款账户
    """
    if not text: return ""
    for kw, account in RECEIPT_MAP.items():
        if kw in text:
            return account
    return ""
