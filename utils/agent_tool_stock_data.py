# type: ignore


"""
StockData功能测试脚本
文件路径: tools_agent/test_stock_data.py
功能: 快速测试StockData类的主要功能

### 财务报表模块
- `get_performance_report(date)` - 获取业绩报表
- `get_performance_express(date)` - 获取业绩快报
- `get_balance_sheet(date)` - 获取资产负债表
- `get_income_statement(date)` - 获取利润表
- `get_cash_flow(date)` - 获取现金流量表
- `get_financial_debt_ths(symbol, indicator)` - 获取财务报表（同花顺数据源）
- `get_financial_abstract_ths(symbol, indicator)` - 获取关键财务指标（同花顺数据源）
- `get_financial_analysis_indicator(symbol, start_year)` - 获取财务指标分析
"""

from tools_agent.stock_data import StockData
import pandas as pd
import os

def get_financial_data(stock_data, symbol, indicator, start_year="2020", folder_path=None):
    """
    fin_debt_df:
    资产负债表，字段包括：
    ---
    '报告期', '报表核心指标', '*所有者权益（或股东权益）合计', '*资产合计', '*负债合计', '*归属于母公司所有者权益合计',
    '报表全部指标', '资产', '现金及存放中央银行款项', '存放同业款项', '贵金属', '拆出资金', '交易性金融资产',
    '衍生金融资产', '买入返售金融资产', '应收利息', '发放贷款及垫款', '可供出售金融资产', '持有至到期投资',
    '应收款项类投资', '长期股权投资', '投资性房地产', '固定资产', '无形资产', '商誉', '递延所得税资产', '其他资产',
    '资产合计', '负债', '向中央银行借款', '同业及其他金融机构存放款项', '拆入资金',
    '以公允价值计量且其变动计入当期损益的金融负债', '衍生金融负债', '卖出回购金融资产款', '吸收存款', '应付职工薪酬',
    '应交税费', '应付利息', '预计负债', '应付债券', '递延所得税负债', '其他负债', '负债合计',
    '所有者权益（或股东权益', '实收资本（或股本）', '资本公积', '其他综合收益', '其他权益工具', '其中：优先股',
    '盈余公积', '一般风险准备', '未分配利润', '外币报表折算差额', '归属于母公司所有者权益合计', '少数股东权益',
    '所有者权益（或股东权益）合计', '负债和所有者权益总计'
    """
    fin_debt_df = stock_data.get_financial_debt_ths(symbol, indicator)
    """
    financial_abstract:
    股票**所有年份**的利润表摘要，字段包括：
    '报告期', '净利润', '净利润同比增长率', '扣非净利润', '扣非净利润同比增长率', '营业总收入', '营业总收入同比增长率',
    '基本每股收益', '每股净资产', '每股资本公积金', '每股未分配利润', '每股经营现金流', '销售净利率', '净资产收益率',
    '净资产收益率-摊薄', '营业周期', '应收账款周转天数', '流动比率', '速动比率', '保守速动比率', '产权比率',
    '资产负债率'
    """
    financial_abstract = stock_data.get_financial_abstract_ths(symbol, indicator)
    """
    financial_analysis_indicator:
    股票**指定年份**的财务指标分析，字段包括：
    ---
    '日期', '摊薄每股收益(元)', '加权每股收益(元)', '每股收益_调整后(元)', '扣除非经常性损益后的每股收益(元)',
    '每股净资产_调整前(元)', '每股净资产_调整后(元)', '每股经营性现金流(元)', '每股资本公积金(元)',
    '每股未分配利润(元)', '调整后的每股净资产(元)', '总资产利润率(%)', '主营业务利润率(%)', '总资产净利润率(%)',
    '成本费用利润率(%)', '营业利润率(%)', '主营业务成本率(%)', '销售净利率(%)', '股本报酬率(%)',
    '净资产报酬率(%)', '资产报酬率(%)', '销售毛利率(%)', '三项费用比重', '非主营比重', '主营利润比重',
    '股息发放率(%)', '投资收益率(%)', '主营业务利润(元)', '净资产收益率(%)', '加权净资产收益率(%)',
    '扣除非经常性损益后的净利润(元)', '主营业务收入增长率(%)', '净利润增长率(%)', '净资产增长率(%)',
    '总资产增长率(%)', '应收账款周转率(次)', '应收账款周转天数(天)', '存货周转天数(天)', '存货周转率(次)',
    '固定资产周转率(次)', '总资产周转率(次)', '总资产周转天数(天)', '流动资产周转率(次)', '流动资产周转天数(天)',
    '股东权益周转率(次)', '流动比率', '速动比率', '现金比率(%)', '利息支付倍数', '长期债务与营运资金比率(%)',
    '股东权益比率(%)', '长期负债比率(%)', '股东权益与固定资产比率(%)', '负债与所有者权益比率(%)',
    '长期资产与长期资金比率(%)', '资本化比率(%)', '固定资产净值率(%)', '资本固定化比率(%)', '产权比率(%)',
    '清算价值比率(%)', '固定资产比重(%)', '资产负债率(%)', '总资产(元)', '经营现金净流量对销售收入比率(%)',
    '资产的经营现金流量回报率(%)', '经营现金净流量与净利润的比率(%)', '经营现金净流量对负债比率(%)', '现金流量比率(%)',
    '短期股票投资(元)', '短期债券投资(元)', '短期其它经营性投资(元)', '长期股票投资(元)', '长期债券投资(元)',
    '长期其它经营性投资(元)', '1年以内应收帐款(元)', '1-2年以内应收帐款(元)', '2-3年以内应收帐款(元)',
    '3年以内应收帐款(元)', '1年以内预付货款(元)', '1-2年以内预付货款(元)', '2-3年以内预付货款(元)',
    '3年以内预付货款(元)', '1年以内其它应收款(元)', '1-2年以内其它应收款(元)', '2-3年以内其它应收款(元)',
    '3年以内其它应收款(元)'
    """
    financial_analysis_indicator = stock_data.get_financial_analysis_indicator(symbol, start_year)
    # 保存到本地
    
    os.makedirs(folder_path, exist_ok=True)
    fin_debt_df.to_csv(f"{folder_path}/fin_debt_df.csv", index=False)
    financial_abstract.to_csv(f"{folder_path}/financial_abstract.csv", index=False)
    financial_analysis_indicator.to_csv(f"{folder_path}/financial_analysis_indicator.csv", index=False)

    return fin_debt_df, financial_abstract, financial_analysis_indicator


