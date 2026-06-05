"""数据校验模块"""

from typing import Optional


def validate_financial_data(data: dict) -> list:
    """
    校验采集到的财务数据的完整性

    返回: 警告信息列表
    """
    warnings = []

    # 必填核心字段
    required_fields = [
        ("operating_revenue", "营业收入"),
        ("net_profit", "净利润"),
        ("total_assets", "总资产"),
        ("total_equity", "所有者权益"),
    ]

    for field, name in required_fields:
        if data.get(field) is None:
            warnings.append(f"缺少核心字段: {name} ({field})")

    # 一致性校验
    revenue = data.get("operating_revenue")
    cost = data.get("operating_cost")
    if revenue and cost and cost > revenue:
        warnings.append(f"营业成本 ({cost}) 大于营业收入 ({revenue}), 数据可能异常")

    total_assets = data.get("total_assets")
    total_liabilities = data.get("total_liabilities")
    total_equity = data.get("total_equity")
    if total_assets and total_liabilities and total_equity:
        diff = abs(total_assets - (total_liabilities + total_equity))
        if diff / total_assets > 0.01:
            warnings.append(f"平衡校验不通过: 总资产({total_assets}) ≠ 总负债({total_liabilities}) + 所有者权益({total_equity})")

    # 异常大值检测
    if revenue and revenue > 1e13:  # 10万亿
        warnings.append(f"营业收入 ({revenue}) 异常偏大")

    if total_assets and total_assets > 1e14:  # 100万亿
        warnings.append(f"总资产 ({total_assets}) 异常偏大")

    return warnings


def quick_sanity_check(data: dict) -> bool:
    """快速合理性检查，返回True表示基本合理"""
    warnings = validate_financial_data(data)
    critical = [w for w in warnings if "缺少核心字段" in w]
    return len(critical) == 0
