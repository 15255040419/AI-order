import os
import json
import pandas as pd
import requests
import math
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# --- 初始化 Flask 应用 ---
app = Flask(__name__)
# 允许所有来源的跨域请求，这样前端HTML文件才能访问后端
CORS(app)

# --- 全局变量，用于缓存数据 ---
STOCK_DATA = pd.DataFrame()
COMBO_DATA = pd.DataFrame()
CUSTOMER_DATA = pd.DataFrame()
CONFIG_DATA = {}
ZHIPU_API_KEY = "7bd6e3eca730448c8ffac4c786cd092a.XfOv2YlnrDp44XO5"
DATA_DIR = 'data'

# --- 数据加载函数 ---
def load_data():
    """在程序启动时加载所有数据文件到内存中"""
    global STOCK_DATA, COMBO_DATA, CUSTOMER_DATA, CONFIG_DATA
    
    data_path = 'data'
    print("--- 正在加载数据文件 ---")
    try:
        STOCK_DATA = pd.read_excel(os.path.join(data_path, '总库存.xlsx'))
        print(f"✅ 总库存.xlsx 加载成功，共 {len(STOCK_DATA)} 条记录")
        
        # 提取一个简单的货品列表给AI参考
        stock_list = STOCK_DATA['货品名称'].dropna().unique().tolist()
        spec_list = STOCK_DATA['规格编号'].dropna().unique().tolist()
        
        COMBO_DATA = pd.read_excel(os.path.join(data_path, '总库存-组合装明细.xlsx'))
        print(f"✅ 总库存-组合装明细.xlsx 加载成功，共 {len(COMBO_DATA)} 条记录")
        combo_list = COMBO_DATA['货品名称'].dropna().unique().tolist()

        # 合并所有货品名称，创建一个给AI参考的知识库
        all_products = list(set(stock_list + spec_list + combo_list))
        
        CUSTOMER_DATA = pd.read_excel(os.path.join(data_path, '客户档案.xlsx'))
        print(f"✅ 客户档案.xlsx 加载成功，共 {len(CUSTOMER_DATA)} 条记录")
        
        with open(os.path.join(data_path, '配置规则.json'), 'r', encoding='utf-8') as f:
            CONFIG_DATA = json.load(f)
        print("✅ 配置规则.json 加载成功")
        
        # 将货品列表存入配置，方便后续使用
        CONFIG_DATA['internal_product_list'] = all_products
        print(f"--- 共整合 {len(all_products)} 种唯一货品名称/规格作为AI参考 ---")
        
    except FileNotFoundError as e:
        print(f"❌ 错误：找不到文件 {e.filename}。请确保所有数据文件都在 'data' 文件夹中。")
    except Exception as e:
        print(f"❌ 加载数据时发生未知错误: {e}")

# --- AI 解析函数 ---
def parse_order_with_ai(text):
    """调用智谱AI并提供上下文（货品列表）进行解析"""
    if not ZHIPU_API_KEY or ZHIPU_API_KEY == "在这里填入你的智谱AI API密钥":
        return None, "智谱AI API密钥未配置"

    product_list = CONFIG_DATA.get('internal_product_list', [])
    # 限制知识库长度，避免超出 Token 限制
    product_knowledge_base = ", ".join(product_list[:500]) if len(product_list) > 500 else ", ".join(product_list)
    # 🌟 字典锚定：先扫描原文中的潜在货品关键词
    hints = get_dictionary_hints(text)
    
    prompt = f"""
你是一个专业的订单解析助手。请从下方的原始文本中提取订单信息，并以 JSON 格式输出。

【重要参考字典锚点】：
这些是库中真实存在的型号，如果原文中有类似内容，请务必以此为准：
{', '.join(hints) if hints else "（无直接匹配，请根据常识解析）"}

【货品列表参考】:
{product_knowledge_base}

【订单文本】:
{text}

请提取以下信息并以纯JSON格式返回（不要包含任何其他文字说明、不要使用代码块标记）：
{{
  "receiver": "收货人姓名",
  "phone": "手机号",
  "address": "完整地址",
  "products": [
    {{
      "name": "识别到的货品名称/型号",
      "qty": 数量(整数),
      "price": 单价(数字)
    }}
  ],
  "payment_status": "付款状态（已付/未付）",
  "payment_account": "收款账户",
  "customer_account": "客户账号",
  "salesman_code": "业务员标记",
  "postage": 邮费,
  "total_amount": 总价,
  "extra_note": "备注"
}}
"""

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
    return re.sub(r'[\s\-_\/\*\(\)\（\）]', '', str(s)).lower()

