# type: ignore
"""
知识库搜索工具
文件路径: agent/utils/agent_tool_kb_search.py
功能: 提供基于关键词的年报信息检索功能，支持向量化搜索和重排序
"""

import os
import pickle
from textwrap import dedent
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.embedding_doubao import VectorDatabase, VectorSearcher
from utils.rerank_cohere import rerank_documents_with_cohere, COHERE_API_KEY
from tools_agent.json_tool import get_json
from utils.agent_tool_split_paras import smart_paragraph_split_v2
from utils.agent_tool_rerank_zhipu import *

# 检索关键词生成
KEYWORDS_GEN_PROMPT = dedent("""
    # 你的任务
    你在帮我查询某只股票年报中的信息，现在我需要你根据用户的问题，生成全面的关键词，用于检索知识库。

    # 用户的问题
    {question}

    # 输出要求
    - 你的输出最后必须包含一个JSON，key是keywords，value是关键词列表List
    参考：
    {{
        "keywords": ["关键词1", "关键词2", "关键词3"]
    }}

    # 思考要求
    - 你必须思考我的问题可能包含哪几个方向，如果需要研究这个问题需要哪些信息，然后生成关键词
    - 你的输出必须包含两个部分：1. 思考过程；2. 关键词列表JSON
    格式如下：
    # 分析
    XXXX

    # JSON
    XXX

    现在，请开始：
""").strip()

# 获取文件夹下的所有md文件
def get_md_file_paths(folder_path):
    md_file_paths = []
    for file in os.listdir(folder_path):
        if file.endswith(".md"):
            md_file_paths.append(os.path.join(folder_path, file))
    return md_file_paths

# 分段
def rag_chunking(md_file_path, target_length=5000): 
    """【模块化设计】对MD文件进行智能分段"""
    with open(md_file_path, "r", encoding="utf-8") as f:
        markdown_content = f.read()
    
    # 【模块化设计】使用已导入的分段模块
    paragraphs = smart_paragraph_split_v2(markdown_content, target_length=target_length)
    return paragraphs

def get_reranked_results(searched_texts, query, top_n_final):
    """【模块化设计】对搜索结果进行重排序"""
    # 重排序，获取最相关的文档
    top_relevant_docs = rerank_documents_with_cohere(
        api_key=COHERE_API_KEY,
        query=query,
        documents_texts=searched_texts,
        top_n_final=top_n_final,
        model_name="rerank-multilingual-v3.0"  # 使用多语言模型，对中文更友好
    )
    
    FINAL_SEARCHED_TEXTS = []
    if top_relevant_docs:
        for item in top_relevant_docs:
            FINAL_SEARCHED_TEXTS.append(item['document_text'])
    
    return FINAL_SEARCHED_TEXTS

def get_reranked_results_zhipu(searched_texts, query, top_n_final):
    results_list, _ = get_most_relevant_passages(query, searched_texts, top_n=top_n_final)
    FINAL_SEARCHED_TEXTS = []
    if results_list:
        for i, item in enumerate(results_list):
            FINAL_SEARCHED_TEXTS.append(item['text'])
    else:
        FINAL_SEARCHED_TEXTS = []
    return FINAL_SEARCHED_TEXTS

def get_bge_reranked_results(passages, query, top_k):
    LOCAL_MODEL_PATH = "agent/models/bge-reranker-v2-m3" 
    reranker = get_reranker_instance(local_model_path=LOCAL_MODEL_PATH)   
    results = reranker.rerank_passages(query, passages, top_k)
    return results

# 基于问题生成全面的关键词，用于检索知识库
def generate_keywords(question, llm):
    """【模块化设计】基于问题生成检索关键词"""
    prompt = KEYWORDS_GEN_PROMPT.format(question=question)
    keywords = llm.generate_stream_conversation([{"role": "user", "content": prompt}])
    ans = ""
    for char in keywords:
        ans += char
    
    # 【模块化设计】使用已导入的JSON工具
    keywords_data = get_json(ans)
    keywords = keywords_data["keywords"] if keywords_data else []
    return keywords

