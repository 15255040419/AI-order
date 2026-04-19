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
from core.processor import ProcessOrderResult
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
ZHIPU_API_KEY = "7bd6e3eca730448c8ffac4c786cd092a.XfOv2YlnrDp44XO5"
ai_parser = OrderAIParser(ZHIPU_API_KEY)

@app.route('/api/parse', methods=['POST'])
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
            "productInfo": details,
            # 提取详细属性供预览展示
            "item_no": details.get('货品编号') or details.get('编码') or '—',
            "spec": details.get('规格') or details.get('型号规格') or '—',
            "barcode": details.get('条码') or '—'
        })

    # 3. 组装结果并应用业务规则 (调用模块化处理器，注入强力正则锁)
    profile = find_customer_profile(raw_text, data_loader.customer_index)
    result = ProcessOrderResult(ai_res, raw_text, processed_products, data_loader.config)
    
    # 细节处理：地址清洗和省份判定
    result['address'] = clean_address(result['address'] or ai_res.get('address', ''))
    result['province'] = get_province(result['address'], ai_res.get('province', ''))
    
    # 应用老客户记忆
    result = apply_customer_rules(result, profile)

    # 4. 快递判定 (集成地址剔除逻辑)
    express_name, express_reason = select_express(
        result['products'], 
        result['province'], 
        result['address'], 
        raw_text,
        data_loader.express_rules,
        data_loader.config,
        receiver=result['receiver']
    )
    result['express'] = express_name
    result['expressReason'] = express_reason

    # 🌟 终极打印：这就是发往网页的真实数据
    print(f"\n[发送给网页的最终数据包]\n收货人: {result['receiver']}, 备注: {result['note']}")
    print("=" * 50)

    # 🌟 强力脱敏：洗掉所有 NaN，防止前端崩溃
    return jsonify(sanitize_data(result))

@app.route('/api/options', methods=['GET'])
def get_options():
    # 动态从配置规则中提取选项，确保前端与后端同步
    config = data_loader.config
    return jsonify({
        "salesmen": list(config.get("业务员映射", {}).values()),
        "receipts": list(set(config.get("收款账户映射", {}).values())),
        "expressOptions": config.get("快递选项", []),
        "allProducts": data_loader.all_products
    })

def sanitize_data(obj):
    """递归清理无效的 JSON 字段 (NaN, Inf)"""
    import math
    if isinstance(obj, dict):
        return {k: sanitize_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_data(v) for v in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0
        return obj
    return obj

if __name__ == '__main__':
    try:
        data_loader.load_all()
        # 允许局域网访问
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        import traceback
        print("\n" + "!"*50)
        print("❌ 系统启动失败，错误堆栈如下：")
        print("!"*50)
        traceback.print_exc()
        print("!"*50 + "\n")
    finally:
        input("\n系统已退出。按回车键关闭窗口...")
