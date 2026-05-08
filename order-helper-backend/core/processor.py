import re
import logging
from core.mapping import find_receipt_account

logger = logging.getLogger(__name__)


def _extract_notes(raw_text):
    """Split service/customer notes without carrying product summaries into remarks."""
    matches = []
    for match in re.finditer(r'(客服备注|客户备注|(?<![客服客户])备注)[：:]', raw_text):
        label = match.group(1)
        kind = "service" if label == "客服备注" else "customer" if label == "客户备注" else "generic"
        matches.append((match.start(), match.end(), kind))

    if not matches:
        return "", ""

    matches.sort(key=lambda item: item[0])
    service_note = ""
    customer_note = ""
    explicit_note_seen = any(kind in {"service", "customer"} for _, _, kind in matches)

    for idx, (start, end, kind) in enumerate(matches):
        next_start = matches[idx + 1][0] if idx + 1 < len(matches) else len(raw_text)
        tracking_match = re.search(r'单号录[:：]', raw_text[end:next_start])
        if tracking_match:
            next_start = end + tracking_match.start()
        content = raw_text[end:next_start].strip(" ，,。;；\n\t")
        if not content:
            continue
        if kind == "service":
            service_note = content
        elif kind == "customer":
            customer_note = content
        elif not explicit_note_seen:
            service_note = content

    return service_note, customer_note


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

    # 3. 金额与手机 (正则先行与多重兜底)
    phones = re.findall(r'1[3-9]\d{9}(?:[-转]\d{1,8})?', raw_text)
    phone = phones[0] if phones else ai_res.get("phone", "")
    
    # 增强总价识别（不再强依赖“元”字）
    total_amount = 0.0
    money_match = re.search(r'(\d+(?:\.\d+)?)\s*元', raw_text)
    eq_matches = re.findall(r'=\s*(\d+(?:\.\d+)?)', raw_text)
    prefix_match = re.search(r'(?:合计|总计|共计|金额|应收|总额|实付|应付|收款)[:：\s]*(\d+(?:\.\d+)?)', raw_text)
    end_num_match = re.search(r'\s+(\d+(?:\.\d+)?)\s*$', raw_text)

    if money_match:
        total_amount = float(money_match.group(1))
    elif eq_matches:
        total_amount = float(eq_matches[-1]) # 拿最后一个等号的结果
    elif prefix_match:
        total_amount = float(prefix_match.group(1))
    else:
        ai_total = float(ai_res.get("total_amount", 0) or 0)
        if ai_total > 0:
            total_amount = ai_total
        elif end_num_match and 0 < float(end_num_match.group(1)) < 100000:
            # 如果结尾是孤立数字（且不是手机号等超大数字），当作金额
            total_amount = float(end_num_match.group(1))
        else:
            # 终极兜底：所有货品（单价 * 数量）之和
            total_amount = sum(float(p.get('price', 0)) * int(p.get('qty', 1)) for p in processed_products)

    # 4. 备注切分：客服备注、客户备注各自入字段；货品信息不再写入任何备注。
    final_note, customer_note = _extract_notes(raw_text)

    # 5. 【新需求】物流单号提取 (单号录：JT...)
    tracking_number = ""
    tracking_match = re.search(r'单号录[:：\s]*([A-Za-z0-9\-]+)', raw_text)
    if tracking_match:
        tracking_number = tracking_match.group(1).strip()

    # 控制台深度报告 (您的调试助手)
    print(f"\n[AI 指挥解析报告]")
    print(f"| 客户账号: {customer_account}")
    print(f"| 业务员: {salesman} ({actual_code})")
    print(f"| 收款额: {total_amount} 元")
    print(f"| 客服备注: {final_note}")
    print(f"| 客户备注: {customer_note}")
    print(f"| 物流单号: {tracking_number}")
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
        "note": final_note,
        "customerNote": customer_note,
        "trackingNumber": tracking_number
    }
