"""Web API 服务 — 为前端提供财务分析接口"""

import sys
import os
import json
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
import akshare as ak
import pandas as pd
import numpy as np

from src.data.fetcher import search_stock, get_all_financial_data
from src.data.standardizer import extract_financial_summary
from src.analysis.ratios import calculate_all_ratios, dupont_decomposition
from src.analysis.benford import run_benford_on_financials
from src.analysis.anomaly import detect_accruals_quality, analyze_trend, detect_breakpoints
from src.analysis.altman import altman_z_score, audit_perspective_analysis
from src.report.generator import generate_charts, OUTPUT_DIR_ABS
from src.utils.validators import validate_financial_data

app = FastAPI(title="A股智能财务分析系统")

# Serve output directory for chart images
app.mount("/output", StaticFiles(directory=OUTPUT_DIR_ABS), name="output")


class AnalyzeRequest(BaseModel):
    keyword: str


class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return round(float(obj), 6)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        if isinstance(obj, pd.Timestamp):
            return str(obj)
        return super().default(obj)


def _safe_val(v):
    """确保值可以被 JSON 序列化"""
    if v is None:
        return None
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (np.floating,)):
        if np.isnan(v) or np.isinf(v):
            return None
        return round(float(v), 6)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, float):
        if np.isnan(v) or np.isinf(v):
            return None
        return round(v, 6)
    if isinstance(v, (np.ndarray,)):
        return v.tolist()
    return v


