"""Altman Z-Score 破产风险模型 + 审计角度分析"""

from typing import Optional

from .ratios import safe_div


def altman_z_score(
    total_assets: Optional[float],
    current_assets: Optional[float],
    current_liabilities: Optional[float],
    retained_earnings: Optional[float],
    operating_profit: Optional[float],
    total_liabilities: Optional[float],
    operating_revenue: Optional[float],
    market_cap: Optional[float] = None,
) -> dict:
    """
    Altman Z-Score 破产风险模型

    判断标准:
        Z > 2.99 → 安全区
        1.81 < Z < 2.99 → 灰色区域（需关注）
        Z < 1.81 → 高风险区

    注意: 如果无法获取市值，使用简化版（Z''-Score，不含X4项）
    """
    missing = []
    if total_assets is None or total_assets == 0:
        missing.append("总资产")
    if current_assets is None:
        missing.append("流动资产")
    if current_liabilities is None:
        missing.append("流动负债")
    if retained_earnings is None:
        missing.append("留存收益")
    if operating_profit is None:
        missing.append("营业利润")
    if total_liabilities is None:
        missing.append("总负债")
    if operating_revenue is None:
        missing.append("营业收入")

    if missing:
        return {"error": f"缺少以下数据: {', '.join(missing)}"}

    working_capital = current_assets - current_liabilities

    X1 = working_capital / total_assets
    X2 = retained_earnings / total_assets if retained_earnings else 0
    X3 = operating_profit / total_assets
    X5 = operating_revenue / total_assets

    if market_cap is not None and market_cap > 0:
        X4 = market_cap / total_liabilities
        Z = 1.2 * X1 + 1.4 * X2 + 3.3 * X3 + 0.6 * X4 + 1.0 * X5
        version = "原始模型"
    else:
        # 简化版 Z''-Score（适用于无法获取市值的场景）
        Z = 6.56 * X1 + 3.26 * X2 + 6.72 * X3 + 1.05 * X5
        version = "简化模型(Z''-Score)"

    if Z > 2.99:
        risk_level = "安全区"
        risk_color = "green"
    elif Z > 1.81:
        risk_level = "灰色区域（需关注）"
        risk_color = "yellow"
    else:
        risk_level = "高风险区"
        risk_color = "red"

    return {
        "z_score": round(Z, 4),
        "risk_level": risk_level,
        "risk_color": risk_color,
        "version": version,
        "components": {
            "X1_wc_ratio": round(X1, 4),
            "X2_re_ratio": round(X2, 4),
            "X3_ebit_ratio": round(X3, 4),
            "X5_sales_ratio": round(X5, 4),
        },
    }


