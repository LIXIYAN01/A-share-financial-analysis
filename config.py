"""全局配置"""

# 数据采集
DATA_SOURCES = ["akshare"]  # 可选: akshare, tushare
AKSHARE_RETRY = 3
AKSHARE_TIMEOUT = 30

# 科目映射表（精确匹配Sina数据源的列名）
ACCOUNT_MAPPING = {
    # === 资产负债表（Sina列名） ===
    "资产总计": "total_assets",
    "负债合计": "total_liabilities",
    "负债和所有者权益(或股东权益)总计": "total_liabilities_equity",
    "所有者权益(或股东权益)合计": "total_equity",
    "归属于母公司股东权益合计": "equity_parent",
    "流动资产合计": "current_assets",
    "非流动资产合计": "non_current_assets",
    "流动负债合计": "current_liabilities",
    "非流动负债合计": "non_current_liabilities",
    "存货": "inventory",
    "应收账款": "accounts_receivable",
    "应收票据及应收账款": "notes_and_ar",
    "应收票据": "notes_receivable",
    "货币资金": "cash_equivalents",
    "短期借款": "short_term_loans",
    "长期借款": "long_term_loans",
    "应付账款": "accounts_payable",
    "应付票据及应付账款": "notes_and_ap",
    "预付款项": "prepayments",
    "预收款项": "advance_receipts",
    "合同负债": "contract_liabilities",
    "固定资产净额": "fixed_assets",
    "固定资产原值": "fixed_assets_original",
    "在建工程": "construction_in_progress",
    "在建工程合计": "construction_in_progress",
    "无形资产": "intangible_assets",
    "商誉": "goodwill",
    "长期股权投资": "long_term_investments",
    "未分配利润": "retained_earnings",
    "盈余公积": "surplus_reserve",
    "实收资本(或股本)": "paid_in_capital",
    "资本公积": "capital_reserve",
    "其他综合收益": "other_comprehensive_income",
    "少数股东权益": "minority_equity",
    "归属于母公司股东权益合计": "equity_parent",

    # === 利润表（Sina列名） ===
    "营业总收入": "operating_revenue",
    "营业总成本": "operating_cost_total",
    "营业成本": "operating_cost",
    "营业税金及附加": "business_tax_surcharge",
    "销售费用": "selling_expenses",
    "管理费用": "admin_expenses",
    "研发费用": "rd_expenses",
    "财务费用": "finance_expenses",
    "利息费用": "interest_expense",
    # "利息支出" 与 "利息费用" 保留一个
    "投资收益": "investment_income",
    "对联营企业和合营企业的投资收益": "joint_venture_income",
    "营业利润": "operating_profit",
    "利润总额": "total_profit",
    "所得税费用": "income_tax",
    "净利润": "net_profit",
    "归属于母公司所有者的净利润": "net_profit_parent",
    "少数股东损益": "minority_interest",
    "其他收益": "other_income",
    "公允价值变动收益": "fair_value_change",
    "信用减值损失": "credit_impairment_loss",
    "资产减值损失": "asset_impairment_loss",
    "资产处置收益": "asset_disposal_income",
    "基本每股收益": "eps",
    "稀释每股收益": "eps_diluted",

    # === 现金流量表（Sina列名） ===
    "经营活动现金流入小计": "operating_cash_inflow",
    "经营活动现金流出小计": "operating_cash_outflow",
    "经营活动产生的现金流量净额": "operating_cashflow",
    "投资活动现金流入小计": "investing_cash_inflow",
    "投资活动现金流出小计": "investing_cash_outflow",
    "投资活动产生的现金流量净额": "investing_cashflow",
    "筹资活动现金流入小计": "financing_cash_inflow",
    "筹资活动现金流出小计": "financing_cash_outflow",
    "筹资活动产生的现金流量净额": "financing_cashflow",
    "现金及现金等价物净增加额": "net_cash_change",
    "销售商品、提供劳务收到的现金": "cash_from_sales",
    "购买商品、接受劳务支付的现金": "cash_for_purchases",
    "购建固定资产、无形资产和其他长期资产所支付的现金": "capex",
}

# 同业对比行业分类（申万一级）
INDUSTRY_MAP = {
    "食品饮料": ["白酒", "啤酒", "乳制品", "调味品", "食品加工", "饮料", "休闲食品"],
    "医药生物": ["化学制药", "中药", "生物制品", "医疗器械", "医药商业", "医疗服务"],
    "电子": ["半导体", "电子元器件", "消费电子", "光学光电子", "电子化学品"],
    "计算机": ["软件开发", "IT服务", "计算机设备"],
    "银行": ["银行"],
    "非银金融": ["证券", "保险", "多元金融"],
}

# 报告输出
OUTPUT_DIR = "output"
REPORT_TITLE = "A股上市公司财务分析报告"
