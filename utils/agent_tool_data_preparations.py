
# type: ignore

import requests
import json
import os
import fitz  # PyMuPDF
import shutil
from dotenv import load_dotenv

from agent.tools_agent.tavily_api import *
from agent.tools_agent.json_tool import *
from agent.tools_agent.llm_manager import *
from agent.tools_agent.system_operations import SystemOperations as so
from agent.utils.pdf_vlm_processor_v4_robust import convert_pdf_to_markdown_v4_robust
from agent.utils.cninfo_advanced_crawler import CninfoAdvancedCrawler
from agent.utils.duckduckgo import DuckDuckGoSearcher

from agent.utils.agent_tool_stock_data import *
from textwrap import dedent

from agent.prompts.fin_agent_prompts import FILE_LOCATE_PROMPT, FIND_LATEST_ANNUAL_REPORT_PROMPT

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

def find_latest_annual_report(seleced_file_paths):
    """
    根据文件路径，找到最新的年度报告的路径
    
    参数：
    seleced_file_paths: 文件路径列表
    
    返回：
    最新的年度报告的路径
    """
    prompt = FIND_LATEST_ANNUAL_REPORT_PROMPT.format(files=seleced_file_paths)
    llm = LLMManager(model="doubao-seed-1-6-flash-250615")
    ans = ""
    for char in llm.generate_char_stream(prompt, temperature=0.0):
        print(char, end="", flush=True)
        ans += char
    print()
    file_path = get_json(ans)["file_path"]
    return file_path