def audit_perspective_analysis(summary: dict, ratios: dict) -> dict:
    """
    审计角度分析——从审计师视角审视财务数据

    分析维度:
    1. 持续经营能力（Going Concern）
    2. 收入确认风险
    3. 资产减值信号
    4. 关联交易风险信号
    5. 财务数据勾稽关系
    6. 关键审计事项预判
    """
    findings = []

    # ===== 1. 持续经营能力评估 =====
    going_concern_risks = []

    # 连续亏损
    if ratios.get("net_margin") is not None and ratios["net_margin"] < 0:
        going_concern_risks.append("当期净利润为负")
    if ratios.get("roe") is not None and ratios["roe"] < 0:
        going_concern_risks.append("净资产收益率为负，股东权益正在被侵蚀")

    # 流动比率过低
    if ratios.get("current_ratio") is not None and ratios["current_ratio"] < 1.0:
        going_concern_risks.append(f"流动比率仅{ratios['current_ratio']:.2f}，流动资产不足以覆盖流动负债")

    # 高负债
    if ratios.get("debt_ratio") is not None and ratios["debt_ratio"] > 0.80:
        going_concern_risks.append(f"资产负债率高达{ratios['debt_ratio']:.1%}，财务杠杆极高")

    # 经营现金流为负
    ocf = summary.get("operating_cashflow")
    if ocf is not None and ocf < 0:
        going_concern_risks.append("经营活动现金流为负，主营业务造血能力不足")

    if going_concern_risks:
        findings.append({
            "area": "持续经营能力",
            "risk_level": "high" if len(going_concern_risks) >= 3 else "medium" if len(going_concern_risks) >= 2 else "low",
            "description": "存在以下持续经营风险信号",
            "details": going_concern_risks,
        })

    # ===== 2. 收入确认风险 =====
    revenue_risks = []

    # 第四季度收入占比过高（如果有时序数据）
    # 这里我们检查应收账款/收入比例
    ar = summary.get("accounts_receivable")
    revenue = summary.get("operating_revenue")
    if ar and revenue and revenue > 0:
        ar_ratio = ar / revenue
        if ar_ratio > 0.60:
            revenue_risks.append(f"应收账款占营业收入{ar_ratio:.1%}，超过60%，大额赊销可能虚增收入")
        elif ar_ratio > 0.40:
            revenue_risks.append(f"应收账款占营业收入{ar_ratio:.1%}，回款周期偏长")

    # 收入增长远高于行业但经营现金流不匹配
    rev_growth = ratios.get("revenue_growth_yoy")
    ocf_to_rev = ratios.get("ocf_to_revenue")
    if rev_growth and ocf_to_rev is not None:
        if rev_growth > 0.3 and ocf_to_rev < 0.05:
            revenue_risks.append(f"收入增速{rev_growth:.1%}但经营现金流/收入仅{ocf_to_rev:.1%}，增长质量可疑")

    if revenue_risks:
        findings.append({
            "area": "收入确认",
            "risk_level": "medium",
            "description": "收入确认存在以下风险信号",
            "details": revenue_risks,
        })

    # ===== 3. 资产减值信号 =====
    impairment_signals = []

    goodwill = summary.get("goodwill")
    equity = summary.get("total_equity")
    if goodwill and equity and equity > 0:
        gw_ratio = goodwill / equity
        if gw_ratio > 0.50:
            impairment_signals.append(f"商誉占净资产{gw_ratio:.1%}，超过50%，减值风险极高")
        elif gw_ratio > 0.30:
            impairment_signals.append(f"商誉占净资产{gw_ratio:.1%}，超过30%，存在商誉减值风险")

    inv = summary.get("inventory")
    if inv and revenue and revenue > 0:
        inv_ratio = inv / revenue
        if inv_ratio > 0.50:
            impairment_signals.append(f"存货/营业收入={inv_ratio:.1%}，库存积压严重，存在存货跌价风险")

    ar = summary.get("accounts_receivable")
    if ar and revenue and revenue > 0:
        aging_risk = ar / revenue
        if aging_risk > 0.80:
            impairment_signals.append(f"应收账款占比高达{aging_risk:.1%}，坏账计提是否充分需关注")

    asset_imp = summary.get("asset_impairment_loss")
    credit_imp = summary.get("credit_impairment_loss")
    if asset_imp and asset_imp > 0:
        impairment_signals.append(f"已确认资产减值损失{asset_imp/1e8:.2f}亿")
    if credit_imp and credit_imp > 0:
        impairment_signals.append(f"已确认信用减值损失{credit_imp/1e8:.2f}亿")

    if impairment_signals:
        findings.append({
            "area": "资产减值",
            "risk_level": "high" if goodwill and equity and goodwill/equity > 0.3 else "medium",
            "description": "资产减值风险需关注",
            "details": impairment_signals,
        })

    # ===== 4. 勾稽关系检查 =====
    cross_check_issues = []

    # 利润与现金流偏离度
    if ocf and summary.get("net_profit"):
        np_val = summary["net_profit"]
        if np_val > 0 and ocf < 0:
            cross_check_issues.append("净利润为正但经营现金流为负，利润与现金流严重背离")
        elif np_val > 0:
            ratio = ocf / np_val
            if ratio < 0.3:
                cross_check_issues.append(f"经营现金流仅覆盖净利润的{ratio:.1%}，利润含金量不足")

    # 收入与税金匹配
    # （简化判断：有收入但所得税费用异常低）
    income_tax = summary.get("income_tax") or summary.get("所得税费用")
    total_profit = summary.get("total_profit")
    if income_tax is not None and total_profit and total_profit > 0 and income_tax <= 0:
        cross_check_issues.append("利润总额为正但所得税费用为零或负数，需检查递延所得税确认是否合理")

    if cross_check_issues:
        findings.append({
            "area": "报表勾稽关系",
            "risk_level": "high",
            "description": "三张报表之间的勾稽关系存在异常",
            "details": cross_check_issues,
        })

    # ===== 5. 关键审计事项预判 =====
    kam_predictions = []

    if goodwill and equity and goodwill / equity > 0.20:
        kam_predictions.append("商誉减值测试——商誉占净资产比例较高，减值测试涉及管理层重大判断")
    if revenue and ar and ar / revenue > 0.50:
        kam_predictions.append("收入确认——应收账款占比较高，收入确认时点和金额准确性是关键审计领域")
    if ratios.get("inventory_turnover_days") and ratios["inventory_turnover_days"] > 180:
        kam_predictions.append("存货跌价准备——存货周转天数过长，可变现净值评估需关注")
    if summary.get("rd_expenses") and revenue and summary["rd_expenses"] / revenue > 0.10:
        kam_predictions.append("研发费用资本化——研发投入占收入比例较高，资本化条件的判断是关键判断")

    if kam_predictions:
        findings.append({
            "area": "关键审计事项预判",
            "risk_level": "info",
            "description": "根据财务数据预判可能的關鍵审计事项",
            "details": kam_predictions,
        })

    return {
        "findings": findings,
        "total_risks": len([f for f in findings if f["risk_level"] in ("high", "medium")]),
        "high_risks": len([f for f in findings if f["risk_level"] == "high"]),
    }
