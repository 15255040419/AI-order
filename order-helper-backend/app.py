import os
import re
import json
import logging
import pandas as pd
import time
import threading
import queue
from flask import Flask, request, jsonify, send_file, Response, stream_with_context
from flask_cors import CORS

# 引入核心模块
from core.address import get_province, clean_address
from core.matcher import find_strict_match, get_product_details, normalize_key
from core.express import select_express
from core.processor import ProcessOrderResult
from core.loader import DataLoader
from core.customer import find_customer_profile, apply_customer_rules
from core.ai_parser import OrderAIParser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

data_loader = DataLoader()

# AI 配置（支持运行时热切换）
AI_CONFIG = {
    "provider": "zhipu",      # zhipu | qianwen | doubao
    "model": "glm-4-flash",
    "api_key": "7bd6e3eca730448c8ffac4c786cd092a.XfOv2YlnrDp44XO5"
}
ai_parser = OrderAIParser(AI_CONFIG["api_key"])

# AI 提供商可选列表（供前端展示）
AI_PROVIDERS = [
    {"id": "zhipu",    "name": "智谱 GLM",     "models": ["glm-4-flash", "glm-4", "glm-3-turbo"]},
    {"id": "qianwen",  "name": "阿里千问",     "models": ["qwen-turbo", "qwen-plus", "qwen-max"]},
    {"id": "doubao",   "name": "字节豆包",     "models": ["doubao-lite-4k", "doubao-pro-4k"]},
]

@app.route('/api/ai-config', methods=['GET'])
def get_ai_config():
    return jsonify({
        "current": AI_CONFIG,
        "providers": AI_PROVIDERS
    })

@app.route('/api/ai-config', methods=['POST'])
def set_ai_config():
    global ai_parser, AI_CONFIG
    data = request.get_json(force=True) or {}
    provider = data.get('provider', AI_CONFIG['provider'])
    model    = data.get('model',    AI_CONFIG['model'])
    api_key  = data.get('api_key',  AI_CONFIG['api_key'])
    AI_CONFIG = {'provider': provider, 'model': model, 'api_key': api_key}
    ai_parser = OrderAIParser(api_key, provider=provider, model=model)
    logger.info(f'🔄 AI 引擎已切换: {provider} / {model}')
    return jsonify({'ok': True, 'config': AI_CONFIG})

def get_candidate_products(text, data_loader, limit=50):
    """动态筛选候选货品，提供给 AI 作为参考锚点（使用归一化避免错失）"""
    candidates = []
    text_norm = normalize_key(text)
    
    for item_no in data_loader.item_no_index:
        if normalize_key(item_no) and normalize_key(item_no) in text_norm:
            candidates.append(str(data_loader.item_no_index[item_no].get('货品名称', item_no)))
            candidates.append(str(item_no))
            
    for prod_name in data_loader.product_name_index:
        if normalize_key(prod_name) and normalize_key(prod_name) in text_norm:
            candidates.append(str(prod_name))
            
    if data_loader.combo_data is not None and not data_loader.combo_data.empty:
        for combo_name in data_loader.combo_data.get('货品名称', []):
            if normalize_key(combo_name) and normalize_key(combo_name) in text_norm:
                candidates.append(str(combo_name))

    potential_models = re.findall(r'[A-Za-z0-9\-]{3,}', text.upper())
    for model in potential_models:
        for p in data_loader.all_products:
            if model in str(p).upper(): 
                candidates.append(str(p))
                
    unique_candidates = []
    seen = set()
    for c in sorted(candidates, key=len, reverse=True):
        if c and c not in seen:
            unique_candidates.append(c)
            seen.add(c)
            
    # 提取所有已知货品作为大底库（截取小部分，供 AI 兜底，避免过长导致智谱 API 变慢）
    fallback = [str(x) for x in data_loader.all_products[:50] if str(x) not in seen]
    return unique_candidates[:limit] + fallback

