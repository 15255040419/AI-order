import pandas as pd
import json
import os
import logging

logger = logging.getLogger(__name__)

class DataLoader:
    def __init__(self):
        self.data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        self.stock_data = pd.DataFrame()
        self.combo_data = pd.DataFrame()
        self.customer_data = pd.DataFrame()
        self.express_rules = {}
        self.customer_index = {}
        self.config = {}
        self.all_products = []

    def load_all(self):
        """全量分步加载，确保单表错误不影响全局"""
        
        # 1. 配置规则
        try:
            config_path = os.path.join(self.data_dir, '配置规则.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info("✅ 已加载配置规则.json")
        except Exception as e: logger.error(f"❌ 配置加载失败: {e}")

        # 2. 库存全量
        try:
            stock_path = os.path.join(self.data_dir, '总库存.xlsx')
            if os.path.exists(stock_path):
                self.stock_data = pd.read_excel(stock_path)
                names = self.stock_data['货品名称'].dropna().unique().tolist()
                self.all_products.extend(names)
                logger.info(f"✅ 已装载库存: {len(names)} 项")
        except Exception as e: logger.error(f"❌ 库存表加载失败: {e}")

        # 3. 组合装明细
        try:
            combo_path = os.path.join(self.data_dir, '总库存-组合装明细.xlsx')
            if os.path.exists(combo_path):
                self.combo_data = pd.read_excel(combo_path)
                # 兼容性处理：尝试多个可能的组合装列名
                possible_cols = ['组合装名称', '货品名称', '商品名称']
                col_found = next((c for c in possible_cols if c in self.combo_data.columns), None)
                if col_found:
                    combo_names = self.combo_data[col_found].dropna().unique().tolist()
                    self.all_products.extend(combo_names)
                    logger.info(f"✅ 已装载组合装: {len(combo_names)} 项")
                else:
                    logger.warning("⚠️ 组合装明细表中未找到预期的货品列名")
        except Exception as e: logger.error(f"❌ 组合装表加载失败: {e}")

        # 4. 客户档案
        try:
            cust_path = os.path.join(self.data_dir, '客户档案.xlsx')
            if os.path.exists(cust_path):
                self.customer_data = pd.read_excel(cust_path)
                for _, row in self.customer_data.iterrows():
                    acc = str(row.get('客户账号', '')).strip()
                    name = str(row.get('客户名称', '')).strip()
                    phone = str(row.get('联系电话', '')).strip()
                    if acc and acc != 'nan': self.customer_index[acc] = row.to_dict()
                    if name and name != 'nan': self.customer_index[name] = row.to_dict()
                    if phone and phone != 'nan': self.customer_index[phone] = row.to_dict()
                logger.info(f"✅ 已索引客户档案: {len(self.customer_data)} 位")
        except Exception as e: logger.error(f"❌ 客户档案加载失败: {e}")

        # 5. 快递表格 (动态 Excel)
        try:
            express_path = os.path.join(self.data_dir, '快递表格.xls')
            if os.path.exists(express_path):
                df_ex = pd.read_excel(express_path)
                for _, row in df_ex.iterrows():
                    prov = str(row.iloc[0]).strip() # 第一个格一般是省份
                    if prov and prov != 'nan':
                        self.express_rules[prov] = row.to_dict()
                logger.info(f"✅ 已装载 {len(self.express_rules)} 省份快递规则")
        except Exception as e: logger.error(f"❌ 快递规则加载失败: {e}")

        # 去重产品库
        self.all_products = list(set(self.all_products))
        logger.info(f"🚀 系统就绪！全量产品库: {len(self.all_products)} 项")
