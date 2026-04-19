import os
import re
import json
import logging
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS

# 引入核心模块
from core.address import get_province, clean_address
from core.matcher import find_best_match, get_product_details
from core.express import select_express
from core.mapping import DEFAULT_SALESMAN
from core.loader import DataLoader
from core.customer import find_customer_profile, apply_customer_rules
from core.ai_parser import OrderAIParser

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 初始化数据装载器与AI解析器
data_loader = DataLoader()
ZHIPU_API_KEY = "9d63c261e479c3f25608518f83038936.pA8hS4J2E5Z6Gk5g"
ai_parser = OrderAIParser(ZHIPU_API_KEY)

@app.route('/api/parse_order', methods=['POST'])
def parse_order():
    data = request.json
    raw_text = data.get('text', '').strip()
    if not raw_text:
        return jsonify({"error": "请输入订单内容"}), 400

    logger.info("==================== 开始指挥解析 ====================")
    
    # 1. AI 初步提取基础信息
    ai_res, err = ai_parser.parse_with_context(
        raw_text, 
        product_ref=", ".join(data_loader.all_products[:200]),
        customer_ref="吴永龙, 罗金舟, 成都星宇星宸科技",
        salesman_ref="TX, L, D, C, W, T, H, F"
    )
    if not ai_res: return jsonify({"error": f"AI服务异常: {err}"}), 500

    # 2. 货品二次对齐
    processed_products = []
    total_inventory = data_loader.stock_data.to_dict('records') + data_loader.combo_data.to_dict('records')
    for p in ai_res.get('products', []):
        search_name = p.get('name', '')
        matched = find_best_match(search_name, data_loader.all_products)
        details = get_product_details(matched, total_inventory)
        
        processed_products.append({
            "searchName": search_name,
            "matchedName": matched or search_name,
            "qty": p.get('qty', 1),
            "price": p.get('price', 0),
            "productInfo": details
        })

    # 3. 客户档案自动化
    profile = find_customer_profile(raw_text, data_loader.customer_index)
    
    # 4. 组装结果并应用业务规则
    result = {
        "receiver": ai_res.get('receiver', ''),
        "phone": ai_res.get('phone', ''),
        "address": clean_address(ai_res.get('address', '')),
        "province": get_province(ai_res.get('address', ''), ai_res.get('province', '')),
        "products": processed_products,
        "payment_status": ai_res.get('payment_status', '未付'),
        "payment_account": ai_res.get('payment_account', ''),
        "customer_account": ai_res.get('customer_account', ''),
        "salesman": DEFAULT_SALESMAN,
        "note": ai_res.get('extra_note', '')
    }
    
    result = apply_customer_rules(result, profile)

    # 5. 快递判定
    express_name, express_reason = select_express(
        result['products'], 
        result['province'], 
        result['address'], 
        raw_text,
        data_loader.express_rules
    )
    result['express'] = express_name
    result['expressReason'] = express_reason

    return jsonify(result)

@app.route('/api/get_options', methods=['GET'])
def get_options():
    return jsonify({
        "salesmen": ["仝心科技(admin)", "陆香(12)", "王德龙(21)", "王德成(31)", "汪朋松(30)"],
        "receipts": ["仝心农商（公账）", "农商银行（成）", "农商（龙）", "财务微信"],
        "expressOptions": ["中通（渠道）", "圆通（渠道）", "德邦特惠", "极兔渠道（新）", "顺丰现付（渠道）"],
        "allProducts": data_loader.all_products
    })

if __name__ == '__main__':
    data_loader.load_all()
    app.run(port=5000)