def local_pre_parse(text, data_loader):
    """
    🌟 本地预解析：识别手机、已知客户、完全匹配的货品（规格编号）
    """
    found = {
        "phone": "",
        "receiver": "",
        "products": [], # 格式: {"raw_name": "...", "qty": 1}
        "customer_account": "",
        "salesman_code": "",
        "is_complete": False
    }
    
    # 1. 提取手机号
    phones = re.findall(r'1[3-9]\d{9}', text)
    if phones:
        found["phone"] = phones[0]
        if phones[0] in data_loader.customer_phone_index:
            cust = data_loader.customer_phone_index[phones[0]]
            found["receiver"] = cust.get('客户名称', '')
            found["customer_account"] = cust.get('客户账号', '')
            found["salesman_code"] = cust.get('业务员', '')

    def make_loose_literal_pattern(value):
        parts = []
        for ch in str(value):
            if ch in "(（":
                parts.append(r"[\(（]")
            elif ch in ")）":
                parts.append(r"[\)）]")
            elif ch.isspace():
                parts.append(r"\s*")
            else:
                parts.append(re.escape(ch))
        return "".join(parts)

    # 2. 扫描货品 (完全匹配规格编号)
    # 【关键】对商品的扫描必须限制在「备注：」之前，备注内容只进客服备注字段
    note_match = re.search(r'备注：|备注:', text)
    if note_match:
        product_scan_text = text[:note_match.start()]
        found["note"] = text[note_match.end():].strip()
    else:
        product_scan_text = text
        found["note"] = ""

    text_upper = product_scan_text.upper()
    normalized_text = normalize_key(product_scan_text)
    seen_products = set()
    for item_no, info in data_loader.item_no_index.items():
        item_no_text = str(item_no).strip()
        if not item_no_text or item_no_text.lower() == 'nan':
            continue
        normalized_item_no = normalize_key(item_no_text)
        if normalized_item_no and normalized_item_no in normalized_text:
            pos = normalized_text.find(normalized_item_no)
            # 简单提取数量 (紧跟在编号后的 *2 或 x2)
            qty = 1
            qty_match = re.search(
                rf'{make_loose_literal_pattern(item_no_text)}\s*(?:[*xX×]\s*)+(\d+)\s*(?:台|个|卷|套|箱|包|张|件)?',
                text,
                re.IGNORECASE
            )
            if qty_match: qty = int(qty_match.group(1))
            name = item_no_text
            if name and name not in seen_products:
                found["products"].append({"raw_name": name, "qty": qty, "_pos": pos})
                seen_products.add(name)

    # 3. 扫描收银机/一体称组合装。只查「总库存-组合装明细.xlsx」的货品名称列。
    occupied_spans = []
    combo_names = []
    if data_loader.combo_data is not None and not data_loader.combo_data.empty:
        combo_names = [
            str(v).strip()
            for v in data_loader.combo_data.get('货品名称', [])
            if str(v).strip() and str(v).strip() != 'nan'
        ]
    for prod_name in sorted(set(combo_names), key=len, reverse=True):
        prod_name = str(prod_name).strip()
        if not prod_name or prod_name == 'nan' or prod_name in seen_products:
            continue
        start = product_scan_text.find(prod_name)
        if start < 0:
            continue
        end = start + len(prod_name)
        if any(not (end <= s or start >= e) for s, e in occupied_spans):
            continue
        suffix = product_scan_text[end:end + 12]
        qty = 1
        qty_match = re.search(r'^\s*(?:[*xX×]\s*)?(\d+)\s*(?:台|个|卷|套|箱|包|张|件)?', suffix)
        if qty_match:
            qty = int(qty_match.group(1))
        found["products"].append({"raw_name": prod_name, "qty": qty, "_pos": start})
        seen_products.add(prod_name)
        occupied_spans.append((start, end))

    found["products"] = [
        {k: v for k, v in p.items() if k != "_pos"}
        for p in sorted(found["products"], key=lambda item: item.get("_pos", 10**9))
    ]

    return found



