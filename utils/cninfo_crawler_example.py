#
# 文件功能：巨潮资讯网高级爬虫使用示例
# 文件路径：utils/cninfo_crawler_example.py
#

import sys
import os
import logging

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.cninfo_advanced_crawler import CninfoAdvancedCrawler

def example_search_and_download():
    """【示例1】搜索并下载五粮液年报"""
    print("=" * 60)
    print("示例1: 搜索并下载五粮液年报")
    print("=" * 60)
    
    # 创建爬虫实例（无头模式）
    crawler = CninfoAdvancedCrawler(headless=True, download_dir='downloads/wuliangye_reports')
    
    try:
        # 搜索五粮液年报相关公告
        announcements = crawler.search_announcements("五粮液 年报", max_results=10)
        
        if announcements:
            print(f"找到 {len(announcements)} 条相关公告")
            
            # 保存公告列表
            crawler.save_announcement_list(announcements, 'wuliangye_announcement_list.txt')
            
            # 批量下载年报
            download_results = crawler.batch_download_announcements(
                announcements, 
                filter_keywords=['年报', '年度报告']
            )
            
            # 统计结果
            successful = sum(1 for path in download_results.values() if path is not None)
            print(f"下载完成: 成功 {successful} 个，失败 {len(download_results) - successful} 个")
            
        else:
            print("未找到相关公告")
            
    except Exception as e:
        print(f"执行出错: {e}")

def example_multiple_companies():
    """【示例2】批量下载多家公司的财报"""
    print("\n" + "=" * 60)
    print("示例2: 批量下载多家公司的财报")
    print("=" * 60)
    
    companies = ["贵州茅台", "五粮液", "泸州老窖"]
    
    for company in companies:
        print(f"\n正在处理: {company}")
        
        # 为每家公司创建独立的下载目录
        download_dir = f'downloads/{company}_reports'
        crawler = CninfoAdvancedCrawler(headless=True, download_dir=download_dir)
        
        try:
            # 搜索年报
            announcements = crawler.search_announcements(f"{company} 年报", max_results=5)
            
            if announcements:
                print(f"  找到 {len(announcements)} 条公告")
                
                # 下载最新的年报
                download_results = crawler.batch_download_announcements(
                    announcements[:3],  # 只下载前3个
                    filter_keywords=['年报', '年度报告']
                )
                
                successful = sum(1 for path in download_results.values() if path is not None)
                print(f"  下载完成: {successful} 个文件")
                
            else:
                print(f"  未找到 {company} 的相关公告")
                
        except Exception as e:
            print(f"  处理 {company} 时出错: {e}")

def example_search_only():
    """【示例3】只搜索不下载，查看公告列表"""
    print("\n" + "=" * 60)
    print("示例3: 只搜索公告，不下载")
    print("=" * 60)
    
    crawler = CninfoAdvancedCrawler(headless=True, download_dir='downloads/search_only')
    
    try:
        # 搜索白酒行业相关公告
        announcements = crawler.search_announcements("白酒 业绩", max_results=20)
        
        if announcements:
            print(f"找到 {len(announcements)} 条相关公告:\n")
            
            for i, announcement in enumerate(announcements[:10], 1):  # 只显示前10条
                print(f"{i:2d}. [{announcement.stock_code}] {announcement.title}")
                print(f"     时间: {announcement.announcement_time}")
                print(f"     链接: {announcement.announcement_url}")
                print()
            
            # 保存完整列表到文件
            crawler.save_announcement_list(announcements, 'baijiu_announcements.txt')
            print("完整公告列表已保存到文件")
            
        else:
            print("未找到相关公告")
            
    except Exception as e:
        print(f"搜索出错: {e}")

def example_custom_filter():
    """【示例4】使用自定义过滤条件"""
    print("\n" + "=" * 60)
    print("示例4: 使用自定义过滤条件")
    print("=" * 60)
    
    crawler = CninfoAdvancedCrawler(headless=True, download_dir='downloads/custom_filter')
    
    try:
        # 搜索五粮液所有公告
        announcements = crawler.search_announcements("五粮液", max_results=30)
        
        if announcements:
            print(f"总共找到 {len(announcements)} 条公告")
            
            # 自定义过滤：只下载重要的财务报告
            important_keywords = ['年报', '半年报', '季报', '业绩', '财务', '分红']
            
            filtered_announcements = []
            for announcement in announcements:
                if any(keyword in announcement.title for keyword in important_keywords):
                    filtered_announcements.append(announcement)
            
            print(f"过滤后剩余 {len(filtered_announcements)} 条重要公告")
            
            if filtered_announcements:
                # 下载过滤后的公告
                download_results = crawler.batch_download_announcements(filtered_announcements)
                
                successful = sum(1 for path in download_results.values() if path is not None)
                print(f"下载完成: {successful} 个文件")
                
        else:
            print("未找到相关公告")
            
    except Exception as e:
        print(f"执行出错: {e}")

def main():
    """主函数 - 运行所有示例"""
    print("巨潮资讯网高级爬虫使用示例")
    print("注意：首次运行需要安装selenium和Chrome浏览器")
    print("安装命令: pip install selenium")
    print("Chrome浏览器需要单独下载安装")
    
    try:
        # 运行示例1：基本搜索和下载
        example_search_and_download()
        
        # 运行示例2：多公司批量处理
        # example_multiple_companies()  # 注释掉以节省时间
        
        # 运行示例3：只搜索不下载
        example_search_only()
        
        # 运行示例4：自定义过滤
        # example_custom_filter()  # 注释掉以节省时间
        
        print("\n" + "=" * 60)
        print("所有示例执行完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"运行示例时出错: {e}")
        print("请确保已安装selenium和Chrome浏览器")

if __name__ == '__main__':
    main() 