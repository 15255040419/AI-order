import re
import logging
from core.mapping import find_receipt_account

logger = logging.getLogger(__name__)

def ProcessOrderResult(ai_res, raw_text, processed_products, config_data):
    """
    100% 还原老项目逻辑的处理器
    """
    # 🌟 内部诊断：确保数据进入函数时是对的
    print(f"DEBUG: ProcessOrderResult 接收到的 AI 结果 receiver -> {ai_res.get('receiver', 'MISSING')}")
    # 1. 业务员验证 (括号强力锁 - 保持)
    salesman_code = str(ai_res.get("salesman_code", "")).strip().upper()
    salesman_map = config_data.get("业务员映射", {})
    codes = re.findall(r'[\(\（]([A-Z0-9\-]+)[\)\）]', raw_text)
    actual_code = salesman_code
    for c in codes:
        if c.upper() in salesman_map:
            actual_code = c.upper()
            break
    salesman = salesman_map.get(actual_code, config_data.get("默认业务员", "仝心科技(admin)"))

    # 2. 客户账号 (系统录强力锁 - 保持)
    customer_account = ""
    match_acc = re.search(r'(?:系统录[入制]?|系统记录)[:：\s]*([^\s\n\（\(\[\]]+)', raw_text)
    if match_acc:
        customer_account = match_acc.group(1).strip()
    else:
        customer_account = ai_res.get("customer_account", "")

    # 3. 金额与手机 (正则先行)
    phones = re.findall(r'1[3-9]\d{9}', raw_text)
    phone = phones[0] if phones else ai_res.get("phone", "")
    money_match = re.search(r'(\d+(?:\.\d+)?)\s*元', raw_text)
    total_amount = float(money_match.group(1)) if money_match else sum(float(p.get('price', 0)) * int(p.get('qty', 1)) for p in processed_products)

    # 4. 【核心改进】备注合成逻辑 (对齐老项目：原文截取 + 备注字样)
    # 老项目逻辑：直接使用 processed_products 里的 searchName (这是从原文中直接拎出来的带属性的名字)
    prod_summaries = []
    for p in processed_products:
        # searchName 存的是 AI 提取出并在原文中定位到的原始文本 (如 "JY-335C黑色")
        s_name = p.get('searchName', '')
        qty = p.get('qty', 1)
        prod_summaries.append(f"{s_name}*{qty}")
    
    prod_summary_text = "+".join(prod_summaries)
    
    # 提取“备注：”之后的内容 (原样保留)
    remark_match = re.search(r'备注[：:](.*)', raw_text)
    manual_remark = remark_match.group(1).strip() if remark_match else ""
    
    # 最终客服备注 = 货品原始摘要 + 备注文字
    final_note = f"{prod_summary_text} {manual_remark}".strip()

    # 控制台深度报告 (您的调试助手)
    print(f"\n[AI 指挥解析报告]")
    print(f"| 客户账号: {customer_account}")
    print(f"| 业务员: {salesman} ({actual_code})")
    print(f"| 收款额: {total_amount} 元")
    print(f"| 最终备注: {final_note}")
    print("-" * 30)

    return {
        "receiver": ai_res.get('receiver', ''),
        "phone": phone,
        "address": ai_res.get('address', ''),
        "province": ai_res.get('province', ''),
        "products": processed_products,
        "payment_status": ai_res.get('payment_status', '未付'),
        "receipt": find_receipt_account(raw_text), 
        "account": customer_account,
        "salesman": salesman,
        "total": total_amount,
        "freight": 0,
        "note": final_note
    }
