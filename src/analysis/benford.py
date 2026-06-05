"""本福特定律检验模块 — 检测财务数据首位数字分布是否异常"""

import math
from typing import Optional

import numpy as np
from scipy import stats

# 本福特定律理论概率
BENFORD_PROBS = {d: math.log10(1 + 1 / d) for d in range(1, 10)}


def _extract_first_digit(x) -> Optional[int]:
    """提取一个数的首位数字（非零）"""
    if x is None:
        return None
    try:
        val = abs(float(x))
        if val == 0:
            return None
        # 找到第一个非零数字
        while val >= 10:
            val /= 10
        while val < 1:
            val *= 10
        return int(val)
    except (ValueError, TypeError):
        return None


def benford_test(data: list, label: str = "") -> dict:
    """
    对一组财务数据做本福特定律首位数字检验

    参数:
        data: 数值列表（必须为正数）
        label: 数据标签（如"营业收入"）

    返回:
        {
            "label": 标签,
            "sample_size": 样本量,
            "chi2_statistic": 卡方统计量,
            "p_value": p值,
            "is_abnormal": 是否异常 (p < 0.05),
            "mad": 平均绝对偏差,
            "conformity": 一致性等级,
            "observed": 观测频次列表,
            "expected": 期望频次列表,
        }
    """
    # 过滤有效数值
    valid_data = []
    for x in data:
        try:
            val = float(x)
            if val > 0 and not math.isnan(val) and not math.isinf(val):
                valid_data.append(val)
        except (ValueError, TypeError):
            continue

    if len(valid_data) < 30:
        return {"label": label, "error": f"样本量不足（{len(valid_data)} < 30）", "sample_size": len(valid_data)}

    # 提取首位数字
    first_digits = []
    for val in valid_data:
        d = _extract_first_digit(val)
        if d is not None:
            first_digits.append(d)

    n = len(first_digits)
    if n < 30:
        return {"label": label, "error": f"有效样本量不足（{n} < 30）", "sample_size": n}

    # 计算各数字的观测频率和期望频率
    observed_counts = [first_digits.count(d) for d in range(1, 10)]
    expected_probs = [BENFORD_PROBS[d] for d in range(1, 10)]
    expected_counts = [p * n for p in expected_probs]

    # 卡方检验
    chi2, p_value = stats.chisquare(observed_counts, f_exp=expected_counts)

    # 平均绝对偏差 (MAD)
    observed_freqs = [c / n for c in observed_counts]
    mad = float(np.mean([abs(o - e) for o, e in zip(observed_freqs, expected_probs)]))

    # MAD一致性等级（Nigrini标准）
    if mad < 0.006:
        conformity = "close_conformity"
        conformity_cn = "高度一致"
    elif mad < 0.012:
        conformity = "acceptable_conformity"
        conformity_cn = "可接受一致"
    elif mad < 0.015:
        conformity = "marginal_conformity"
        conformity_cn = "边缘一致"
    else:
        conformity = "non_conformity"
        conformity_cn = "不一致（需关注）"

    return {
        "label": label,
        "sample_size": n,
        "chi2_statistic": round(chi2, 4),
        "p_value": round(p_value, 6),
        "is_abnormal": p_value < 0.05,
        "mad": round(mad, 6),
        "conformity": conformity,
        "conformity_cn": conformity_cn,
        "observed_counts": observed_counts,
        "expected_counts": [round(c, 1) for c in expected_counts],
    }


def run_benford_on_financials(summary: dict, ts_data: dict) -> list:
    """
    对财务数据的多个关键科目运行本福特定律检验

    检测科目:
    - 营业收入
    - 营业成本
    - 净利润
    - 总资产
    - 应收账款
    - 存货
    """
    results = []
    income_ts = ts_data.get("income", None)
    balance_ts = ts_data.get("balance", None)

    # 应收账款
    if balance_ts is not None and not balance_ts.empty and "accounts_receivable" in balance_ts.columns:
        ar_data = balance_ts["accounts_receivable"].dropna().tolist()
        if ar_data:
            results.append(benford_test(ar_data, "应收账款"))

    # 存货
    if balance_ts is not None and not balance_ts.empty and "inventory" in balance_ts.columns:
        inv_data = balance_ts["inventory"].dropna().tolist()
        if inv_data:
            results.append(benford_test(inv_data, "存货"))

    # 营业收入
    if income_ts is not None and not income_ts.empty and "operating_revenue" in income_ts.columns:
        rev_data = income_ts["operating_revenue"].dropna().tolist()
        if rev_data:
            results.append(benford_test(rev_data, "营业收入"))

    # 净利润
    if income_ts is not None and not income_ts.empty and "net_profit" in income_ts.columns:
        np_data = income_ts["net_profit"].dropna().tolist()
        if np_data:
            results.append(benford_test(np_data, "净利润"))

    # 总资产
    if balance_ts is not None and not balance_ts.empty:
        if "total_assets" in balance_ts.columns:
            ta_data = balance_ts["total_assets"].dropna().tolist()
            if ta_data:
                results.append(benford_test(ta_data, "总资产"))

    return results