# type: ignore
def get_embedding_searched_results(keywords, searcher, vector_save_path=None):
    """获取embbedding+关键词检索的结果"""
    TOTAL_EMBEDDING_SEARCHED_PARAS_LIST = []

    def search_keyword(keyword, index):
        results = searcher.search(keyword, top_k=10, threshold=0)
        searched_texts = []
        for i, (text, score) in enumerate(results, 1):
            searched_texts.append(text)
        return searched_texts

    def get_keyword_texts(keywords, vector_save_path):  # 获取关键词检索到的文本
        with open(vector_save_path, 'rb') as f:
            data = pickle.load(f)
        texts = data['texts']
        keywords_texts_list = [text for text in texts if any(keyword in text for keyword in keywords)]
        return keywords_texts_list
        
    # 快速向量检索
    max_workers = min(32, len(keywords)) 
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(search_keyword, keyword, i): i for i, keyword in enumerate(keywords)}
        for future in as_completed(futures):
            result = future.result()
            TOTAL_EMBEDDING_SEARCHED_PARAS_LIST.extend(result)

    # 关键词检索
    keywords_texts_list = get_keyword_texts(keywords, vector_save_path)
    TOTAL_EMBEDDING_SEARCHED_PARAS_LIST.extend(keywords_texts_list)
    TOTAL_EMBEDDING_SEARCHED_PARAS_LIST = list(set(TOTAL_EMBEDDING_SEARCHED_PARAS_LIST))

    print(f"总共检索到{len(TOTAL_EMBEDDING_SEARCHED_PARAS_LIST)}个段落")
    return TOTAL_EMBEDDING_SEARCHED_PARAS_LIST


def get_rag_reranked_results(TOTAL_EMBEDDING_SEARCHED_PARAS_LIST, query, top_n_final, bge=False):
    if bge:
        reranked_results = get_bge_reranked_results(TOTAL_EMBEDDING_SEARCHED_PARAS_LIST, query, top_k=top_n_final)
        FINAL_SEARCHED_TEXTS = ""
        for i, text in enumerate(reranked_results):
            FINAL_SEARCHED_TEXTS += f"==检索到的段落{i+1}== \n{text[0]}\n"
    else:
        reranked_results = get_reranked_results_zhipu(TOTAL_EMBEDDING_SEARCHED_PARAS_LIST, query, top_n_final=top_n_final)
        FINAL_SEARCHED_TEXTS = ""
        for i, text in enumerate(reranked_results):
            FINAL_SEARCHED_TEXTS += f"==检索到的段落{i+1}== \n{text}\n"

    return FINAL_SEARCHED_TEXTS, reranked_results

# 将文本-向量列表保存到pkl
def save_paras_to_pkl(
        vector_save_path, 
        md_texts, 
        max_workers=16, 
        embedding_model="doubao-embedding-vision-250328",
        model_type="doubao",
        bge_batch_size=4,
        bge_model_path=None
    ):
    """【模块化设计】保存文本向量到pickle文件"""
    # 如果vector_save_path已经存在，则跳过
    if os.path.exists(vector_save_path):
        print(f"向量数据库已存在，跳过向量化")
        return None
    
    # 【模块化设计】使用已导入的嵌入模块
    db = VectorDatabase(save_path=vector_save_path)
    db.batch_vectorize(
        texts=md_texts,
        max_workers=max_workers,
        model=embedding_model,
        model_type=model_type, 
        bge_batch_size=bge_batch_size,  
        bge_model_path=bge_model_path
    )

    # 保存向量数据库
    db.save_to_file()
    return db

# 获取文件夹下的所有md文件并批量向量化
def batch_vectorize_files(folder_path, vector_save_path):
    md_file_paths = get_md_file_paths(folder_path)

    # 汇总所有内容
    md_texts = []
    for md_file_path in md_file_paths:
        temp_paras = rag_chunking(md_file_path, target_length=4000)
        final_paras = []    
        # 将md_file_path增加到每个段落的开头
        for para in temp_paras:
            final_paras.append(f"{md_file_path}\n{para}")
        md_texts.extend(final_paras)
    print(len(md_texts))

    save_paras_to_pkl(vector_save_path, md_texts)

