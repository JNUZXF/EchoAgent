# 论文下载工具
import os
import requests
from urllib.parse import urlparse

def download_arxiv_paper(url, folder="files/arxiv_papers"):
    # 确保文件夹存在
    os.makedirs(folder, exist_ok=True)
    
    # 解析URL获取文件名
    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path)
    
    # 如果文件名不是PDF格式,添加.pdf扩展名
    if not filename.lower().endswith('.pdf'):
        filename += '.pdf'
    
    filepath = os.path.join(folder, filename)
    
    # 检查文件是否已存在
    if os.path.exists(filepath):
        print(f"文件 {filename} 已存在。")
        return filepath
    
    # 下载文件
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # 如果请求失败则抛出异常
        
        with open(filepath, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        
        print(f"文件 {filename} 下载成功。")
        return filepath
    
    except requests.exceptions.RequestException as e:
        print(f"下载失败: {e}")
        return None

# 下载urls
def download_arxiv_papers(urls, folder="files/arxiv_papers"):
    for url in urls:
        download_arxiv_paper(url, folder)
    return "下载成功"

if __name__ == "__main__":
    # 使用示例
    url = [
        "http://arxiv.org/pdf/2408.01310v1",
        "https://arxiv.org/pdf/2408.01423"
    ]
    result = download_arxiv_papers(url)


