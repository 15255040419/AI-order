import os
import json
import pandas as pd
import requests
import math
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

# --- 配置日志 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# --- 初始化 Flask 应用 ---
app = Flask(__name__)
# 允许所有来源的跨域请求，这样前端HTML文件才能访问后端
CORS(app)

# --- 全局变量，用于缓存数据 ---
STOCK_DATA = pd.DataFrame()
COMBO_DATA = pd.DataFrame()
CUSTOMER_DATA = pd.DataFrame()
CONFIG_DATA = {}
ZHIPU_API_KEY = "7bd6e3eca730448c8ffac4c786cd092a.XfOv2YlnrDp44XO5" # <-- 在这里替换成你的API Key

# --- 数据加载函数 ---
def load_data():
    """在程序启动时加载所有数据文件到内存中"""
    global STOCK_DATA, COMBO_DATA, CUSTOMER_DATA, CONFIG_DATA
    
    data_path = 'data'
    print("--- 正在加载数据文件 ---", flush=True)
    try:
        STOCK_DATA = pd.read_excel(os.path.join(data_path, '总库存.xlsx'))
        print(f"[OK] 总库存.xlsx 加载成功，共 {len(STOCK_DATA)} 条记录", flush=True)
        
        # 提取一个简单的货品列表给AI参考
        stock_list = STOCK_DATA['货品名称'].dropna().unique().tolist()
        spec_list = STOCK_DATA['规格编号'].dropna().unique().tolist()
        
        COMBO_DATA = pd.read_excel(os.path.join(data_path, '总库存-组合装明细.xlsx'))
        print(f"[OK] 总库存-组合装明细.xlsx 加载成功，共 {len(COMBO_DATA)} 条记录", flush=True)
        combo_list = COMBO_DATA['货品名称'].dropna().unique().tolist()

        # 合并所有货品名称，创建一个给AI参考的知识库
        all_products = list(set(stock_list + spec_list + combo_list))
        
        CUSTOMER_DATA = pd.read_excel(os.path.join(data_path, '客户档案.xlsx'))
        print(f"[OK] 客户档案.xlsx 加载成功，共 {len(CUSTOMER_DATA)} 条记录", flush=True)
        
        with open(os.path.join(data_path, '配置规则.json'), 'r', encoding='utf-8') as f:
            CONFIG_DATA = json.load(f)
        print("[OK] 配置规则.json 加载成功", flush=True)
        
        # 将货品列表存入配置，方便后续使用
        CONFIG_DATA['internal_product_list'] = all_products
        print(f"--- 共整合 {len(all_products)} 种唯一货品名称/规格作为AI参考 ---", flush=True)
        
    except FileNotFoundError as e:
        print(f"[ERROR] 错误：找不到文件 {e.filename}。请确保所有数据文件都在 'data' 文件夹中。")
    except Exception as e:
        print(f"[ERROR] 加载数据时发生未知错误: {e}")

# --- AI 解析函数 ---
# --- AI 解析函数 ---
def parse_order_with_ai(text):
    """调用智谱AI并提供上下文（货品列表）进行解析"""
    if not ZHIPU_API_KEY or ZHIPU_API_KEY == "在这里填入你的智谱AI API密钥":
        return None, "智谱AI API密钥未配置"

    prompt = f"""请从以下文本中提取订单信息，以 JSON 格式输出。
不要输出解释，不要使用代码块，直接返回 JSON。

【待解析文本】:
{text}

【JSON 字段要求】:
{{
  "receiver": "姓名",
  "phone": "电话",
  "address": "地址",
  "province": "省份（如：广东、北京、新疆，不要带'省'或'市'后缀）",
  "products": [ {{ "name": "货品名", "qty": 数量, "price": 单价 }} ],
  "payment_status": "已付/未付",
  "payment_account": "收款账户（关键词：如'农商'、'财务微信'、'仝心'等，若未付则留空）",
  "customer_account": "客户账号（重点：提取'系统录'后面的名字，如'系统录：张三'则填'张三'）",
  "salesman_code": "业务员标记(识别括号内的字母，如 (W) 填 W)",
  "postage": 0,
  "total_amount": 0,
  "extra_note": "仅抓取：如'晚付'、'上楼'、'备注'等特殊指示，备注后面可能没有冒号"
}}

【重要规则】:
1. 名字或地址后方的 [1783] 这种内容必须原样保留在对应字段中，不要当做 ID 拆分。
2. 即使地址不完整，也要尽力根据城市推断省份。
3. 直接返回 JSON，禁止任何前导或后继文字。"""

    system_prompt = "你是一个极速订单解析器，严格按格式返回 JSON。"

    try:
        response = requests.post(
            'https://open.bigmodel.cn/api/paas/v4/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {ZHIPU_API_KEY}'
            },
            json={
                'model': 'glm-4-flash',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0,
                'max_tokens': 1500
            },
            timeout=30
        )
        response.raise_for_status()
        
        content = response.json()['choices'][0]['message']['content']
        json_str = content[content.find('{'):content.rfind('}')+1]
        return json.loads(json_str), None
    except Exception as e:
        return None, f"解析过程出错: {e}"


