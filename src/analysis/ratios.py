"""财务比率分析模块 — 计算盈利能力、偿债能力、营运能力、成长能力、现金流质量指标"""

import math
from typing import Optional

import pandas as pd


def safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """安全除法"""
    if a is None or b is None or b == 0:
        return None
    return a / b


def _get_unique_col(df: pd.DataFrame, candidates: list) -> str:
    """从DataFrame中找第一个存在的列名，返回列名字符串"""
    for c in candidates:
        if c in df.columns:
            # Check it's actually a single column
            col_data = df[c]
            if isinstance(col_data, pd.DataFrame):
                # Multiple columns with same name - use the first
                return col_data.columns[0]
            return c
    return None


def score_metric(value: Optional[float], good: float, bad: float) -> float:
    """
    线性插值打分: good=100分, bad=0分
    越大越好的指标用此函数
    """
    if value is None or math.isnan(value):
        return 50.0
    if good > bad:
        return max(0.0, min(100.0, (value - bad) / (good - bad) * 100))
    else:
        return max(0.0, min(100.0, (bad - value) / (bad - good) * 100))


def calculate_all_ratios(summary: dict) -> dict:
    """
    基于财务摘要数据计算所有核心财务比率

    返回完整指标字典，包括：
    - 盈利能力指标
    - 偿债能力指标
    - 营运能力指标
    - 成长能力指标
    - 现金流质量指标
    - 每股指标
    - 综合评分
    """
    r = {}

    # ====== 盈利能力 ======
    s = summary
    revenue = s.get("operating_revenue")
    cost = s.get("operating_cost")
    net_profit = s.get("net_profit")
    net_profit_parent = s.get("net_profit_parent")
    total_assets = s.get("total_assets")
    total_equity = s.get("total_equity")
    operating_profit = s.get("operating_profit")
    total_profit = s.get("total_profit")

    r["gross_margin"] = safe_div(revenue - cost, revenue) if revenue and cost else None
    r["net_margin"] = safe_div(net_profit, revenue)
    r["operating_margin"] = safe_div(operating_profit, revenue)
    r["roa"] = safe_div(net_profit, total_assets)
    r["roe"] = safe_div(net_profit, total_equity)
    r["roe_parent"] = safe_div(net_profit_parent, total_equity)

    # 费用率
    r["selling_expense_ratio"] = safe_div(s.get("selling_expenses"), revenue)
    r["admin_expense_ratio"] = safe_div(s.get("admin_expenses"), revenue)
    r["rd_expense_ratio"] = safe_div(s.get("rd_expenses"), revenue)
    r["finance_expense_ratio"] = safe_div(s.get("finance_expenses"), revenue)

    # ====== 偿债能力 ======
    total_liabilities = s.get("total_liabilities")
    curr_assets = s.get("current_assets")
    curr_liabilities = s.get("current_liabilities")
    inventory = s.get("inventory")

    r["debt_ratio"] = safe_div(total_liabilities, total_assets)
    r["equity_ratio"] = safe_div(total_equity, total_assets)
    r["debt_to_equity"] = safe_div(total_liabilities, total_equity)
    r["current_ratio"] = safe_div(curr_assets, curr_liabilities)
    r["quick_ratio"] = safe_div(curr_assets - inventory, curr_liabilities) if curr_assets and inventory and curr_liabilities else None

    # 有息负债率
    interest_bearing_debt = (s.get("short_term_loans") or 0) + (s.get("long_term_loans") or 0)
    r["interest_bearing_debt_ratio"] = safe_div(interest_bearing_debt, total_assets) if interest_bearing_debt > 0 else 0

    # ====== 营运能力 ======
    ar = s.get("accounts_receivable")
    ap = s.get("accounts_payable")
    inv = s.get("inventory")

    r["ar_turnover"] = safe_div(revenue, ar)
    r["ar_turnover_days"] = safe_div(365, r["ar_turnover"]) if r["ar_turnover"] else None
    r["inventory_turnover"] = safe_div(cost, inv)
    r["inventory_turnover_days"] = safe_div(365, r["inventory_turnover"]) if r["inventory_turnover"] else None
    r["ap_turnover"] = safe_div(cost, ap)
    r["ap_turnover_days"] = safe_div(365, r["ap_turnover"]) if r["ap_turnover"] else None
    r["total_asset_turnover"] = safe_div(revenue, total_assets)

    # 现金循环周期
    ar_days = r.get("ar_turnover_days") or 0
    inv_days = r.get("inventory_turnover_days") or 0
    ap_days = r.get("ap_turnover_days") or 0
    r["cash_conversion_cycle"] = ar_days + inv_days - ap_days

    # ====== 成长能力 ======
    ts_data = s.get("_time_series", {})
    income_ts = ts_data.get("income", pd.DataFrame())

    if not income_ts.empty and "report_date" in income_ts.columns:
        income_ts = income_ts.sort_values("report_date")
        # Ensure unique operating_revenue column
        rev_col = _get_unique_col(income_ts, ["operating_revenue", "营业总收入"])
        np_col = _get_unique_col(income_ts, ["net_profit", "净利润"])

        if rev_col and len(income_ts) >= 2:
            prev_rev = float(income_ts[rev_col].iloc[-2]) if pd.notna(income_ts[rev_col].iloc[-2]) else None
            curr_rev = float(income_ts[rev_col].iloc[-1]) if pd.notna(income_ts[rev_col].iloc[-1]) else None
            r["revenue_growth_yoy"] = safe_div(curr_rev - prev_rev, prev_rev) if prev_rev and curr_rev else None
        else:
            r["revenue_growth_yoy"] = None

        if np_col and len(income_ts) >= 2:
            prev_np = float(income_ts[np_col].iloc[-2]) if pd.notna(income_ts[np_col].iloc[-2]) else None
            curr_np = float(income_ts[np_col].iloc[-1]) if pd.notna(income_ts[np_col].iloc[-1]) else None
            r["profit_growth_yoy"] = safe_div(curr_np - prev_np, prev_np) if prev_np and curr_np else None
        else:
            r["profit_growth_yoy"] = None

        # 3年复合增长率
        if rev_col and len(income_ts) >= 4:
            old_rev = float(income_ts[rev_col].iloc[0]) if pd.notna(income_ts[rev_col].iloc[0]) else None
            new_rev = float(income_ts[rev_col].iloc[-1]) if pd.notna(income_ts[rev_col].iloc[-1]) else None
            if old_rev and new_rev and old_rev > 0 and new_rev > 0:
                r["revenue_cagr_3y"] = (new_rev / old_rev) ** (1 / 3) - 1
            else:
                r["revenue_cagr_3y"] = None
        else:
            r["revenue_cagr_3y"] = None
    else:
        r["revenue_growth_yoy"] = None
        r["profit_growth_yoy"] = None
        r["revenue_cagr_3y"] = None

    # ====== 现金流质量 ======
    ocf = s.get("operating_cashflow")
    r["ocf_to_profit"] = safe_div(ocf, net_profit)
    r["ocf_to_revenue"] = safe_div(ocf, revenue)
    r["free_cashflow"] = (ocf or 0) + (s.get("investing_cashflow") or 0)

    # ====== 盈利质量指标 ======
    r["investment_income_to_profit"] = safe_div(s.get("investment_income"), operating_profit)
    r["fair_value_to_profit"] = safe_div(s.get("fair_value_change"), operating_profit)
    r["other_income_to_profit"] = safe_div(s.get("other_income"), operating_profit)
    r["asset_impairment_to_profit"] = safe_div(abs(s.get("asset_impairment_loss") or 0), abs(operating_profit or 1))

    # 核心利润占比 = (营业利润 - 投资收益 - 公允价值变动 - 其他收益) / 营业利润
    core_profit = (operating_profit or 0) - (s.get("investment_income") or 0) - (s.get("fair_value_change") or 0) - (s.get("other_income") or 0)
    r["core_profit_ratio"] = safe_div(core_profit, operating_profit)

    # ====== 资产结构指标 ======
    r["goodwill_to_equity"] = safe_div(s.get("goodwill"), total_equity)
    r["fixed_asset_ratio"] = safe_div(s.get("fixed_assets"), total_assets)
    r["intangible_ratio"] = safe_div(s.get("intangible_assets"), total_assets)

    # ====== 综合评分 (0-100) ======
    profitability_score = (
        score_metric(r["roe"], 0.15, 0.03) * 0.35 +
        score_metric(r["gross_margin"], 0.40, 0.15) * 0.30 +
        score_metric(r["net_margin"], 0.15, 0.03) * 0.20 +
        score_metric(r["core_profit_ratio"], 0.85, 0.50) * 0.15
    ) * 0.30

    solvency_score = (
        score_metric(1 - (r["debt_ratio"] or 0.5), 0.60, 0.30) * 0.40 +
        score_metric(r["current_ratio"], 2.0, 0.8) * 0.30 +
        score_metric(r["quick_ratio"], 1.2, 0.5) * 0.30
    ) * 0.25

    efficiency_score = (
        score_metric(90 - (r["ar_turnover_days"] or 90), 60, 0) * 0.30 +
        score_metric(180 - (r["inventory_turnover_days"] or 180), 120, 0) * 0.30 +
        score_metric(r["total_asset_turnover"], 1.0, 0.3) * 0.40
    ) * 0.15

    growth_score = (
        score_metric(r["revenue_growth_yoy"], 0.20, 0.0) * 0.50 +
        score_metric(r["profit_growth_yoy"], 0.20, -0.10) * 0.50
    ) * 0.15

    cashflow_score = (
        score_metric(r["ocf_to_profit"], 1.2, 0.5) * 0.60 +
        score_metric(r["ocf_to_revenue"], 0.15, 0.0) * 0.40
    ) * 0.15

    r["health_score"] = round(profitability_score + solvency_score + efficiency_score + growth_score + cashflow_score, 1)
    r["health_score_breakdown"] = {
        "profitability": round(profitability_score, 1),
        "solvency": round(solvency_score, 1),
        "efficiency": round(efficiency_score, 1),
        "growth": round(growth_score, 1),
        "cashflow": round(cashflow_score, 1),
    }

    return r


def format_ratio(value: Optional[float], as_percent: bool = True, decimals: int = 2) -> str:
    """格式化比率为可读字符串"""
    if value is None:
        return "N/A"
    if as_percent:
        return f"{value * 100:.{decimals}f}%"
    return f"{value:.{decimals}f}"


def dupont_decomposition(summary: dict) -> dict:
    """杜邦分析——ROE三因素分解"""
    net_margin = safe_div(summary.get("net_profit"), summary.get("operating_revenue"))
    asset_turnover = safe_div(summary.get("operating_revenue"), summary.get("total_assets"))
    equity_multiplier = safe_div(summary.get("total_assets"), summary.get("total_equity"))
    roe = safe_div(summary.get("net_profit"), summary.get("total_equity"))

    return {
        "roe": roe,
        "net_profit_margin": net_margin,
        "asset_turnover": asset_turnover,
        "equity_multiplier": equity_multiplier,
        "roe_calculated": (net_margin * asset_turnover * equity_multiplier) if all([net_margin, asset_turnover, equity_multiplier]) else None,
    }