def rag_kb_search(
    query,
    top_n_final=5,
    embeddding_model="doubao-embedding-vision-250328", 
    model_type="doubao", 
    keywords=None,
    vector_save_path=None,
    ):
    """【模块化设计】执行RAG知识库搜索"""
    
    searcher = VectorSearcher(
        db_path=vector_save_path,
        model=embeddding_model, 
        model_type=model_type,  
        bge_model_path=None 
    )

    searcher.load_database()

    embedding_searched_results = get_embedding_searched_results(
        keywords=keywords, 
        searcher=searcher, 
        vector_save_path=vector_save_path
    )

    FINAL_SEARCHED_TEXTS, reranked_results = get_rag_reranked_results(
        TOTAL_EMBEDDING_SEARCHED_PARAS_LIST=embedding_searched_results,
        query=query,
        top_n_final=top_n_final,
        bge=False
    )
    return FINAL_SEARCHED_TEXTS, reranked_results


class KBSearch:
    def execute(self, **kwargs):
        # 问题
        self.query = kwargs.get("query", None)
        self.embedding_model = kwargs.get("embedding_model", "doubao-embedding-vision-250328")
        self.mdvec_path = kwargs.get("mdvec_path", None)
        self.top_n = kwargs.get("top_n", 10)
        self.keywords = kwargs.get("keywords", None)
        self.model_type = kwargs.get("model_type", "doubao")
        FINAL_SEARCHED_TEXTS, keyword_results_list = rag_kb_search(
            query=self.query,
            top_n_final=self.top_n,
            embeddding_model=self.embedding_model, 
            model_type=self.model_type, 
            keywords=self.keywords,
            vector_save_path=self.mdvec_path,
            )
        return FINAL_SEARCHED_TEXTS, keyword_results_list

def get_pkl_files_from_directory(directory_path):
    """【模块化设计】获取目录下所有pkl文件路径"""
    pkl_files = []
    try:
        for file in os.listdir(directory_path):
            if file.endswith(".pkl"):
                pkl_files.append(os.path.join(directory_path, file))
        print(f"[LOG] 在 {directory_path} 中找到 {len(pkl_files)} 个pkl文件")
    except Exception as e:
        print(f"[ERROR] 读取目录 {directory_path} 失败: {e}")
    return pkl_files

def search_single_pkl_file(pkl_file_path, query, keywords, embedding_model, model_type, top_n_per_file):
    """【模块化设计】搜索单个pkl文件的函数，用于并行处理"""
    try:
        print(f"[LOG] 开始搜索文件: {pkl_file_path}")
        
        # 创建搜索器
        searcher = VectorSearcher(
            db_path=pkl_file_path,
            model=embedding_model, 
            model_type=model_type,  
            bge_model_path=None 
        )
        searcher.load_database()
        
        # 获取搜索结果
        embedding_searched_results = get_embedding_searched_results(
            keywords=keywords, 
            searcher=searcher, 
            vector_save_path=pkl_file_path
        )
        
        # 重排序并获取topN结果
        _, reranked_results = get_rag_reranked_results(
            TOTAL_EMBEDDING_SEARCHED_PARAS_LIST=embedding_searched_results,
            query=query,
            top_n_final=top_n_per_file,
            bge=False
        )
        
        # 为每个结果添加来源信息
        file_name = os.path.basename(pkl_file_path)
        results_with_source = []
        for result in reranked_results:
            result_with_source = {
                'text': result,
                'source_file': file_name,
                'source_path': pkl_file_path
            }
            results_with_source.append(result_with_source)
        
        print(f"[LOG] 文件 {file_name} 搜索完成，找到 {len(results_with_source)} 个相关段落")
        return results_with_source
        
    except Exception as e:
        print(f"[ERROR] 搜索文件 {pkl_file_path} 时出错: {e}")
        return []