def _safe_dict(d):
    """递归清理字典中的值"""
    if isinstance(d, dict):
        return {k: _safe_dict(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [_safe_dict(i) for i in d]
    else:
        return _safe_val(d)


@app.get("/", response_class=HTMLResponse)
async def index():
    """返回前端页面"""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>Frontend not found</h1>")


def _extract_code(keyword: str) -> str:
    """从输入中提取股票代码。支持 '600839', '600839 四川长虹', '四川长虹' 等格式"""
    kw = keyword.strip()
    # 取第一个空格或中文前的数字部分
    code_part = kw.split()[0] if kw.split() else kw
    # 如果第一部分是纯数字且长度为6，直接返回
    if code_part.isdigit() and len(code_part) <= 6:
        return code_part.zfill(6)
    # 否则尝试从开头提取数字
    digits = ""
    for ch in kw:
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    if digits and len(digits) <= 6:
        return digits.zfill(6)
    return ""


def _extract_name(keyword: str) -> str:
    """从输入中提取公司名称部分"""
    kw = keyword.strip()
    code = _extract_code(kw)
    if code and len(kw) > len(code):
        return kw[len(code):].strip()
    return kw


@app.post("/api/search")
async def search(req: AnalyzeRequest):
    """搜索股票"""
    keyword = req.keyword.strip()
    code = _extract_code(keyword)

    # 如果能提取出纯数字代码，直接返回
    if code:
        return {"stocks": [{"code": code, "name": _extract_name(keyword)}]}

    try:
        results = search_stock(keyword)
        if results is not None and not results.empty:
            stocks = []
            for _, row in results.iterrows():
                stocks.append({
                    "code": str(row.get("code", "")).zfill(6),
                    "name": str(row.get("name", "")),
                })
            return {"stocks": stocks[:20]}
        return {"stocks": []}
    except Exception as e:
        return {"stocks": []}


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    """执行完整财务分析"""
    keyword = req.keyword.strip()

    # Step 1: Quick stock code resolution — 优先从输入中提取数字代码
    code = _extract_code(keyword)
    if code:
        stock_code = code
        stock_name = ""
    else:
        try:
            results = search_stock(keyword)
            if results is not None and not results.empty:
                stock_code = str(results.iloc[0]["code"]).zfill(6)
                stock_name = str(results.iloc[0]["name"])
            else:
                raise HTTPException(status_code=400, detail=f"未找到匹配的股票: {keyword}")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail=f"搜索失败: {keyword}")

    # Step 2: Fetch data + resolve name in parallel
    import concurrent.futures
    all_data = None
    stock_name = ""

    def _fetch_data():
        return get_all_financial_data(stock_code)

    def _resolve_name():
        # Try multiple methods to get company name
        try:
            df = ak.stock_info_a_code_name()
            row = df[df["code"] == stock_code]
            if not row.empty:
                return str(row.iloc[0]["name"])
        except Exception:
            pass
        return ""

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_data = executor.submit(_fetch_data)
        future_name = executor.submit(_resolve_name)
        try:
            all_data = future_data.result(timeout=90)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"数据采集失败: {str(e)}")
        try:
            stock_name = future_name.result(timeout=30) or ""
        except Exception:
            stock_name = ""

    if not stock_name:
        basic_info = all_data.get("basic_info", {})
        stock_name = basic_info.get("股票简称", stock_code)
    if not stock_name or stock_name == stock_code:
        stock_name = stock_code

    # Step 3: Standardize
    summary = extract_financial_summary(all_data)

    if summary.get("operating_revenue") is None and summary.get("total_assets") is None:
        raise HTTPException(status_code=400, detail="无法提取有效的财务数据")

    # Step 4: Analysis
    ratios = calculate_all_ratios(summary)
    dupont = dupont_decomposition(summary)

    ts_data = summary.get("_time_series", {})
    benford_results = run_benford_on_financials(summary, ts_data)

    # Anomaly detection
    income_ts = ts_data.get("income")
    anomaly_results = {}
    if income_ts is not None and not income_ts.empty and "report_date" in income_ts.columns:
        def _get_ts(df, col_name):
            if col_name not in df.columns:
                return None
            col = df[col_name]
            if isinstance(col, pd.DataFrame):
                col = col.iloc[:, 0]
            ts = pd.to_numeric(col, errors="coerce").dropna()
            return ts

        np_ts = _get_ts(income_ts, "net_profit")
        if np_ts is not None and len(np_ts) >= 4:
            ts_indexed = pd.Series(np_ts.values, index=pd.to_datetime(income_ts["report_date"].values[:len(np_ts)])).sort_index()
            anomaly_results["net_profit_trend"] = analyze_trend(ts_indexed)
            anomaly_results["net_profit_breakpoints"] = detect_breakpoints(ts_indexed, method="zscore")

        rev_ts = _get_ts(income_ts, "operating_revenue")
        if rev_ts is not None and len(rev_ts) >= 4:
            ts_indexed = pd.Series(rev_ts.values, index=pd.to_datetime(income_ts["report_date"].values[:len(rev_ts)])).sort_index()
            anomaly_results["revenue_trend"] = analyze_trend(ts_indexed)

    accruals = detect_accruals_quality(summary)

    altman_result = altman_z_score(
        total_assets=summary.get("total_assets"),
        current_assets=summary.get("current_assets"),
        current_liabilities=summary.get("current_liabilities"),
        retained_earnings=summary.get("retained_earnings"),
        operating_profit=summary.get("operating_profit"),
        total_liabilities=summary.get("total_liabilities"),
        operating_revenue=summary.get("operating_revenue"),
    )

    audit_result = audit_perspective_analysis(summary, ratios)

    # Step 5: Generate charts
    try:
        chart_paths = generate_charts(summary, ratios, stock_code, stock_name)
        charts = []
        for cp in chart_paths:
            fname = os.path.basename(cp)
            charts.append(f"/output/{fname}")
    except Exception:
        charts = []

    # Step 6: Build response
    response = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "report_date": str(income_ts["report_date"].iloc[0]) if income_ts is not None and not income_ts.empty and "report_date" in income_ts.columns else "",
        "summary": {
            "operating_revenue": _safe_val(summary.get("operating_revenue")),
            "operating_cost": _safe_val(summary.get("operating_cost")),
            "net_profit": _safe_val(summary.get("net_profit")),
            "net_profit_parent": _safe_val(summary.get("net_profit_parent")),
            "total_assets": _safe_val(summary.get("total_assets")),
            "total_liabilities": _safe_val(summary.get("total_liabilities")),
            "total_equity": _safe_val(summary.get("total_equity")),
            "operating_cashflow": _safe_val(summary.get("operating_cashflow")),
            "investing_cashflow": _safe_val(summary.get("investing_cashflow")),
            "financing_cashflow": _safe_val(summary.get("financing_cashflow")),
            "accounts_receivable": _safe_val(summary.get("accounts_receivable")),
            "inventory": _safe_val(summary.get("inventory")),
            "goodwill": _safe_val(summary.get("goodwill")),
            "retained_earnings": _safe_val(summary.get("retained_earnings")),
            "rd_expenses": _safe_val(summary.get("rd_expenses")),
            "selling_expenses": _safe_val(summary.get("selling_expenses")),
            "admin_expenses": _safe_val(summary.get("admin_expenses")),
            "finance_expenses": _safe_val(summary.get("finance_expenses")),
            "investment_income": _safe_val(summary.get("investment_income")),
            "fair_value_change": _safe_val(summary.get("fair_value_change")),
            "other_income": _safe_val(summary.get("other_income")),
            "asset_impairment_loss": _safe_val(summary.get("asset_impairment_loss")),
            "credit_impairment_loss": _safe_val(summary.get("credit_impairment_loss")),
        },
        "ratios": _safe_dict(ratios),
        "dupont": _safe_dict(dupont),
        "benford": _safe_dict(benford_results),
        "anomaly": _safe_dict(anomaly_results),
        "accruals": _safe_dict(accruals),
        "altman": _safe_dict(altman_result),
        "audit": _safe_dict(audit_result),
        "charts": charts,
        "warnings": validate_financial_data(summary),
    }

    # Use custom encoder to handle numpy types
    json_str = json.dumps(response, ensure_ascii=False, cls=NpEncoder)
    return JSONResponse(content=json.loads(json_str))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
