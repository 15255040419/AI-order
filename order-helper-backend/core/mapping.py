import json
import os

# 读取配置规则.json
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', '配置规则.json')
CONFIG_DATA = {}

def load_config():
    global CONFIG_DATA
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            CONFIG_DATA = json.load(f)
    except Exception as e:
        print(f"警告：加载配置文件失败 {e}")
        CONFIG_DATA = {}

# 初次加载
load_config()

def get_salesman_map():
    return CONFIG_DATA.get("业务员映射", {})

def get_default_salesman():
    return CONFIG_DATA.get("默认业务员", "仝心科技(admin)")

def get_receipt_map():
    return CONFIG_DATA.get("收款账户映射", {})

def get_customer_map():
    # 原版中也有客户对应关系
    return CONFIG_DATA.get("客户对应关系", {})

def get_salesman_by_code(code, default=None):
    if not default: default = get_default_salesman()
    if not code: return default
    return get_salesman_map().get(str(code).upper(), default)

def find_receipt_account(text):
    if not text: return ""
    receipt_map = get_receipt_map()
    # 原版中还有对关键词的模糊判定
    for kw, account in receipt_map.items():
        if kw in text:
            return account
    return ""