@app.route('/')
def index():
    # 尝试在当前目录或上级目录查找 HTML
    potential_paths = [
        os.path.join(os.path.dirname(__file__), '..', 'order-assistant-full.html'),
        os.path.join(os.path.dirname(__file__), 'order-assistant-full.html'),
        'order-assistant-full.html'
    ]
    for path in potential_paths:
        if os.path.exists(path):
            return send_file(path)
    return "Frontend file not found", 404

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/api/options', methods=['GET'])
def get_options():
    config = data_loader.config
    products_data = []

    seen_rows = set()
    for frame in [data_loader.stock_data, data_loader.combo_data]:
        if frame is None or frame.empty:
            continue
        for _, row in frame.iterrows():
            info = row.to_dict()
            name = str(info.get('货品名称') or info.get('组合装名称') or info.get('商品名称') or '').strip()
            if not name or name == 'nan':
                continue
            row_key = (
                name,
                str(info.get('规格编号', '')),
                str(info.get('货品编号', '')),
                str(info.get('条码', '')),
                str(info.get('货品条码', '')),
                str(info.get('规格', '')),
            )
            if row_key in seen_rows:
                continue
            seen_rows.add(row_key)
            products_data.append({
                "name": name,
                "货品名称": name,
                "item_no": info.get('规格编号') or info.get('货品编号') or info.get('编码') or '—',
                "规格编号": info.get('规格编号') or info.get('编码') or '',
                "货品编号": info.get('货品编号') or info.get('货品代码') or info.get('商品编号') or '',
                "条码": info.get('条码') or info.get('货品条码') or info.get('商品条码') or '',
                "规格": info.get('规格') or info.get('型号规格') or ''
            })
    
    logger.info(f"📊 [API] 已向网页发送配置数据: {len(products_data)} 项货品, {len(config.get('业务员映射', {}))} 位业务员")
    return jsonify(sanitize_data({
        "salesmen": list(config.get("业务员映射", {}).values()),
        "receipts": list(set(config.get("收款账户映射", {}).values())),
        "expressOptions": config.get("快递选项", []),
        "allProducts": data_loader.all_products,
        "allProductsData": products_data
    }))

def local_payment_check(text, config):
    """
    🌟 核心优化：全本地化支付与账户判定引擎
    分工：钱款、账户、结算方式 100% 本地正则判定，不依赖 AI。
    """
    receipt_map = config.get("收款账户映射", {})
    # 支付方式关键词
    paid_keywords = ["已付", "转账", "已转"]
    unpaid_keywords = ["未付", "欠款"]
    
    final_method = "欠款计应收"
    final_receipt = ""

    # 1. 判定结算方式 (只要有已付关键字就设为银行收款，除非有未付关键字)
    if any(kw in text for kw in paid_keywords):
        final_method = "银行收款"
    if any(kw in text for kw in unpaid_keywords):
        final_method = "欠款计应收"

    # 2. 匹配具体账户 (基于配置映射)
    # 按关键词长度倒序，防止“农行公账”被误切为“农行”
    sorted_keywords = sorted(receipt_map.keys(), key=len, reverse=True)
    for kw in sorted_keywords:
        if kw in text:
            final_method = "银行收款" # 只要提到了账户，默认就是已付
            final_receipt = receipt_map[kw]
            break
            
    # 3. 如果判定为银行收款但没搜到具体账户，给个默认
    if final_method == "银行收款" and not final_receipt:
        final_receipt = list(receipt_map.values())[0] if receipt_map else ""

    return final_method, final_receipt

def infer_unit_price(raw_text, product_text, qty):
    """
    Infer unit price from deterministic price formulas in the original order.
    Examples: 90*2=180元, 95 * 3 = 285, 3*95=285元, 80*60纸 10元.
    """
    if not raw_text:
        return 0

    try:
        qty = int(qty or 1)
    except:
        qty = 1

    normalized = raw_text.replace("×", "*").replace("X", "*").replace("x", "*")
    windows = []
    if product_text:
        idx = normalized.find(str(product_text))
        if idx >= 0:
            windows.append(normalized[max(0, idx - 40):idx + len(str(product_text)) + 80])
    if not windows:
        windows.append(normalized)

    patterns = [
        re.compile(r'(?<![a-zA-Z0-9_\-])(\d+(?:\.\d+)?)\s*\*\s*(\d+)\s*=?\s*(\d+(?:\.\d+)?)?\s*元?'),
        re.compile(r'(?<![a-zA-Z0-9_\-])(\d+)\s*\*\s*(\d+(?:\.\d+)?)\s*=?\s*(\d+(?:\.\d+)?)?\s*元?'),
    ]

    for window in windows:
        matches = []
        for pattern in patterns:
            matches.extend(pattern.findall(window))
        for a, b, total in matches:
            try:
                first = float(a)
                second = float(b)
                total_val = float(total) if total else None
            except:
                continue

            candidates = []
            if int(second) == qty:
                candidates.append(first)
            if int(first) == qty:
                candidates.append(second)

            for unit_price in candidates:
                if total_val is None or abs(unit_price * qty - total_val) < 0.01:
                    return unit_price

    # 增强兜底价格提取：提取类似 "80*60纸 10元" 或 "80*60纸-10" 的简单格式
    if product_text:
        product_str = str(product_text).strip()
        if product_str:
            escaped = re.escape(product_str)
            # 模式1: 货品名称 后接可选的数量 再接标点/空格 再接价格及元/块
            m = re.search(rf'{escaped}\s*(?:[*xX×]\s*\d+\s*)?(?:[-:：=,，]*)\s*(\d+(?:\.\d+)?)\s*[元块]', raw_text)
            if m:
                try: return round(float(m.group(1)) / qty, 2)
                except: pass
            
            # 模式2: 货品名称 后接破折号/等号 再接纯数字
            m2 = re.search(rf'{escaped}\s*(?:[*xX×]\s*\d+\s*)?(?:[-:：=]+)\s*(\d+(?:\.\d+)?)(?!\d)', raw_text)
            if m2:
                try: return round(float(m2.group(1)) / qty, 2)
                except: pass

    return 0