def extract_pdf_text(pdf_path: str) -> str:
    """
    提取给定 PDF 文件中的所有文本内容。
    
    参数:
        pdf_path (str): PDF 文件的完整路径。
    
    返回:
        str: 提取的全部文本。
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"指定路径不存在: {pdf_path}")
    if not pdf_path.lower().endswith(".pdf"):
        raise ValueError("该文件不是 PDF 格式")

    text = ""
    with fitz.open(pdf_path) as doc:
        for page_num, page in enumerate(doc, start=1):
            text += f"\n\n--- 第 {page_num} 页 ---\n"
            text += page.get_text()
    
    return text

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
            crawler.save_announcement_list(announcements, f'{userID}/{stock_name}/announcements.txt')
            download_results = crawler.batch_download_announcements(announcements, filter_keywords=filter_keywords)
            successful = sum(1 for path in download_results.values() if path is not None)
            notice = f"下载完成: 成功 {successful} 个，失败 {len(download_results) - successful} 个"
            print(notice)
            return notice
        else:
            notice = "未找到相关公告"
            print(notice)
            return notice

def rag_chunking(md_file_path, target_length=10000): 
    # 使用示例
    completer = TextFragmentCompleter(md_file_path)

    ## 分段函数
    def smart_paragraph_split(text, target_length=500):
        """
        智能地将文本分成多个段落，每个段落长度接近目标长度，同时尽量在句子结尾处分段
        
        参数:
            text (str): 需要分段的文本
            target_length (int): 目标段落长度
            
        返回:
            list: 分段后的段落列表
        """
        # 定义句子结束的标点符号
        end_marks = ['。', '！', '？', '!', '?', '\n\n']
        
        # 如果文本长度小于目标长度，直接返回
        if len(text) <= target_length:
            return [text]
        
        paragraphs = []
        start = 0
        
        while start < len(text):
            # 如果剩余文本长度小于目标长度，直接添加并结束
            if len(text) - start <= target_length:
                paragraphs.append(text[start:])
                break
                
            # 寻找目标长度范围内的最后一个句子结束标记
            end = start + target_length
            best_end = end
            
            # 向前查找最近的句子结束标记
            for i in range(end, start, -1):
                if text[i-1] in end_marks:
                    best_end = i
                    break
                    
            # 如果在目标长度前没找到句子结束标记，向后查找
            if best_end == end:
                for i in range(end, min(end + target_length//4, len(text))):
                    if text[i] in end_marks:
                        best_end = i + 1
                        break
                # 如果向后也没找到，就在目标长度处截断
                if best_end == end:
                    best_end = end
            
            # 添加段落
            paragraphs.append(text[start:best_end])
            start = best_end
            
        return paragraphs

    # 读取D:\AgentBuilding\FinAgent\ada\北方华创\total_texts.md
    with open(md_file_path, "r", encoding="utf-8") as f:
        markdown_content = f.read()
    # 使用示例
    paragraphs = smart_paragraph_split(markdown_content, target_length=target_length)

    complete_paras = []
    for i, p in enumerate(paragraphs, 1):
        print(f"段落{i}: {p}")
        results = completer.find_complete_context(p)
        if results:
            complete_content = results['complete_text']
            complete_paras.append(complete_content)
        else:
            complete_paras.append(p)
            print("未找到匹配的片段")
    return complete_paras

# 定位与问题最相关的文件
def find_relevant_file(question, userID, stock_name, model="doubao-seed-1-6-flash-250615"):
    # 定位最相关的文件
    user_folder_path = f'{userID}/{stock_name}'
    files = so.extract_all_files_from_folder(user_folder_path)
    # 将files下面的所有文件名都重命名，剔除多余的空格
    print(f"==========正在重命名文件==========")
    for file in files:
        new_file_name = file.replace(" ", "")
        # 大写转换为小写
        new_file_name = new_file_name.lower()
        os.rename(file, new_file_name)
    files = so.extract_all_files_from_folder(user_folder_path)
    print(files)
    # 定位文件
    def locate_file(question, files, model):
        llm = LLMManager(model=model)
        prompt = FILE_LOCATE_PROMPT.format(question=question, files=files)
        ans = ""
        for char in llm.generate_char_stream(prompt, temperature=0.0):
            print(char, end="", flush=True)
            ans += char
        print()
        file_path = get_json(ans)["file_path"]
        return file_path

    file_path = locate_file(question, files, model)
    print(file_path)
    # 提取文件名
    file_name = file_path.split("/")[-1]
    # 保存file_name这个PDF文件到共享笔记路径：{userID}/{stock_name}/announcement/{file_name}.pdf
    common_save_path = f"{userID}/{stock_name}/announcements"
    # 如果common_save_path不存在，则创建
    if not os.path.exists(common_save_path):
        os.makedirs(common_save_path)
    shutil.copy(file_path, f"{common_save_path}/{file_name}")
    print(f"文件路径已保存到：{common_save_path}/{file_name}")
    return file_path

# 将pdf转换为md
def pdf_to_md(pdf_file, userID, stock_name):
    output_md_file = f"{userID}/{stock_name}/total_texts.md"

    # 鲁棒配置：平衡速度和稳定性
    config = {
        "batch_size": 10,          # 每个批次包含的图片数量，较保守的批次大小
        "concurrent_per_batch": 8, # 较保守的并发数
        "vlm_batch_workers": 5,    # 较少的批次进程数
        "pdf_workers": 4,          # PDF转图片进程数
        "max_retries": 3,          # 最大重试次数
        "dpi": 200,               # 图片分辨率
        "pdf2image_batch_size": 5, # PDF转图片批次大小
        "cleanup_images": True
    }

    markdown_content = convert_pdf_to_markdown_v4_robust(
        pdf_path=pdf_file,
        output_md_path=output_md_file,
        **config
    )
    return markdown_content

# 博查搜索
class BochaSearch:
    def execute(self, **kwargs):
        keyword = kwargs.get("keyword")
        count = kwargs.get("count", 10)
        
        url = "https://api.bochaai.com/v1/web-search"
        payload = json.dumps({
            "query": keyword,
            "summary": True,
            "count": count
        })

        BOCHA_KEY = os.getenv("BOCHA_KEY")
        headers = {
        'Authorization': f'Bearer {BOCHA_KEY}',
        'Content-Type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        search_result = response.json()["data"]["webPages"]["value"]

        searched_content = ""
        for result in search_result:
            searched_content += result["name"] + "\n" + result["url"] + "\n" + result["snippet"] + "\n---------------------------\n"
        return searched_content

# tavily搜索
class TavilySearch:
    def execute(self, **kwargs):
        keyword = kwargs.get("keyword", "")
        count = kwargs.get("count", 10)
        
        search_api = TavilySearchAPI(
            max_concurrent_requests=10,  # 最大并发请求数
            request_timeout=10,  # 请求超时时间（秒）
            clean_content=True  # 是否清理内容
        )

        results = search_api.search(
            keyword,
            max_results=count,
            search_depth="advanced"
        )
        return results

# Duckduckgo搜索
class DuckduckgoSearch:
    def execute(self, **kwargs):
        keyword = kwargs.get("keyword", "")
        count = kwargs.get("count", 10)
        searcher = DuckDuckGoSearcher()
        results = searcher.search_and_get_content(keyword, count)

        full_content = ""
        for result in results["search_results"]:
            page_content = result["page_content"]
            if page_content and page_content["status"] == "success":
                url = page_content["url"]
                full_content += "链接：" + url + "\n" + page_content["content"] + "\n---------------------------\n"

        return full_content


SUMMARIZE_CONTENT_PROMPT = dedent("""
    # 你的任务
    总结我下面提供的长段文本，你需要保留所有核心内容，使用markdown输出总结。

    # 文本
    {content}

    # 输出要求
    - 使用标准的markdown格式
    - 如果有多个不同的内容，需要用不同的标题来区分
    - 需要有一个标题，参考输出：
    ### 标题1
    XXXXX(这里是一段尽可能详细的总结)
    url: 链接
    ---
    ### 标题2
    XXXXX(这里是一段尽可能详细的总结)
    url: 链接
    ...
