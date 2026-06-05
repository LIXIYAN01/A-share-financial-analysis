"""异常检测模块 — 时间序列突变检测、趋势分析"""

from typing import Optional

import numpy as np
import pandas as pd


def detect_breakpoints(
    series: pd.Series,
    method: str = "zscore",
    threshold: float = 3.0,
) -> list:
    """
    检测财务指标时间序列中的异常突变点

    参数:
        series: 时间序列（index为日期）
        method: "zscore" 基于滚动窗口Z-Score; "pct_change" 基于环比变化
        threshold: 异常阈值

    返回:
        [{"date": ..., "value": ..., "z_score": ..., "type": "spike"/"drop"}, ...]
    """
    anomalies = []
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    s = series.dropna().sort_index()
    s = pd.to_numeric(s, errors="coerce").dropna()

    if len(s) < 4:
        return anomalies

    if method == "zscore":
        rolling_mean = s.rolling(window=5, min_periods=3).mean()
        rolling_std = s.rolling(window=5, min_periods=3).std()
        z_scores = ((s - rolling_mean) / rolling_std.replace(0, np.nan)).dropna()

        for idx, z in z_scores.items():
            if abs(z) > threshold:
                anomalies.append({
                    "date": str(idx),
                    "value": round(float(s[idx]), 2),
                    "z_score": round(float(z), 2),
                    "type": "spike" if z > 0 else "drop",
                })

    elif method == "pct_change":
        pct = s.pct_change().dropna()
        for idx, val in pct.items():
            if abs(val) > threshold:
                anomalies.append({
                    "date": str(idx),
                    "value": round(float(s[idx]), 2),
                    "change_pct": round(float(val) * 100, 2),
                    "type": "surge" if val > 0 else "plunge",
                })

    return anomalies


def analyze_trend(series: pd.Series) -> dict:
    """
    分析时间序列的趋势

    返回:
        {
            "trend": "upward"/"downward"/"stable",
            "slope": 线性回归斜率,
            "volatility": 变异系数,
            "mean": 均值,
            "latest": 最新值,
            "min": 最小值,
            "max": 最大值,
            "count": 数据点数量,
        }
    """
    # Ensure it's a Series with numeric values
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    s = series.dropna().sort_index()
    s = pd.to_numeric(s, errors="coerce").dropna()
    if len(s) < 2:
        return {"error": "数据点不足"}

    x = np.arange(len(s))
    y = s.values.astype(float)

    # 线性回归
    slope, intercept = np.polyfit(x, y, 1)

    if slope > 0:
        trend = "upward"
        trend_cn = "上升趋势"
    elif slope < 0:
        trend = "downward"
        trend_cn = "下降趋势"
    else:
        trend = "stable"
        trend_cn = "平稳"

    # 变异系数
    mean_val = float(np.mean(y))
    std_val = float(np.std(y))
    cv = std_val / mean_val if mean_val != 0 else 0

    return {
        "trend": trend,
        "trend_cn": trend_cn,
        "slope": round(float(slope), 4),
        "volatility": round(float(cv), 4),
        "mean": round(mean_val, 2),
        "latest": round(float(s.iloc[-1]), 2),
        "min": round(float(s.min()), 2),
        "max": round(float(s.max()), 2),
        "count": len(s),
    }


def detect_accruals_quality(summary: dict) -> dict:
    """
    检测应计利润质量

    应计利润 = 净利润 - 经营活动现金流
    如果应计利润持续显著为正，说明利润的现金回收能力差
    """
    net_profit = summary.get("net_profit")
    ocf = summary.get("operating_cashflow")

    if net_profit is None or ocf is None:
        return {"error": "数据不足，无法计算应计利润质量"}

    total_accruals = net_profit - ocf
    accruals_ratio = total_accruals / abs(net_profit) if net_profit != 0 else 0

    if accruals_ratio < 0.3:
        quality = "良好（现金流充分覆盖利润）"
        level = "good"
    elif accruals_ratio < 0.6:
        quality = "一般（部分利润缺乏现金流支撑）"
        level = "moderate"
    elif accruals_ratio < 1.0:
        quality = "偏差（较大比例利润缺乏现金流支撑）"
        level = "poor"
    else:
        quality = "严重异常（应计利润超过净利润，需重点关注）"
        level = "critical"

    return {
        "net_profit": net_profit,
        "operating_cashflow": ocf,
        "total_accruals": round(total_accruals, 2),
        "accruals_ratio": round(accruals_ratio, 4),
        "quality": quality,
        "level": level,
    }


def revenue_quality_check(summary: dict) -> dict:
    """
    收入质量检查

    检查项:
    1. 经营现金流 / 营业收入 < 0.8 → 收入回款差
    2. 应收账款 / 营业收入 > 0.5 → 赊销比例高
    3. (营业收入增幅 - 应收账款增幅) < -0.1 → 收入增长靠赊销
    """
    issues = []
    warnings = []

    ocf_to_rev = summary.get("ocf_to_revenue")
    if ocf_to_rev is not None and ocf_to_rev < 0.8:
        issues.append(f"经营现金流入/营业收入={ocf_to_rev:.1%}，低于80%，收入回款质量需关注")

    ar_to_rev = summary.get("ar_to_revenue")
    if ar_to_rev is not None and ar_to_rev > 0.5:
        warnings.append(f"应收账款/营业收入={ar_to_rev:.1%}，赊销比例偏高")

    return {"issues": issues, "warnings": warnings, "has_issues": len(issues) > 0}
