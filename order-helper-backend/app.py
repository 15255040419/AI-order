import os
import json
import pandas as pd
import requests
import math
from flask import Flask, request, jsonify
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
ZHIPU_API_KEY = "7bd6e3eca730448c8ffac4c786cd092a.XfOv2YlnrDp44XO5" # <-- 在这里替换成你的API Key

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
# --- AI 解析函数 ---
def parse_order_with_ai(text):
    """调用智谱AI并提供上下文（货品列表）进行解析"""
    if not ZHIPU_API_KEY or ZHIPU_API_KEY == "在这里填入你的智谱AI API密钥":
        return None, "智谱AI API密钥未配置"

    product_list = CONFIG_DATA.get('internal_product_list', [])
    # 限制知识库长度，避免超出 Token 限制
    product_knowledge_base = ", ".join(product_list[:500]) if len(product_list) > 500 else ", ".join(product_list)
    
    prompt = f"""
你是一个专业的订单解析助手。请解析以下订单文本，提取结构化信息。

【订单文本】:
{text}

【货品列表参考】:
{product_knowledge_base}

请提取以下信息并以纯JSON格式返回（不要包含任何其他文字说明、不要使用代码块标记）：
{{
  "receiver": "收货人姓名",
  "phone": "手机号",
  "address": "完整地址",
  "products": [
    {{
      "name": "识别到的货品名称/型号",
      "qty": 数量(整数),
      "price": 单价(数字，如果文本中有 90*2=180 这种，单价是90)
    }}
  ],
  "payment_status": "付款状态（已付/未付）",
  "payment_account": "收款账户（如已付农商、财务微信等）",
  "customer_account": "客户账号",
  "salesman_code": "业务员标记字母（如 L, W, TX 等）",
  "postage": 邮费(数字),
  "total_amount": 总价(数字，加法算式后的结果),
  "extra_note": "附加备注（如工厂代发等）"
}}

识别规则：
1. 信息结构：[收件人/电话] [地址] [详情*数量 价格] [已付/未付 收款账户] [系统录 客户账号] [业务员代码]。
2. 基础信息：从文本开头提取 姓名、手机、地址。地址识别要全，补全省市区逻辑。
3. 货品与算式：识别 "货品*数量 价格" 或 "名称*数量=总价"。注意防污染：若货品名含星号（如 57*50 纸），严禁将数量后缀（如 *10）带入 name。例："57*50*10卷纸" 解析为 name: "57*50卷纸", qty: 10。
4. 收款：找到 "已付" 关键字，提取其紧随其后的账户名（如 "已付农商成" 账户为 "农商成"）。
5. 客户识别：查找“系统录”关键字，其后的文字即为客户账号。必须精准抓取名字（如“罗金舟”）。
6. 业务员验证：只有在文中出现括号内的字母时才识别（例如：(L), (W)）。严禁凭空猜测或从杂碎文字中关联。若无括号包裹代码，salesman_code 必须为空。
7. 返回格式必须是 JSON，字段名参考前述说明。
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
    # 去除空隙和常见分隔符：空格, -, _, /, *, ( )
    return re.sub(r'[\s\-_\/\*\(\)\（\）]', '', str(s)).lower()

def find_product_match(name):
    """在本地库中查找货品匹配 (强化模糊匹配 & 符号容错)"""
    if not name: return {"matchedName": "未知", "matchType": "unmatched"}
    
    # 1. 特殊映射优先
    special_map = CONFIG_DATA.get("货品特殊映射", {})
    search_name = name
    c_search_name = clean_str(name)

    # 查特殊映射时也走一次规范化匹配
    for key, val in special_map.items():
        if c_search_name == clean_str(key) or c_search_name == clean_str(val):
            if val == "__SKIP__":
                return {"matchedName": name, "matchType": "skip", "source": "特殊映射跳过"}
            search_name = val
            break
    
def find_product_match(name):
    """在本地库中查找货品匹配 (强化模糊评分 & 权重算法)"""
    if not name: return {"matchedName": "未知", "matchType": "unmatched"}
    
    import difflib
    
    # 1. 特殊映射优先
    special_map = CONFIG_DATA.get("货品特殊映射", {})
    c_search_name = clean_str(name)
    for key, val in special_map.items():
        if c_search_name == clean_str(key):
            return {"matchedName": val, "matchType": "matched", "source": "记忆学习"}

    # 2. 评分机制
    candidates = []
    
    # 抽取所有库存用于评分
    for _, row in STOCK_DATA.iterrows():
        t_name = str(row.get('货品名称', '')).strip()
        t_spec_no = str(row.get('规格编号', '')).strip()
        t_spec = str(row.get('规格', '')).strip()
        
        # 针对三列分别计算模糊相似度 (0.0 - 1.0)
        # 权重：规格编号(1.2) > 货品名称(1.0) > 规格(0.8)
        s1 = difflib.SequenceMatcher(None, c_search_name, clean_str(t_spec_no)).ratio() * 1.2
        s2 = difflib.SequenceMatcher(None, c_search_name, clean_str(t_name)).ratio() * 1.0
        s3 = difflib.SequenceMatcher(None, c_search_name, clean_str(t_spec)).ratio() * 0.8
        
        max_score = max(s1, s2, s3)
        if max_score > 0.4: # 设定一个最低阈值，防止风马牛不相及的也进来
            candidates.append({"score": max_score, "data": row.to_dict()})

    if candidates:
        # 按评分由高到低排序
        candidates.sort(key=lambda x: x['score'], reverse=True)
        best = candidates[0]['data']
        return {
            **best, 
            "matchedName": best.get('货品名称'), 
            "matchType": "matched", 
            "source": f"智能匹配(相似度:{round(candidates[0]['score'],2)})",
            "candidates": [c['data'].get('货品名称') for c in candidates[:10]] # 返回前10个备选
        }
    
    # 3. 组合装兜底 (略)
    return {"matchedName": name, "matchType": "unmatched", "source": "未匹配"}


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
            return target

    # 1. 检查工厂代发/直发
    text_to_check = (address + " " + " ".join([p.get('searchName', '') for p in products])).lower()
    if '工厂代发' in text_to_check: return '工厂代发'
    if '工厂直发' in text_to_check: return '工厂直发'
    
    # 2. 识别省份
    provinces = ['北京','天津','上海','重庆','河北','山西','辽宁','吉林','黑龙江','江苏','浙江','安徽','福建','江西','山东','河南','湖北','湖南','广东','海南','四川','贵州','云南','陕西','甘肃','青海','内蒙古','广西','西藏','宁夏','新疆']
    province = ""
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

def process_parsed_data(ai_result):
    """对AI返回的结果进行二次处理和数据补充"""
    raw_text = ai_result.get("raw", "")
    
    # 1. 业务员验证 (必须在原文中有括号包裹的代码，如 (L))
    salesman_code = str(ai_result.get("salesman_code", "")).strip().upper()
    salesman_map = CONFIG_DATA.get("业务员映射", {})
    
    # 二次验证逻辑：原文中必须包含类似 (L) 或 (W) 的字样才接受
    import re
    actual_code = None
    if salesman_code:
        # 支持各种形式的括号，包括中文/英文、单双括号 (W), （W）, （W））
        if re.search(rf'[\(\（]{salesman_code}[\)\）]+', raw_text, re.I):
            actual_code = salesman_code
            
    salesman = salesman_map.get(actual_code, CONFIG_DATA.get("默认业务员", "未分配"))

    # 2. 客户账号清洗与正则兜底
    # 优先从原文正则寻找“系统录”后面的名字，因为AI抓取的可能带杂质（如括号代码）
    customer_account = ""
    match = re.search(r'系统录\s*([^\s\n\（\(]+)', raw_text)
    if match:
        customer_account = match.group(1).strip()
        customer_account = customer_account.replace('“', '').replace('”', '').replace('"', '')
    
    # 如果正则没抓到，再用AI抓的结果作为补充
    if not customer_account:
        customer_account = str(ai_result.get("customer_account", "")).strip()
    
    # 清洗：如果带了 (W) 或 （W）之类的后缀，强行剥离
    customer_account = re.sub(r'[\(\（].*?[\)\）]+', '', customer_account).strip()

    # 2.1 客户账号匹配 (从档案里找真正的账号ID)
    if customer_account and CUSTOMER_DATA is not None and not CUSTOMER_DATA.empty:
        # 尝试查找客户名称、联系人或账号匹配
        search_phone = str(ai_result.get("phone", "")).strip()
        
        # 使用 regex=False 避免符号报错
        cust_match = CUSTOMER_DATA[
            (CUSTOMER_DATA['客户名称'].str.contains(customer_account, na=False, regex=False)) |
            (CUSTOMER_DATA['联系人'].str.contains(customer_account, na=False, regex=False)) |
            (CUSTOMER_DATA['客户账号'].str.contains(customer_account, na=False, regex=False))
        ]
        
        # 如果名称没找到，尝试通过电话找
        if cust_match.empty and search_phone:
            cust_match = CUSTOMER_DATA[CUSTOMER_DATA['联系电话'].astype(str).str.contains(search_phone, na=False, regex=False)]

        if not cust_match.empty:
            customer_account = cust_match.iloc[0]['客户账号']

    # 3. 收款账户映射与清洗
    raw_account = str(ai_result.get("payment_account", "")).strip()
    if raw_account.startswith("已付"):
        raw_account = raw_account[2:].strip()
        
    receipt_map = CONFIG_DATA.get("收款账户映射", {})
    receipt = raw_account
    for key, val in receipt_map.items():
        if key in raw_account or raw_account in key:
            receipt = val
            break

    final_result = {
        "phone": ai_result.get("phone", ""),
        "receiver": ai_result.get("receiver", ""),
        "address": ai_result.get("address", ""),
        "products": [],
        "total": ai_result.get("total_amount", 0),
        "freight": ai_result.get("postage", 0),
        "note": ai_result.get("extra_note", ""),
        "account": customer_account,
        "salesman": salesman,
        "payMethod": "银行收款" if ai_result.get("payment_status") == "已付" else "欠款计应收",
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
    final_result["express"] = select_express(final_result["address"], final_result["products"], raw_text=raw_text)

    # 客户匹配
    if CUSTOMER_DATA is not None and not CUSTOMER_DATA.empty:
        search_phone = str(final_result['phone'])
        c_match = CUSTOMER_DATA[CUSTOMER_DATA['联系电话'].astype(str).str.contains(search_phone, na=False)]
        if c_match.empty and final_result['account']:
            c_match = CUSTOMER_DATA[CUSTOMER_DATA['客户账号'].str.contains(final_result['account'], na=False)]
        
        if not c_match.empty:
            final_result["customer"] = c_match.iloc[0].to_dict()

    # 备注补充
    prod_note = " ".join([f"{p['searchName']}*{p['qty']}" for p in final_result["products"]])
    final_result["note"] = f"{prod_note} {final_result['note']}".strip()

    return final_result




# --- API 路由（程序入口） ---
@app.route('/api/learn', methods=['POST'])
def learn_endpoint():
    """学习接口：保存用户的手动修正映射"""
    try:
        data = request.json
        raw_name = data.get("rawName") # 用户输入的原始名
        matched_name = data.get("matchedName") # 库中真实的货品名称
        
        if not raw_name or not matched_name:
            return jsonify({"status": "error", "message": "缺少参数"}), 400
            
        # 更新配置
        if "货品特殊映射" not in CONFIG_DATA:
            CONFIG_DATA["货品特殊映射"] = {}
        
        # 记录映射
        CONFIG_DATA["货品特殊映射"][raw_name] = matched_name
        
        # 保存到本地文件以持久化
        with open('data/配置规则.json', 'w', encoding='utf-8') as f:
            json.dump(CONFIG_DATA, f, ensure_ascii=False, indent=4)
            
        print(f"💡 系统已自动进步：学习了映射 {raw_name} -> {matched_name}")
        return jsonify({"status": "ok", "message": "进步成功"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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
    
    # 提取所有货品名供前端手动修正
    all_products = []
    if STOCK_DATA is not None and not STOCK_DATA.empty:
        all_products = list(STOCK_DATA['货品名称'].dropna().unique())

    return jsonify({
        "salesmen": salesmen,
        "customers": customers,
        "payMethods": pay_methods,
        "receipts": receipts,
        "allProducts": all_products
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
    final_data = process_parsed_data(ai_result)
    final_data['raw'] = order_text
    
    # 核心修复：清理所有可能来自 Excel 的 NaN 值，防止前端解析 JSON 报错
    final_data = sanitize_data(final_data)

    print(f"✅ 数据后处理完成, 准备返回前端。")
    return jsonify(final_data)


# --- 主程序运行 ---
if __name__ == '__main__':
    load_data() # 程序启动时，加载一次数据
    # host='0.0.0.0' 让局域网内其他电脑可以访问
    # port=5000 是端口号
    app.run(host='0.0.0.0', port=5000, debug=True)
