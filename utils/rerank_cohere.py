import cohere
from typing import List, Dict, Union
from dotenv import load_dotenv
import os

load_dotenv()

COHERE_API_KEY = os.getenv("COHERE_API_KEY")

def rerank_documents_with_cohere(
    api_key: str,
    query: str,
    documents_texts: List[str],
    top_n_final: int = 5,
    model_name: str = "rerank-english-v3.0" # 或者 "rerank-multilingual-v3.0" 用于多语言
) -> List[Dict[str, Union[str, float]]]:
    """
    使用Cohere Rerank API对文档列表进行重排序，并返回最相关的top_n_final个文档。

    Args:
        api_key (str): 你的Cohere API密钥。
        query (str):用户的查询语句。
        documents_texts (List[str]): 初步检索到的文档文本列表 (例如10个候选文档)。
        top_n_final (int): 重排序后希望返回的最相关文档数量。
        model_name (str): 要使用的Cohere Rerank模型名称。

    Returns:
        List[Dict[str, Union[str, float]]]: 一个包含重排序后文档及其相关性得分的列表，
                                            按相关性从高到低排序。
                                            每个字典包含 "document_text" 和 "relevance_score"。
    """
    if not documents_texts:
        print("警告：输入的文档列表为空。")
        return []
    if not query:
        print("警告：输入的查询为空。")
        # 根据情况，可能返回空列表或所有文档（未排序）
        return [{"document_text": doc, "relevance_score": 0.0} for doc in documents_texts]


    co = cohere.Client(api_key)

    try:
        # Cohere API 的 rerank 方法可以直接接收文档文本列表
        # top_n 参数指定了从 rerank 结果中返回多少个文档
        response = co.rerank(
            model=model_name,
            query=query,
            documents=documents_texts, # 直接传递文档文本列表
            top_n=top_n_final
        )

        # response.results 已经按照相关性排序，并且只包含 top_n_final 个结果
        # 每个 result 对象包含 'index' (原始列表中的索引) 和 'relevance_score'
        reranked_results = []
        for res in response.results:
            # res.index 是文档在原始 documents_texts 列表中的索引
            original_document_text = documents_texts[res.index]
            reranked_results.append({
                "document_text": original_document_text,
                "relevance_score": res.relevance_score
            })
        
        return reranked_results

    except cohere.CohereAPIError as e: # type: ignore
        print(f"Cohere API 错误: {e}")
        print(f"  错误详情: {e.message}") # CohereAPIError 有 message 属性
        if hasattr(e, 'http_status'):
            print(f"  HTTP 状态码: {e.http_status}")
        if hasattr(e, 'body'):
            print(f"  响应体: {e.body}")
        return []
    except Exception as e:
        print(f"发生未知错误: {e}")
        return []

# --- 示例用法 ---
if __name__ == "__main__":
    # 假设这是你的查询
    example_query = "全球变暖对北极熊的影响"

    # 假设这是通过向量检索等方式初步召回的10个文档的文本内容
    # 在实际应用中，这些文档通常是与查询有一定相关性的候选文档
    candidate_documents = [
        "北极熊是生活在北极地区的食肉动物。",
        "气候变化导致北极海冰融化速度加快。",
        "全球变暖是一个严重的环境问题，影响着全球生态系统。",
        "研究表明，海冰减少直接威胁到北极熊的捕食和生存。",
        "企鹅主要生活在南半球，尤其是南极洲。",
        "可再生能源的发展有助于减缓全球变暖的趋势。",
        "北极熊依赖海冰平台捕猎海豹。",
        "国际社会正努力通过减少温室气体排放来应对气候变化。",
        "一些动物园也在进行北极熊的繁育计划。",
        "海洋酸化是全球变暖的另一个后果。"
    ]

    print(f"查询: {example_query}")
    print(f"候选文档数量: {len(candidate_documents)}")
    print("-" * 30)

    # 调用函数进行重排序，获取最相关的5个文档
    top_5_relevant_docs = rerank_documents_with_cohere(
        api_key=COHERE_API_KEY, # type: ignore
        query=example_query,
        documents_texts=candidate_documents,
        top_n_final=5,
        model_name="rerank-multilingual-v3.0" # 使用多语言模型，因为它对中文查询和示例文档更合适
    )

    if top_5_relevant_docs:
        print(f"\n重排序后最相关的 Top 5 文档:")
        for i, item in enumerate(top_5_relevant_docs):
            print(f"{i+1}. 相关性得分: {item['relevance_score']:.4f}") # type: ignore
            print(f"   文档: {item['document_text'][:100]}...") # type: ignore
            print("-" * 20)
    else:
        print("\n未能获取重排序结果。请检查API密钥和网络连接，或查看错误信息。")

