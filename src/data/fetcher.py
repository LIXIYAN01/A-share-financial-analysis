"""数据采集模块 — 通过AKShare获取A股上市公司财务数据

数据源优先级:
1. Sina (stock_financial_report_sina) — 覆盖全、结构完整、免费
2. THS (stock_financial_abstract_ths) — 同花顺指标数据
3. East Money — 作为补充
"""

import time
from typing import Optional

import akshare as ak
import pandas as pd

from config import AKSHARE_RETRY


def _retry(func, *args, **kwargs):
    """带重试的函数调用"""
    last_err = None
    for attempt in range(AKSHARE_RETRY):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_err = e
            if attempt < AKSHARE_RETRY - 1:
                time.sleep(1.5 ** attempt)
    raise last_err


def _ensure_code_prefix(stock_code: str) -> str:
    """确保股票代码有交易所前缀（Sina需要）"""
    code = str(stock_code).zfill(6)
    if code.startswith("6") or code.startswith("9"):
        return f"sh{code}"
    elif code.startswith("0") or code.startswith("3") or code.startswith("2"):
        return f"sz{code}"
    elif code.startswith("8") or code.startswith("4"):
        return f"bj{code}"
    return code


def search_stock(keyword: str) -> pd.DataFrame:
    """
    根据关键词搜索股票

    参数:
        keyword: 股票代码（如"600519"）或名称（如"贵州茅台"）

    返回:
        匹配的股票列表 DataFrame
    """
    # 名称搜索
    try:
        df = _retry(ak.stock_info_a_code_name)
        if df is not None and not df.empty:
            mask = df["code"].str.contains(keyword, na=False) | df["name"].str.contains(keyword, na=False)
            results = df[mask].copy()
            if not results.empty:
                return results.rename(columns={c: c for c in results.columns})
    except Exception:
        pass

    # 如果输入是纯数字代码，直接用THS获取名称
    if keyword.isdigit():
        try:
            info = _retry(ak.stock_financial_abstract_ths, symbol=keyword)
            # 仅用于确认代码存在，具体名称从Sina获取
            return pd.DataFrame([{"code": keyword.zfill(6), "name": ""}])
        except Exception:
            pass

    return pd.DataFrame()


def get_company_info(stock_code: str) -> dict:
    """获取上市公司基本信息"""
    info = {"code": stock_code}
    try:
        basic = _retry(ak.stock_individual_info_em, symbol=stock_code)
        if basic is not None and not basic.empty:
            for _, row in basic.iterrows():
                info[row["item"]] = row["value"]
    except Exception:
        pass
    return info


def get_balance_sheet(stock_code: str) -> pd.DataFrame:
    """获取资产负债表（Sina数据源）"""
    try:
        prefix = _ensure_code_prefix(stock_code)
        df = _retry(ak.stock_financial_report_sina, stock=prefix, symbol="资产负债表")
        if df is not None and not df.empty:
            df = df.rename(columns={df.columns[0]: "report_date"})
            df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
            df = df.sort_values("report_date", ascending=False).reset_index(drop=True)
            return df
    except Exception:
        pass

    # 降级：尝试THS
    try:
        df = _retry(ak.stock_financial_debt_ths, symbol=stock_code)
        return _clean_ths_df(df, stock_code)
    except Exception:
        pass

    return pd.DataFrame()


def get_income_statement(stock_code: str) -> pd.DataFrame:
    """获取利润表（Sina数据源）"""
    try:
        prefix = _ensure_code_prefix(stock_code)
        df = _retry(ak.stock_financial_report_sina, stock=prefix, symbol="利润表")
        if df is not None and not df.empty:
            df = df.rename(columns={df.columns[0]: "report_date"})
            df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
            df = df.sort_values("report_date", ascending=False).reset_index(drop=True)
            return df
    except Exception:
        pass

    # 降级：尝试THS
    try:
        df = _retry(ak.stock_financial_benefit_ths, symbol=stock_code)
        return _clean_ths_df(df, stock_code)
    except Exception:
        pass

    return pd.DataFrame()


def get_cashflow_statement(stock_code: str) -> pd.DataFrame:
    """获取现金流量表（Sina数据源）"""
    try:
        prefix = _ensure_code_prefix(stock_code)
        df = _retry(ak.stock_financial_report_sina, stock=prefix, symbol="现金流量表")
        if df is not None and not df.empty:
            df = df.rename(columns={df.columns[0]: "report_date"})
            df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
            df = df.sort_values("report_date", ascending=False).reset_index(drop=True)
            return df
    except Exception:
        pass

    # 降级：尝试THS
    try:
        df = _retry(ak.stock_financial_cash_ths, symbol=stock_code)
        return _clean_ths_df(df, stock_code)
    except Exception:
        pass

    return pd.DataFrame()


def get_financial_indicators(stock_code: str) -> pd.DataFrame:
    """获取财务指标摘要（THS数据源）"""
    try:
        df = _retry(ak.stock_financial_abstract_ths, symbol=stock_code)
        if df is not None and not df.empty and "报告期" in df.columns:
            df["report_date"] = pd.to_datetime(df["report期"], errors="coerce")
            df = df.sort_values("report_date", ascending=False).reset_index(drop=True)
            return df
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _clean_ths_df(df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
    """清洗THS数据源返回的DataFrame"""
    if df is None or df.empty:
        return pd.DataFrame()

    if "股票代码" in df.columns:
        df = df[df["股票代码"] == stock_code]

    for col in ["报告期", "报告日", "截止日期", "报表日期"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df.rename(columns={col: "report_date"}, inplace=True)
            break

    if "report_date" in df.columns:
        df = df.sort_values("report_date", ascending=False)

    return df.reset_index(drop=True)


def get_all_financial_data(stock_code: str) -> dict:
    """
    一次获取所有财务数据

    返回:
        {
            "basic_info": dict,
            "balance_sheet": DataFrame,
            "income_statement": DataFrame,
            "cashflow_statement": DataFrame,
            "financial_indicators": DataFrame,
        }
    """
    print(f"  [数据采集] 正在获取 {stock_code} 的财务数据...")

    balance = get_balance_sheet(stock_code)
    print(f"  [数据采集] 资产负债表已获取 ({len(balance)} 期, {len(balance.columns)} 科目)")

    income = get_income_statement(stock_code)
    print(f"  [数据采集] 利润表已获取 ({len(income)} 期, {len(income.columns)} 科目)")

    cashflow = get_cashflow_statement(stock_code)
    print(f"  [数据采集] 现金流量表已获取 ({len(cashflow)} 期, {len(cashflow.columns)} 科目)")

    indicators = get_financial_indicators(stock_code)
    print(f"  [数据采集] 财务指标已获取 ({len(indicators)} 期)")

    basic_info = get_company_info(stock_code)

    return {
        "basic_info": basic_info,
        "balance_sheet": balance,
        "income_statement": income,
        "cashflow_statement": cashflow,
        "financial_indicators": indicators,
    }
