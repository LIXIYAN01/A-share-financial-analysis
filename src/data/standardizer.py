"""数据标准化模块 — 统一不同数据源的科目口径

Sina数据源格式: 每行代表一个报告期，列名为中文科目名称
"""

import pandas as pd

from config import ACCOUNT_MAPPING


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    将中文科目名称映射为标准化英文名
    仅精确匹配，不做模糊匹配（避免误匹配如 非流动资产合计 → 资产合计）
    如果目标列名已存在，跳过（避免重复）
    """
    if df is None or df.empty:
        return df

    result = df.copy()
    col_map = {}

    skip_cols = ["report_date", "报告期", "报告日", "截止日期", "股票代码", "公司名称",
                 "指标", "代码", "名称", "数据源", "是否审计", "公告日期", "币种", "类型", "更新日期"]

    existing_columns = set(result.columns)

    for col in result.columns:
        col_str = str(col).strip()
        if col_str in skip_cols:
            continue
        if col_str in ACCOUNT_MAPPING:
            new_name = ACCOUNT_MAPPING[col_str]
            # 避免重复列名：如果目标名已存在且来自不同源列，则不重命名
            if new_name not in existing_columns or new_name == col_str:
                col_map[col] = new_name
                existing_columns.discard(col_str)
                existing_columns.add(new_name)

    if col_map:
        result = result.rename(columns=col_map)

    return result


def extract_latest_period(df: pd.DataFrame) -> pd.Series:
    """提取最近一期的数据（返回Series，包含该期所有科目的值）"""
    if df is None or df.empty:
        return pd.Series(dtype=float)

    if "report_date" in df.columns:
        df = df.sort_values("report_date", ascending=False)

    return df.iloc[0]


def extract_financial_summary(all_data: dict) -> dict:
    """
    从采集的原始数据中提取摘要，构建统一的分析数据结构

    策略：从Sina数据源读取，它返回的是"报告期 × 科目"的宽表
    - 每列是一个科目
    - 最新一行是最新报告期数据
    """
    balance = all_data.get("balance_sheet", pd.DataFrame())
    income = all_data.get("income_statement", pd.DataFrame())
    cashflow = all_data.get("cashflow_statement", pd.DataFrame())

    # 标准化
    balance_std = standardize_columns(balance)
    income_std = standardize_columns(income)
    cashflow_std = standardize_columns(cashflow)

    # 取最新一期数据
    latest_bs = extract_latest_period(balance_std)
    latest_is_ = extract_latest_period(income_std)
    latest_cf = extract_latest_period(cashflow_std)

    def _get(series, *keys):
        """从多个可能的键中获取第一个存在的值"""
        for k in keys:
            if k in series.index and pd.notna(series.get(k)):
                val = series[k]
                try:
                    return float(val)
                except (ValueError, TypeError):
                    continue
        return None

    # 按优先级遍历所有可能的列名
    summary = _extract_combined_summary(
        latest_bs, latest_is_, latest_cf, balance_std, income_std, cashflow_std
    )

    # 时间序列数据
    summary["_time_series"] = {
        "balance": balance_std,
        "income": income_std,
        "cashflow": cashflow_std,
    }

    return summary


def _extract_combined_summary(latest_bs, latest_is, latest_cf,
                              balance_df, income_df, cashflow_df) -> dict:
    """综合提取所有字段"""

    def get_any(*series_list_and_keys):
        """从多个Series中查找键"""
        for series, key in series_list_and_keys:
            if isinstance(series, pd.Series) and key in series.index and pd.notna(series[key]):
                try:
                    return float(series[key])
                except (ValueError, TypeError):
                    continue
        return None

    # 资产负债表字段 => (Series, key)
    bs = ("bs", latest_bs)
    pl = ("pl", latest_is)
    cf = ("cf", latest_cf)

    fields = {}

    # --- 资产类 ---
    fields["total_assets"] = _find_in_sina_data(latest_bs, ["资产总计", "总资产", "total_assets"])
    fields["current_assets"] = _find_in_sina_data(latest_bs, ["流动资产合计", "current_assets"])
    fields["cash_equivalents"] = _find_in_sina_data(latest_bs, ["货币资金", "cash_equivalents"])
    fields["accounts_receivable"] = _find_in_sina_data(latest_bs, ["应收账款", "accounts_receivable"])
    fields["inventory"] = _find_in_sina_data(latest_bs, ["存货", "inventory"])
    fields["fixed_assets"] = _find_in_sina_data(latest_bs, ["固定资产", "fixed_assets"])
    fields["construction_in_progress"] = _find_in_sina_data(latest_bs, ["在建工程", "construction_in_progress"])
    fields["intangible_assets"] = _find_in_sina_data(latest_bs, ["无形资产", "intangible_assets"])
    fields["goodwill"] = _find_in_sina_data(latest_bs, ["商誉", "goodwill"])
    fields["long_term_investments"] = _find_in_sina_data(latest_bs, ["长期股权投资", "long_term_investments"])
    fields["prepayments"] = _find_in_sina_data(latest_bs, ["预付款项", "prepayments"])

    # --- 负债类 ---
    fields["total_liabilities"] = _find_in_sina_data(latest_bs, ["负债合计", "总负债", "total_liabilities"])
    fields["current_liabilities"] = _find_in_sina_data(latest_bs, ["流动负债合计", "current_liabilities"])
    fields["short_term_loans"] = _find_in_sina_data(latest_bs, ["短期借款", "short_term_loans"])
    fields["long_term_loans"] = _find_in_sina_data(latest_bs, ["长期借款", "long_term_loans"])
    fields["accounts_payable"] = _find_in_sina_data(latest_bs, ["应付账款", "accounts_payable"])
    fields["advance_receipts"] = _find_in_sina_data(latest_bs, ["预收款项", "预收账款", "advance_receipts"])
    fields["contract_liabilities"] = _find_in_sina_data(latest_bs, ["合同负债", "contract_liabilities"])

    # --- 权益类 ---
    fields["total_equity"] = _find_in_sina_data(latest_bs, ["所有者权益合计", "股东权益合计", "total_equity"])
    fields["equity_parent"] = _find_in_sina_data(latest_bs, ["归属于母公司所有者权益合计", "归母权益", "equity_parent"])
    fields["retained_earnings"] = _find_in_sina_data(latest_bs, ["未分配利润", "retained_earnings"])
    fields["paid_in_capital"] = _find_in_sina_data(latest_bs, ["实收资本（或股本）", "实收资本", "paid_in_capital"])
    fields["surplus_reserve"] = _find_in_sina_data(latest_bs, ["盈余公积", "surplus_reserve"])

    # --- 利润表 ---
    fields["operating_revenue"] = _find_in_sina_data(latest_is, ["营业收入", "营业总收入", "operating_revenue"])
    fields["operating_cost"] = _find_in_sina_data(latest_is, ["营业成本", "营业总成本", "operating_cost"])
    fields["selling_expenses"] = _find_in_sina_data(latest_is, ["销售费用", "selling_expenses"])
    fields["admin_expenses"] = _find_in_sina_data(latest_is, ["管理费用", "admin_expenses"])
    fields["rd_expenses"] = _find_in_sina_data(latest_is, ["研发费用", "rd_expenses"])
    fields["finance_expenses"] = _find_in_sina_data(latest_is, ["财务费用", "finance_expenses"])
    fields["interest_expense"] = _find_in_sina_data(latest_is, ["利息费用", "interest_expense"])
    fields["investment_income"] = _find_in_sina_data(latest_is, ["投资收益", "investment_income"])
    fields["operating_profit"] = _find_in_sina_data(latest_is, ["营业利润", "operating_profit"])
    fields["total_profit"] = _find_in_sina_data(latest_is, ["利润总额", "total_profit"])
    fields["net_profit"] = _find_in_sina_data(latest_is, ["净利润", "net_profit"])
    fields["net_profit_parent"] = _find_in_sina_data(latest_is, ["归属于母公司所有者的净利润", "归母净利润", "net_profit_parent"])
    fields["minority_interest"] = _find_in_sina_data(latest_is, ["少数股东损益", "minority_interest"])
    fields["other_income"] = _find_in_sina_data(latest_is, ["其他收益", "other_income"])
    fields["fair_value_change"] = _find_in_sina_data(latest_is, ["公允价值变动收益", "fair_value_change"])
    fields["credit_impairment_loss"] = _find_in_sina_data(latest_is, ["信用减值损失", "credit_impairment_loss"])
    fields["asset_impairment_loss"] = _find_in_sina_data(latest_is, ["资产减值损失", "asset_impairment_loss"])
    fields["asset_disposal_income"] = _find_in_sina_data(latest_is, ["资产处置收益", "asset_disposal_income"])
    fields["income_tax"] = _find_in_sina_data(latest_is, ["所得税费用", "income_tax"])

    # --- 现金流量表 ---
    fields["operating_cashflow"] = _find_in_sina_data(latest_cf, ["经营活动产生的现金流量净额", "operating_cashflow"])
    fields["investing_cashflow"] = _find_in_sina_data(latest_cf, ["投资活动产生的现金流量净额", "investing_cashflow"])
    fields["financing_cashflow"] = _find_in_sina_data(latest_cf, ["筹资活动产生的现金流量净额", "financing_cashflow"])
    fields["net_cash_change"] = _find_in_sina_data(latest_cf, ["现金及现金等价物净增加额", "net_cash_change"])
    fields["operating_cash_inflow"] = _find_in_sina_data(latest_cf, ["经营活动现金流入小计", "operating_cash_inflow"])
    fields["operating_cash_outflow"] = _find_in_sina_data(latest_cf, ["经营活动现金流出小计", "operating_cash_outflow"])

    return fields


def _find_in_sina_data(series: pd.Series, candidates: list) -> float:
    """从Series中按优先级查找值"""
    if series is None or not isinstance(series, pd.Series):
        return None
    for key in candidates:
        if key in series.index:
            try:
                val = series[key]
                if isinstance(val, pd.Series):
                    val = val.iloc[0]
                if pd.isna(val):
                    continue
                return float(val)
            except (ValueError, TypeError, IndexError):
                continue
    return None
