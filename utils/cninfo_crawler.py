# 
# 文件功能：巨潮资讯网公告爬虫
# 文件路径：utils/cninfo_crawler.py
#

import os
import re
import logging
import requests
from urllib.parse import urlparse
from typing import Optional

# 【日志系统原则】配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clean_filename(filename: str) -> str:
    """
    【单一职责原则】清理文件名，去除Windows文件系统不支持的字符
    
    :param filename: 原始文件名
    :return: 清理后的文件名
    """
    # 【修复】处理HTML标签，如 <em>、</em> 等
    import re
    clean_name = re.sub(r'<[^>]+>', '', filename)  # 移除HTML标签
    
    # Windows文件名不允许的字符
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    
    # 替换无效字符为下划线
    for char in invalid_chars:
        clean_name = clean_name.replace(char, '_')
    
    # 【新增】替换多个连续空格为单个空格
    clean_name = re.sub(r'\s+', ' ', clean_name)
    
    # 去除首尾空格和点号
    clean_name = clean_name.strip(' .')
    
    # 【修复】确保文件名不为空
    if not clean_name:
        clean_name = "未命名文件"
    
    # 限制文件名长度（Windows路径限制，考虑中文字符）
    if len(clean_name.encode('utf-8')) > 200:  # 字节长度限制
        # 按字符截取，确保不超过字节限制
        while len(clean_name.encode('utf-8')) > 200 and len(clean_name) > 1:
            clean_name = clean_name[:-1]
    
    return clean_name

def get_unique_filename(base_path: str, filename: str, extension: str) -> str:
    """
    【容错设计】确保文件名唯一，避免重复覆盖
    
    :param base_path: 文件保存目录
    :param filename: 基础文件名（不含扩展名）
    :param extension: 文件扩展名（含点号）
    :return: 唯一的完整文件路径
    """
    file_path = os.path.join(base_path, f"{filename}{extension}")
    
    if not os.path.exists(file_path):
        return file_path
    
    # 如果文件已存在，添加数字后缀
    counter = 1
    while True:
        new_filename = f"{filename}_{counter}{extension}"
        file_path = os.path.join(base_path, new_filename)
        if not os.path.exists(file_path):
            return file_path
        counter += 1