def infer_additive_prices(raw_text, products):
    """
    Infer per-product prices from formulas like 90+210=300.

    If quantities are all 1, the parts are treated as unit prices. If quantities
    are greater than 1 and the parts sum to the total, each part is treated as
    that product line amount and divided by quantity.
    """
    if not raw_text or not products:
        return []

    normalized = raw_text.replace("＋", "+").replace("=", "=")
    pattern = re.compile(r'(\d+(?:\.\d+)?(?:\s*\+\s*\d+(?:\.\d+)?)+)\s*=\s*(\d+(?:\.\d+)?)')
    for expr, total in pattern.findall(normalized):
        parts = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', expr)]
        if len(parts) != len(products):
            continue
        total_val = float(total)
        if abs(sum(parts) - total_val) > 0.01:
            continue

        qtys = []
        for p in products:
            try:
                qtys.append(int(p.get('qty', 1) or 1))
            except:
                qtys.append(1)

        if all(q == 1 for q in qtys):
            return parts

        unit_total = sum(part * qty for part, qty in zip(parts, qtys))
        if abs(unit_total - total_val) < 0.01:
            return parts

        return [round(part / qty, 4) if qty else part for part, qty in zip(parts, qtys)]

    return []

def _eval_price_term(term):
    term = str(term or "").strip().replace("×", "*").replace("X", "*").replace("x", "*")
    if not term:
        return None
    if "*" in term:
        parts = [p.strip() for p in term.split("*") if p.strip()]
        if len(parts) != 2:
            return None
        try:
            a, b = float(parts[0]), float(parts[1])
            return {"raw": term, "value": a * b, "factors": (a, b)}
        except:
            return None
    try:
        value = float(term)
        return {"raw": term, "value": value, "factors": None}
    except:
        return None

