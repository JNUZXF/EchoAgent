
"""
akshare 爬取股票信息
pip install akshare --upgrade
"""


import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class StockAnalyzer:
    """
    基于akshare的股票信息获取和分析类
    提供股票行情数据、财务报表、技术指标等信息的获取功能
    """
    
    def __init__(self, stock_code):
        """
        初始化股票分析器
        
        Args:
            stock_code (str): 股票代码，如 '000001' 或 'sh000001'
        """
        self.stock_code = self._format_stock_code(stock_code)
        self.raw_code = stock_code
        self.stock_info = None
        
    def _format_stock_code(self, code):
        """格式化股票代码"""
        # 移除前缀，保留6位数字
        if isinstance(code, str):
            if code.startswith(('sh', 'sz')):
                return code[2:]
            elif '.' in code:
                return code.split('.')[0]
        return str(code).zfill(6)
    
    def get_basic_info(self):
        """获取股票基本信息"""
        try:
            # 获取股票基本信息
            stock_info = ak.stock_individual_info_em(symbol=self.stock_code)
            self.stock_info = stock_info
            return stock_info
        except Exception as e:
            print(f"获取基本信息失败: {e}")
            return None
    
    def get_historical_data(self, period="daily", start_date=None, end_date=None, adjust="qfq"):
        """
        获取历史行情数据
        
        Args:
            period (str): 数据周期，'daily', 'weekly', 'monthly'
            start_date (str): 开始日期，格式 'YYYYMMDD'
            end_date (str): 结束日期，格式 'YYYYMMDD'
            adjust (str): 复权类型，'qfq'前复权, 'hfq'后复权, ''不复权
        """
        try:
            if not end_date:
                end_date = datetime.now().strftime('%Y%m%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            
            if period == "daily":
                data = ak.stock_zh_a_hist(symbol=self.stock_code, 
                                        period="daily", 
                                        start_date=start_date, 
                                        end_date=end_date, 
                                        adjust=adjust)
            elif period == "weekly":
                data = ak.stock_zh_a_hist(symbol=self.stock_code, 
                                        period="weekly", 
                                        start_date=start_date, 
                                        end_date=end_date, 
                                        adjust=adjust)
            elif period == "monthly":
                data = ak.stock_zh_a_hist(symbol=self.stock_code, 
                                        period="monthly", 
                                        start_date=start_date, 
                                        end_date=end_date, 
                                        adjust=adjust)
            
            return data
        except Exception as e:
            print(f"获取历史数据失败: {e}")
            return None
    
    def get_realtime_data(self):
        """获取实时行情数据"""
        try:
            # 获取实时数据
            data = ak.stock_zh_a_spot_em()
            stock_data = data[data['代码'] == self.stock_code]
            return stock_data
        except Exception as e:
            print(f"获取实时数据失败: {e}")
            return None
    
    def get_financial_statements(self, report_type="资产负债表", year=None):
        """
        获取财务报表
        
        Args:
            report_type (str): 报表类型，'资产负债表', '利润表', '现金流量表'
            year (str): 年份，如 '2023'
        """
        try:
            if not year:
                year = str(datetime.now().year - 1)
            
            if report_type == "资产负债表":
                data = ak.stock_balance_sheet_by_report_em(symbol=self.stock_code, date=year)
            elif report_type == "利润表":
                data = ak.stock_profit_sheet_by_report_em(symbol=self.stock_code, date=year)
            elif report_type == "现金流量表":
                data = ak.stock_cash_flow_sheet_by_report_em(symbol=self.stock_code, date=year)
            else:
                print("报表类型错误，请选择：资产负债表、利润表、现金流量表")
                return None
            
            return data
        except Exception as e:
            print(f"获取财务报表失败: {e}")
            return None
    
    def get_financial_indicators(self):
        """获取主要财务指标"""
        try:
            # 获取财务指标
            data = ak.stock_financial_abstract_em(symbol=self.stock_code)
            return data
        except Exception as e:
            print(f"获取财务指标失败: {e}")
            return None
    
    def get_technical_indicators(self, indicator="MACD", period="daily"):
        """
        获取技术指标
        
        Args:
            indicator (str): 技术指标类型
            period (str): 周期
        """
        try:
            # 先获取历史数据
            hist_data = self.get_historical_data(period=period)
            if hist_data is None or hist_data.empty:
                return None
            
            # 计算技术指标（这里简化处理，实际可以扩展更多指标）
            if indicator == "MA":
                hist_data['MA5'] = hist_data['收盘'].rolling(window=5).mean()
                hist_data['MA10'] = hist_data['收盘'].rolling(window=10).mean()
                hist_data['MA20'] = hist_data['收盘'].rolling(window=20).mean()
            
            return hist_data
        except Exception as e:
            print(f"获取技术指标失败: {e}")
            return None
    
    def get_news_sentiment(self):
        """获取新闻资讯"""
        try:
            # 获取个股新闻
            news = ak.stock_news_em(symbol=self.stock_code)
            return news
        except Exception as e:
            print(f"获取新闻资讯失败: {e}")
            return None
    
    def get_holder_info(self):
        """获取股东信息"""
        try:
            # 获取股东信息
            holders = ak.stock_gdfx_holding_analyse_em(symbol=self.stock_code)
            return holders
        except Exception as e:
            print(f"获取股东信息失败: {e}")
            return None
    
    def get_dividend_info(self):
        """获取分红配股信息"""
        try:
            dividend = ak.stock_fhpg_em(symbol=self.stock_code)
            return dividend
        except Exception as e:
            print(f"获取分红信息失败: {e}")
            return None
    
    def get_comprehensive_analysis(self):
        """获取综合分析数据"""
        analysis = {}
        
        print(f"正在获取股票 {self.stock_code} 的综合信息...")
        
        # 基本信息
        print("1. 获取基本信息...")
        analysis['basic_info'] = self.get_basic_info()
        
        # 实时数据
        print("2. 获取实时数据...")
        analysis['realtime_data'] = self.get_realtime_data()
        
        # 历史数据（最近一年）
        print("3. 获取历史数据...")
        analysis['historical_data'] = self.get_historical_data()
        
        # 财务报表
        print("4. 获取财务报表...")
        analysis['balance_sheet'] = self.get_financial_statements("资产负债表")
        analysis['profit_sheet'] = self.get_financial_statements("利润表")
        analysis['cash_flow'] = self.get_financial_statements("现金流量表")
        
        # 财务指标
        print("5. 获取财务指标...")
        analysis['financial_indicators'] = self.get_financial_indicators()
        
        # 技术指标
        print("6. 获取技术指标...")
        analysis['technical_indicators'] = self.get_technical_indicators("MA")
        
        # 新闻资讯
        print("7. 获取新闻资讯...")
        analysis['news'] = self.get_news_sentiment()
        
        # 股东信息
        print("8. 获取股东信息...")
        analysis['holders'] = self.get_holder_info()
        
        # 分红信息
        print("9. 获取分红信息...")
        analysis['dividend'] = self.get_dividend_info()
        
        print("数据获取完成！")
        return analysis
    
    def save_to_excel(self, analysis_data, filename=None):
        """将分析数据保存到Excel文件"""
        if not filename:
            filename = f"stock_analysis_{self.stock_code}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        try:
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                for key, data in analysis_data.items():
                    if data is not None and not data.empty:
                        data.to_excel(writer, sheet_name=key[:31], index=False)  # Excel工作表名称限制31字符
            
            print(f"数据已保存到: {filename}")
            return filename
        except Exception as e:
            print(f"保存Excel文件失败: {e}")
            return None
    
    def print_summary(self, analysis_data):
        """打印数据摘要"""
        print(f"\n{'='*50}")
        print(f"股票代码: {self.stock_code}")
        print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")
        
        for key, data in analysis_data.items():
            if data is not None:
                if isinstance(data, pd.DataFrame) and not data.empty:
                    print(f"{key}: {len(data)} 条记录")
                else:
                    print(f"{key}: 数据获取成功")
            else:
                print(f"{key}: 数据获取失败")

# 使用示例
if __name__ == "__main__":
    # 创建股票分析器实例
    analyzer = StockAnalyzer("000001")  # 平安银行
    
    # 获取综合分析
    analysis = analyzer.get_comprehensive_analysis()
    
    # 打印摘要
    analyzer.print_summary(analysis)
    
    # 保存到Excel
    analyzer.save_to_excel(analysis)
    
    # 也可以单独获取某项数据
    # hist_data = analyzer.get_historical_data(start_date="20230101", end_date="20231231")
    # print(hist_data.head())