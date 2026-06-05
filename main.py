"""
A股上市公司智能财务分析系统

用法:
    python main.py <股票代码或名称>

示例:
    python main.py 600519
    python main.py 贵州茅台
"""

import os
import sys
import traceback
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.data.fetcher import search_stock, get_all_financial_data
from src.data.standardizer import extract_financial_summary
from src.analysis.ratios import calculate_all_ratios, dupont_decomposition
from src.analysis.benford import run_benford_on_financials
from src.analysis.anomaly import detect_accruals_quality, detect_breakpoints, analyze_trend
from src.analysis.altman import altman_z_score, audit_perspective_analysis
from src.report.generator import (
    generate_html_report,
    generate_excel_report,
    generate_charts,
    OUTPUT_DIR_ABS,
)

import pandas as pd


def run_analysis(stock_code: str, stock_name: str = None):
    """执行完整的财务分析流程"""
    print(f"\n{'='*60}")
    print(f"  A股上市公司智能财务分析系统")
    print(f"  分析对象: {stock_name or stock_code} ({stock_code})")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # ===== Step 1: 数据采集 =====
    print("[Step 1/5] 正在采集财务数据...")
    try:
        all_data = get_all_financial_data(stock_code)
    except Exception as e:
        print(f"\n  [错误] 数据采集失败: {e}")
        traceback.print_exc()
        return

    if not stock_name:
        basic_info = all_data.get("basic_info", {})
        stock_name = basic_info.get("股票简称", stock_code)
        if "error" in basic_info:
            # 尝试从搜索结果中获取名称
            pass

    print(f"\n  公司名称: {stock_name}")

    # ===== Step 2: 数据标准化 & 摘要提取 =====
    print(f"\n[Step 2/5] 正在标准化数据并提取摘要...")
    summary = extract_financial_summary(all_data)

    # 验证核心数据
    if summary.get("operating_revenue") is None and summary.get("total_assets") is None:
        print("\n  [错误] 无法提取有效的财务数据。请检查:")
        print("    1. 股票代码是否正确")
        print("    2. AKShare数据源是否可访问")
        print("    3. 该股票是否已发布财务报告")
        return

    print(f"  营业收入: {summary.get('operating_revenue', 'N/A')}")
    print(f"  净利润:   {summary.get('net_profit', 'N/A')}")
    print(f"  总资产:   {summary.get('total_assets', 'N/A')}")

    # ===== Step 3: 多维度分析 =====
    print(f"\n[Step 3/5] 正在执行多维度分析...")

    # 3a. 财务比率分析
    print("  [比率分析] 计算核心财务指标...")
    ratios = calculate_all_ratios(summary)
    print(f"    综合健康度评分: {ratios.get('health_score', 'N/A')} / 100")
    print(f"    ROE: {ratios.get('roe', 'N/A')}")
    print(f"    毛利率: {ratios.get('gross_margin', 'N/A')}")

    # 3b. 杜邦分析
    dupont = dupont_decomposition(summary)
    print(f"    杜邦分析: 净利率={dupont.get('net_profit_margin')}, "
          f"周转率={dupont.get('asset_turnover')}, "
          f"杠杆={dupont.get('equity_multiplier')}")

    # 3c. 本福特定律检验
    print("  [本福特检验] 检验财务数据数字分布...")
    ts_data = summary.get("_time_series", {})
    benford_results = run_benford_on_financials(summary, ts_data)
    ab_count = sum(1 for b in benford_results if b.get("is_abnormal"))
    print(f"    检验科目: {len(benford_results)} 个, 异常: {ab_count} 个")

    # 3d. 异常检测
    print("  [异常检测] 检测时间序列异常...")
    income_ts = ts_data.get("income")
    anomaly_results = {}
    if income_ts is not None and not income_ts.empty and "report_date" in income_ts.columns:
        def _get_ts(df, col_name):
            """安全获取时间序列"""
            if col_name not in df.columns:
                return None
            col = df[col_name]
            if isinstance(col, pd.DataFrame):
                col = col.iloc[:, 0]
            ts = col.dropna()
            ts = pd.to_numeric(ts, errors="coerce").dropna()
            return ts

        np_ts = _get_ts(income_ts, "net_profit")
        if np_ts is not None and len(np_ts) >= 4:
            ts_indexed = pd.Series(np_ts.values, index=pd.to_datetime(income_ts["report_date"].values[:len(np_ts)])).sort_index()
            breakpoints = detect_breakpoints(ts_indexed, method="zscore")
            trend = analyze_trend(ts_indexed)
            anomaly_results["net_profit_breakpoints"] = breakpoints
            anomaly_results["net_profit_trend"] = trend
            print(f"    净利润趋势: {trend.get('trend_cn', 'N/A')}, 异常点: {len(breakpoints)}")

        rev_ts = _get_ts(income_ts, "operating_revenue")
        if rev_ts is not None and len(rev_ts) >= 4:
            ts_indexed = pd.Series(rev_ts.values, index=pd.to_datetime(income_ts["report_date"].values[:len(rev_ts)])).sort_index()
            anomaly_results["revenue_trend"] = analyze_trend(ts_indexed)

    # 3e. 应计利润质量
    accruals = detect_accruals_quality(summary)
    print(f"    应计利润质量: {accruals.get('quality', 'N/A')}")

    # 3f. Altman Z-Score
    print("  [Altman Z-Score] 计算破产风险...")
    altman_result = altman_z_score(
        total_assets=summary.get("total_assets"),
        current_assets=summary.get("current_assets"),
        current_liabilities=summary.get("current_liabilities"),
        retained_earnings=summary.get("retained_earnings"),
        operating_profit=summary.get("operating_profit"),
        total_liabilities=summary.get("total_liabilities"),
        operating_revenue=summary.get("operating_revenue"),
    )
    if "error" not in altman_result:
        print(f"    Z-Score: {altman_result['z_score']} ({altman_result['risk_level']})")

    # 3g. 审计角度分析
    print("  [审计分析] 从审计视角审视财务数据...")
    audit_result = audit_perspective_analysis(summary, ratios)
    print(f"    高风险项: {audit_result.get('high_risks', 0)}, "
          f"总风险项: {audit_result.get('total_risks', 0)}")

    # ===== Step 4: 生成图表 =====
    print(f"\n[Step 4/5] 正在生成分析图表...")
    chart_paths = generate_charts(summary, ratios, stock_code, stock_name)
    print(f"  图表生成: {len(chart_paths)} 张")

    # ===== Step 5: 生成报告 =====
    print(f"\n[Step 5/5] 正在生成报告...")

    # 整理基础信息
    basic_info = all_data.get("basic_info", {})
    if isinstance(basic_info, pd.DataFrame):
        basic_info = {}

    # HTML报告
    html_path = generate_html_report(
        stock_code=stock_code,
        stock_name=stock_name,
        basic_info=basic_info,
        summary=summary,
        ratios=ratios,
        benford_results=benford_results,
        altman_result=altman_result,
        audit_result=audit_result,
        chart_paths=chart_paths,
        anomaly_results=anomaly_results,
    )
    if html_path:
        print(f"  HTML报告: {html_path}")

    # Excel报告
    excel_path = generate_excel_report(
        stock_code=stock_code,
        stock_name=stock_name,
        summary=summary,
        ratios=ratios,
        benford_results=benford_results,
        altman_result=altman_result,
        audit_result=audit_result,
    )
    if excel_path:
        print(f"  Excel报告: {excel_path}")

    # 打印摘要
    _print_console_summary(stock_code, stock_name, ratios, audit_result, altman_result, benford_results)

    print(f"\n{'='*60}")
    print(f"  分析完成！")
    print(f"  输出目录: {OUTPUT_DIR_ABS}")
    print(f"{'='*60}\n")

    return {
        "ratios": ratios,
        "audit_result": audit_result,
        "altman_result": altman_result,
        "benford_results": benford_results,
    }


