"""
StockData使用示例
文件路径: tools_agent/stock_data_example.py
功能: 展示如何使用StockData类获取各种金融数据
作者: AI Assistant
创建时间: 2025-01-28
"""

from stock_data import StockData
import pandas as pd

def main():
    """主函数：演示StockData类的各种功能"""
    
    # 【日志系统原则】创建StockData实例，所有操作都会记录日志
    print("=== 初始化StockData类 ===")
    stock_data = StockData()
    
    # 【模块化设计】按功能模块展示不同的数据获取方法
    
    print("\n=== 1. 市场总览数据 ===")
    try:
        # 获取上交所总览
        sse_summary = stock_data.get_sse_summary()
        print("上交所总览数据:")
        print(sse_summary.head())
        
        # 获取深交所总览
        szse_summary = stock_data.get_szse_summary()
        print("\n深交所总览数据:")
        print(szse_summary.head())
        
    except Exception as e:
        print(f"获取市场总览数据失败: {e}")
    
    print("\n=== 2. 个股基本信息 ===")
    try:
        # 获取平安银行(000001)基本信息
        stock_info = stock_data.get_stock_info_em("000001")
        print("平安银行基本信息:")
        print(stock_info)
        
        # 获取公司概况
        profile = stock_data.get_stock_profile_cninfo("000001")
        print("\n平安银行公司概况:")
        print(profile.head())
        
    except Exception as e:
        print(f"获取个股信息失败: {e}")
    
    print("\n=== 3. 股价历史数据 ===")
    try:
        # 获取平安银行近期历史行情
        hist_data = stock_data.get_stock_hist(
            symbol="000001", 
            start_date="20250101", 
            end_date="20250128"
        )
        print("平安银行近期行情:")
        print(hist_data.head())
        
    except Exception as e:
        print(f"获取历史行情失败: {e}")
    
    print("\n=== 4. 财务报表数据 ===")
    try:
        # 获取2024年Q3业绩报表
        performance = stock_data.get_performance_report("20240930")
        print("2024年Q3业绩报表(前5条):")
        print(performance.head())
        
        # 获取财务指标分析
        financial_indicator = stock_data.get_financial_analysis_indicator("000001", "2023")
        print("\n平安银行财务指标分析:")
        print(financial_indicator.head())
        
    except Exception as e:
        print(f"获取财务数据失败: {e}")
    
    print("\n=== 5. 股东信息 ===")
    try:
        # 获取十大股东信息
        top_holders = stock_data.get_top_10_holders("sz000001", "20240930")
        print("平安银行十大股东:")
        print(top_holders.head())
        
    except Exception as e:
        print(f"获取股东信息失败: {e}")
    
    print("\n=== 6. 新闻资讯 ===")
    try:
        # 获取个股新闻
        news = stock_data.get_stock_news("000001")
        print("平安银行相关新闻(前3条):")
        print(news.head(3))
        
        # 获取财经早餐
        morning_news = stock_data.get_morning_news()
        print("\n财经早餐:")
        print(morning_news.head(3))
        
    except Exception as e:
        print(f"获取新闻资讯失败: {e}")
    
    print("\n=== 7. 行业板块数据 ===")
    try:
        # 获取行业板块行情
        sector_data = stock_data.get_sector_spot("新浪行业")
        print("行业板块行情(前5个):")
        print(sector_data.head())
        
    except Exception as e:
        print(f"获取行业数据失败: {e}")
    
    print("\n=== 8. 股票列表 ===")
    try:
        # 获取A股列表
        a_stock_list = stock_data.get_a_stock_list()
        print(f"A股总数: {len(a_stock_list)}")
        print("A股列表(前10个):")
        print(a_stock_list.head(10))
        
    except Exception as e:
        print(f"获取股票列表失败: {e}")


def advanced_usage_example():
    """高级使用示例：组合多个数据源进行分析"""
    
    print("\n" + "="*50)
    print("=== 高级使用示例：综合股票分析 ===")
    print("="*50)
    
    stock_data = StockData()
    stock_code = "000001"  # 平安银行
    
    try:
        # 【单一职责原则】每个方法只负责获取一种类型的数据
        print(f"\n正在分析股票: {stock_code}")
        
        # 1. 获取基本信息
        basic_info = stock_data.get_stock_info_em(stock_code)
        print(f"股票名称: {basic_info.iloc[0]['value'] if not basic_info.empty else '未知'}")
        
        # 2. 获取最近行情
        recent_data = stock_data.get_stock_hist(
            symbol=stock_code,
            start_date="20250120",
            end_date="20250128"
        )
        
        if not recent_data.empty:
            latest_price = recent_data.iloc[-1]['收盘']
            print(f"最新收盘价: {latest_price}")
            
            # 计算涨跌幅
            if len(recent_data) > 1:
                prev_price = recent_data.iloc[-2]['收盘']
                change_pct = (latest_price - prev_price) / prev_price * 100
                print(f"日涨跌幅: {change_pct:.2f}%")
        
        # 3. 获取财务指标
        financial_data = stock_data.get_financial_analysis_indicator(stock_code, "2023")
        if not financial_data.empty:
            print("主要财务指标:")
            print(financial_data[['日期', '净资产收益率', '总资产收益率']].head(3))
        
        # 4. 获取最新新闻
        news_data = stock_data.get_stock_news(stock_code)
        if not news_data.empty:
            print(f"\n最新新闻标题: {news_data.iloc[0]['新闻标题']}")
        
        print("\n综合分析完成！")
        
    except Exception as e:
        print(f"综合分析失败: {e}")


def batch_analysis_example():
    """批量分析示例：分析多只股票"""
    
    print("\n" + "="*50)
    print("=== 批量分析示例 ===")
    print("="*50)
    
    stock_data = StockData()
    
    # 【配置外置】股票代码列表可以从配置文件读取
    stock_codes = ["000001", "000002", "600036"]  # 平安银行、万科A、招商银行
    
    results = []
    
    for code in stock_codes:
        try:
            print(f"\n分析股票: {code}")
            
            # 获取基本信息
            info = stock_data.get_stock_info_em(code)
            stock_name = info.iloc[0]['value'] if not info.empty else "未知"
            
            # 获取最近价格
            hist = stock_data.get_stock_hist(
                symbol=code,
                start_date="20250125",
                end_date="20250128"
            )
            
            latest_price = hist.iloc[-1]['收盘'] if not hist.empty else 0
            
            results.append({
                '股票代码': code,
                '股票名称': stock_name,
                '最新价格': latest_price
            })
            
            print(f"  - 股票名称: {stock_name}")
            print(f"  - 最新价格: {latest_price}")
            
        except Exception as e:
            print(f"  - 分析失败: {e}")
            continue
    
    # 生成汇总报告
    if results:
        summary_df = pd.DataFrame(results)
        print("\n=== 批量分析汇总 ===")
        print(summary_df)
        
        # 【文档原则】可以保存到文件
        # summary_df.to_csv('batch_analysis_result.csv', index=False)
        # print("结果已保存到 batch_analysis_result.csv")


if __name__ == "__main__":
    # 【测试策略】运行基础功能测试
    print("开始StockData功能演示...")
    
    # 基础功能演示
    main()
    
    # 高级功能演示
    advanced_usage_example()
    
    # 批量分析演示
    batch_analysis_example()
    
    print("\n" + "="*50)
    print("所有演示完成！")
    print("您现在可以使用 stock_data.方法名() 来获取各种金融数据")
    print("="*50) 