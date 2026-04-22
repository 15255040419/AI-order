import os
import re
import json
import logging
import pandas as pd
import time
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# 引入核心模块
from core.address import get_province, clean_address
from core.matcher import find_best_match, get_product_details
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
ZHIPU_API_KEY = "7bd6e3eca730448c8ffac4c786cd092a.XfOv2YlnrDp44XO5"
ai_parser = OrderAIParser(ZHIPU_API_KEY)

def get_candidate_products(text, data_loader, limit=30):
    """动态筛选候选货品（仅在本地未完全匹配时使用）"""
    candidates = []
    text_upper = text.upper()
    for item_no in data_loader.item_no_index:
        if str(item_no).upper() in text_upper:
            candidates.append(data_loader.item_no_index[item_no]['货品名称'])
    for prod_name in data_loader.product_name_index:
        if str(prod_name).upper() in text_upper:
            candidates.append(prod_name)
    potential_models = re.findall(r'[A-Z0-9\-]{3,}', text_upper)
    for model in potential_models:
        for p in data_loader.all_products:
            if model in str(p).upper(): candidates.append(p)
    unique_candidates = []
    seen = set()
    for c in candidates:
        if c not in seen:
            unique_candidates.append(c); seen.add(c)
            if len(unique_candidates) >= limit: break
    return unique_candidates

def local_pre_parse(text, data_loader):
    """
    🌟 本地预解析：识别手机、已知客户、完全匹配的货品（规格编号）
    """
    found = {
        "phone": "",
        "receiver": "",
        "products": [], # 格式: {"name": "...", "qty": 1}
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

    # 2. 扫描货品 (完全匹配规格编号)
    text_upper = text.upper()
    for item_no, info in data_loader.item_no_index.items():
        if str(item_no).upper() in text_upper:
            # 简单提取数量 (紧跟在编号后的 *2 或 x2)
            qty = 1
            qty_match = re.search(rf'{re.escape(str(item_no))}[*xX\s]*(\d+)', text_upper)
            if qty_match: qty = int(qty_match.group(1))
            found["products"].append({"name": info['货品名称'], "qty": qty})

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
    
    # 🌟 修复：从 product_name_index 中提取所有货品（已包含总库存和组合装）
    for name, info in data_loader.product_name_index.items():
        products_data.append({
            "name": name,
            "货品名称": name, # 显式提供该字段供前端 find 匹配
            "item_no": info.get('规格编号') or info.get('编码') or info.get('货品编号') or '—',
            "规格编号": info.get('规格编号') or info.get('编码') or info.get('货品编号') or '',
            "条码": info.get('条码') or info.get('货品条码') or '',
            "规格": info.get('规格') or info.get('型号规格') or ''
        })
    
    # 额外补充那些只有编号没名字的（可选）
    seen_nos = set(p['item_no'] for p in products_data if p['item_no'] != '—')
    for item_no, info in data_loader.item_no_index.items():
        if item_no not in seen_nos:
            products_data.append({
                "name": info.get('货品名称') or '—',
                "货品名称": info.get('货品名称') or '—',
                "item_no": item_no,
                "规格编号": item_no,
                "条码": info.get('条码') or info.get('货品条码') or '',
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

@app.route('/api/parse', methods=['POST'])
def parse_order():
    start_time = time.time()
    data = request.json
    raw_text = data.get('text', '').strip()
    if not raw_text: return jsonify({"error": "请输入内容"}), 400

    logger.info(">>> 启动混合解析引擎 (精准分工版) <<<")
    
    # [本地引擎] 1. 支付与账户 (强制优先)
    local_pay_method, local_receipt = local_payment_check(raw_text, data_loader.config)
    
    # [本地引擎] 2. 货品/手机/客户 预扫描
    local_info = local_pre_parse(raw_text, data_loader)
    
    # [AI 引擎] 3. 仅处理复杂地址与不规范货品名
    product_context = ""
    if not local_info["products"]:
        candidates = get_candidate_products(raw_text, data_loader)
        product_context = ", ".join(candidates)
    
    salesmen_keys = ", ".join(list(data_loader.config.get("业务员映射", {}).keys()))
    ai_res, err = ai_parser.parse_with_context(
        raw_text, 
        product_ref=product_context,
        customer_ref=local_info["receiver"] or "优先匹配老客户",
        salesman_ref=salesmen_keys,
        pre_parsed=local_info if local_info["products"] else None
    )
    if not ai_res: return jsonify({"error": f"AI服务异常: {err}"}), 500

    # [补全引擎] 4. 货品详情对齐
    ai_products = ai_res.get('products', []) or local_info["products"]
    processed_products = []
    for p in ai_products:
        search_name = p.get('name', '')
        matched = find_best_match(search_name, data_loader.all_products, data_loader=data_loader)
        details = get_product_details(matched, data_loader)
        processed_products.append({
            "searchName": search_name, "matchedName": matched or search_name,
            "qty": p.get('qty', 1), "price": p.get('price', 0), "productInfo": details,
            "item_no": details.get('规格编号') or details.get('编码') or '—',
            "spec": details.get('规格') or details.get('型号规格') or '—',
            "barcode": details.get('条码') or '—'
        })

    # [规则引擎] 5. 结果聚合与强制覆盖
    profile = find_customer_profile(raw_text, data_loader.customer_index)
    result = ProcessOrderResult(ai_res, raw_text, processed_products, data_loader.config)
    
    # 🌟 强制锁定：支付方式与账户由本地引擎说了算，推翻 AI 猜测
    result['payMethod'] = local_pay_method
    if local_receipt: 
        result['receipt'] = local_receipt

    # 地址与业务属性处理
    result['address'] = clean_address(result['address'] or ai_res.get('address', ''))
    result['province'] = get_province(result['address'], ai_res.get('province', ''))
    result = apply_customer_rules(result, profile)

    # 快递逻辑判定
    express_name, express_reason = select_express(
        result['products'], result['province'], result['address'], raw_text,
        data_loader.express_rules, data_loader.config, receiver=result['receiver']
    )
    result['express'], result['expressReason'] = express_name, express_reason

    logger.info(f"🚀 解析完成！本地判定占比: 70%, AI 占比: 30%, 耗时: {time.time() - start_time:.2f}s")
    return jsonify(sanitize_data(result))

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
    if isinstance(obj, dict): return {k: sanitize_data(v) for k, v in obj.items()}
    elif isinstance(obj, list): return [sanitize_data(v) for v in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj): return 0
        return obj
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