def infer_price_plan(raw_text, products):
    """
    Infer product unit prices and freight from mixed formulas.

    Example: 98*2+95+10=301 with two products whose quantities are 2 and 1
    becomes prices [98, 95] and freight 10.
    """
    result = {"prices": [], "freight": 0}
    if not raw_text or not products:
        return result

    normalized = raw_text.replace("＋", "+").replace("×", "*").replace("X", "*").replace("x", "*")
    pattern = re.compile(
        r'((?:\d+(?:\.\d+)?(?:\s*\*\s*\d+(?:\.\d+)?)?\s*\+\s*)+\d+(?:\.\d+)?(?:\s*\*\s*\d+(?:\.\d+)?)?)\s*=\s*(\d+(?:\.\d+)?)'
    )

    freight_keywords = re.compile(r'(?:补\s*)?运费|邮费|快递费')

    for match in pattern.finditer(normalized):
        expr, total = match.group(1), match.group(2)
        terms = [_eval_price_term(t) for t in expr.split("+")]
        if any(t is None for t in terms):
            continue
        try:
            total_val = float(total)
        except:
            continue
        if abs(sum(t["value"] for t in terms) - total_val) > 0.01:
            continue
        freight_indices = []
        prefix = normalized[max(0, match.start() - 180):match.start()]
        if freight_keywords.search(prefix):
            # 移除括号内的内容以防止括号内的 + 号干扰切割
            clean_prefix = re.sub(r'[\(（][^\)）]*[\)）]', '', prefix)
            segments = [seg.strip() for seg in clean_prefix.split("+") if seg.strip()]
            if len(segments) == len(terms):
                freight_indices = [i for i, seg in enumerate(segments) if freight_keywords.search(seg)]

        if not freight_indices and len(terms) > len(products) and freight_keywords.search(raw_text):
            freight_indices = list(range(len(products), len(terms)))

        product_terms = [term for i, term in enumerate(terms) if i not in freight_indices]
        freight_terms = [term for i, term in enumerate(terms) if i in freight_indices]

        # 允许产品数量大于价格数量（例如末尾有赠品），不再 continue，而是按序匹配已有的价格
        prices = []
        valid = True
        for term, product in zip(product_terms, products):
            try:
                qty = int(product.get("qty", 1) or 1)
            except:
                qty = 1

            unit_price = None
            if term["factors"]:
                a, b = term["factors"]
                if int(b) == qty:
                    unit_price = a
                elif int(a) == qty:
                    unit_price = b
                elif qty == 1:
                    unit_price = term["value"]
            elif qty == 1:
                unit_price = term["value"]
            elif term["value"] % qty == 0:
                unit_price = term["value"] / qty

            if unit_price is None:
                valid = False
                break
            prices.append(unit_price)

        if not valid:
            continue

        freight = 0
        if freight_terms:
            freight = sum(t["value"] for t in freight_terms)

        result["prices"] = prices
        result["freight"] = freight
        return result

    additive_prices = infer_additive_prices(raw_text, products)
    if additive_prices:
        result["prices"] = additive_prices
        return result

    # 【兜底3】单件货品 + 原文直写金额（如 "880元"），无加法公式
    if len(products) == 1:
        # 去掉货品名称内的纯数字干扰，只在货品名称之后的部分搜索
        single_amount = re.search(
            r'(?<![a-zA-Z0-9\-])(\d{2,6}(?:\.\d{1,2})?)\s*元',
            raw_text
        )
        if single_amount:
            try:
                qty = int(products[0].get("qty", 1) or 1)
                total = float(single_amount.group(1))
                result["prices"] = [round(total / qty, 2)]
                logger.debug(f"[价格] 单品直写金额兜底: {total}元 / qty={qty} => 单价={result['prices'][0]}")
                return result
            except:
                pass

    return result

def _progress(progress, step, message, **extra):
    if progress:
        progress({
            "step": step,
            "message": message,
            **extra
        })

