"""
StockData - 统一的股票数据获取类
文件路径: tools_agent/stock_data.py
功能: 整合所有akshare金融数据API，提供统一的数据获取接口
作者: AI Assistant
创建时间: 2025-01-28

## 功能概述
StockData类整合了akshare的各种金融数据API，按功能模块分组，提供统一的数据获取接口。
支持获取股票基本信息、历史行情、财务数据、机构持仓、新闻资讯等多维度数据。

## 函数功能列表

### 1. 市场总览模块
- `get_sse_summary()` - 获取上海证券交易所总览信息（总市值、上市公司数量等）
- `get_szse_summary()` - 获取深圳证券交易所总览信息（总市值、上市公司数量等）
- `get_szse_sector_summary(symbol, date)` - 获取深交所行业成交总览

### 2. 个股信息模块
- `get_stock_info_em(symbol)` - 获取个股基本信息（东方财富数据源）
- `get_stock_info_xq(symbol)` - 获取个股基本信息（雪球数据源）
- `get_stock_profile_cninfo(symbol)` - 获取公司概况信息（巨潮资讯数据源）

### 3. 股价行情模块
- `get_stock_hist(symbol, period, start_date, end_date, adjust)` - 获取股票历史行情数据（支持复权）

### 4. 公司业务模块
- `get_main_business_ths(symbol)` - 获取主营业务介绍（同花顺数据源）
- `get_main_composition_em(symbol)` - 获取主营构成分析（东方财富数据源）

### 5. 机构调研模块
- `get_institutional_research(date)` - 获取机构调研统计数据
- `get_institutional_holding(symbol)` - 获取机构持股情况

### 6. 质押信息模块
- `get_pledge_ratio(date)` - 获取上市公司股票质押比例

### 7. 新闻资讯模块
- `get_stock_news(symbol)` - 获取个股相关新闻
- `get_financial_news()` - 获取财经内容精选
- `get_morning_news()` - 获取财经早餐资讯

### 8. 财务报表模块
- `get_performance_report(date)` - 获取业绩报表
- `get_performance_express(date)` - 获取业绩快报
- `get_balance_sheet(date)` - 获取资产负债表
- `get_income_statement(date)` - 获取利润表
- `get_cash_flow(date)` - 获取现金流量表
- `get_financial_debt_ths(symbol, indicator)` - 获取财务报表（同花顺数据源）
- `get_financial_abstract_ths(symbol, indicator)` - 获取关键财务指标（同花顺数据源）
- `get_financial_analysis_indicator(symbol, start_year)` - 获取财务指标分析

### 9. 股东信息模块
- `get_top_10_free_holders(symbol, date)` - 获取十大流通股东信息
- `get_top_10_holders(symbol, date)` - 获取十大股东信息
- `get_shareholder_count(symbol)` - 获取股东户数变化

### 10. 行业板块模块
- `get_sector_spot(indicator)` - 获取板块行情数据

### 11. 股票列表模块
- `get_a_stock_list()` - 获取A股股票列表
- `get_sh_stock_list(symbol)` - 获取上证股票列表
- `get_sz_stock_list(symbol)` - 获取深证股票列表

## 使用说明
1. 所有函数都包含完整的错误处理和日志记录
2. 函数参数说明详见各函数的docstring
3. 股票代码格式要求根据不同数据源有所不同，请参考具体函数说明
4. 日期格式统一为YYYYMMDD格式
"""

import akshare as ak
import pandas as pd
from typing import Optional, Union
import logging
from datetime import datetime, date

