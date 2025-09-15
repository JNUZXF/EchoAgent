import os
import shutil
import asyncio
import logging
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from textwrap import dedent
from typing import List, Tuple, Dict, Any
from datetime import datetime
from tqdm.asyncio import tqdm
import json
import warnings

# 抑制openpyxl的颜色警告
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

from tools_agent.llm_manager import *
from tools_agent.json_tool import *
from utils.content_extract.pdf_reader_markitdown import *

class PaperProcessor:
    def __init__(self, model: str, transfer_path: str, max_concurrent: int = 3):
        self.model = model
        self.transfer_path = transfer_path
        self.max_concurrent = max_concurrent
        self.llm_manager = LLMManager(model)
        
        # 设置日志
        self.setup_logging()
        
        # 存储处理结果
        self.results = []
        
        # 创建目标文件夹
        if not os.path.exists(transfer_path):
            os.makedirs(transfer_path)
        
        # 获取已存在的论文文件（用于去重检查）
        self.existing_papers = [f for f in os.listdir(transfer_path) if f.endswith('.pdf')] if os.path.exists(transfer_path) else []
    
    def setup_logging(self):
        """设置日志系统"""
        # 创建logs文件夹
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 生成带时间戳的日志文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"paper_processing_{timestamp}.log")
        
        # 配置日志格式
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"开始论文处理任务 - 模型: {self.model}")
        self.logger.info(f"最大并发数: {self.max_concurrent}")
        self.logger.info(f"目标路径: {self.transfer_path}")

    async def get_md_async(self, pdf_file: str, executor: ThreadPoolExecutor) -> str:
        """异步获取PDF的markdown内容"""
        def _get_md():
            try:
                enable_ocr = False
                endpoint = None
                converter = PDFToMarkdown(enable_plugins=False, use_ocr=enable_ocr, docintel_endpoint=endpoint)
                md = converter.convert(pdf_file)[:10000]
                return md
            except Exception as e:
                raise Exception(f"PDF转换失败: {e}")
        
        loop = asyncio.get_event_loop()
        md = await loop.run_in_executor(executor, _get_md)
        return md

    async def transfer_pdf_async(self, pdf_file: str, executor: ThreadPoolExecutor) -> None:
        """异步转移PDF文件"""
        def _transfer():
            try:
                shutil.copy(pdf_file, os.path.join(self.transfer_path, os.path.basename(pdf_file)))
            except Exception as e:
                raise Exception(f"文件转移失败: {e}")
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, _transfer)

    async def judge_paper_relevence_async(self, PAPER_REQUIREMENTS: str, md: str) -> Tuple[bool, str, str]:
        """异步判断论文相关性，返回(是否相关, 完整回答, 质量评分)"""
        prompt = PAPER_SELECT_PROMPT.format(PAPER_REQUIREMENTS=PAPER_REQUIREMENTS, md=md)
        
        def _generate():
            try:
                ans = ""
                for char in self.llm_manager.generate_char_stream(prompt):
                    ans += char
                return ans
            except Exception as e:
                raise Exception(f"LLM调用失败: {e}")
        
        loop = asyncio.get_event_loop()
        # 使用单独的执行器来处理LLM调用
        with ThreadPoolExecutor(max_workers=1) as llm_executor:
            ans = await loop.run_in_executor(llm_executor, _generate)
        
        try:
            json_result = get_json(ans)
            is_related = json_result.get("is_related", False)
            quality_score = json_result.get("quality_score", "未知")
            return is_related, ans, quality_score
        except Exception as e:
            self.logger.error(f"解析LLM回答失败: {e}")
            self.logger.error(f"原始回答: {ans}")
            return False, ans, "解析失败"

    def extract_paper_title(self, pdf_file: str, md_content: str) -> str:
        """从PDF文件名或内容中提取论文标题"""
        # 首先尝试从文件名提取
        filename = os.path.basename(pdf_file)
        title_from_filename = filename.replace('.pdf', '').replace('_', ' ').replace('-', ' ')
        
        # 尝试从markdown内容的前几行提取标题
        lines = md_content.split('\n')[:10]
        for line in lines:
            line = line.strip()
            if line and len(line) > 10 and len(line) < 200:
                # 简单的标题识别逻辑
                if any(keyword in line.lower() for keyword in ['abstract', 'introduction']) == False:
                    if not line.startswith('#') and not line.startswith('*'):
                        return line
        
        return title_from_filename

    async def process_single_paper(self, pdf_file: str, PAPER_REQUIREMENTS: str, 
                                  executor: ThreadPoolExecutor, pbar: tqdm) -> Dict[str, Any]:
        """处理单个PDF文件的完整流程"""
        start_time = datetime.now()
        paper_name = os.path.basename(pdf_file)
        
        result = {
            'pdf_file': pdf_file,
            'paper_name': paper_name,
            'title': '',
            'is_related': False,
            'quality_score': '',
            'llm_response': '',
            'error': None,
            'processing_time': 0,
            'transferred': False
        }
        
        try:
            self.logger.info(f"开始处理: {paper_name}")
            
            # 异步获取markdown内容
            md = await self.get_md_async(pdf_file, executor)
            self.logger.debug(f"{paper_name} - PDF转换完成，内容长度: {len(md)}")
            
            # 提取论文标题
            title = self.extract_paper_title(pdf_file, md)
            result['title'] = title
            self.logger.info(f"{paper_name} - 提取标题: {title}")
            
            # 异步判断相关性
            is_related, llm_response, quality_score = await self.judge_paper_relevence_async(PAPER_REQUIREMENTS, md)
            result['is_related'] = is_related
            result['quality_score'] = quality_score
            result['llm_response'] = llm_response
            
            self.logger.info(f"{paper_name} - LLM判断完成: 相关={is_related}, 质量={quality_score}")
            
            if is_related:
                # 异步转移文件
                await self.transfer_pdf_async(pdf_file, executor)
                result['transferred'] = True
                self.logger.info(f"✓ {paper_name} - 相关论文，已转移到目标文件夹")
            else:
                self.logger.info(f"✗ {paper_name} - 不相关论文")
                
        except Exception as e:
            error_msg = str(e)
            result['error'] = error_msg
            self.logger.error(f"处理 {paper_name} 时出错: {error_msg}")
        
        finally:
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            result['processing_time'] = processing_time
            
            # 更新进度条
            pbar.set_postfix({
                'current': paper_name[:20] + '...' if len(paper_name) > 20 else paper_name,
                'related': '✓' if result['is_related'] else '✗'
            })
            pbar.update(1)
            
            self.logger.info(f"{paper_name} - 处理完成，耗时: {processing_time:.2f}秒")
        
        return result

    async def process_papers_batch(self, pdf_files: List[str], PAPER_REQUIREMENTS: str) -> List[Dict[str, Any]]:
        """批量处理PDF文件，控制并发数量"""
        
        # 创建信号量来控制并发数量
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # 创建进度条
        pbar = tqdm(total=len(pdf_files), desc="处理论文", 
                   bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}')
        
        async def process_with_semaphore(pdf_file):
            async with semaphore:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    return await self.process_single_paper(pdf_file, PAPER_REQUIREMENTS, executor, pbar)
        
        # 创建所有任务
        tasks = [process_with_semaphore(pdf_file) for pdf_file in pdf_files]
        
        # 并发执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 关闭进度条
        pbar.close()
        
        # 处理异常结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = {
                    'pdf_file': pdf_files[i],
                    'paper_name': os.path.basename(pdf_files[i]),
                    'title': '处理异常',
                    'is_related': False,
                    'quality_score': '',
                    'llm_response': '',
                    'error': str(result),
                    'processing_time': 0,
                    'transferred': False
                }
                final_results.append(error_result)
                self.logger.error(f"任务执行异常: {result}")
            else:
                final_results.append(result)
        
        return final_results

    def save_results_to_excel(self, results: List[Dict[str, Any]]) -> str:
        """将结果保存为Excel文件"""
        
        # 准备DataFrame数据
        df_data = []
        for result in results:
            # 确保质量评分是安全的字符串格式
            quality_score = str(result['quality_score']) if result['quality_score'] else '未知'
            
            df_data.append({
                '论文标题': str(result['title']) if result['title'] else '',
                'LLM判断': str(result['llm_response']) if result['llm_response'] else '',
                '相关与否': '是' if result['is_related'] else '否',
                '质量评分': quality_score,
                '文件名': str(result['paper_name']) if result['paper_name'] else '',
                '处理时间(秒)': round(result['processing_time'], 2),
                '是否转移': '是' if result['transferred'] else '否',
                '错误信息': str(result['error']) if result['error'] else ''
            })
        
        df = pd.DataFrame(df_data)
        
        # 生成带时间戳的Excel文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_file = f"论文筛选结果_{timestamp}.xlsx"
        
        # 保存Excel文件
        with pd.ExcelWriter(excel_file, engine='openpyxl', options={'remove_timezone': True}) as writer:
            df.to_excel(writer, sheet_name='筛选结果', index=False)
            
            # 调整列宽
            worksheet = writer.sheets['筛选结果']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        # 确保单元格值是字符串格式，避免格式冲突
                        cell_value = str(cell.value) if cell.value is not None else ""
                        if len(cell_value) > max_length:
                            max_length = len(cell_value)
                    except Exception:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        self.logger.info(f"结果已保存到Excel文件: {excel_file}")
        return excel_file

    def print_summary(self, results: List[Dict[str, Any]]):
        """打印处理结果摘要"""
        total_count = len(results)
        relevant_count = sum(1 for r in results if r['is_related'])
        transferred_count = sum(1 for r in results if r['transferred'])
        error_count = sum(1 for r in results if r['error'])
        
        total_time = sum(r['processing_time'] for r in results)
        avg_time = total_time / total_count if total_count > 0 else 0
        
        print("\n" + "="*60)
        print("📊 处理结果摘要")
        print("="*60)
        print(f"📁 总文件数: {total_count}")
        print(f"✅ 相关文件数: {relevant_count}")
        print(f"📋 转移成功: {transferred_count}")
        print(f"❌ 处理错误: {error_count}")
        print(f"⏱️  总处理时间: {total_time:.2f}秒")
        print(f"⚡ 平均处理时间: {avg_time:.2f}秒/文件")
        print(f"📈 相关率: {(relevant_count/total_count*100):.1f}%" if total_count > 0 else "📈 相关率: 0%")
        print("="*60)

    async def run(self, pdf_files: List[str], PAPER_REQUIREMENTS: str):
        """运行主处理流程"""
        self.logger.info(f"开始批量处理 {len(pdf_files)} 个PDF文件")
        
        # 异步批量处理
        results = await self.process_papers_batch(pdf_files, PAPER_REQUIREMENTS)
        
        # 保存结果
        self.results = results
        
        # 保存到Excel
        excel_file = self.save_results_to_excel(results)
        
        # 打印摘要
        self.print_summary(results)
        
        self.logger.info("所有任务处理完成!")
        
        return results, excel_file