def calculate_similarity(s1, s2):
    """计算两个字符串的相似度评分 (0-100)"""
    if not s1 or not s2: return 0
    s1, s2 = str(s1).lower(), str(s2).lower()
    if s1 == s2: return 100
    if s1 in s2 or s2 in s1: return 90
    import difflib
    return int(difflib.SequenceMatcher(None, s1, s2).ratio() * 100)

def get_dictionary_hints(text):
    """扫描文本，从库存中提取潜在关键词，辅助 AI 解析"""
    if STOCK_DATA.empty: return []
    hints = []
    text_upper = str(text).upper()
    # 提取库中名称和规格编号
    names = STOCK_DATA['货品名称'].dropna().unique().tolist()
    specs = STOCK_DATA['规格编号'].dropna().unique().tolist()
    for k in set(names + specs):
        sk = str(k)
        if len(sk) > 2 and sk.upper() in text_upper:
            hints.append(sk)
    return list(set(hints))[:15]

def find_product_match_advanced(search_name):
    """
    升级版匹配引擎：
    1. 100分：特殊映射/完全匹配
    2. 90分：包含匹配
    3. 60-90分：模糊纠错匹配 (Levenshtein算法)
    """
    search_name = str(search_name).strip()
    if not search_name: return {"matchType": "none", "confidence": 0}

    # 1. 检查特殊映射 (用户手动纠正过的历史记录)
    special_map = CONFIG_DATA.get("货品特殊映射", {})
    if search_name in special_map:
        matched_name = special_map[search_name]
        row = STOCK_DATA[STOCK_DATA['货品名称'] == matched_name]
        if not row.empty:
            res = row.iloc[0].to_dict()
            res.update({"matchType": "matched", "confidence": 100, "source": "special_map", "matchedName": matched_name})
            return res

    # 2. 精确匹配
    exact_name = STOCK_DATA[STOCK_DATA['货品名称'] == search_name]
    if not exact_name.empty:
        res = exact_name.iloc[0].to_dict()
        res.update({"matchType": "matched", "confidence": 100, "source": "exact", "matchedName": search_name})
        return res
        
    exact_spec = STOCK_DATA[STOCK_DATA['规格编号'] == search_name]
    if not exact_spec.empty:
        res = exact_spec.iloc[0].to_dict()
        res.update({"matchType": "matched", "confidence": 100, "source": "exact_spec", "matchedName": res.get('货品名称')})
        return res

    # 3. 模糊纠错引擎
    best_match = None
    max_score = 0
    for _, row in STOCK_DATA.iterrows():
        t_name = str(row.get('货品名称', ''))
        t_spec = str(row.get('规格编号', ''))
        
        score = max(calculate_similarity(search_name, t_name), 
                    calculate_similarity(search_name, t_spec))
        
        if score > max_score:
            max_score = score
            best_match = row.to_dict()
            
    if best_match and max_score > 60:
        best_match.update({
            "matchType": "matched" if max_score > 85 else "fuzzy", 
            "confidence": max_score,
            "source": "fuzzy_engine",
            "matchedName": best_match.get('货品名称')
        })
        return best_match

    return {"matchType": "none", "confidence": 0, "searchName": search_name, "matchedName": "未找到匹配"}

def find_product_match(search_name):
    """
    桥接函数，统一调用高精度引擎
    """
    return find_product_match_advanced(search_name)