class StockData:
    """
    统一的股票数据获取类
    整合akshare的各种金融数据API，按功能模块分组
    """
    
    def __init__(self):
        """初始化StockData类"""
        self.logger = self._setup_logger()
        self.logger.info("StockData类初始化完成")
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('StockData')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _log_operation(self, operation: str, **kwargs):
        """记录操作日志"""
        params = ', '.join([f"{k}={v}" for k, v in kwargs.items()])
        self.logger.info(f"执行操作: {operation}, 参数: {params}")
    
    # ==================== 市场总览模块 ====================
    
    def get_sse_summary(self) -> pd.DataFrame:
        """
        获取上海证券交易所总览信息
        返回: 总市值、上市公司数量、流通市值等信息
        """
        self._log_operation("获取上交所总览")
        try:
            return ak.stock_sse_summary()
        except Exception as e:
            self.logger.error(f"获取上交所总览失败: {e}")
            raise
    
    def get_szse_summary(self) -> pd.DataFrame:
        """
        获取深圳证券交易所总览信息
        返回: 总市值、上市公司数量、流通市值等信息
        """
        self._log_operation("获取深交所总览")
        try:
            return ak.stock_szse_summary()
        except Exception as e:
            self.logger.error(f"获取深交所总览失败: {e}")
            raise
    
    def get_szse_sector_summary(self, symbol: str = "当年", date: str = "202506") -> pd.DataFrame:
        """
        获取深交所行业成交总览
        参数:
            symbol: 统计周期，默认"当年"
            date: 日期，格式YYYYMM，默认当前年月
        """
        self._log_operation("获取深交所行业成交总览", symbol=symbol, date=date)
        try:
            return ak.stock_szse_sector_summary(symbol=symbol, date=date)
        except Exception as e:
            self.logger.error(f"获取深交所行业成交总览失败: {e}")
            raise
    
    # ==================== 个股信息模块 ====================
    
    def get_stock_info_em(self, symbol: str) -> pd.DataFrame:
        """
        获取个股基本信息-东方财富
        参数:
            symbol: 股票代码，如"000001"
        """
        self._log_operation("获取个股信息(东财)", symbol=symbol)
        try:
            return ak.stock_individual_info_em(symbol=symbol)
        except Exception as e:
            self.logger.error(f"获取个股信息(东财)失败: {e}")
            raise
    
    def get_stock_info_xq(self, symbol: str) -> pd.DataFrame:
        """
        获取个股基本信息-雪球
        参数:
            symbol: 股票代码，如"SH601127"
        """
        self._log_operation("获取个股信息(雪球)", symbol=symbol)
        try:
            return ak.stock_individual_basic_info_xq(symbol=symbol)
        except Exception as e:
            self.logger.error(f"获取个股信息(雪球)失败: {e}")
            raise
    
    def get_stock_profile_cninfo(self, symbol: str) -> pd.DataFrame:
        """
        获取公司概况-巨潮资讯
        参数:
            symbol: 股票代码，如"600030"
        """
        self._log_operation("获取公司概况", symbol=symbol)
        try:
            return ak.stock_profile_cninfo(symbol=symbol)
        except Exception as e:
            self.logger.error(f"获取公司概况失败: {e}")
            raise
    
    # ==================== 股价行情模块 ====================
    
    def get_stock_hist(self, symbol: str, period: str = "daily", 
                      start_date: str = "20200101", end_date: str = "20250628", 
                      adjust: str = "qfq") -> pd.DataFrame:
        """
        获取股票历史行情数据
        参数:
            symbol: 股票代码，如"000001"
            period: 周期，默认"daily"
            start_date: 开始日期，格式YYYYMMDD
            end_date: 结束日期，格式YYYYMMDD
            adjust: 复权类型，默认"qfq"前复权
        """
        self._log_operation("获取股票历史行情", symbol=symbol, period=period, 
                          start_date=start_date, end_date=end_date, adjust=adjust)
        try:
            return ak.stock_zh_a_hist(
                symbol=symbol, period=period, 
                start_date=start_date, end_date=end_date, 
                adjust=adjust
            )
        except Exception as e:
            self.logger.error(f"获取股票历史行情失败: {e}")
            raise
    
    # ==================== 公司业务模块 ====================
    
    def get_main_business_ths(self, symbol: str) -> pd.DataFrame:
        """
        获取主营介绍-同花顺
        参数:
            symbol: 股票代码，如"000066"
        """
        self._log_operation("获取主营介绍", symbol=symbol)
        try:
            return ak.stock_zyjs_ths(symbol=symbol)
        except Exception as e:
            self.logger.error(f"获取主营介绍失败: {e}")
            raise
    
    def get_main_composition_em(self, symbol: str) -> pd.DataFrame:
        """
        获取主营构成-东方财富
        参数:
            symbol: 股票代码，如"SH688041"
        """
        self._log_operation("获取主营构成", symbol=symbol)
        try:
            return ak.stock_zygc_em(symbol=symbol)
        except Exception as e:
            self.logger.error(f"获取主营构成失败: {e}")
            raise
    
    # ==================== 机构调研模块 ====================
    
    def get_institutional_research(self, date: str = "20250628") -> pd.DataFrame:
        """
        获取机构调研统计
        参数:
            date: 日期，格式YYYYMMDD，默认当前日期
        """
        self._log_operation("获取机构调研统计", date=date)
        try:
            return ak.stock_jgdy_tj_em(date=date)
        except Exception as e:
            self.logger.error(f"获取机构调研统计失败: {e}")
            raise
    
    def get_institutional_holding(self, symbol: str) -> pd.DataFrame:
        """
        获取机构持股情况
        参数:
            symbol: 日期，格式YYYYMM，如"202501"
        """
        self._log_operation("获取机构持股", symbol=symbol)
        try:
            return ak.stock_institute_hold(symbol=symbol)
        except Exception as e:
            self.logger.error(f"获取机构持股失败: {e}")
            raise
    
    # ==================== 质押信息模块 ====================
    
    def get_pledge_ratio(self, date: str = "20250628") -> pd.DataFrame:
        """
        获取上市公司质押比例
        参数:
            date: 日期，格式YYYYMMDD，默认当前日期
        """
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
            
        self._log_operation("获取质押比例", date=date)
        try:
            return ak.stock_gpzy_pledge_ratio_em(date=date)
        except Exception as e:
            self.logger.error(f"获取质押比例失败: {e}")
            raise
    
    # ==================== 新闻资讯模块 ====================
    
    def get_stock_news(self, symbol: str) -> pd.DataFrame:
        """
        获取个股新闻
        参数:
            symbol: 股票代码，如"603777"
        """
        self._log_operation("获取个股新闻", symbol=symbol)
        try:
            return ak.stock_news_em(symbol=symbol)
        except Exception as e:
            self.logger.error(f"获取个股新闻失败: {e}")
            raise
    
    def get_financial_news(self) -> pd.DataFrame:
        """
        获取财经内容精选
        """
        self._log_operation("获取财经新闻")
        try:
            return ak.stock_news_main_cx()
        except Exception as e:
            self.logger.error(f"获取财经新闻失败: {e}")
            raise
    
    def get_morning_news(self) -> pd.DataFrame:
        """
        获取财经早餐-东方财富
        """
        self._log_operation("获取财经早餐")
        try:
            return ak.stock_info_cjzc_em()
        except Exception as e:
            self.logger.error(f"获取财经早餐失败: {e}")
            raise
    
    # ==================== 财务报表模块 ====================
    
    def get_performance_report(self, date: str) -> pd.DataFrame:
        """
        获取业绩报表
        参数:
            date: 报告期，格式YYYYMMDD，如"20240331"
        """
        self._log_operation("获取业绩报表", date=date)
        try:
            return ak.stock_yjbb_em(date=date)
        except Exception as e:
            self.logger.error(f"获取业绩报表失败: {e}")
            raise
    
    def get_performance_express(self, date: str) -> pd.DataFrame:
        """
        获取业绩快报
        参数:
            date: 报告期，格式YYYYMMDD，如"20240331"
        """
        self._log_operation("获取业绩快报", date=date)
        try:
            return ak.stock_yjkb_em(date=date)
        except Exception as e:
            self.logger.error(f"获取业绩快报失败: {e}")
            raise
    
    def get_balance_sheet(self, date: str) -> pd.DataFrame:
        """
        获取资产负债表
        参数:
            date: 报告期，格式YYYYMMDD，如"20240331"
        """
        self._log_operation("获取资产负债表", date=date)
        try:
            return ak.stock_zcfz_em(date=date)
        except Exception as e:
            self.logger.error(f"获取资产负债表失败: {e}")
            raise
    
    def get_income_statement(self, date: str) -> pd.DataFrame:
        """
        获取利润表
        参数:
            date: 报告期，格式YYYYMMDD，如"20240331"
        """
        self._log_operation("获取利润表", date=date)
        try:
            return ak.stock_lrb_em(date=date)
        except Exception as e:
            self.logger.error(f"获取利润表失败: {e}")
            raise
    
    def get_cash_flow(self, date: str) -> pd.DataFrame:
        """
        获取现金流量表
        参数:
            date: 报告期，格式YYYYMMDD，如"20241231"
        """
        self._log_operation("获取现金流量表", date=date)
        try:
            return ak.stock_xjll_em(date=date)
        except Exception as e:
            self.logger.error(f"获取现金流量表失败: {e}")
            raise
    
    def get_financial_debt_ths(self, symbol: str, indicator: str = "按年度") -> pd.DataFrame:
        """
        获取财务报表-同花顺
        参数:
            symbol: 股票代码，如"600519"
            indicator: 指标类型，默认"按年度"
        """
        self._log_operation("获取财务报表(同花顺)", symbol=symbol, indicator=indicator)
        try:
            return ak.stock_financial_debt_ths(symbol=symbol, indicator=indicator)
        except Exception as e:
            self.logger.error(f"获取财务报表(同花顺)失败: {e}")
            raise
    
    def get_financial_abstract_ths(self, symbol: str, indicator: str = "按报告期") -> pd.DataFrame:
        """
        获取关键指标-同花顺
        参数:
            symbol: 股票代码，如"000063"
            indicator: 指标类型，默认"按报告期"
        """
        self._log_operation("获取关键指标(同花顺)", symbol=symbol, indicator=indicator)
        try:
            return ak.stock_financial_abstract_ths(symbol=symbol, indicator=indicator)
        except Exception as e:
            self.logger.error(f"获取关键指标(同花顺)失败: {e}")
            raise
    
    def get_financial_analysis_indicator(self, symbol: str, start_year: str = "2020") -> pd.DataFrame:
        """
        获取财务指标分析
        参数:
            symbol: 股票代码，如"600519"
            start_year: 开始年份，默认"2020"
        """
        self._log_operation("获取财务指标分析", symbol=symbol, start_year=start_year)
        try:
            return ak.stock_financial_analysis_indicator(symbol=symbol, start_year=start_year)
        except Exception as e:
            self.logger.error(f"获取财务指标分析失败: {e}")
            raise
    
    # ==================== 股东信息模块 ====================
    
    def get_top_10_free_holders(self, symbol: str, date: str) -> pd.DataFrame:
        """
        获取十大流通股东
        参数:
            symbol: 股票代码，如"sh688686"
            date: 报告期，格式YYYYMMDD，如"20240930"
        """
        self._log_operation("获取十大流通股东", symbol=symbol, date=date)
        try:
            return ak.stock_gdfx_free_top_10_em(symbol=symbol, date=date)
        except Exception as e:
            self.logger.error(f"获取十大流通股东失败: {e}")
            raise
    
    def get_top_10_holders(self, symbol: str, date: str) -> pd.DataFrame:
        """
        获取十大股东
        参数:
            symbol: 股票代码，如"sh688686"
            date: 报告期，格式YYYYMMDD，如"20250331"
        """
        self._log_operation("获取十大股东", symbol=symbol, date=date)
        try:
            return ak.stock_gdfx_top_10_em(symbol=symbol, date=date)
        except Exception as e:
            self.logger.error(f"获取十大股东失败: {e}")
            raise
    
    def get_shareholder_count(self, symbol: str) -> pd.DataFrame:
        """
        获取股东户数
        参数:
            symbol: 报告期，格式YYYYMMDD，如"20250331"
        """
        self._log_operation("获取股东户数", symbol=symbol)
        try:
            return ak.stock_zh_a_gdhs(symbol=symbol)
        except Exception as e:
            self.logger.error(f"获取股东户数失败: {e}")
            raise
    
    # ==================== 行业板块模块 ====================
    
    def get_sector_spot(self, indicator: str = "新浪行业") -> pd.DataFrame:
        """
        获取板块行情
        参数:
            indicator: 板块类型，默认"新浪行业"
        """
        self._log_operation("获取板块行情", indicator=indicator)
        try:
            return ak.stock_sector_spot(indicator=indicator)
        except Exception as e:
            self.logger.error(f"获取板块行情失败: {e}")
            raise
    
    # ==================== 股票列表模块 ====================
    
    def get_a_stock_list(self) -> pd.DataFrame:
        """
        获取A股股票列表
        """
        self._log_operation("获取A股列表")
        try:
            return ak.stock_info_a_code_name()
        except Exception as e:
            self.logger.error(f"获取A股列表失败: {e}")
            raise
    
    def get_sh_stock_list(self, symbol: str = "主板A股") -> pd.DataFrame:
        """
        获取上证股票列表
        参数:
            symbol: 板块类型，默认"主板A股"
        """
        self._log_operation("获取上证股票列表", symbol=symbol)
        try:
            return ak.stock_info_sh_name_code(symbol=symbol)
        except Exception as e:
            self.logger.error(f"获取上证股票列表失败: {e}")
            raise
    
    def get_sz_stock_list(self, symbol: str = "A股列表") -> pd.DataFrame:
        """
        获取深证股票列表
        参数:
            symbol: 板块类型，默认"A股列表"
        """
        self._log_operation("获取深证股票列表", symbol=symbol)
        try:
            return ak.stock_info_sz_name_code(symbol=symbol)
        except Exception as e:
            self.logger.error(f"获取深证股票列表失败: {e}")
            raise


# 使用示例
if __name__ == "__main__":
    # 创建StockData实例
    stock_data = StockData()
    
    # 示例：获取平安银行的基本信息
    try:
        info = stock_data.get_stock_info_em("000001")
        print("平安银行基本信息:")
        print(info)
    except Exception as e:
        print(f"获取数据失败: {e}") 