async def main():
    """主函数"""
    # 配置参数
    model = "doubao-seed-1-6-250615"
    root_path = "arxiv_papers"
    transfer_path = os.path.join(root_path, "selected_papers")
    max_concurrent = 12  # 控制并发数量，避免过度占用资源
    
    # 创建处理器
    processor = PaperProcessor(model, transfer_path, max_concurrent)
    
    # 获取所有PDF文件
    all_pdf_files = [os.path.join(root_path, f) for f in os.listdir(root_path) if f.endswith('.pdf')]
    
    if not all_pdf_files:
        print(f"❌ 在 {root_path} 文件夹中未找到PDF文件")
        return
    
    print(f"🔍 找到 {len(all_pdf_files)} 个PDF文件")
    
    # 检查去重情况
    existing_count = len(processor.existing_papers)
    if existing_count > 0:
        print(f"📋 发现 {existing_count} 个已存在的论文文件")
        
        # 过滤掉已存在的文件
        pdf_files = []
        skipped_count = 0
        for pdf_file in all_pdf_files:
            filename = os.path.basename(pdf_file)
            if filename not in processor.existing_papers:
                pdf_files.append(pdf_file)
            else:
                skipped_count += 1
                processor.logger.info(f"跳过已存在的文件: {filename}")
        
        print(f"⏭️  跳过 {skipped_count} 个已存在的文件")
        print(f"📝 需要处理 {len(pdf_files)} 个新文件")
        
        if not pdf_files:
            print("✅ 所有文件都已处理过，无需重复处理")
            return
    else:
        pdf_files = all_pdf_files
        print(f"📝 需要处理 {len(pdf_files)} 个文件")
    
    print(f"🚀 开始异步处理 (最大并发数: {max_concurrent})")
    
    # 运行处理流程
    results, excel_file = await processor.run(pdf_files, PAPER_REQUIREMENTS)
    
    print(f"\n📊 详细结果已保存到: {excel_file}")