# --- 强化型匹配工具 ---
def clean_str(s):
    """清理字符串：去空格、去特殊符号、转小写"""
    if not s: return ""
    import re
    # 去除空隙和常见分隔符：空格, -, _, /, *, ( )
    return re.sub(r'[\s\-_\/\*\(\)\（\）]', '', str(s)).lower()

def find_product_match(name):
    """在本地库中查找货品匹配 (强化模糊评分 & 权重算法)"""
    if not name: return {"matchedName": "未知", "matchType": "unmatched"}
    
    import difflib
    
    # 1. 特殊映射优先
    special_map = CONFIG_DATA.get("货品特殊映射", {})
    c_search_name = clean_str(name)
    for key, val in special_map.items():
        if c_search_name == clean_str(key):
            # 找到映射名后，去库存表里精确捞一下元数据
            m_row = STOCK_DATA[STOCK_DATA['货品名称'].astype(str).str.strip() == str(val).strip()]
            if not m_row.empty:
                best = m_row.iloc[0].to_dict()
                return {**best, "matchedName": val, "matchType": "matched", "source": "记忆映射+库存同步"}
            return {"matchedName": val, "matchType": "matched", "source": "仅记忆映射(库中未找到)"}

    # 1. 尝试完全匹配 (原样比对)
    exact_match = STOCK_DATA[STOCK_DATA['货品名称'].astype(str).str.strip() == name.strip()]
    if not exact_match.empty:
        best = exact_match.iloc[0].to_dict()
        return {**best, "matchedName": best.get('货品名称'), "matchType": "matched", "source": "精确匹配"}

    # 2. 评分机制
    candidates = []
    
    # 抽取所有库存用于评分
    for _, row in STOCK_DATA.iterrows():
        t_name = str(row.get('货品名称', '')).strip()
        t_spec_no = str(row.get('规格编号', '')).strip()
        t_spec = str(row.get('规格', '')).strip()
        
        # 🌟 强力逻辑：如果原文直接包含了库存中的名称或编号，直接给满分并提前返回
        if (t_name and t_name in name) or (t_spec_no and t_spec_no in name):
             return {**row.to_dict(), "matchedName": t_name, "matchType": "matched", "source": "包含匹配(100%准确)"}

        # 针对三列分别计算模糊相似度 (0.0 - 1.0)
        # 权重：规格编号(1.2) > 货品名称(1.0) > 规格(0.8)
        s1 = difflib.SequenceMatcher(None, c_search_name, clean_str(t_spec_no)).ratio() * 1.2
        s2 = difflib.SequenceMatcher(None, c_search_name, clean_str(t_name)).ratio() * 1.0
        s3 = difflib.SequenceMatcher(None, c_search_name, clean_str(t_spec)).ratio() * 0.8
        
        max_score = max(s1, s2, s3)
        if max_score > 0.4: # 设定一个最低阈值
            candidates.append({"score": max_score, "data": row.to_dict()})

    if candidates:
        # 按评分由高到低排序
        candidates.sort(key=lambda x: x['score'], reverse=True)
        # 增加逻辑：如果得分最高项相似度够高，就采用它
        best = candidates[0]['data']
        # 为了让 57*50纸 这种能匹配到含此关键字的项目，做一次强包含检查
        if candidates[0]['score'] < 0.8:
            for cand in candidates:
                c_name = str(cand['data'].get('货品名称', ''))
                if name in c_name or c_name in name:
                    best = cand['data']
                    break

        return {
            **best, 
            "matchedName": best.get('货品名称'), 
            "matchType": "matched", 
            "source": f"智能匹配(相似度:{round(candidates[0]['score'],2)})",
            "candidates": [c['data'].get('货品名称') for c in candidates[:10]] # 返回前10个备选
        }
    
    # 3. 组合装兜底 (略)
    return {"matchedName": name, "matchType": "unmatched", "source": "未匹配"}