""").strip()

# 网页总结
def llm_summarize(content, model):
    llm = LLMManager(model=model)
    
    prompt = SUMMARIZE_CONTENT_PROMPT.format(content=content)
    summary = ""
    for char in llm.generate_char_stream(prompt):
        print(char, end="", flush=True)
        summary += char
    print()
    return summary

# 勤奋搜索：数据预准备工作流
class DataPreparationWorkflow:
    def execute(self, **kwargs):
        """
        通用搜索：
        - 近五年年报、最新一期财报
        - 招股说明书
        - 辞职
        - 风险提示
        - 分红
        - 重大合同
        """
        count = kwargs.get("count", 20)
        userID = kwargs.get("userID", "")
        stock_name = kwargs.get("stock_name", "")
        folder_path = kwargs.get("folder_path", "")
        basic_keywords = [
            "年报",
            "招股说明书",
            # "辞职",
            # "风险提示",
            # "分红",
            # "重大合同",
        ]
        stock_specific_keywords = []
        for keyword in basic_keywords:
            stock_specific_keywords.append(f"{stock_name} {keyword}")
        for i,keyword in enumerate(stock_specific_keywords):
            print(f"==========正在搜索第{i+1}/{len(stock_specific_keywords)}个关键词：{keyword}==========")
            crawler = CninfoAdvancedCrawler(headless=True, download_dir=f'{userID}/{stock_name}')
            announcements = crawler.search_announcements(keyword, count)
            if announcements:
                crawler.save_announcement_list(announcements, 'announcement_list.txt')
                download_results = crawler.batch_download_announcements(announcements, filter_keywords=[])
                successful = sum(1 for path in download_results.values() if path is not None)
                notice = f"下载完成: 成功 {successful} 个，失败 {len(download_results) - successful} 个"
                print(notice)
            else:
                notice = "未找到相关公告"
                print(notice)

        # 获取folder_path下所有的文件的绝对路径
        file_paths = [
            f"{folder_path}/{file}" for file in os.listdir(folder_path) if file.endswith(".pdf") or file.endswith(".PDF")
        ]
        # 选出包含"年度报告"或者"招股说明书"的文件
        seleced_file_paths = [
            file_path for file_path in file_paths if "年度报告" in file_path or "招股说明书" in file_path or "年报" in file_path
        ]
        # 将seleced_file_paths的文件保存到files/{useID}/{stock_name}/announcements
        for file_path in seleced_file_paths:
            shutil.copy(file_path, f"{folder_path}/announcements")

        latest_annual_report_file_path = find_latest_annual_report(seleced_file_paths)
        latest_annual_report_text = extract_pdf_text(latest_annual_report_file_path)[:10000]

        # 提取file_path中的pdf名称
        pdf_name = latest_annual_report_file_path.split("/")[-1].split(".")[0]
        print(f"pdf_name: {pdf_name}")
        md_save_path = f"{folder_path}/announcements/{pdf_name}.md"
        print(f"md_save_path: {md_save_path}")
        markdown_content = pdf_to_md(latest_annual_report_file_path, md_save_path, stock_name)
        print(f"markdown_content已保存到：{md_save_path}")

        bocha_search = BochaSearch()
        bocha_results = bocha_search.execute(**kwargs)[:10000]
        print(f"bocha搜索总字数：{len(bocha_results)}")

        indicator = "按年度"

        fin_debt_df, financial_abstract, financial_analysis_indicator = prepare_data(stock_name, indicator, start_year="2020", folder_path=f"{folder_path}/data")
        preview_fin_debt_df =  preview_dataframe_as_blocks(fin_debt_df)
        preview_financial_abstract =  preview_dataframe_as_blocks(financial_abstract)
        preview_financial_analysis_indicator =  preview_dataframe_as_blocks(financial_analysis_indicator)

        data_preview = f"""
        # 资产负债表
        {preview_fin_debt_df}
        # 利润表摘要
        {preview_financial_abstract}
        # 财务指标分析
        {preview_financial_analysis_indicator}
        """


        total_preview = f"""
        # 股票数据预览
        {data_preview}

        # 最新财报部分信息
        {latest_annual_report_text}

        # 互联网搜索信息
        {bocha_results}
        """
        print(f"total_preview总字数：{len(total_preview)}")
        # 保存到文件
        with open(f"{folder_path}/total_preview.md", "w", encoding="utf-8") as f:
            f.write(total_preview)
        return total_preview

if __name__ == "__main__":
    userID = "fizz"
    stock_name = "北方华创"
    keyword = f"{stock_name} 主营业务"
    folder_path = f"{userID}/{stock_name}"
    announcement_path = f"{folder_path}/announcements"
    if not os.path.exists(announcement_path):
        os.makedirs(announcement_path)

    kwargs = {
        "keyword": keyword,
        "count": 20,
        "userID": userID,
        "stock_name": stock_name,
        "folder_path": folder_path,
    }

    cninfo_crawler = DataPreparationWorkflow()
    result = cninfo_crawler.execute(**kwargs)
