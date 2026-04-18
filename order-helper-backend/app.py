import os
import re
import json
import pandas as pd
import requests
import math
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import difflib
from fuzzywuzzy import fuzz

# --- 全局变量 ---
CUSTOMER_HISTORY = {} # { "客户名": ["货品A", "货品B"] }

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

# 全局变量定义
EXPRESS_RULES = {}
EXPRESS_OPTIONS = []
EXPRESS_TABLE = {}  # 🌟 新增：省份品类重量映射表

def load_data():
    """在程序启动时加载所有数据文件到内存中"""
    global STOCK_DATA, COMBO_DATA, CUSTOMER_DATA, CONFIG_DATA, EXPRESS_RULES, EXPRESS_OPTIONS, CUSTOMER_HISTORY
    
    data_path = 'data'
    print("--- 正在加载数据文件 ---", flush=True)
    try:
        STOCK_DATA = pd.read_excel(os.path.join(data_path, '总库存.xlsx'))
        print(f"[OK] 总库存.xlsx 加载成功，共 {len(STOCK_DATA)} 条记录", flush=True)
        # 辅助函数：判断是否需要重新加载 Excel
        def get_cached_data(excel_name, cache_name):
            e_p = os.path.join(data_path, excel_name)
            c_p = os.path.join(data_path, cache_name)
            if not os.path.exists(e_p): return None
            
            # 如果存在缓存且缓存比 Excel 新，直接读缓存
            if os.path.exists(c_p) and os.path.getmtime(c_p) > os.path.getmtime(e_p):
                try:
                    return pd.read_json(c_p, orient='records')
                except: pass
            
            # 否则读取 Excel 并存入缓存
            df = pd.read_excel(e_p)
            df.to_json(c_p, orient='records', force_ascii=False)
            return df

        # 1. 🌟 加载配置规则 (始终优先读取 JSON)
        cfg_path = os.path.join(data_path, '配置规则.json')
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                CONFIG_DATA = json.load(f)
            EXPRESS_RULES = CONFIG_DATA.get("快递规则", {})
        
        # 2. 🌟 加载核心数据 (带缓存机制)
        STOCK_DATA = get_cached_data('总库存.xlsx', 'stock_cache.json')
        COMBO_DATA = get_cached_data('总库存-组合装明细.xlsx', 'combo_cache.json')
        CUSTOMER_DATA = get_cached_data('客户档案.xlsx', 'customer_cache.json')
        
        print("[OK] 基础数据加载成功 (已启用 JSON 缓存提速)", flush=True)

        # 提取一个简单的货品列表给AI参考
        stock_list = STOCK_DATA['货品名称'].dropna().unique().tolist()
        spec_list = STOCK_DATA['规格编号'].dropna().unique().tolist()
        combo_list = COMBO_DATA['货品名称'].dropna().unique().tolist()

        # 合并所有货品名称，创建一个给AI参考的知识库
        all_products = list(set(stock_list + spec_list + combo_list))
        
        print("[OK] 配置规则.json 加载成功", flush=True)
        
        # 🌟 加载客户历史库
        try:
            with open(os.path.join(data_path, 'customer_history.json'), 'r', encoding='utf-8') as f:
                CUSTOMER_HISTORY = json.load(f)
        except: CUSTOMER_HISTORY = {}
        
        # 🌟 3. 动态加载快递选项 (带缓存机制)
        ex_path = 'data/快递表格.xls'
        ex_cache = 'data/express_cache.json'
        df_ex = None
        
        if os.path.exists(ex_cache) and os.path.exists(ex_path) and os.path.getmtime(ex_cache) > os.path.getmtime(ex_path):
            try: df_ex = pd.read_json(ex_cache, orient='records')
            except: pass
            
        if df_ex is None and os.path.exists(ex_path):
            df_ex = pd.read_excel(ex_path, header=None)
            df_ex.to_json(ex_cache, orient='records', force_ascii=False)

        if df_ex is not None:
            
            # 1. 提取下拉框选项
            cols_idx = [1, 2, 3, 4, 5, 6]
            opts = set()
            for c_idx in cols_idx:
                col_key = c_idx if c_idx in df_ex.columns else str(c_idx)
                opts.update(df_ex[col_key].dropna().astype(str).unique())
            noise = ['1.01-2KG', '2kg-5kg', '5kg以上', '不按重量只按地区', '只要是称都发德邦', 'nan']
            EXPRESS_OPTIONS = sorted([x for x in opts if x.strip() and x not in noise])
            
            # 2. 🌟 构建核心分拣映射表 (EXPRESS_TABLE)
            # 结构: { "浙江": { "打印机_小": "中通", ... } }
            for i in range(2, len(df_ex)):
                row = df_ex.iloc[i]
                prov = str(row[0]).strip().replace('省', '').replace('市', '')
                if not prov or prov == 'nan' or len(prov) > 5: continue
                
                EXPRESS_TABLE[prov] = {
                    "打印机_小": str(row[1]).strip(),
                    "打印机_中": str(row[2]).strip(),
                    "打印机_大": str(row[3]).strip(),
                    "收银机": str(row[4]).strip(),
                    "一体称": str(row[5]).strip(),
                    "其他": str(row[6]).strip()
                }
            logger.info(f"成功加载快递分拣引擎：已缓存 {len(EXPRESS_TABLE)} 个省份规则")

        # 将货品列表存入配置，方便后续使用
        CONFIG_DATA['internal_product_list'] = all_products
        # 🌟 进一步优化：增加客户和业务员的精简参考
        customer_list = []
        if CUSTOMER_DATA is not None and not CUSTOMER_DATA.empty:
            customer_list = CUSTOMER_DATA['客户账号'].dropna().unique().tolist()[:300] # 取前300个老客户
        
        salesmen_list = list(CONFIG_DATA.get("业务员映射", {}).keys())
        
        # 创建一个全能的 AI 上下文参考
        CONFIG_DATA['ai_product_reference'] = ", ".join(all_products[:600]) 
        CONFIG_DATA['ai_customer_reference'] = ", ".join(customer_list)
        CONFIG_DATA['ai_salesman_reference'] = ", ".join(salesmen_list)
        
        print(f"--- 数据预加载完成：库存({len(all_products)})，客户({len(customer_list)})，业务员({len(salesmen_list)}) ---", flush=True)
        
    except FileNotFoundError as e:
        print(f"[ERROR] 错误：找不到文件 {e.filename}。请确保所有数据文件都在 'data' 文件夹中。")
    except Exception as e:
        print(f"[ERROR] 加载数据时发生未知错误: {e}")

