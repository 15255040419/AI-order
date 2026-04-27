import re

def normalize_express_name(name):
    if not name or str(name) == "nan": return None
    if name == "圆通": return "圆通（渠道）"
    if name == "中通": return "中通（渠道）"
    return str(name).strip()

def select_express(products, province, address_text, raw_text, express_table, config_data, receiver=""):
    """
    根据货品、省份和地址判定快递（克隆自原版精准分拣逻辑）
    """
    # 核心增强：从原文中扣除地址、姓名
    text_to_check = raw_text
    if address_text: text_to_check = text_to_check.replace(address_text, "")
    if receiver: text_to_check = text_to_check.replace(receiver, "")

    # 1. 检查用户手动指定
    manual_keywords = {
        "顺丰": "顺丰现付（渠道）", 
        "圆通": "圆通（渠道）", 
        "中通": "中通（渠道）",
        "极兔": "极兔渠道（新）", 
        "德邦": "德邦特惠", 
        "工厂": "工厂直发"
    }
    
    for kw, target in manual_keywords.items():
        pattern = rf"(?:发|走|指定|要|送|快递|备注)[:：\s]*{kw}"
        if re.search(pattern, text_to_check):
            return target, f"[用户手动指定] -> {target}"

    # 2. 匹配省份规则
    province_rule = None
    if province:
        province_rule = express_table.get(province)
        if not province_rule:
            for k, v in express_table.items():
                if province in k or k in province:
                    province_rule = v; break

    if not province_rule:
        print(f"| 快递判定: 失败 (省份 '{province}' 在表格中找不到规则)")
        return "中通（渠道）", f"[{province or '未知'}] 暂无匹配规则，默认中通"

    # 3. 品类判定 logic
    has_scale, has_cashier, total_weight = False, False, 0
    cat_rules = config_data.get("品类判定", {})
    scale_cfg = cat_rules.get("一体称", {"前缀": ["X"], "关键词": ["一体称"]})
    reg_cfg = cat_rules.get("收银机", {"前缀": ["K"], "关键词": ["收银机"]})

    for p in products:
        if p.get("needsReview") or not p.get("matchedName"):
            continue
        info = p.get("productInfo", {}) or {}
        name = str(p.get("matchedName", "")).upper()
        qty = int(p.get("qty", 1))
        # 🌟 修复：跳过无效或空的重量数值
        try:
            w = float(info.get("重量", 0))
            if not import_math().isnan(w):
                total_weight += w * qty
        except: pass
        
        # 🌟 精准规则：X 或 K 后面跟数字的才是大件
        if re.match(r'^[XK]\d', name) or any(kw in name for kw in ["一体称", "收银机"]):
            if name.startswith('X'):
                has_scale = True
            elif name.startswith('K'):
                # 排除配件
                if not any(kw in name for kw in ["适配器", "色带", "纸", "摄像头"]):
                    has_cashier = True

    # 4. 结果判定逻辑
    log_reason = f"省份: {province}"
    if has_scale:
        res_name = normalize_express_name(province_rule.get("一体称")) or "德邦特惠"
        log_reason += " (判定: 包含一体称/大件)"
    elif has_cashier:
        res_name = normalize_express_name(province_rule.get("收银机")) or normalize_express_name(province_rule.get("打印机_大")) or "圆通（渠道）"
        log_reason += " (判定: 包含收银机/打印机大件)"
    else:
        if total_weight <= 2.0:
            res_name = normalize_express_name(province_rule.get("打印机_小"))
            log_reason += f" (判定: 普通小件 <=2kg)"
        elif total_weight <= 5.0:
            res_name = normalize_express_name(province_rule.get("打印机_中")) or normalize_express_name(province_rule.get("打印机_大"))
            log_reason += f" (判定: 普通中件 2-5kg)"
        else:
            res_name = normalize_express_name(province_rule.get("打印机_大"))
            log_reason += f" (判定: 大件/重物 >5kg)"
    
    final_express = res_name or "中通（渠道）"
    formatted_reason = f"{log_reason}, 实计总重: {total_weight:.2f}kg"
    print(f"| 快递判定: 成功 -> {final_express} ({formatted_reason})")
    return final_express, formatted_reason

def import_math():
    import math
    return math