def select_express(address, products, raw_text=""):
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
            return target, f"根据原文关键词 '{kw}' 自动匹配"

    # 1. 检查工厂代发/直发
    text_to_check = (address + " " + " ".join([p.get('searchName', '') for p in products])).lower()
    if '工厂代发' in text_to_check: return '工厂代发', "检测到关键词 '工厂代发'"
    if '工厂直发' in text_to_check: return '工厂直发', "检测到关键词 '工厂直发'"
    
    # 2. 识别省份
    provinces = ['北京','天津','上海','重庆','河北','山西','辽宁','吉林','黑龙江','江苏','浙江','安徽','福建','江西','山东','河南','湖北','湖南','广东','海南','四川','贵州','云南','陕西','甘肃','青海','内蒙古','广西','西藏','宁夏','新疆']
    
    # 🌟 强化逻辑：增加省会/主要城市到省份的映射，防止地址中省略省名
    city_to_province = {
        '杭州': '浙江', '宁波': '浙江', '温州': '浙江', '嘉兴': '浙江', '湖州': '浙江', '绍兴': '浙江', '金华': '浙江', '衢州': '浙江', '舟山': '浙江', '台州': '浙江', '丽水': '浙江',
        '南京': '江苏', '无锡': '江苏', '徐州': '江苏', '常州': '江苏', '苏州': '江苏', '南通': '江苏', '连云港': '江苏', '淮安': '江苏', '盐城': '江苏', '扬州': '江苏', '镇江': '江苏', '泰州': '江苏', '宿迁': '江苏',
        '合肥': '安徽', '芜湖': '安徽', '蚌埠': '安徽', '淮南': '安徽', '马鞍山': '安徽', '淮北': '安徽', '铜陵': '安徽', '安庆': '安徽', '黄山': '安徽', '滁州': '安徽', '阜阳': '安徽', '宿州': '安徽', '六安': '安徽', '亳州': '安徽', '池州': '安徽', '宣城': '安徽',
        '广州': '广东', '深圳': '广东', '珠海': '广东', '汕头': '广东', '佛山': '广东', '韶关': '广东', '河源': '广东', '梅州': '广东', '惠州': '广东', '汕尾': '广东', '东莞': '广东', '中山': '广东', '江门': '广东', '阳江': '广东', '湛江': '广东', '茂名': '广东', '肇庆': '广东', '清远': '广东', '潮州': '广东', '揭阳': '广东', '云浮': '广东',
        '福州': '福建', '厦门': '福建', '莆田': '福建', '三明': '福建', '泉州': '福建', '漳州': '福建', '南平': '福建', '龙岩': '福建', '宁德': '福建'
    }

    province = ""
    for p in provinces:
        if p in address:
            province = p
            break
            
    if not province:
        for city, p in city_to_province.items():
            if city in address:
                province = p
                break

    if not province: return "待定(未识别省份)", "无法从地址中识别省份"

    # 3. 检查特殊品类
    # 一体称判定：X开头且不是XP开头
    has_scale = any(str(p.get('searchName','')).upper().startswith('X') and not str(p.get('searchName','')).upper().startswith('XP') for p in products)
    
    # 收银机判定：K开头
    has_register = any(str(p.get('searchName','')).upper().startswith('K') for p in products)
    
    # 计算总重量 (g)
    total_weight = sum([float((p.get('productInfo') or {}).get('重量', 0)) * int(p.get('qty', 1)) for p in products])
    
    if has_scale:
        res = express_rules.get("一体称", {}).get("所有地区", "德邦特惠")
        return res, "货品包含一体称，根据规则使用德邦"
    
    if has_register:
        reg_map = express_rules.get("收银机", {}).get("地区映射", {})
        res = reg_map.get(province, "中通（渠道）")
        return res, f"货品包含收银机，省份 {province} 映射为 {res}"
    
    # 4. 打印机/普通货品 (根据重量分段)
    printer_rules = express_rules.get("打印机", {})
    
    # 确定重量区间
    if total_weight <= 2000:
        weight_seg = "1.01-2kg"
    elif total_weight <= 5000:
        weight_seg = "2kg-5kg"
    else:
        weight_seg = "5kg以上"
        
    seg_map = printer_rules.get(weight_seg, {})
    res = seg_map.get(province, "中通（渠道）")
    
    return res, f"普通货品 (打印机类)，总重 {total_weight}g，适用区间 {weight_seg}，省份 {province} 映射为 {res}"