def download_cninfo_announcement(page_url: str, save_dir: str = 'cninfo_downloads', announcement_title: Optional[str] = None):
    """
    【单一职责原则】
    根据给定的巨潮资讯网公告页面URL，下载对应的PDF公告文件。
    通过解析页面中的JavaScript变量来构造PDF的直接下载链接。

    :param page_url: 公告页面的URL. 
                     Example: 'https://www.cninfo.com.cn/new/disclosure/detail?stockCode=600519&announcementId=1224017589'
    :param save_dir: PDF文件保存的目录
    :param announcement_title: 公告标题（优先使用此参数作为文件名）
    :return: 保存的文件路径，如果失败则返回None
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        logging.info(f"正在抓取页面: {page_url}")
        response = requests.get(page_url, headers=headers, timeout=10)
        response.raise_for_status()
        html_text = response.text

        # 【核心逻辑】使用正则表达式从html中的<script>标签内提取关键信息
        # 【修复】更新正则表达式以匹配实际的JavaScript变量格式
        announcement_id_match = re.search(r'var announcementId = "(\d+)"', html_text)
        announcement_time_match = re.search(r'var announcementTime = "([\d-]+\s+[\d:]+)"', html_text)
        
        # 【修复】如果第一种格式不匹配，尝试其他格式
        if not announcement_id_match:
            announcement_id_match = re.search(r'announcementId = "(\d+)"', html_text)
        if not announcement_time_match:
            announcement_time_match = re.search(r'announcementTime = "([\d-]+)"', html_text)

        if not (announcement_id_match and announcement_time_match):
            logging.error("在页面中未能通过正则表达式找到 announcementId 或 announcementTime。")
            # 调试：保存获取到的HTML内容
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            with open(os.path.join(save_dir, 'debug_error.html'), 'w', encoding='utf-8') as f:
                f.write(html_text)
            logging.info(f"已将HTML内容保存到 {os.path.join(save_dir, 'debug_error.html')} 以便调试")
            
            # 【修复】尝试从URL参数中提取信息作为备用方案
            try:
                from urllib.parse import parse_qs, urlparse
                parsed_url = urlparse(page_url)
                params = parse_qs(parsed_url.query)
                
                if 'announcementId' in params and 'announcementTime' in params:
                    announcement_id = params['announcementId'][0]
                    announcement_time = params['announcementTime'][0].split()[0]  # 只取日期部分
                    logging.info(f"从URL参数中提取信息: announcementId={announcement_id}, announcementTime={announcement_time}")
                else:
                    return None
            except Exception as e:
                logging.error(f"从URL参数提取信息失败: {e}")
                return None
        else:
            announcement_id = announcement_id_match.group(1)
            announcement_time = announcement_time_match.group(1).split()[0]  # 只取日期部分



        logging.info(f"成功提取信息: announcementId={announcement_id}, announcementTime={announcement_time}")

        # 【代码扩展性原则-配置外置】创建保存目录
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            logging.info(f"创建目录: {save_dir}")

        # 【容错设计】尝试不同的文件扩展名（小写pdf和大写PDF），以及老路径/新路径结构
        pdf_extensions = ['.pdf', '.PDF']
        pdf_response = None
        actual_extension = None
        
        tried_urls = []
        for ext in pdf_extensions:
            # 新路径
            url_candidates = [
                f"https://static.cninfo.com.cn/finalpage/{announcement_time}/{announcement_id}{ext}",
                # 老路径备选
                f"https://static.cninfo.com.cn/finalpage/{announcement_time}/{'0'*(10-len(announcement_id))+announcement_id if len(announcement_id)<10 else announcement_id}{ext}"
            ]
            for pdf_url in url_candidates:
                tried_urls.append(pdf_url)
                logging.info(f"尝试下载PDF文件: {pdf_url}")
                try:
                    pdf_response = requests.get(pdf_url, headers=headers, stream=True, timeout=30)
                    pdf_response.raise_for_status()
                    actual_extension = ext
                    logging.info(f"成功找到PDF文件: {pdf_url}")
                    break
                except requests.exceptions.RequestException as e:
                    logging.warning(f"尝试失败: {e}")
                    pdf_response = None
            if pdf_response is not None:
                break
        
        if pdf_response is None or actual_extension is None:
            logging.error(f"所有扩展名与路径尝试都失败了，尝试过: {tried_urls}")
            return None

        # 【新增功能】智能文件命名逻辑 - 优先使用传入的标题参数
        final_title = None
        
        if announcement_title:
            # 优先使用传入的标题参数
            final_title = announcement_title.strip()
            logging.info(f"使用传入的公告标题: {final_title}")
        else:
            # 【新增功能】提取页面中的公告标题作为备用
            announcement_title_match = re.search(r'<div class="title">([^<]+)</div>', html_text)
            
            # 【修复】如果第一种格式不匹配，尝试其他格式
            if not announcement_title_match:
                # 尝试从页面title标签提取
                title_tag_match = re.search(r'<title>([^<]+)</title>', html_text)
                if title_tag_match:
                    full_title = title_tag_match.group(1)
                    # 去除公司名称等前缀，保留核心标题
                    if '：' in full_title:
                        announcement_title_match = re.search(r'：([^-]+)', full_title)
                    elif '-' in full_title:
                        announcement_title_match = re.search(r'-([^-]+)', full_title)

            if announcement_title_match:
                final_title = announcement_title_match.group(1).strip()
                logging.info(f"从页面提取到公告标题: {final_title}")
            else:
                logging.warning("未能提取到公告标题，将使用默认命名")

        # 确定最终的文件名
        if final_title:
            # 使用公告标题作为文件名
            clean_title = clean_filename(final_title)
            base_filename = clean_title
            logging.info(f"使用公告标题作为文件名: {clean_title}")
        else:
            # 【备用方案】使用公告ID和时间作为文件名
            base_filename = f"{announcement_id}_{announcement_time}"
            logging.info(f"使用默认命名方案: {base_filename}")
        
        file_path = f"{save_dir}/{base_filename}{actual_extension}"
        if os.path.exists(file_path):
            logging.info(f"文件已存在: {file_path}")
            return file_path

        # 【日志系统原则-INFO】下载PDF文件
        logging.info(f"开始下载PDF文件到: {file_path}")

        # 写入文件
        with open(file_path, 'wb') as f:
            for chunk in pdf_response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        logging.info(f"文件下载成功: {file_path}")
        return file_path

    except requests.exceptions.RequestException as e:
        logging.error(f"请求失败: {e}")
        return None
    except Exception as e:
        logging.error(f"发生未知错误: {e}")
        return None

if __name__ == '__main__':
    # 【测试策略】提供一个示例URL进行测试
    test_url = "https://www.cninfo.com.cn/new/disclosure/detail?plate=sse&orgId=gssh0600519&stockCode=600519&announcementId=1224017589&announcementTime=2025-06-28"
    
    print("开始测试下载功能...")
    downloaded_file = download_cninfo_announcement(test_url)
    if downloaded_file:
        print(f"测试成功，文件保存在: {os.path.abspath(downloaded_file)}")
    else:
        print("测试失败。") 