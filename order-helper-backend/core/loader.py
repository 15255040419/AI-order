import os
import pandas as pd
import logging
import json

logger = logging.getLogger(__name__)

class DataLoader:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.stock_data = None
        self.combo_data = None
        self.customer_data = None
        self.express_rules = {}
        self.all_products = []
        self.customer_index = {} # 用于快速查找：手机号/名称 -> 完整资料

    def load_all(self):
        """一次性加载所有 Excel 数据并建立索引"""
        try:
            # 1. 货品数据
            stock_path = os.path.join(self.data_dir, '总库存.xlsx')
            combo_path = os.path.join(self.data_dir, '总库存-组合装明细.xlsx')
            
            if os.path.exists(stock_path):
                self.stock_data = pd.read_excel(stock_path)
                logger.info(f"Loaded stock: {len(self.stock_data)} items")
            
            if os.path.exists(combo_path):
                self.combo_data = pd.read_excel(combo_path)
                logger.info(f"Loaded combos: {len(self.combo_data)} items")

            # 汇总所有货品全名
            p1 = self.stock_data['货品名称'].dropna().unique().tolist() if self.stock_data is not None else []
            p2 = self.stock_data['规格编号'].dropna().unique().tolist() if self.stock_data is not None else []
            p3 = self.combo_data['货品名称'].dropna().unique().tolist() if self.combo_data is not None else []
            self.all_products = list(set(p1 + p2 + p3))

            # 2. 客户档案索引
            cust_path = os.path.join(self.data_dir, '客户档案.xlsx')
            if os.path.exists(cust_path):
                df_cust = pd.read_excel(cust_path)
                # 建立手机号和名称的索引
                for _, row in df_cust.iterrows():
                    info = row.to_dict()
                    name = str(info.get('客户名称', '')).strip()
                    phone = str(info.get('联系电话', '')).strip()
                    if name: self.customer_index[name] = info
                    if phone and phone != 'nan': self.customer_index[phone] = info
                logger.info(f"Indexed {len(df_cust)} customers")

            # 3. 快递表格规则
            ex_path = os.path.join(self.data_dir, '快递表格.xls')
            if os.path.exists(ex_path):
                df_ex = pd.read_excel(ex_path, header=None)
                for i in range(2, len(df_ex)):
                    row = df_ex.iloc[i]
                    prov = str(row[0]).strip().replace('省', '').replace('市', '')
                    if not prov or prov == 'nan': continue
                    self.express_rules[prov] = {
                        "打印机_小": str(row[1]).strip(),
                        "打印机_中": str(row[2]).strip(),
                        "打印机_大": str(row[3]).strip(),
                        "收银机": str(row[4]).strip(),
                        "一体称": str(row[5]).strip(),
                        "其他": str(row[6]).strip()
                    }
                logger.info(f"Loaded {len(self.express_rules)} province express rules")

        except Exception as e:
            logger.error(f"DataLoader Error: {str(e)}")

    def get_customer(self, identifier):
        """通过名字或手机号查找客户档案"""
        return self.customer_index.get(str(identifier).strip())

    def get_express_rule(self, province):
        """获取省份对应的快递规则"""
        return self.express_rules.get(province.replace('省', '').replace('市', ''))