# 常量定义
PAPER_SELECT_PROMPT = dedent("""
    # 你的任务
    根据我提供的PDF文本，判断这个PDF是否跟我的需求相关，然后输出特定的JSON

    # 需求
    {PAPER_REQUIREMENTS}

    # 论文内容
    {md}

    # 输出格式
    ## 内容分析
    这里输出论文的主要内容，以及关键结论
    ## 内容质量分析
    请你按照顶级期刊的水准，分析论文的质量，并给出三个等级的评分：
    - 高：论文质量非常高，符合顶级期刊的要求
    - 中：论文质量一般，符合一般期刊的要求
    - 低：论文质量较低，不符合期刊的要求
    ---
    然后给出论文的优缺点


    ## 论文是否相关
    这里输出论文是否与我的需求相关，以及原因（然后输出下面的JSON，key包含is_related和quality_score)
    {{
        "is_related": true/false,
        "quality_score": "高/中/低"
    }}
""").strip()

PAPER_REQUIREMENTS = dedent("""
    我想要筛选的论文必须是与LLM Agent相关

    # LLM Agent定义
    以大语言模型为底座，能进行计划、反思，能调用工具，具有记忆机制的系统

    # 需要筛选出来的论文
    - 与上述定义相关(不需要全部元素都有，但必须是以大语言模型为底座），比如提升计划能力，探讨记忆系统实现等等
    - AI Agent的应用相关，各行各业相关的应用都可以
    - AI Agent综述
    - 能提升AI Agent的能力
    - AI Agent的评测相关
    - 多智能体系统（以LLM为底座）相关

    # 不筛选的论文
    - 论文不能与具身智能相关
""").strip()

# 运行异步主函数
if __name__ == "__main__":
    asyncio.run(main())