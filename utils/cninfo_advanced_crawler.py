#
# 文件功能：巨潮资讯网高级爬虫 - 支持动态内容抓取和批量下载
# 文件路径：utils/cninfo_advanced_crawler.py
#

import os
import re
import time
import logging
from urllib.parse import urljoin, quote
from typing import List, Dict, Optional
from dataclasses import dataclass

# Selenium相关导入
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# 导入之前创建的下载函数
from .cninfo_crawler import download_cninfo_announcement

# 【日志系统原则】配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class AnnouncementInfo:
    """【单一职责原则】公告信息数据类"""
    stock_code: str
    title: str
    announcement_url: str
    announcement_time: str
    announcement_id: str
    org_id: str

class CninfoAdvancedCrawler:
    """
    【架构设计原则-分层架构】【模块化设计】
    巨潮资讯网高级爬虫类，支持：
    1. 处理JavaScript动态加载的搜索结果页面
    2. 批量提取公告链接信息
    3. 批量下载PDF文件
    """
    
    def __init__(self, headless: bool = True, download_dir: str = 'cninfo_downloads'):
        """
        初始化爬虫
        
        :param headless: 是否使用无头模式
        :param download_dir: 下载目录
        """
        self.base_url = "https://www.cninfo.com.cn"
        self.download_dir = download_dir
        self.driver = None
        self.headless = headless
        
        # 【代码扩展性原则-配置外置】创建下载目录
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
            logging.info(f"创建下载目录: {download_dir}")
    
    def _setup_driver(self) -> webdriver.Chrome:
        """【单一职责原则】设置Chrome浏览器驱动"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            logging.info("Chrome浏览器驱动初始化成功")
            return driver
        except Exception as e:
            logging.error(f"Chrome浏览器驱动初始化失败: {e}")
            raise
    
    def search_announcements(self, keyword: str, max_results: int = 50) -> List[AnnouncementInfo]:
        """
        【核心业务逻辑】搜索公告信息
        
        :param keyword: 搜索关键词（如股票名称）
        :param max_results: 最大结果数量
        :return: 公告信息列表
        """
        self.driver = self._setup_driver()
        announcements = []
        
        try:
            # 构造搜索URL
            encoded_keyword = quote(keyword)
            search_url = f"{self.base_url}/new/fulltextSearch?notautosubmit=&keyWord={encoded_keyword}&searchType=0"
            
            logging.info(f"正在访问搜索页面: {search_url}")
            self.driver.get(search_url)
            
            # 【容错设计】等待页面加载完成
            wait = WebDriverWait(self.driver, 15)  # 【修复】增加等待时间
            
            # 【修复】等待搜索结果表格出现 - 使用更可靠的等待条件
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".el-table__body")))
                logging.info("搜索结果页面加载完成")
                
                # 【修复】额外等待确保JavaScript完全执行
                time.sleep(3)
                
            except TimeoutException:
                logging.warning("等待搜索结果超时，尝试继续解析")
                # 【修复】如果表格没有加载，尝试等待其他元素
                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.ahover")))
                    logging.info("找到公告链接，继续解析")
                except TimeoutException:
                    logging.error("页面加载失败，没有找到任何公告链接")
            
            # 【日志系统原则-DEBUG】保存页面源码用于调试
            with open(os.path.join(self.download_dir, 'search_page_source.html'), 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            
            # 滚动页面以加载更多内容
            self._scroll_to_load_more()
            
            # 解析公告链接
            announcements = self._parse_announcement_links(max_results)
            
            logging.info(f"成功提取到 {len(announcements)} 条公告信息")
            
        except Exception as e:
            logging.error(f"搜索公告时发生错误: {e}")
        finally:
            if self.driver:
                self.driver.quit()
        
        return announcements
    
    def _scroll_to_load_more(self):
        """【性能优化】滚动页面加载更多内容"""
        try:
            # 滚动到页面底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);") # type: ignore
            time.sleep(2)
            
            # 检查是否有"加载更多"按钮并点击
            try:
                load_more_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), '加载更多') or contains(text(), '更多')]") # type: ignore
                if load_more_btn.is_displayed():
                    load_more_btn.click()
                    time.sleep(3)
                    logging.info("点击了加载更多按钮")
            except NoSuchElementException:
                logging.info("未找到加载更多按钮")
                
        except Exception as e:
            logging.warning(f"滚动加载时出现问题: {e}")
    
    def _parse_announcement_links(self, max_results: int) -> List[AnnouncementInfo]:
        """【核心解析逻辑】解析公告链接"""
        announcements = []
        
        try:
            # 查找所有公告链接
            link_elements = self.driver.find_elements(By.CSS_SELECTOR, "a.ahover") # type: ignore
            
            logging.info(f"找到 {len(link_elements)} 个公告链接")
            
            for i, link_elem in enumerate(link_elements[:max_results]):
                try:
                    # 提取链接信息
                    href = link_elem.get_attribute('href')
                    if not href or '/new/disclosure/detail' not in href:
                        continue
                    
                    # 提取data属性
                    announcement_id = link_elem.get_attribute('data-id')
                    org_id = link_elem.get_attribute('data-orgid')
                    stock_code = link_elem.get_attribute('data-seccode')
                    
                    # 【修复】提取完整公告标题 - 公司名称 + 公告内容
                    title = "未知标题"
                    try:
                        # 策略1：提取完整标题（推荐方案）
                        # 查找包含完整标题的r-title元素
                        r_title_elem = link_elem.find_element(By.CSS_SELECTOR, "span.r-title")
                        full_title_text = r_title_elem.text.strip()
                        if full_title_text:
                            title = full_title_text
                            logging.debug(f"成功提取完整标题: {title}")
                        else:
                            raise Exception("r-title元素为空")
                    except:
                        try:
                            # 策略2：分别提取公司名称和公告内容
                            company_name = ""
                            announcement_content = ""
                            
                            # 提取公司名称
                            try:
                                company_elem = link_elem.find_element(By.CSS_SELECTOR, ".secNameSuper")
                                company_name = company_elem.text.strip()
                            except:
                                pass
                            
                            # 提取公告内容
                            try:
                                content_elem = link_elem.find_element(By.CSS_SELECTOR, ".tileSecName-content")
                                announcement_content = content_elem.text.strip()
                            except:
                                pass
                            
                            # 组合完整标题
                            if company_name and announcement_content:
                                title = f"{company_name} {announcement_content}"
                            elif announcement_content:
                                title = announcement_content
                            elif company_name:
                                title = company_name
                            else:
                                raise Exception("无法提取标题内容")
                                
                            logging.debug(f"通过组合提取标题: {title}")
                        except:
                            try:
                                # 策略3：使用链接的title属性
                                title_attr = link_elem.get_attribute('title')
                                if title_attr and title_attr.strip():
                                    title = title_attr.strip()
                                else:
                                    raise Exception("title属性为空")
                            except:
                                try:
                                    # 策略4：使用链接的完整文本内容
                                    link_text = link_elem.text.strip()
                                    if link_text:
                                        title = link_text
                                    else:
                                        title = "未知标题"
                                except:
                                    title = "未知标题"
                    
                    # 【修复】提取时间信息（从父级tr元素中查找）
                    announcement_time = "未知时间"
                    try:
                        tr_elem = link_elem.find_element(By.XPATH, "./ancestor::tr")
                        time_elem = tr_elem.find_element(By.CSS_SELECTOR, ".time")
                        announcement_time = time_elem.text.strip()
                    except:
                        try:
                            # 备用策略：从URL参数中提取时间
                            if 'announcementTime=' in href:
                                time_match = re.search(r'announcementTime=([^&]+)', href)
                                if time_match:
                                    announcement_time = time_match.group(1).replace('%20', ' ')
                        except:
                            pass
                    
                    # 构造完整URL
                    if href.startswith('/'):
                        full_url = self.base_url + href
                    else:
                        full_url = href
                    
                    # 创建公告信息对象
                    announcement = AnnouncementInfo(
                        stock_code=stock_code or "未知代码",
                        title=title,
                        announcement_url=full_url,
                        announcement_time=announcement_time,
                        announcement_id=announcement_id or "",
                        org_id=org_id or ""
                    )
                    
                    announcements.append(announcement)
                    
                    # 【日志系统原则-DEBUG】记录解析进度
                    if (i + 1) % 10 == 0:
                        logging.info(f"已解析 {i + 1} 条公告信息")
                        
                except Exception as e:
                    logging.warning(f"解析第 {i + 1} 个公告链接时出错: {e}")
                    continue
                    
        except Exception as e:
            logging.error(f"解析公告链接时发生错误: {e}")
        
        return announcements
    
    def batch_download_announcements(self, announcements: List[AnnouncementInfo], 
                                   filter_keywords: Optional[List[str]] = None) -> Dict[str, str]:
        """
        【批量处理】批量下载公告PDF文件
        
        :param announcements: 公告信息列表
        :param filter_keywords: 过滤关键词列表（如['年报', '季报']）
        :return: 下载结果字典 {announcement_id: file_path}
        """
        download_results = {}
        successful_downloads = 0
        
        # 【性能监控】记录开始时间
        start_time = time.time()
        
        for i, announcement in enumerate(announcements):
            try:
                # 如果
                logging.info(f"正在下载第 {i + 1}/{len(announcements)} 个公告: {announcement.title}")
                
                # 可选关键词过滤：若提供，仅保留包含关键词的条目（排除摘要/英文/更正等）
                if filter_keywords:
                    title_lower = (announcement.title or "").lower()
                    if not any(k.lower() in title_lower for k in filter_keywords):
                        continue
                    bad_substrings = ["摘要", "英文", "修订", "更正", "取消", "取消审核", "问询回复", "回复", "公告格式"]
                    if any(bad.lower() in title_lower for bad in bad_substrings):
                        continue

                # 【修复】调用下载函数并传递标题参数
                file_path = download_cninfo_announcement(
                    announcement.announcement_url, 
                    self.download_dir,
                    announcement.title  # 传递提取到的公告标题
                )
                
                if file_path:
                    download_results[announcement.announcement_id] = file_path
                    successful_downloads += 1
                    logging.info(f"下载成功: {file_path}")
                else:
                    download_results[announcement.announcement_id] = None
                    logging.warning(f"下载失败: {announcement.title}")
                
                # 【性能优化】避免请求过于频繁
                time.sleep(1)
                
            except Exception as e:
                logging.error(f"下载公告 {announcement.title} 时发生错误: {e}")
                download_results[announcement.announcement_id] = None
        
        # 【性能监控】记录总耗时
        total_time = time.time() - start_time
        logging.info(f"批量下载完成! 成功: {successful_downloads}/{len(announcements)}, 耗时: {total_time:.2f}秒")
        
        return download_results
    
    def save_announcement_list(self, announcements: List[AnnouncementInfo], filename: str = 'announcement_list.txt'):
        """【数据持久化】保存公告列表到文件"""
        file_path = os.path.join(self.download_dir, filename)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"公告列表 (共 {len(announcements)} 条)\n")
                f.write("=" * 80 + "\n\n")
                
                for i, announcement in enumerate(announcements, 1):
                    f.write(f"{i}. 股票代码: {announcement.stock_code}\n")
                    f.write(f"   公告标题: {announcement.title}\n")
                    f.write(f"   公告时间: {announcement.announcement_time}\n")
                    f.write(f"   公告链接: {announcement.announcement_url}\n")
                    f.write(f"   公告ID: {announcement.announcement_id}\n")
                    f.write("-" * 80 + "\n")
            
            logging.info(f"公告列表已保存到: {file_path}")
            return file_path
            
        except Exception as e:
            logging.error(f"保存公告列表时发生错误: {e}")
            return None

def main():
    """【测试策略】主函数 - 用于测试功能"""
    # 创建爬虫实例
    crawler = CninfoAdvancedCrawler(headless=False)  # 设置为False以便观察浏览器行为
    
    try:
        # 搜索五粮液相关公告
        keyword = "泸州老窖 年度报告"
        logging.info(f"开始搜索关键词: {keyword}")
        
        announcements = crawler.search_announcements(keyword, max_results=20)
        
        if announcements:
            # 保存公告列表
            crawler.save_announcement_list(announcements)
            
            # 批量下载（只下载包含"年报"的公告）
            download_results = crawler.batch_download_announcements(
                announcements, 
                filter_keywords=[]
            )
            
            # 输出下载结果统计
            successful = sum(1 for path in download_results.values() if path is not None)
            print(f"\n下载完成统计:")
            print(f"总计公告: {len(announcements)}")
            print(f"下载成功: {successful}")
            print(f"下载失败: {len(download_results) - successful}")
            
        else:
            print("未找到相关公告")
            
    except Exception as e:
        logging.error(f"主程序执行出错: {e}")

if __name__ == '__main__':
    main() 