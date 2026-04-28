import re
import json
import logging
from zhipuai import ZhipuAI

logger = logging.getLogger(__name__)

BIZ_CONSTRAINTS = {
    "receipt_accounts": ["仝心农商（公账）", "农商银行（成）", "农商（龙）", "财务微信"],
    "payment_statuses": ["已付", "未付"]
}

DEFAULT_SYSTEM_PROMPT = "你是一个极速订单解析器，严格按格式返回 JSON，不要任何废话。"

class OrderAIParser:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = ZhipuAI(api_key=api_key) if api_key else None

    def parse_with_context(self, text, product_ref, customer_ref, salesman_ref, pre_parsed=None):
        if not self.client:
            return None, "智谱AI API密钥未配置"

        pre_parsed_info = ""
        if pre_parsed:
            # 过滤掉 products，让 AI 独立完整地提取所有货品，防止 AI 偷懒只输出本地提前找到的部分货品
            pre_parsed_filtered = {k: v for k, v in pre_parsed.items() if k != "products" and v}
            if pre_parsed_filtered:
                pre_parsed_info = f"\n【已知信息（直接使用，无需重新推导）】: {json.dumps(pre_parsed_filtered, ensure_ascii=False)}"

        prompt = f"""解析订单，输出 JSON。
【文本】:
{text}
{pre_parsed_info}

【参考候选】:
- 货品候选仅供判断哪些文字可能是货品，不要改写成候选名称: {product_ref}
- 客户/业务: {customer_ref} / {salesman_ref}

【业务规则】:
- 收款账户: {', '.join(BIZ_CONSTRAINTS['receipt_accounts'])}
- 付款状态: {', '.join(BIZ_CONSTRAINTS['payment_statuses'])}

【输出格式】:
{{
  "receiver": "姓名", "phone": "电话", "address": "详细地址", "province": "省份",
  "products": [ {{ "raw_name": "订单原文里的货品文字（如果有多个货品被+号连接，请拆分开，不要遗漏任何纸张或耗材）", "qty": 数量, "price": 单价 }} ],
  "payment_status": "已付/未付", "payment_account": "收款账户",
  "customer_account": "客户账号", "salesman_code": "业务员代码",
  "postage": 0, "total_amount": 0, "extra_note": "备注"
}}

【规则】:
1. products.raw_name 必须从订单原文中原样截取，不要补字、不要改字、不要标准化。
2. 不要把货品改写成参考候选中的标准名称，最终货品由本地库存表精确匹配。
3. 如果已知信息已有字段，请保持一致。
4. 直接返回 JSON 字符串。"""

        try:
            response = self.client.chat.completions.create(
                model="glm-4-flash",
                messages=[
                    {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                top_p=0.1
            )
            content = response.choices[0].message.content.strip()
            
            # 提取 JSON
            json_match = re.search(r'(\{.*\})', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                content = re.sub(r"```json\s*|\s*```", "", content).strip()
            
            res = json.loads(content)
            if not res.get('receiver') or not str(res.get('receiver')).strip():
                res['receiver'] = "未知收货人"
                
            return res, None
        except Exception as e:
            msg = f"AI 解析失败: {str(e)}"
            logger.error(msg)
            return None, msg