def _print_console_summary(stock_code, stock_name, ratios, audit_result, altman_result, benford_results):
    """在控制台打印分析摘要"""
    print(f"\n{'─'*60}")
    print(f"  [{stock_name}({stock_code}) 分析摘要]")
    print(f"{'─'*60}")

    score = ratios.get("health_score", "N/A")
    print(f"  综合评分: {score}/100")

    print(f"\n  【核心指标】")
    print(f"  ROE: {_p(ratios.get('roe'))}    ROA: {_p(ratios.get('roa'))}")
    print(f"  毛利率: {_p(ratios.get('gross_margin'))}    净利率: {_p(ratios.get('net_margin'))}")
    print(f"  资产负债率: {_p(ratios.get('debt_ratio'))}    流动比率: {_f(ratios.get('current_ratio'))}")
    print(f"  营收增速: {_p(ratios.get('revenue_growth_yoy'))}    利润增速: {_p(ratios.get('profit_growth_yoy'))}")
    print(f"  经营现金流/净利润: {_f(ratios.get('ocf_to_profit'))}")

    if altman_result and "error" not in altman_result:
        print(f"\n  【破产风险】Z-Score: {altman_result['z_score']} ({altman_result['risk_level']})")

    print(f"\n  【审计风险】高风险项: {audit_result.get('high_risks', 0)}, 总关注项: {audit_result.get('total_risks', 0)}")
    for f in audit_result.get("findings", []):
        if f["risk_level"] in ("high", "medium"):
            print(f"    [!] [{f['area']}] {f['description']}")

    ab_items = [b for b in benford_results if b.get("is_abnormal")]
    if ab_items:
        print(f"\n  【本福特异常】")
        for b in ab_items:
            print(f"    [!] {b.get('label', '')}: p={b.get('p_value', '')}, MAD={b.get('mad', '')}")


