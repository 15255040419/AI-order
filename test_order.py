import json
import sys
import os
import requests

sys.path.append(r"e:\FTH\AI-order\order-helper-backend")
os.chdir(r"e:\FTH\AI-order\order-helper-backend")

import app

# 强制加载数据
app.load_data()

test_order = "任女士 13810787933 地址:北京市门头沟区永定镇欢乐大都汇10-1京西骑福 XP-80TS（USB+网口）*1+XP-246B(USB)*1+TX-688*1+80*60纸*1卷+40*30不干胶（300张）*1+补运费 100+160+40+0+0+28=328元 已付 仝心农商 系统录 上海禹禄信息-宋群辉（F）发顺丰现付"

ai_res, err = app.parse_order_with_ai(test_order)
print("AI Result:", json.dumps(ai_res, ensure_ascii=False, indent=2))
print("Error:", err)

if ai_res:
    final = app.process_parsed_data(ai_res, test_order)
    print("Final Processed:", json.dumps(final, ensure_ascii=False, indent=2))