def process_order_text(raw_text, progress=None):
    start_time = time.time()
    raw_text = (raw_text or '').strip()
    if not raw_text:
        raise ValueError("请输入内容")

    logger.info(">>> 启动混合解析引擎 (精准分工版) <<<")
    _progress(progress, "start", "启动混合解析引擎")
    debug_trace = {
        "rawText": raw_text,
        "steps": []
    }
    
    # [本地引擎] 1. 支付与账户 (强制优先)
    _progress(progress, "payment", "识别付款状态与收款账户")
    local_pay_method, local_receipt = local_payment_check(raw_text, data_loader.config)
    debug_trace["steps"].append({
        "name": "payment_local_rule",
        "payMethod": local_pay_method,
        "receipt": local_receipt,
    })
    
    # [本地引擎] 2. 货品/手机/客户 预扫描
    _progress(progress, "local_pre_parse", "本地预解析手机号、客户和货品")
    local_info = local_pre_parse(raw_text, data_loader)
    debug_trace["steps"].append({
        "name": "local_pre_parse",
        "phone": local_info.get("phone"),
        "receiver": local_info.get("receiver"),
        "products": local_info.get("products", []),
        "customerAccount": local_info.get("customer_account"),
        "salesmanCode": local_info.get("salesman_code"),
    })
    
    # [AI 引擎] 3. 仅处理复杂地址与不规范货品名
    _progress(progress, "candidate_products", "准备货品候选与业务员规则")
    # 无论本地是否提前查到了货品，都必须把商品库喂给 AI，否则 AI 会漏切或者瞎切
    candidates = get_candidate_products(raw_text, data_loader)
    product_context = ", ".join(candidates)
    
    salesmen_keys = ", ".join(list(data_loader.config.get("业务员映射", {}).keys()))
    has_local_context = any([
        local_info.get("phone"),
        local_info.get("receiver"),
        local_info.get("products"),
        local_info.get("customer_account"),
        local_info.get("salesman_code"),
    ])
    _progress(progress, "ai_parse", "调用 AI 解析地址与订单字段", usedLocalContext=has_local_context)
    ai_start = time.time()
    ai_res, err = ai_parser.parse_with_context(
        raw_text, 
        product_ref=product_context,
        customer_ref=local_info["receiver"] or "优先匹配老客户",
        salesman_ref=salesmen_keys,
        pre_parsed=local_info if has_local_context else None
    )
    if not ai_res:
        raise RuntimeError(f"AI服务异常: {err}")
    debug_trace["steps"].append({
        "name": "ai_parse",
        "durationSeconds": round(time.time() - ai_start, 3),
        "usedProductCandidates": bool(product_context),
        "usedLocalContext": has_local_context,
        "receiver": ai_res.get("receiver"),
        "address": ai_res.get("address"),
        "products": ai_res.get("products", []),
    })

    # [补全引擎] 4. 货品详情严格对齐
    _progress(progress, "price_plan", "拆分价格与补运费")
    
    # 【修复】提取并剥离 AI 可能误识别为货品的“运费”
    ai_products_raw = ai_res.get('products', [])
    ai_products = []
    ai_freight_from_products = 0.0
    freight_pattern = re.compile(r'(?:补\s*)?运费|邮费|快递费|运费补差')
    
    # 【规则】备注区货品过滤：备注:之后的文字不算货品，只进客服备注
    _note_m = re.search('备注：|备注:', raw_text)
    _note_text   = normalize_key(raw_text[_note_m.start():]) if _note_m else ""
    _prod_text   = normalize_key(raw_text[:_note_m.start()]) if _note_m else normalize_key(raw_text)

    for p in ai_products_raw:
        name = str(p.get('raw_name') or p.get('name') or '')
        if freight_pattern.search(name):
            try: ai_freight_from_products += float(p.get('price', 0)) * float(p.get('qty', 1) or 1)
            except: pass
            continue
        # 备注区专属货品过滤
        name_norm = normalize_key(name)
        if _note_text and name_norm and name_norm in _note_text and name_norm not in _prod_text:
            logger.info(f"[过滤] '{name}' 仅出现在备注区，已排除出货品列表")
            continue
        ai_products.append(p)


    # 合并 AI 提取的货品和本地预扫描发现的货品，确保万无一失
    local_prods_raw = local_info.get("products", [])
    local_prods = []
    for lp in local_prods_raw:
        lp_name = str(lp.get("searchName") or lp.get("name") or lp.get("raw_name") or "")
        if not freight_pattern.search(lp_name):
            local_prods.append(lp)
    
    for lp in local_prods:
        lp_name = normalize_key(lp.get("raw_name", ""))
        already_has = False
        for i, ap in enumerate(ai_products):
            ap_name = normalize_key(ap.get("raw_name", "") or ap.get("name", ""))
            if lp_name == ap_name:
                # 完全一致，无需处理
                already_has = True
                break
            elif ap_name in lp_name and len(lp_name) > len(ap_name):
                # 本地名称更完整（如 "K7白单(...)ME" vs AI的 "K7白单(...)"），用本地替换 AI 版
                ai_products[i] = lp
                already_has = True
                break
            elif lp_name in ap_name:
                # AI 名称更长，AI 版已覆盖，无需追加
                already_has = True
                break
        if not already_has:
            ai_products.append(lp)
            
    if not ai_products:
        ai_products = local_prods
        
    price_plan = infer_price_plan(raw_text, ai_products)
    if ai_freight_from_products > 0 and price_plan.get("freight", 0) == 0:
        price_plan["freight"] = ai_freight_from_products
    logger.info(f"[价格计划] 共{len(ai_products)}件货品 | 解析出价格{len(price_plan.get('prices',[]))}个: {price_plan.get('prices',[])} | 运费: {price_plan.get('freight',0)}")
    debug_trace["steps"].append({
        "name": "price_plan",
        "prices": price_plan.get("prices", []),
        "freight": price_plan.get("freight", 0),
    })
    _progress(progress, "product_match", "精确匹配库存表货品")
    processed_products = []
    for idx, p in enumerate(ai_products):
        search_name = p.get('raw_name') or p.get('name', '')
        match_result = find_strict_match(search_name, data_loader)
        matched = match_result.get('matched')
        details = match_result.get('details') or get_product_details(matched, data_loader)
        status = match_result.get('status', 'unmatched')
        qty = p.get('qty', 1)
        
        price_from_plan = price_plan["prices"][idx] if idx < len(price_plan.get("prices", [])) else None
        
        if price_from_plan is not None:
            price = price_from_plan
            price_source = f"公式对齐[{idx}]={price}"
        elif p.get('price'):
            price = p.get('price')
            price_source = f"AI返回价格={price}"
        else:
            price = infer_unit_price(raw_text, search_name, qty)
            price_source = f"兜底盲猜={price}"
        logger.info(f"[货品{idx+1}] 原文:'{search_name}' | 匹配:{matched or '❌待确认'} ({match_result.get('matchType','')}) | 价格来源:{price_source}")
        processed_products.append({
            "searchName": search_name,
            "matchedName": matched or "",
            "qty": qty, "price": price, "productInfo": details,
            "item_no": details.get('规格编号') or details.get('编码') or details.get('货品编号') or '—',
            "spec": details.get('规格') or details.get('型号规格') or '—',
            "barcode": details.get('条码') or details.get('货品条码') or '—',
            "matchStatus": status,
            "matchType": match_result.get('matchType', ''),
            "needsReview": status != "matched",
            "candidates": match_result.get('candidates', [])
        })

    debug_trace["steps"].append({
        "name": "strict_product_match",
        "products": [
            {
                "raw": p.get("searchName"),
                "matched": p.get("matchedName"),
                "qty": p.get("qty"),
                "price": p.get("price"),
                "status": p.get("matchStatus"),
                "matchType": p.get("matchType"),
            }
            for p in processed_products
        ],
    })

    # [规则引擎] 5. 结果聚合与强制覆盖
    _progress(progress, "customer_rules", "套用客户档案与固定业务规则")
    profile = find_customer_profile(raw_text, data_loader.customer_index)
    result = ProcessOrderResult(ai_res, raw_text, processed_products, data_loader.config)
    if price_plan.get("freight"):
        result["freight"] = price_plan["freight"]
        
    # 🌟 价格修复：如果仅有一款商品且价格为0，则用订单总金额自动反推单价
    if len(result.get('products', [])) == 1 and result['products'][0].get('price', 0) == 0 and result.get('total', 0) > 0:
        qty = int(result['products'][0].get('qty', 1) or 1)
        result['products'][0]['price'] = round(result['total'] / qty, 2)
    
    # 🌟 强制锁定：支付方式与账户由本地引擎说了算，推翻 AI 猜测
    result['payMethod'] = local_pay_method
    if local_receipt: 
        result['receipt'] = local_receipt

    # 地址与业务属性处理
    result['address'] = clean_address(result['address'] or ai_res.get('address', ''))
    result['province'] = get_province(result['address'], ai_res.get('province', ''))
    result = apply_customer_rules(result, profile)

    # 快递逻辑判定：货品未精确确认时，不自动猜快递
    _progress(progress, "express_rule", "判定快递规则")
    if any(p.get("needsReview") for p in result.get("products", [])):
        result['express'] = "待确认"
        result['expressReason'] = "存在未精确匹配货品，确认货品后再判定快递"
    else:
        express_name, express_reason = select_express(
            result['products'], result['province'], result['address'], raw_text,
            data_loader.express_rules, data_loader.config, receiver=result['receiver']
        )
        result['express'], result['expressReason'] = express_name, express_reason

    debug_trace["steps"].append({
        "name": "express_rule",
        "province": result.get("province"),
        "express": result.get("express"),
        "reason": result.get("expressReason"),
    })
    debug_trace["durationSeconds"] = round(time.time() - start_time, 3)
    result["debugTrace"] = debug_trace

    logger.info(f"🚀 解析完成！本地判定占比: 70%, AI 占比: 30%, 耗时: {time.time() - start_time:.2f}s")
    _progress(progress, "complete", "识别完成", durationSeconds=debug_trace["durationSeconds"])
    return sanitize_data(result)