def _p(val) -> str:
    if val is None:
        return "N/A"
    return f"{val*100:.2f}%"


def _f(val) -> str:
    if val is None:
        return "N/A"
    return f"{val:.2f}"


def main():
    if len(sys.argv) < 2:
        print("用法: python main.py <股票代码或名称>")
        print("示例: python main.py 600519")
        print("      python main.py 贵州茅台")
        sys.exit(1)

    keyword = sys.argv[1].strip()

    # 首先搜索匹配的股票
    print(f"正在搜索: {keyword}...")
    try:
        results = search_stock(keyword)
    except Exception as e:
        print(f"搜索失败: {e}")
        print("尝试直接使用输入作为股票代码...")
        results = None

    if results is not None and not results.empty:
        if len(results) == 1:
            code = str(results.iloc[0]["code"]).zfill(6)
            name = str(results.iloc[0]["name"])
            print(f"找到: {name} ({code})")
            run_analysis(code, name)
        else:
            # 多个匹配结果，让用户选择
            print(f"找到 {len(results)} 个匹配结果:")
            for i, (_, row) in enumerate(results.iterrows()):
                print(f"  [{i+1}] {row['code']} {row['name']}")
            print(f"  [0] 取消")

            try:
                choice = input("请选择 (输入序号): ").strip()
                idx = int(choice)
                if idx == 0:
                    print("已取消")
                    return
                if 1 <= idx <= len(results):
                    row = results.iloc[idx - 1]
                    code = str(row["code"]).zfill(6)
                    name = str(row["name"])
                    run_analysis(code, name)
                else:
                    print("无效选择")
            except (ValueError, IndexError):
                print("无效输入")
    else:
        # 尝试直接作为代码处理
        code = keyword.zfill(6)
        print(f"直接使用代码: {code}")
        run_analysis(code)


if __name__ == "__main__":
    main()
