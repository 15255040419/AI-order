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
1. 禁止污染名字：货品名称中不要包含数量标识（如 *2, x1）。数量必须单独放在 "qty" 字段。
2. **完整保留规格**：货品名称中**必须完整保留颜色、型号后缀及关键规格**（例如：原文是 "JY-335C黑色"，name 字段就必须返回 "JY-335C黑色"），严禁私自删减。
3. 匹配优先：如果原文货品名在【参考库】中有相似项，尽可能对齐库中的标准全称。
4. 排除干扰：姓名或地址后的编号（如 [1783]）请保留在原字段，不要漏掉。
5. 价格拆分：正确关联货品与对应的单价。
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
            content = response.choices[0].message.content.strip()
            
            # 🌟 调试神器：打印 AI 的原话 (确保这次真的能看到)
            print(f"\n[AI 模块原始回复内容]\n{content}\n" + "—"*20)
            
            # 🌟 强力提取 JSON (防止 AI 带废话)
            json_match = re.search(r'(\{.*\})', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                content = re.sub(r"```json\s*|\s*```", "", content).strip()
            
            res = json.loads(content)
            # 保底处理：防止收货人为空导致前端判定失败
            if not res.get('receiver') or not str(res.get('receiver')).strip():
                res['receiver'] = "未知收货人"
                
            return res, None
        except Exception as e:
            msg = f"AI 解析转换 JSON 失败: {str(e)}"
            print(f"❌ {msg}")
            return None, msg