def select_express(address, products, raw_text="", ai_province=""):
    """根据地址、货品以及原文关键词自动匹配快递"""
    express_rules = CONFIG_DATA.get("快递规则", {})
    
    # 0. 优先检测原文中的明确指派
    explicit_map = {
        '顺丰': '顺丰速运',
        '圆通': '圆通（渠道）',
        '中通': '中通（渠道）',
        '申通': '申通快递',
        '韵达': '韵达快递',
        '极兔': '极兔渠道（新）',
        '德邦': '德邦特惠',
        '邮政': '邮政EMS'
    }
    for kw, target in explicit_map.items():
        if kw in raw_text:
            return target

    # 1. 检查特殊映射 (学习进化的结果)
    express_special_map = CONFIG_DATA.get("快递特殊映射", {})
    # 尝试匹配收货人或地址关键词
    for key, val in express_special_map.items():
        if key in address or key in raw_text:
            return val

    # 2. 检查工厂代发/直发
    text_to_check = (address + " " + " ".join([p.get('searchName', '') for p in products])).lower()
    if '工厂代发' in text_to_check: return '工厂代发'
    if '工厂直发' in text_to_check: return '工厂直发'
    
    # 3. 识别省份
    provinces = ['北京','天津','上海','重庆','河北','山西','辽宁','吉林','黑龙江','江苏','浙江','安徽','福建','江西','山东','河南','湖北','湖南','广东','海南','四川','贵州','云南','陕西','甘肃','青海','内蒙古','广西','西藏','宁夏','新疆']
    province = ""
    
    # 优先从 AI 返回的省份字段匹配（增加容错：如“广东省”匹配“广东”）
    if ai_province:
        for p in provinces:
            if p in ai_province:
                province = p
                break
    
    # 如果 AI 没识别出有效的，从地址里暴力匹配
    if not province:
        for p in provinces:
            if p in address:
                province = p
                break
    
    if not province: return "待定(未识别省份)"

    # 3. 检查特殊品类
    # 一体称判定：X开头+配置关键词
    has_scale = any(str(p.get('searchName','')).upper().startswith('X') and any(word in str(p.get('searchName','')) for word in ['单屏','双屏','白色','黑色']) for p in products)
    
    # 收银机判定：K开头 或 包含特定型号/关键词
    has_register = any(
        str(p.get('searchName','')).upper().startswith('K') or 
        '收银' in str(p.get('searchName','')) or 
        'XP-C' in str(p.get('searchName','')).upper() or 
        'TX-' in str(p.get('searchName','')).upper() 
        for p in products
    )
    
    # 计算总重量 (g)
    total_weight = sum([float((p.get('productInfo') or {}).get('重量', 0)) * int(p.get('qty', 1)) for p in products])
    
    if has_scale:
        return express_rules.get("一体称", {}).get("所有地区", "德邦特惠")
    
    if has_register:
        reg_map = express_rules.get("收银机", {}).get("地区映射", {})
        return reg_map.get(province, "中通（渠道）")
    
    # 4. 普通货品按重量
    weight_seg = "1-2kg" if total_weight <= 2000 else "2-5kg" if total_weight <= 5000 else "5kg以上"
    normal_rules = express_rules.get("普通货品", {}).get("重量分段", {})
    return normal_rules.get(weight_seg, {}).get(province, "中通（渠道）")