def process_parsed_data(ai_result, raw_text):
    """对AI返回的结果进行二次处理和数据补充"""
    # 🌟 核心：直接使用传入的原始文本进行正则匹配，不再依赖 AI 返回的 raw 字段
    
    # 1. 业务员验证 (从全文或系统录行末尾识别)
    salesman_code = str(ai_result.get("salesman_code", "")).strip().upper()
    salesman_map = CONFIG_DATA.get("业务员映射", {})
    
    # 增强逻辑：如果原文中有 (W), （W）, (W-新) 等格式，强行提炼
    import re
    actual_code = salesman_code
    # 如果AI没抓到，正则强行在“系统录”最后补位抓取
    if not actual_code:
        m = re.search(r'[\(\（]([A-Z0-9]+)[\)\）]\s*$', raw_text, re.M)
        if m: actual_code = m.group(1).upper()
            
    salesman = salesman_map.get(actual_code, CONFIG_DATA.get("默认业务员", "未分配"))

    # 2. 客户账号提取 (强力锁定“系统录”后面的名字)
    customer_account = ""
    # 增强版正则：穿透所有空格，抓取到第一个分隔符之前的所有文字
    match = re.search(r'系统录[:：\s]*([^\s\n\（\(\[\]]+)', raw_text)
    if match:
        customer_account = match.group(1).strip()
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
    final_customer = None
    customer_candidates = []
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
            customer_candidates = cands[:5]

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
        receipt = raw_account
        for key, val in receipt_map.items():
            if key in raw_account or raw_account in key:
                receipt = val
                break
    else:
        # 如果是“未付”，强制收款账户为空
        receipt = ""

    final_result = {
        "phone": ai_result.get("phone", ""),
        "receiver": ai_result.get("receiver", ""),
        "address": ai_result.get("address", ""),
        "products": [],
        "total": ai_result.get("total_amount", 0),
        "freight": ai_result.get("postage", 0),
        "note": "", # 初始为空，稍后通过正则提取
        "account": customer_account,
        "salesman": salesman,
        "payMethod": pay_method,
        "receipt": receipt,
        "salesChannel": CONFIG_DATA.get("销售渠道", "仝心科技线下批发"),
        "express": "",
        "customer": final_customer,
        "customer_candidates": customer_candidates,
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
        
        match_info = find_product_match_advanced(p_name)
        
        final_result["products"].append({
            "searchName": p_name,
            "noteName": p_name,
            "qty": p_qty,
            "price": p_price,
            "matchedName": match_info.get('货品名称') or match_info.get("matchedName"),
            "matchType": match_info.get("matchType"),
            "source": match_info.get("source"),
            "productInfo": match_info if match_info.get("matchType") in ["matched", "fuzzy"] else None,
            "confidence": match_info.get("confidence", 0),
            "note": "" 
        })
        try:
            calculated_total += float(p_price) * int(p_qty)
        except: pass

    if not final_result["total"] or final_result["total"] == 0:
        final_result["total"] = calculated_total

    # 快递计算
    express_res, express_reason = select_express(final_result["address"], final_result["products"], raw_text=raw_text)
    final_result["express"] = express_res
    final_result["express_reason"] = express_reason

    if final_customer:
        final_result["account"] = final_customer.get("客户账号", "")

    # 备注补充 (强力抓取原文中“备注：”之后的所有内容)
    # 1. 提取产品信息部分
    prod_note = "+".join([f"{p['searchName']}*{p['qty']}" for p in final_result["products"] if p.get('searchName')])
    
    # 2. 从原文中强力提取“备注”二字后的内容
    import re
    extra_remark = ""
    remark_match = re.search(r'备注[:：\s]*(.*)', raw_text, re.S)
    if remark_match:
        extra_remark = remark_match.group(1).strip()
    else:
        # 如果原文中没有“备注”关键字，则不添加额外备注
        extra_remark = ""
        
    final_result["note"] = f"{prod_note} {extra_remark}".strip()

    # 3. 将备注也同步给每一个具体的货品行
    for p in final_result["products"]:
        p["note"] = extra_remark

    return sanitize_data(final_result)


# --- API 路由 ---
@app.route('/api/learn', methods=['POST'])
def learn_endpoint():
    try:
        data = request.json
        l_type, raw, matched = data.get("type", "product"), data.get("rawName"), data.get("matchedName")
        if not raw or not matched: return jsonify({"status": "error"}), 400
        key = "货品特殊映射" if l_type == "product" else "客户特殊映射"
        if key not in CONFIG_DATA: CONFIG_DATA[key] = {}
        CONFIG_DATA[key][raw] = matched
        with open('data/配置规则.json', 'w', encoding='utf-8') as f:
            json.dump(CONFIG_DATA, f, ensure_ascii=False, indent=4)
        print(f"💡 系统进步：[{l_type}] {raw} -> {matched}")
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
    
    # 提取所有货品名及完整元数据供前端联动 (合并总库存与组合装)
    all_products_set = set()
    all_products_data = []
    
    if STOCK_DATA is not None and not STOCK_DATA.empty:
        all_products_set.update(STOCK_DATA['货品名称'].dropna().unique())
        all_products_data.extend(STOCK_DATA.to_dict('records'))
        
    if COMBO_DATA is not None and not COMBO_DATA.empty:
        all_products_set.update(COMBO_DATA['货品名称'].dropna().unique())
        all_products_data.extend(COMBO_DATA.to_dict('records'))

    return sanitize_data({
        "salesmen": salesmen,
        "customers": customers,
        "payMethods": pay_methods,
        "receipts": receipts,
        "allProducts": sorted(list(all_products_set)),
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
        
    print("\n--- 收到新的解析请求 ---")
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "请求体为空或缺少'text'字段"}), 400

    order_text = data['text']
    print(f"订单原文: {order_text[:100]}...")

    # 1. 使用AI进行初步解析
    ai_result, error = parse_order_with_ai(order_text)
    
    if error:
        print(f"❌ AI解析失败: {error}")
        return jsonify({"error": error, "parseMethod": "AI失败"}), 500

    print(f"✅ AI 初步解析成功: {ai_result}")

    # 2. 对AI结果进行后处理和数据补充
    final_data = process_parsed_data(ai_result, order_text)
    final_data['raw'] = order_text
    
    # 核心修复：清理所有可能来自 Excel 的 NaN 值，防止前端解析 JSON 报错
    final_data = sanitize_data(final_data)

    print(f"✅ 数据后处理完成, 准备返回前端。")
    return jsonify(final_data)


# --- 配置管理接口 ---
@app.route('/api/config', methods=['GET'])
def get_config():
    """获取当前所有配置"""
    return jsonify(sanitize_data(CONFIG_DATA))

@app.route('/api/config', methods=['POST'])
def save_config():
    """保存并更新配置"""
    global CONFIG_DATA
    try:
        new_config = request.json
        if not new_config: return jsonify({"error": "无效配置"}), 400
        
        # 合并或替换
        CONFIG_DATA = new_config
        
        # 写入文件
        config_path = os.path.join(DATA_DIR, '配置规则.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(CONFIG_DATA, f, ensure_ascii=False, indent=4)
            
        print("✅ 配置文件已通过网页更新")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    """让内网用户通过IP直接访问网页界面"""
    html_path = os.path.join(os.path.dirname(__file__), '..', 'order-assistant-full.html')
    if os.path.exists(html_path):
        return send_file(html_path)
    return "找不到页面文件，请确保 order-assistant-full.html 在正确位置。"

# --- 主程序运行 ---
if __name__ == '__main__':
    try:
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
            print(f"🚀 下单助手内网版已启动！")
            print(f"🏠 本地访问: http://127.0.0.1:5000")
            print(f"🌐 局域网访问: http://{local_ip}:5000 (同事请访问此地址)")
            print("="*50 + "\n")

        # 注意：这里不再传 debug=True，因为上面已经设过了
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        print("\n" + "!"*60)
        print(f"❌ 程序发生严重错误，无法启动:")
        print(f"【错误简述】: {e}")
        print("-" * 20 + " 详细错误堆栈 " + "-" * 20)
        import traceback
        traceback.print_exc()
        print("!"*60 + "\n")
        input("程序已停止，请查看上方错误信息后，按回车键关闭窗口...")