@app.route('/api/parse', methods=['POST'])
def parse_order():
    data = request.json or {}
    raw_text = data.get('text', '').strip()
    if not raw_text:
        return jsonify({"error": "请输入内容"}), 400
    try:
        return jsonify(process_order_text(raw_text))
    except Exception as e:
        logger.exception("订单解析失败")
        return jsonify({"error": str(e)}), 500

def _sse(event, payload):
    return f"event: {event}\ndata: {json.dumps(sanitize_data(payload), ensure_ascii=False)}\n\n"

@app.route('/api/parse-stream', methods=['POST'])
def parse_order_stream():
    data = request.json or {}
    raw_text = data.get('text', '').strip()
    if not raw_text:
        return jsonify({"error": "请输入内容"}), 400

    @stream_with_context
    def generate():
        events = queue.Queue()

        def push_progress(payload):
            events.put(("progress", payload))

        def worker():
            try:
                result = process_order_text(raw_text, push_progress)
                events.put(("done", result))
            except Exception as e:
                logger.exception("流式订单解析失败")
                events.put(("error", {"message": str(e)}))
            finally:
                events.put(("close", {}))

        threading.Thread(target=worker, daemon=True).start()
        yield _sse("progress", {"step": "queued", "message": "订单已进入解析队列"})

        while True:
            event, payload = events.get()
            if event == "close":
                break
            yield _sse(event, payload)

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    })