def process_parsed_data(ai_result, raw_text):
    """对AI返回的结果进行二次处理和数据补充"""
    # 🌟 核心：直接使用传入的原始文本进行正则匹配，不再依赖 AI 返回的 raw 字段
    
    # 1. 业务员验证 (从全文或系统录行末尾识别)
    salesman_code = str(ai_result.get("salesman_code", "")).strip().upper()
    salesman_map = CONFIG_DATA.get("业务员映射", {})
    
    # 增强逻辑：如果原文中有 (W), （W）, (W-新) 等格式，强行提炼
    import re
    actual_code = salesman_code
    # 如果 AI 没抓到或者抓的不准，在全文搜索括号内的代码
    codes = re.findall(r'[\(\（]([A-Z0-9\-]+)[\)\）]', raw_text)
    for c in codes:
        c_upper = c.upper()
        if c_upper in salesman_map:
            actual_code = c_upper
            break
            
    salesman = salesman_map.get(actual_code, CONFIG_DATA.get("默认业务员", "未分配"))

    # 2. 客户账号提取 (强力锁定“系统录”或“系统录入”后面的名字)
    customer_account = ""
    # 增强版正则：兼容“系统录”、“系统录入”、“系统记录”，穿透冒号和空格
    match = re.search(r'(?:系统录[入制]?|系统记录)[:：\s]*([^\s\n\（\(\[\]]+)', raw_text)
    if match:
        customer_account = match.group(1).strip()
    
    # 🌟 强力锁：手机号正则兜底 (100% 准确提取)
    phones = re.findall(r'1[3-9]\d{9}', raw_text)
    phone = phones[0] if phones else ai_result.get("phone", "")

    # 🌟 强力锁：金额正则兜底 (抓取如 "210元" 这种结尾的数字)
    total_amount = ai_result.get("total_amount", 0)
    money_match = re.search(r'(\d+(?:\.\d+)?)\s*元', raw_text)
    if money_match:
        total_amount = float(money_match.group(1))

    # 剥离杂质
    customer_account = re.sub(r'[“”"\[\]]', '', customer_account)
    
    # 只有当正则完全没抓到时，才看AI的结果，但 AI 的结果必须经过 1783 过滤
    if not customer_account:
        ai_acc = str(ai_result.get("customer_account", "")).strip()
        if not (ai_acc.isdigit() and f"[{ai_acc}]" in raw_text):
            customer_account = ai_acc
    
    # 彻底清除客户名字里残留的业务代码后缀
    customer_account = re.sub(r'[\(\（].*?[\)\）]+', '', customer_account).strip()

    # 2.1 客户账号匹配
    if CUSTOMER_DATA is not None and not CUSTOMER_DATA.empty:
        p_phone = str(ai_result.get('phone', ''))
        # 尝试通过手机号匹配
        c_match = CUSTOMER_DATA[CUSTOMER_DATA['联系电话'].astype(str).str.contains(p_phone, na=False)] if p_phone else pd.DataFrame()
        
        if c_match.empty:
            cust_map = CONFIG_DATA.get("客户特殊映射", {})
            if customer_account in cust_map:
                c_match = CUSTOMER_DATA[CUSTOMER_DATA['客户账号'] == cust_map[customer_account]]

        if not c_match.empty:
            final_customer = c_match.iloc[0].to_dict()
            customer_account = final_customer.get("客户账号", "")
        else:
            # 生成候选
            cands = []
            recv = ai_result.get("receiver", "")
            for _, row in CUSTOMER_DATA.iterrows():
                c_name, c_acc = str(row.get('客户名称', '')), str(row.get('客户账号', ''))
                if recv and (recv in c_name or recv in c_acc):
                    cands.append({"客户账号": c_acc, "客户名称": c_name})
            final_customer = None
            customer_candidates = cands[:5]
    else:
        final_customer = None
        customer_candidates = []

    # 3. 支付状态与收款账户逻辑 (严格遵循用户业务规则)
    payment_status = ai_result.get("payment_status", "未付")
    pay_method = "欠款计应收"
    receipt = "" # 默认不填

    if payment_status == "已付":
        pay_method = "银行收款"
        raw_account = str(ai_result.get("payment_account", "")).strip()
        if raw_account.startswith("已付"):
            raw_account = raw_account[2:].strip()
        # 剥离后缀
        raw_account = re.sub(r'[\(\（].*?[\)\）]+', '', raw_account).strip()
        
        receipt_map = CONFIG_DATA.get("收款账户映射", {})
        receipt = ""
        # 优先从 AI 识别的账户字段匹配
        for key, val in receipt_map.items():
            if raw_account and (key in raw_account or raw_account in key):
                receipt = val
                break
        
        # 🌟 遵循 Rule 30：如果 AI 没识别到账户，但识别到了“系统录”，且确实已付，则查询系统录名是否为账户
        if not receipt and customer_account:
            for key, val in receipt_map.items():
                if key in customer_account or customer_account in key:
                    receipt = val
                    break
        
        # 如果依然没匹配上映射，则保留原始抓取内容
        if not receipt:
            receipt = raw_account
    else:
        # 如果是“未付”，强制收款账户为空
        receipt = ""

    final_result = {
        "phone": phone,
        "receiver": ai_result.get("receiver", ""),
        "address": ai_result.get("address", ""),
        "products": [],
        "total": total_amount,
        "freight": ai_result.get("postage", 0),
        "note": ai_result.get("extra_note", ""),
        "account": customer_account,
        "salesman": salesman,
        "payMethod": pay_method,
        "receipt": receipt,
        "salesChannel": CONFIG_DATA.get("销售渠道", "仝心科技线下批发"),
        "express": "",
        "customer": None,
        "raw": raw_text,
        "error": False,
        "parseMethod": "AI (Regex-Fallback)"
    }




    # 货品处理
    calculated_total = 0
    for prod in ai_result.get("products", []):
        p_name = prod.get("name")
        p_qty = prod.get("qty", 1)
        p_price = prod.get("price", 0)
        
        match_info = find_product_match(p_name)
        
        final_result["products"].append({
            "searchName": p_name,
            "noteName": p_name,
            "qty": p_qty,
            "price": p_price,
            "matchedName": match_info.get("货品名称") or match_info.get("matchedName"),
            "matchType": match_info.get("matchType"),
            "source": match_info.get("source"),
            "productInfo": match_info if match_info.get("matchType") == "matched" else None
        })
        try:
            calculated_total += float(p_price) * int(p_qty)
        except: pass

    if not final_result["total"] or final_result["total"] == 0:
        final_result["total"] = calculated_total

    # 快递计算
    final_result["express"] = select_express(final_result["address"], final_result["products"], raw_text=raw_text, ai_province=ai_result.get("province", ""))

    # 最终结果整合
    final_result["customer"] = final_customer
    final_result["customer_candidates"] = customer_candidates
    if final_customer:
        final_result["account"] = final_customer.get("客户账号", "")

    # 备注简化：[货品简述] + [AI 备注]
    prod_note = " ".join([f"{p['searchName']}*{p['qty']}" for p in final_result["products"] if p.get('searchName')])
    
    # 🌟 强力锁：备注内容正则强行抓取 (捕捉“备注”后所有文字)
    ai_extra = ai_result.get("extra_note", "")
    note_regex_match = re.search(r'备注[:：\s]*(.*)', raw_text, re.S) # re.S 支持跨行抓取
    if note_regex_match:
        ai_extra = note_regex_match.group(1).strip()

    if ai_extra in ["无", "none", "None", ""]: ai_extra = ""
    
    final_result["note"] = f"{prod_note} {ai_extra}".strip()

    logger.info(f"匹配结果: 客户={final_result['account']}, 业务员={final_result['salesman']}, 快递={final_result['express']}")
    logger.info(f"货品明细: {[{'name': p['matchedName'], 'qty': p['qty']} for p in final_result['products']]}")

    return sanitize_data(final_result)