def rag_kb_search_multi_files(
    query,
    pkl_files_or_directory,
    keywords=None, 
    top_n_per_file=3,
    final_top_n=10,
    embedding_model="doubao-embedding-vision-250328",
    model_type="doubao",
    max_workers=4,
    auto_generate_keywords=False,
    llm_manager=None
):
    """
    【模块化设计】【性能优化】批量搜索多个pkl向量数据库文件
    
    Args:
        query: 查询问题
        pkl_files_or_directory: pkl文件路径列表 或 包含pkl文件的目录路径
        keywords: 关键词列表，如果为None且auto_generate_keywords=True则自动生成
        top_n_per_file: 每个文件返回的top结果数量
        final_top_n: 最终返回的结果数量  
        embedding_model: 嵌入模型名称
        model_type: 模型类型
        max_workers: 并行处理的最大工作线程数
        auto_generate_keywords: 是否自动生成关键词
        llm_manager: LLM管理器，用于自动生成关键词
        
    Returns:
        tuple: (合并后的搜索文本, 详细结果列表)
    """
    
    print(f"[LOG] 开始批量KB搜索: {query}")
    
    # 【模块化设计】处理输入参数，支持目录路径或文件列表
    if isinstance(pkl_files_or_directory, str):
        # 如果是字符串，判断是文件还是目录
        if os.path.isdir(pkl_files_or_directory):
            pkl_files = get_pkl_files_from_directory(pkl_files_or_directory)
        else:
            pkl_files = [pkl_files_or_directory]
    else:
        # 如果是列表，直接使用
        pkl_files = pkl_files_or_directory
    
    if not pkl_files:
        print("[ERROR] 没有找到可搜索的pkl文件")
        return "", []
    
    # 【模块化设计】自动生成关键词
    if auto_generate_keywords and keywords is None and llm_manager is not None:
        try:
            keywords = generate_keywords(query, llm_manager)
            print(f"[LOG] 自动生成关键词: {keywords}")
        except Exception as e:
            print(f"[ERROR] 自动生成关键词失败: {e}")
            keywords = []
    
    # 【性能优化】设置默认关键词和工作线程数
    if keywords is None:
        keywords = []
    
    max_workers = min(max_workers, len(pkl_files))
    all_results = []
    
    # 【性能优化】并行搜索多个pkl文件
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有搜索任务
        future_to_file = {
            executor.submit(
                search_single_pkl_file, 
                pkl_file, 
                query, 
                keywords, 
                embedding_model, 
                model_type, 
                top_n_per_file
            ): pkl_file 
            for pkl_file in pkl_files
        }
        
        # 收集结果
        for future in as_completed(future_to_file):
            pkl_file = future_to_file[future]
            try:
                results = future.result()
                all_results.extend(results)
            except Exception as e:
                print(f"[ERROR] 处理文件 {pkl_file} 的结果时出错: {e}")
    
    print(f"[LOG] 所有文件搜索完成，共找到 {len(all_results)} 个段落")
    
    # 【模块化设计】提取文本进行最终重排序
    if all_results:
        all_texts = [result['text'] for result in all_results]
        
        # 【性能优化】最终重排序，获取最相关的结果
        try:
            final_reranked_texts = get_reranked_results(
                all_texts, 
                query, 
                top_n_final=final_top_n
            )
            
            # 【模块化设计】匹配重排序后的文本与原始结果，保留来源信息
            final_results_with_source = []
            for reranked_text in final_reranked_texts:
                for result in all_results:
                    if result['text'] == reranked_text:
                        final_results_with_source.append(result)
                        break
            
            # 【日志】格式化最终输出
            FINAL_SEARCHED_TEXTS = ""
            for i, result in enumerate(final_results_with_source):
                FINAL_SEARCHED_TEXTS += f"==检索到的段落{i+1}== [来源: {result['source_file']}]\n{result['text']}\n\n"
            
            print(f"[LOG] 批量搜索完成，最终返回 {len(final_results_with_source)} 个段落")
            return FINAL_SEARCHED_TEXTS, final_results_with_source
            
        except Exception as e:
            print(f"[ERROR] 最终重排序失败: {e}")
            # 如果重排序失败，返回原始结果
            FINAL_SEARCHED_TEXTS = ""
            for i, result in enumerate(all_results[:final_top_n]):
                FINAL_SEARCHED_TEXTS += f"==检索到的段落{i+1}== [来源: {result['source_file']}]\n{result['text']}\n\n"
            
            return FINAL_SEARCHED_TEXTS, all_results[:final_top_n]
    else:
        print("[LOG] 没有找到相关结果")
        return "", []