def get_stock_symbol(a_stocks, stock_name):
    stock_symbol = a_stocks[a_stocks["name"].str.contains(stock_name)]
    return stock_symbol["code"].values[0]
    
# 获取所有股票的代码信息
def get_all_stock_symbol():
    stock_list_file_path = "files/a_stocks.csv"
    a_stocks = pd.read_csv(stock_list_file_path)
    a_stocks["code"] = a_stocks["code"].astype(str).str.zfill(6)
    return a_stocks

# 准备数据
def prepare_data(stock_name, indicator, start_year="2020", folder_path=None):
    stock_data = StockData()
    a_stocks = get_all_stock_symbol()
    stock_symbol = get_stock_symbol(a_stocks, stock_name)
    fin_debt_df, financial_abstract, financial_analysis_indicator = get_financial_data(stock_data, stock_symbol, indicator, start_year=start_year, folder_path=folder_path)
    return fin_debt_df, financial_abstract, financial_analysis_indicator

def preview_dataframe_as_blocks(df, num_rows=5, max_colwidth=60):
    preview_rows = []
    for idx, row in df.head(num_rows).iterrows():
        preview_rows.append(f"Row {idx + 1}:")
        for col in df.columns:
            val = str(row[col])
            if len(val) > max_colwidth:
                val = val[:max_colwidth] + '...'
            preview_rows.append(f"  {col}: {val}")
        preview_rows.append("")  # 空行分隔
    return "\n".join(preview_rows)


class get_stock_data:
    def execute(self, **kwargs):
        stock_name = kwargs.get("stock_name", "")
        indicator = kwargs.get("indicator", "")
        start_year = kwargs.get("start_year", "2020")
        folder_path = kwargs.get("folder_path", "")
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        
        fin_debt_df, financial_abstract, financial_analysis_indicator = prepare_data(
            stock_name, 
            indicator, 
            start_year=start_year, 
            folder_path=folder_path
        )
        preview_fin_debt_df =  preview_dataframe_as_blocks(fin_debt_df)
        preview_financial_abstract =  preview_dataframe_as_blocks(financial_abstract)
        preview_financial_analysis_indicator =  preview_dataframe_as_blocks(financial_analysis_indicator)
        
        total_preview = f"""
# 资产负债表
{preview_fin_debt_df}
# 利润表摘要
{preview_financial_abstract}
# 财务指标分析
{preview_financial_analysis_indicator}

相关数据已保存到本地：{folder_path}
路径：
- 资产负债表：{folder_path}/fin_debt_df.csv
- 利润表摘要：{folder_path}/financial_abstract.csv
- 财务指标分析：{folder_path}/financial_analysis_indicator.csv
""" 

        return total_preview


if __name__ == "__main__":
    stock_name = "歌尔股份"
    indicator = "按年度"
    userID = "fizz"

    fin_debt_df, financial_abstract, financial_analysis_indicator = prepare_data(
        stock_name, 
        indicator, 
        start_year="2020", 
        folder_path=f"files/{userID}/{stock_name}/data"
    )
    preview_fin_debt_df =  preview_dataframe_as_blocks(fin_debt_df)
    preview_financial_abstract =  preview_dataframe_as_blocks(financial_abstract)
    preview_financial_analysis_indicator =  preview_dataframe_as_blocks(financial_analysis_indicator)

    total_preview = f"""
    # 资产负债表
    {preview_fin_debt_df}
    # 利润表摘要
    {preview_financial_abstract}
    # 财务指标分析
    {preview_financial_analysis_indicator}
    """

    print(preview_fin_debt_df)
    print(preview_financial_abstract)
    print(preview_financial_analysis_indicator)
    print(total_preview)