# --- API 路由 ---
@app.route('/api/learn', methods=['POST'])
def learn_endpoint():
    try:
        data = request.json
        l_type, raw, matched = data.get("type", "product"), data.get("rawName"), data.get("matchedName")
        if not raw or not matched: return jsonify({"status": "error"}), 400
        
        mapping = {
            "product": "货品特殊映射",
            "customer": "客户特殊映射",
            "express": "快递特殊映射"
        }
        key = mapping.get(l_type, "货品特殊映射")
        
        if key not in CONFIG_DATA: CONFIG_DATA[key] = {}
        CONFIG_DATA[key][raw] = matched
        with open('data/配置规则.json', 'w', encoding='utf-8') as f:
            json.dump(CONFIG_DATA, f, ensure_ascii=False, indent=4)
        print(f"[INFO] 系统进步：[{l_type}] {raw} -> {matched}")
        return jsonify({"status": "ok"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/options', methods=['GET'])
def get_options():
    """返回供前端下拉选择的选项列表"""
    salesmen = list(CONFIG_DATA.get("业务员映射", {}).values())
    if "默认业务员" in CONFIG_DATA and CONFIG_DATA["默认业务员"] not in salesmen:
        salesmen.append(CONFIG_DATA["默认业务员"])
    
    customers = []
    if CUSTOMER_DATA is not None and not CUSTOMER_DATA.empty:
        # 提取客户账号和名称
        customers = CUSTOMER_DATA[['客户账号', '客户名称']].dropna().to_dict('records')

    pay_methods = ["银行收款", "欠款计应收", "现金支付"]
    receipts = list(set(CONFIG_DATA.get("收款账户映射", {}).values()))
    
    # 提取所有货品名及完整元数据供前端联动
    all_products = []
    all_products_data = []
    if STOCK_DATA is not None and not STOCK_DATA.empty:
        all_products = list(STOCK_DATA['货品名称'].dropna().unique())
        all_products_data = STOCK_DATA.to_dict('records')

    return sanitize_data({
        "salesmen": salesmen,
        "customers": customers,
        "payMethods": pay_methods,
        "receipts": receipts,
        "allProducts": all_products,
        "allProductsData": all_products_data
    })


def sanitize_data(data):
    """递归清理字典中的 NaN 值，将其转换为 None (JSON null)"""
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(i) for i in data]
    elif isinstance(data, float) and math.isnan(data):
        return None
    return data

@app.route('/api/parse', methods=['POST', 'OPTIONS'])
def parse_endpoint():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
        
    logger.info("="*20 + " 收到解析请求 " + "="*20)
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "请求体为空或缺少'text'字段"}), 400

    order_text = data['text']
    logger.info(f"订单原文提取: {order_text[:100]}...")

    # 1. 使用AI进行初步解析
    ai_result, error = parse_order_with_ai(order_text)
    
    if error:
        logger.error(f"AI解析失败: {error}")
        return jsonify({"error": error, "parseMethod": "AI失败"}), 500

    logger.info(f"AI 初步解析成功: {ai_result}")

    # 2. 对AI结果进行后处理和数据补充
    final_data = process_parsed_data(ai_result, order_text)
    final_data['raw'] = order_text
    
    # 核心修复：清理所有可能来自 Excel 的 NaN 值，防止前端解析 JSON 报错
    final_data = sanitize_data(final_data)

    logger.info("数据后处理完成, 准备返回前端。")
    return jsonify(final_data)


from flask import Flask, request, jsonify, send_file
import os

# ... (rest of imports)

@app.route('/')
def index():
    """让内网用户通过IP直接访问网页界面"""
    html_path = os.path.join(os.path.dirname(__file__), '..', 'order-assistant-full.html')
    if os.path.exists(html_path):
        return send_file(html_path)
    return "找不到页面文件，请确保 order-assistant-full.html 在正确位置。"

# --- 主程序运行 ---
if __name__ == '__main__':
    # 🌟 强力修复：先设定调试模式，再进行进程判定
    app.debug = True 
    
    # 只有正式工作的子进程（或者关闭了重启器的模式）才允许加载数据和打印
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        load_data() 
        
        import socket
        def get_ip():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except: return '127.0.0.1'

        local_ip = get_ip()
        print("\n" + "="*50)
        print(f"[START] 下单助手内网版已启动！")
        print(f"Local: http://127.0.0.1:5000")
        print(f"Network: http://{local_ip}:5000 (请在局域网内访问此地址)")
        print("="*50 + "\n")

    # 注意：这里不再传 debug=True，因为上面已经设过了
    app.run(host='0.0.0.0', port=5000)