@app.route('/api/learn', methods=['POST'])
def learn_correction():
    data = request.json
    logger.info(f"🧠 [学习引擎] 收到手动修正: {data}")
    
    try:
        rules_path = os.path.join(data_loader.data_dir, 'learn_rules.json')
        rules = {}
        if os.path.exists(rules_path):
            with open(rules_path, 'r', encoding='utf-8') as f:
                rules = json.load(f)
        
        # 按类型存储规则
        rule_type = data.get('type')
        if rule_type not in rules: rules[rule_type] = {}
        
        raw_name = data.get('rawName')
        matched_name = data.get('matchedName')
        
        if raw_name and matched_name:
            rules[rule_type][raw_name] = matched_name
            with open(rules_path, 'w', encoding='utf-8') as f:
                json.dump(rules, f, ensure_ascii=False, indent=4)
            
            # 同步更新内存中的配置
            if rule_type == 'product':
                data_loader.config.setdefault('货品特殊映射', {})[raw_name] = matched_name
            elif rule_type == 'customer':
                # 客户学习可能涉及更多逻辑，暂时存入配置
                data_loader.config.setdefault('客户特殊映射', {})[raw_name] = matched_name
                
            logger.info(f"✅ 规则已持久化至 learn_rules.json: {raw_name} -> {matched_name}")
            return jsonify({"status": "success", "message": "学习成功，已永久记录该匹配规则"})
    except Exception as e:
        logger.error(f"❌ 学习失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "error", "message": "无效的数据"}), 400

def sanitize_data(obj):
    import math
    import pandas as pd
    import numpy as np
    if isinstance(obj, dict): return {k: sanitize_data(v) for k, v in obj.items()}
    elif isinstance(obj, list): return [sanitize_data(v) for v in obj]
    elif obj is None or obj is pd.NaT: return ""
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj): return 0
        return obj
    elif isinstance(obj, (np.integer,)): return int(obj)
    elif isinstance(obj, (np.floating,)):
        value = float(obj)
        if math.isnan(value) or math.isinf(value): return 0
        return value
    elif isinstance(obj, (pd.Timestamp,)): return obj.isoformat()
    return obj

if __name__ == '__main__':
    try:
        logger.info("--- 系统启动中 ---")
        data_loader.load_all()
        logger.info("🚀 API 服务启动成功！")
        app.run(host='0.0.0.0', port=5005, debug=False, use_reloader=False)
    except Exception as e:
        print("\n" + "!"*50)
        print("💥 系统启动崩溃报告：")
        import traceback
        traceback.print_exc()
        print("!"*50 + "\n")
    finally:
        print("\n" + "="*50)
        print("💡 提示：程序已停止运行。请检查上方错误日志。")
        print("   解决问题后，关闭此窗口重新运行 app.py 即可。")
        print("="*50)
        input("按【回车键】关闭此窗口...")