# --- AI 解析函数 ---
# --- AI 解析函数 ---
def parse_order_with_ai(text):
    """调用智谱AI并提供动态上下文"""
    if not ZHIPU_API_KEY or ZHIPU_API_KEY == "在这里填入你的智谱AI API密钥":
        return None, "智谱AI API密钥未配置"

    # 1. 尝试识别客户背景，获取偏好货品
    history_hint = ""
    for customer, items in CUSTOMER_HISTORY.items():
        if customer in text or (len(customer) > 4 and customer[:4] in text):
            history_details = []
            for item in items[:12]:
                if isinstance(item, dict):
                    name_str = item.get("matchedName", "")
                    spec_str = f"[{item.get('spec','')}]" if item.get('spec') else ""
                    no_str = f"编号:{item.get('spec_no','')}" if item.get('spec_no') else ""
                    history_details.append(f"{name_str} {spec_str} {no_str}")
                else:
                    history_details.append(str(item))
            history_hint = f"\n【重要：该客户历史档案】:\n- " + "\n- ".join(history_details) + "\n(注意：如果原文包含以上货品，请务必返回对应的标准名称和编号)"
            break

    # 2. 货品筛选优化 (兼顾广度)
    all_products = CONFIG_DATA.get('internal_product_list', [])
    relevant_products = []
    keywords = re.findall(r'[A-Z0-9]{2,}|[\u4e00-\u9fa5]{2,}', text.upper())
    
    for p in all_products:
        p_up = p.upper()
        if any(kw in p_up for kw in keywords):
            relevant_products.append(p)
        if len(relevant_products) > 300: break
    
    # 基础兜底
    if len(relevant_products) < 50:
        relevant_products.extend(all_products[:100])
        relevant_products = list(set(relevant_products))
        
    product_ref = ", ".join(relevant_products)
    customer_ref = CONFIG_DATA.get('ai_customer_reference', '无')
    salesman_ref = CONFIG_DATA.get('ai_salesman_reference', '无')

    # 1.5 注入业务规范约束 (来自配置规则.json)
    biz_constraints = f"""
- 可选快递: {', '.join(list(CONFIG_DATA.get('快递对应关系', {}).keys())[:20])}
- 付款账号: {', '.join(list(CONFIG_DATA.get('付款账号对应关系', {}).keys()))}
- 付款状态: {', '.join(list(CONFIG_DATA.get('付款状态对应关系', {}).keys()))}
"""

    prompt = f"""请提取订单信息，返回 JSON。
不要解释。

【待解析文本】:
{text}
{history_hint}

【参考库】:
- 货品目录: {product_ref}
- 老客户名单: {customer_ref}
- 业务员代码: {salesman_ref}
【业务规范】:
{biz_constraints}

【JSON 字段要求】:
{{
  "receiver": "姓名",
  "phone": "电话",
  "address": "地址",
  "province": "省份",
  "products": [ {{ "name": "标准货品名", "qty": 数量, "price": 单价 }} ],
  "payment_status": "已付/未付",
  "payment_account": "收款账户 (匹配【业务规范】中的付款账号)",
  "customer_account": "客户账号 (优先匹配【老客户名单】)",
  "salesman_code": "业务员代码 (优先匹配【业务员代码】)",
  "postage": 0,
  "total_amount": 0,
  "extra_note": "备注内容"
}}

【特别硬规则（必须严格遵守）】:
1. 禁止污染名字：货品名称中绝对不能包含数量标识（如 *2, x1, 2台, 两台）。数量必须单独放在 "qty" 字段。
2. 剥离备注：如果原文是 "T80Q黑色"，请将 "T80Q" 填入 name，"黑色" 填入 extra_note。
3. 匹配优先：如果原文货品名在【参考库】或【历史档案】中有相似项，必须返回库中的标准全称。
4. 排除干扰：姓名或地址后的编号（如 [1783]）请保留在原字段，不要漏掉。
5. 结果格式：直接返回 JSON，不要任何解释文字。"""

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
    """
    货品智能匹配引擎 (高精度版)
    目标：匹配到最详细的 [货品名称(规格)] 并携带所有元数据
    """
    if not name: return {"matchedName": "未知", "matchType": "unmatched"}
    
    # 🌟 预处理：剔除常见的数量干扰项 (如 *2, x1, X3)
    clean_name = re.sub(r'[*xX]\d+$', '', name.strip())
    name_clean = clean_str(clean_name).upper()
    # 0. 尝试记忆映射
    special_map = CONFIG_DATA.get("货品对应关系", {})
    for key, val in special_map.items():
        if name_clean == clean_str(key).upper():
            m_row = STOCK_DATA[STOCK_DATA['货品名称'].astype(str).str.strip() == str(val).strip()]
            if not m_row.empty:
                row = m_row.iloc[0]
                spec = str(row.get('规格', '')).strip()
                full_name = f"{val}({spec})" if spec and spec != '默认规格' and spec != 'nan' else str(val)
                return {**row.to_dict(), "matchedName": full_name, "matchType": "matched", "source": "记忆映射"}
            return {"matchedName": val, "matchType": "matched", "source": "仅记忆映射"}

    # 1. 完全匹配 (使用清理后的名字)
    exact = STOCK_DATA[(STOCK_DATA['货品名称'].astype(str) == clean_name) | (STOCK_DATA['规格编号'].astype(str) == clean_name)]
    if not exact.empty:
        row = exact.iloc[0]
        p_name = str(row['货品名称'])
        p_spec = str(row.get('规格', '')).strip()
        full_name = f"{p_name}({p_spec})" if p_spec and p_spec != '默认规格' and p_spec != 'nan' else p_name
        return {**row.to_dict(), "matchedName": full_name, "matchType": "matched", "source": "精确匹配"}

    # 2. 遍历库存，模糊/包含评分
    best_match = None
    max_score = 0
    for _, row in STOCK_DATA.iterrows():
        p_name = str(row.get('货品名称', '')).strip()
        p_spec = str(row.get('规格', '')).strip()
        p_no = str(row.get('规格编号', '')).strip()
        full_name = f"{p_name}({p_spec})" if p_spec and p_spec != '默认规格' and p_spec != 'nan' else p_name
        
        if (p_no and p_no.upper() in name_clean) or (p_name and p_name.upper() in name_clean):
            matched_key = p_no if (p_no and p_no.upper() in name_clean) else p_name
            rem = name_clean.replace(matched_key.upper(), '', 1)
            if not re.search(r'^[A-Z0-9]', rem):
                return {**row.to_dict(), "matchedName": full_name, "matchType": "matched", "source": "包含匹配"}

        score = fuzz.token_sort_ratio(name_clean, clean_str(full_name).upper())
        if score > max_score:
            max_score = score
            best_match = {**row.to_dict(), "matchedName": full_name}

    if max_score > 55:
        return {**best_match, "matchType": "matched", "source": f"智能匹配({max_score}分)"}
    
    return {"matchedName": name, "matchType": "unmatched", "source": "未匹配"}



