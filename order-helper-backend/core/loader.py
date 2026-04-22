import pandas as pd
import json
import os
import logging
import pickle
import time

logger = logging.getLogger(__name__)

class DataLoader:
    def __init__(self):
        self.data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        self.cache_dir = os.path.join(self.data_dir, '.cache')
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
        self.stock_data = pd.DataFrame()
        self.combo_data = pd.DataFrame()
        self.customer_data = pd.DataFrame()
        self.express_rules = {}
        self.customer_index = {}
        self.config = {}
        self.all_products = []
        
        # 🌟 快速索引 (Hash Maps)
        self.item_no_index = {}   # 规格编号 -> 详情
        self.product_name_index = {} # 货品名称 -> 详情
        self.customer_phone_index = {} # 电话 -> 客户信息

    def _get_cache_path(self, filename):
        return os.path.join(self.cache_dir, f"{filename}.pkl")

    def _should_refresh(self, source_path, cache_path):
        if not os.path.exists(cache_path): return True
        return os.path.getmtime(source_path) > os.path.getmtime(cache_path)

    def _load_excel_with_cache(self, filename):
        source_path = os.path.join(self.data_dir, filename)
        if not os.path.exists(source_path):
            return None
            
        cache_path = self._get_cache_path(filename)
        if not self._should_refresh(source_path, cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except: pass
            
        # 缓存失效或不存在，从 Excel 读取
        df = pd.read_excel(source_path)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(df, f)
        except: pass
        return df

    def load_all(self):
        """全量分步加载，带有二进制缓存"""
        start_time = time.time()
        
        # 1. 配置规则
        try:
            config_path = os.path.join(self.data_dir, '配置规则.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info("✅ 已加载配置规则.json")
            
            # 🌟 额外加载学习到的规则并合并
            learn_path = os.path.join(self.data_dir, 'learn_rules.json')
            if os.path.exists(learn_path):
                with open(learn_path, 'r', encoding='utf-8') as f:
                    learned = json.load(f)
                    if 'product' in learned:
                        self.config.setdefault('货品特殊映射', {}).update(learned['product'])
                    if 'customer' in learned:
                        self.config.setdefault('客户特殊映射', {}).update(learned['customer'])
                logger.info(f"✅ 已合并学习到的规则: 产品({len(learned.get('product',{}))}), 客户({len(learned.get('customer',{}))})")
        except Exception as e: logger.error(f"❌ 配置加载失败: {e}")

        # 2. 库存全量
        try:
            self.stock_data = self._load_excel_with_cache('总库存.xlsx')
            if self.stock_data is not None:
                # 建立规格编号和货品名称索引
                for _, row in self.stock_data.iterrows():
                    d = row.to_dict()
                    name = str(d.get('货品名称', '')).strip()
                    item_no = str(d.get('规格编号', '')).strip()
                    if name and name != 'nan': 
                        self.product_name_index[name] = d
                        if name not in self.all_products: self.all_products.append(name)
                    if item_no and item_no != 'nan': self.item_no_index[item_no] = d
                logger.info(f"✅ 已装载库存索引: {len(self.product_name_index)} 项")
        except Exception as e: logger.error(f"❌ 库存表索引失败: {e}")

        # 3. 组合装明细
        try:
            self.combo_data = self._load_excel_with_cache('总库存-组合装明细.xlsx')
            if self.combo_data is not None:
                possible_cols = ['组合装名称', '货品名称', '商品名称']
                col_found = next((c for c in possible_cols if c in self.combo_data.columns), None)
                if col_found:
                    for _, row in self.combo_data.iterrows():
                        d = row.to_dict()
                        name = str(d.get(col_found, '')).strip()
                        if name and name != 'nan':
                            self.product_name_index[name] = d
                            if name not in self.all_products: self.all_products.append(name)
                    logger.info(f"✅ 已装载组合装索引: {len(self.combo_data)} 项")
        except Exception as e: logger.error(f"❌ 组合装索引失败: {e}")

        # 4. 客户档案
        try:
            self.customer_data = self._load_excel_with_cache('客户档案.xlsx')
            if self.customer_data is not None:
                for _, row in self.customer_data.iterrows():
                    d = row.to_dict()
                    acc = str(d.get('客户账号', '')).strip()
                    name = str(d.get('客户名称', '')).strip()
                    phone = str(d.get('联系电话', '')).strip()
                    if acc and acc != 'nan': self.customer_index[acc] = d
                    if name and name != 'nan': self.customer_index[name] = d
                    if phone and phone != 'nan': 
                        self.customer_index[phone] = d
                        self.customer_phone_index[phone] = d
                logger.info(f"✅ 已索引客户档案: {len(self.customer_data)} 位")
        except Exception as e: logger.error(f"❌ 客户档案加载失败: {e}")

        # 5. 快递表格
        try:
            self.express_rules = {}
            ex_df = self._load_excel_with_cache('快递表格.xls')
            if ex_df is not None:
                for _, row in ex_df.iterrows():
                    prov = str(row.iloc[0]).strip()
                    if prov and prov != 'nan':
                        self.express_rules[prov] = row.to_dict()
                logger.info(f"✅ 已装载 {len(self.express_rules)} 省份快递规则")
        except Exception as e: logger.error(f"❌ 快递规则加载失败: {e}")

        logger.info(f"🚀 系统就绪！耗时: {time.time() - start_time:.2f}s, 产品库: {len(self.all_products)} 项")