class MultiKBSearch:
    """【模块化设计】多知识库搜索类"""
    
    def execute(self, **kwargs):
        """
        执行多知识库搜索
        
        Args:
            query: 查询问题
            pkl_files_or_directory: pkl文件路径列表或目录路径
            keywords: 关键词列表
            top_n_per_file: 每个文件的top结果数量，默认10   
            final_top_n: 最终结果数量，默认8
            embedding_model: 嵌入模型，默认"doubao-embedding-vision-250328"
            model_type: 模型类型，默认"doubao"
            max_workers: 最大工作线程数，默认4
            auto_generate_keywords: 是否自动生成关键词，默认False
            llm_manager: LLM管理器
        """
        self.query = kwargs.get("query", None)
        self.embedding_model = kwargs.get("embedding_model", "doubao-embedding-vision-250328")
        self.mdvec_path = kwargs.get("mdvec_path", None)
        self.top_n_per_file = kwargs.get("top_n_per_file", 10)
        self.top_n = kwargs.get("top_n", 8)
        self.keywords = kwargs.get("keywords", None)
        self.max_workers = kwargs.get("max_workers", 4)
        FINAL_SEARCHED_TEXTS, results = rag_kb_search_multi_files(
            query=self.query,
            pkl_files_or_directory=self.mdvec_path,  # 目录路径
            keywords=self.keywords,
            top_n_per_file=self.top_n_per_file,    # 每个文件返回结果
            final_top_n=self.top_n,       # 最终返回结果  
            max_workers=self.max_workers,        # 并行处理文件
        )
        results_list = []
        for result in results:
            results_list.append(result["text"])
        return FINAL_SEARCHED_TEXTS, results_list

def _demo_usage():
    """【测试策略】演示KB搜索工具的使用方法"""
    top_n = 3
    vector_save_path = r"D:\AgentBuilding\FinAgent\agent\files\sam\招商银行\vectors\招商银行： 年度报告2023_vectors.pkl"
    embedding_model = "doubao-embedding-vision-250328"
    query = "利润表和现金流量表"
    kwargs = {
        "query": query,
        "embedding_model": embedding_model,
        "mdvec_path": vector_save_path,
        "top_n": top_n, 
        "keywords": ["利润表"],
    }

    # 【日志】记录演示过程
    print(f"[DEMO] 开始KB搜索演示: {query}")
    FINAL_SEARCHED_TEXTS, reranked_results = KBSearch().execute(**kwargs)
    print(f"[DEMO] 搜索结果: {len(FINAL_SEARCHED_TEXTS)} 个文档")
    print(FINAL_SEARCHED_TEXTS)
    print(reranked_results)

def _demo_multi_usage():
    """【测试策略】演示多KB搜索工具的使用方法"""
    query = "利润表和现金流量表"
    
    # 测试目录方式
    vectors_directory = r"D:\AgentBuilding\FinAgent\agent\files\sam\招商银行\vectors"
    
    kwargs = {
        "query": query,
        "pkl_files_or_directory": vectors_directory,  # 或者使用 pkl_files
        "keywords": ["利润表", "现金流量表"],
        "top_n_per_file": 3,
        "final_top_n": 5,
        "embedding_model": "doubao-embedding-vision-250328",
        "model_type": "doubao",
        "max_workers": 4
    }
    
    print(f"[DEMO] 开始多KB搜索演示: {query}")
    FINAL_SEARCHED_TEXTS, results = MultiKBSearch().execute(**kwargs)
    print(f"[DEMO] 搜索结果: {len(results)} 个文档")
    print(FINAL_SEARCHED_TEXTS)

if __name__ == "__main__":
    # 【代码组织原则】确保模块代码只在直接运行时执行
    print("选择演示模式:")
    print("1. 单KB搜索演示")
    print("2. 多KB搜索演示")
    choice = input("请输入选择 (1/2): ").strip()
    
    if choice == "1":
        _demo_usage()
    elif choice == "2":
        _demo_multi_usage()
    else:
        print("无效选择，运行单KB搜索演示")
        _demo_usage()