def select_express(address, products, raw_text="", ai_province="", receiver=""):
    """
    根据地址、品类、重量自动分拣快递 (排除姓名和地址干扰)
    """
    explicit_map = {
        "顺丰": "顺丰现付（渠道）", "圆通": "圆通（渠道）", "中通": "中通（渠道）",
        "极兔": "极兔渠道（新）", "德邦": "德邦特惠", "工厂": "工厂直发"
    }
    
    # 🌟 严谨逻辑：从原文中扣除地址和姓名，防止“圆通北路”这种地名干扰判定
    text_to_check = raw_text
    if address: text_to_check = text_to_check.replace(address, "")
    if receiver: text_to_check = text_to_check.replace(receiver, "")
    
    for kw, target in explicit_map.items():
        # 仅在非地址、非姓名的区域匹配明确的指令
        pattern = rf"(?:发|走|指定|要|送|快递|备注)[:：\s]*{kw}"
        if re.search(pattern, text_to_check):
            return target, f"[用户手动指定] -> {target}"
    
    provinces = ["北京","天津","河北","山西","内蒙古","辽宁","吉林","黑龙江","上海","江苏","浙江","安徽","福建","江西","山东","河南","湖北","湖南","广东","广西","海南","重庆","四川","贵州","云南","西藏","陕西","甘肃","青海","新疆"]
    province = ""
    for p in provinces:
        if (ai_province and p in ai_province) or (p in address): province = p; break
    if not province: return "中通（渠道）", "未识别到省份，默认发中通"
    
    rule = EXPRESS_TABLE.get(province)
    if not rule: return "中通（渠道）", f"[{province}] 暂无匹配规则，默认中通"
    
    total_weight, has_scale, has_cashier = 0, False, False
    cat_rules = CONFIG_DATA.get("品类判定", {})
    scale_cfg = cat_rules.get("一体称", {"前缀": ["X"], "关键词": ["一体称"]})
    reg_cfg = cat_rules.get("收银机", {"前缀": ["K"], "关键词": ["收银机"]})
    
    for p in products:
        info = p.get("productInfo", {}) or {}
        name = str(p.get("matchedName", "") or p.get("searchName", "")).upper()
        qty = int(p.get("qty", 1))
        w = info.get("重量", 0)
        try: total_weight += float(w) * qty
        except: pass
        # 判定品类 (结合正则前缀和关键词判定)
        # 一体称判定：正则 X+数字 OR 关键词
        if re.match(r'^X\d', name) or any(kw in name for kw in scale_cfg.get("关键词", [])):
            has_scale = True
        
        # 收银机判定：正则 K+数字 OR 关键词
        if re.match(r'^K\d', name) or any(kw in name for kw in reg_cfg.get("关键词", [])):
            has_cashier = True
    
    def normalize(name):
        if not name or str(name) == "nan": return None
        if name == "圆通": return "圆通（渠道）"
        if name == "中通": return "中通（渠道）"
        return str(name).strip()
    
    if has_scale:
        res = normalize(rule.get("一体称"))
        final = res or "德邦特惠"
        return final, f"[{province}][一体称] -> {final}"
    if has_cashier:
        res = normalize(rule.get("收银机"))
        final = res or normalize(rule.get("打印机_大")) or "圆通（渠道）"
        return final, f"[{province}][收银机] -> {final}"
    
    weight_str = f"{round(total_weight,2)}kg"
    if total_weight <= 2.0:
        res = normalize(rule.get("打印机_小"))
        return res, f"[{province}][打印机][{weight_str}] -> {res}"
    elif total_weight <= 5.0:
        res = normalize(rule.get("打印机_中"))
        return res, f"[{province}][打印机][{weight_str}] -> {res}"
    else:
        res = normalize(rule.get("打印机_大"))
        return res, f"[{province}][打印机][{weight_str}] -> {res}"

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
    customer_candidates = []
    if CUSTOMER_DATA is not None and not CUSTOMER_DATA.empty:
        p_phone = str(ai_result.get('phone', ''))
        # 尝试通过手机号匹配
        c_match = CUSTOMER_DATA[CUSTOMER_DATA['联系电话'].astype(str).str.contains(p_phone, na=False)] if p_phone else pd.DataFrame()
        
        if c_match.empty:
            # 🌟 硬规则：客户对应关系强制拦截
            cust_map = CONFIG_DATA.get("客户对应关系", {})
            # A. 精确匹配
            if customer_account in cust_map:
                target_acc = cust_map[customer_account]
                c_match = CUSTOMER_DATA[CUSTOMER_DATA['客户账号'] == target_acc]
            # B. 关键词拦截 (只要原文包含关键词)
            else:
                for kw, target_acc in cust_map.items():
                    if kw in raw_text:
                        customer_account = target_acc
                        c_match = CUSTOMER_DATA[CUSTOMER_DATA['客户账号'] == target_acc]
                        break

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
        
        # 🌟 多表头兼容提取
        def get_field(data, keys):
            for k in keys:
                if data.get(k): return str(data[k])
            return ""

        product_entry = {
            "searchName": p_name,
            "noteName": p_name,
            "qty": p_qty,
            "price": p_price,
            "matchedName": match_info.get("matchedName", p_name),
            "matchType": match_info.get("matchType"),
            "source": match_info.get("source"),
            "spec_no": get_field(match_info, ["规格编号", "货品代码", "编码", "货品编号"]),
            "item_no": get_field(match_info, ["货品编号", "货品代码", "商品编号"]),
            "barcode": get_field(match_info, ["条码", "条形码", "商品条码"]),
            "spec": get_field(match_info, ["规格", "货品规格", "型号规格"]),
            "productInfo": match_info if match_info.get("matchType") == "matched" else None
        }
        final_result["products"].append(product_entry)
        try:
            calculated_total += float(p_price) * int(p_qty)
        except: pass

    if not final_result["total"] or final_result["total"] == 0:
        final_result["total"] = calculated_total

    # 快递计算
    # 快递处理
    res_exp, res_reason = select_express(
        final_result["address"], 
        final_result["products"], 
        raw_text=raw_text, 
        ai_province=ai_result.get("province", ""),
        receiver=final_result["receiver"]
    )
    final_result["express"] = res_exp
    final_result["expressReason"] = res_reason

    # 最终结果整合
    final_result["customer"] = final_customer
    final_result["customer_candidates"] = customer_candidates
    if final_customer:
        final_result["account"] = final_customer.get("客户账号", "")

    # 🌟 最终备注逻辑：货品清单(必填) + 显式备注(选填)
    # 1. 自动生成货品清单部分 (本地逻辑)
    prod_list_str = " ".join([f"{p['searchName']}*{p['qty']}" for p in final_result["products"] if p.get('searchName')])
    
    # 2. 尝试从原文抓取显式备注
    note_regex_match = re.search(r'备注[:：\s]*(.*)', raw_text, re.S)
    explicit_note = ""
    if note_regex_match:
        explicit_note = note_regex_match.group(1).strip()
        # 简单清洗显式备注里的垃圾词
        for trash in ["元", "未付", "系统录", "：", ":"]:
            explicit_note = explicit_note.replace(trash, "")
    
    # 3. 组合最终备注
    final_result["note"] = f"{prod_list_str} {explicit_note}".strip()

    # 🌟 4. 全自动记录客户购买习惯 (本地持久化)
    cust_acc = final_result.get("account")
    if cust_acc:
        global CUSTOMER_HISTORY
        changed = False
        if cust_acc not in CUSTOMER_HISTORY:
            CUSTOMER_HISTORY[cust_acc] = []
            changed = True
        
        for p in final_result["products"]:
            m_name = p.get("matchedName")
            if m_name:
                # 🌟 升级：存入完整对象，包含编号、条码、规格
                p_entry = {
                    "matchedName": m_name,
                    "spec_no": p.get("spec_no"),
                    "item_no": p.get("item_no"),
                    "barcode": p.get("barcode"),
                    "spec": p.get("spec")
                }
                
                # 检查是否已存在（按全称判断）
                existing_names = [item["matchedName"] if isinstance(item, dict) else item for item in CUSTOMER_HISTORY[cust_acc]]
                if m_name not in existing_names:
                    CUSTOMER_HISTORY[cust_acc].append(p_entry)
                    changed = True
        
        if changed:
            try:
                with open('data/customer_history.json', 'w', encoding='utf-8') as f:
                    json.dump(CUSTOMER_HISTORY, f, ensure_ascii=False, indent=4)
            except: pass

    logger.info(f"匹配结果: 客户={final_result['account']}, 业务员={final_result['salesman']}, 快递={final_result['express']}")
    logger.info(f"货品明细: {[{'name': p['matchedName'], 'qty': p['qty']} for p in final_result['products']]}")

    return sanitize_data(final_result)




