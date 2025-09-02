# type: ignore
from utils.cninfo_advanced_crawler import CninfoAdvancedCrawler

class CninfoAdvancedCrawlerWrapper:
    def execute(self, **kwargs):
        keyword = kwargs.get('keyword', '')
        max_results = kwargs.get('max_results', 10)
        filter_keywords = kwargs.get('filter_keywords', [])
        download_dir = kwargs.get('download_dir', 'downloads/腾讯控股')
        crawler = CninfoAdvancedCrawler(headless=True, download_dir=download_dir)
        userID = kwargs.get('userID', '')
        stock_name = kwargs.get('stock_name', '')

        announcements = crawler.search_announcements(keyword, max_results)
        if announcements:
            crawler.save_announcement_list(announcements, f'{userID}/{stock_name}/announcement_list.txt')
            download_results = crawler.batch_download_announcements(announcements, filter_keywords=filter_keywords)
            successful = sum(1 for path in download_results.values() if path is not None)
            notice = f"下载完成: 成功 {successful} 个，失败 {len(download_results) - successful} 个"
            print(notice)
            return notice
        else:
            notice = "未找到相关公告"
            print(notice)
            return notice



