import re
import json
import logging
from zhipuai import ZhipuAI

logger = logging.getLogger(__name__)

# 硬编码配置与规则 (从 app.py/配置规则.json 彻底分离)
BIZ_CONSTRAINTS = {
    "receipt_accounts": ["仝心农商（公账）", "农商银行（成）", "农商（龙）", "财务微信"],
    "payment_statuses": ["已付", "未付"]
}

DEFAULT_SYSTEM_PROMPT = "你是一个极速订单解析器，严格按格式返回 JSON。"

class OrderAIParser:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = ZhipuAI(api_key=api_key) if api_key else None

    def parse_with_context(self, text, product_ref, customer_ref, salesman_ref, history_hint=""):
        if not self.client:
            return None, "智谱AI API密钥未配置"

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
- 付款账号: {', '.join(BIZ_CONSTRAINTS['receipt_accounts'])}
- 付款状态: {', '.join(BIZ_CONSTRAINTS['payment_statuses'])}

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
5. 价格拆分：如果原文中货品和价格是按顺序排列的（如 A*1+B*2 10+20），请将 10 对应到 A 的 price，20 对应到 B 的 price，不要只返回总价。
6. 结果格式：直接返回 JSON，不要任何解释文字。"""

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
            content = response.choices[0].message.content
            # 清洗渲染层可能带有的 ```json ``` 标记
            content = re.sub(r"```json\s*|\s*```", "", content)
            return json.loads(content), None
        except Exception as e:
            logger.error(f"AI解析失败: {str(e)}")
            return None, str(e)