# --- API 路由 ---
@app.route('/api/learn', methods=['POST'])
def learn_endpoint():
    try:
        data = request.json
        l_type = data.get("type", "product")
        raw = data.get("rawName")
        matched = data.get("matchedName")
        customer = data.get("customer") # 允许传入客户名
        
        if not raw or not matched: return jsonify({"status": "error"}), 400
        
        # 1. 更新特殊映射
        mapping = {"product": "货品特殊映射", "customer": "客户特殊映射", "express": "快递特殊映射"}
        key = mapping.get(l_type, "货品特殊映射")
        if key not in CONFIG_DATA: CONFIG_DATA[key] = {}
        CONFIG_DATA[key][raw] = matched
        
        with open('data/配置规则.json', 'w', encoding='utf-8') as f:
            json.dump(CONFIG_DATA, f, ensure_ascii=False, indent=4)
            
        # 2. 🌟 更新客户历史库
        if l_type == "product" and customer:
            global CUSTOMER_HISTORY
            if customer not in CUSTOMER_HISTORY: CUSTOMER_HISTORY[customer] = []
            if matched not in CUSTOMER_HISTORY[customer]:
                CUSTOMER_HISTORY[customer].append(matched)
                with open('data/customer_history.json', 'w', encoding='utf-8') as f:
                    json.dump(CUSTOMER_HISTORY, f, ensure_ascii=False, indent=4)

        print(f"[INFO] 系统进步：[{l_type}] {raw} -> {matched} (客户:{customer or '未知'})")
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
        "expressOptions": EXPRESS_OPTIONS,
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
@app.route('/api/product_info', methods=['GET'])
def get_product_info_api():
    name = request.args.get('name', '')
    if not name:
        return jsonify({"error": "Missing name"}), 400
    
    match_info = find_product_match(name)
    
    # 🌟 复用之前的多表头兼容提取逻辑
    def get_field(data, keys):
        for k in keys:
            if data.get(k): return str(data[k])
        return ""

    res = {
        "matchedName": match_info.get("matchedName", name),
        "matchType": match_info.get("matchType"),
        "spec_no": get_field(match_info, ["规格编号", "货品代码", "编码", "货品编号"]),
        "item_no": get_field(match_info, ["货品编号", "货品代码", "商品编号"]),
        "barcode": get_field(match_info, ["条码", "条形码", "商品条码"]),
        "spec": get_field(match_info, ["规格", "货品规格", "型号规格"])
    }
    return jsonify(res)

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
