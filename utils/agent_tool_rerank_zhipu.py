"""
智谱AI的rerank工具
"""
import os
import requests
import json
from typing import List, Dict, Tuple
from dotenv import load_dotenv

load_dotenv()

class ZhipuRerank:
    def __init__(self):
        """
        初始化智谱AI Rerank客户端
        
        Args:
            api_key: 智谱AI的API密钥
        """
        self.api_key = os.getenv("ZHIPU_API_KEY")
        self.base_url = "https://open.bigmodel.cn/api/paas/v4/rerank"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def rerank_passages(self, 
                       query: str, 
                       passages: List[str], 
                       top_n: int = None,
                       model: str = "rerank") -> List[Dict]:
        """
        使用智谱AI对段落进行重排序
        
        Args:
            query: 查询文本
            passages: 待排序的段落列表
            top_n: 返回前n个最相关的段落，如果为None则返回所有段落
            model: 使用的模型名称
            
        Returns:
            包含排序后段落信息的列表，每个元素包含：
            - text: 段落文本
            - score: 相关性分数
            - original_index: 原始索引
        """
        if not passages:
            return []
            
        if top_n is None:
            top_n = len(passages)
        else:
            top_n = min(top_n, len(passages))
        
        # 构建请求数据
        request_data = {
            "model": model,
            "query": query,
            "documents": passages
        }
        
        try:
            # 发送API请求
            response = requests.post(
                self.base_url,
                json=request_data,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            
            if "results" not in result:
                raise Exception(f"API响应格式错误: {result}")
            
            # 按相关性分数排序（从高到低）
            sorted_results = sorted(result["results"], key=lambda x: x["relevance_score"], reverse=True)
            
            # 处理结果，只返回前top_n个
            if top_n is not None:
                sorted_results = sorted_results[:top_n]
            
            ranked_results = []
            for item in sorted_results:
                ranked_results.append({
                    "text": passages[item["index"]],
                    "score": item["relevance_score"], 
                    "original_index": item["index"]
                })
            
            return ranked_results
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"API请求失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"响应解析失败: {str(e)}")
        except Exception as e:
            raise Exception(f"Rerank处理失败: {str(e)}")

def get_most_relevant_passages(
                             query: str, 
                             passages: List[str], 
                             top_n: int = 5) -> List[Dict]:
    """
    便捷函数：获取与query最相关的n个段落
    
    Args:
        api_key: 智谱AI的API密钥
        query: 查询文本
        passages: 段落列表
        top_n: 返回最相关的前n个段落
        
    Returns:
        排序后的段落列表，按相关性从高到低排序
        
    Example:
        >>> api_key = "your_zhipu_api_key"
        >>> query = "机器学习的应用"
        >>> passages = [
        ...     "深度学习是机器学习的一个重要分支",
        ...     "今天天气很好，适合外出",
        ...     "人工智能在医疗领域有广泛应用",
        ...     "机器学习算法可以用于数据分析"
        ... ]
        >>> results = get_most_relevant_passages(api_key, query, passages, 2)
        >>> for i, result in enumerate(results):
        ...     print(f"{i+1}. {result['text']} (分数: {result['score']:.3f})")
    """
    reranker = ZhipuRerank()
    results_list = reranker.rerank_passages(query, passages, top_n)
    reranked_texts = ""
    for i, result in enumerate(results_list, 1):
        result_score = result['score']
        result_text = result['text']
        reranked_texts += "分数：" + str(result_score) + "\n"
        reranked_texts += "内容：" + result_text + "\n===========\n"
    return results_list, reranked_texts

# 使用示例
if __name__ == "__main__":
    # 示例数据
    query = "梯度消失问题怎么解"
    
    passages = [
        "深度学习是机器学习的一个子领域，它模拟人脑神经网络的结构和功能。",
        "计算机视觉是人工智能的重要分支，主要研究如何让计算机理解和分析图像。",
        "卷积神经网络(CNN)在图像识别任务中表现出色，是深度学习的重要应用。",
        "自然语言处理技术可以帮助计算机理解和生成人类语言。",
        "深度学习在医疗影像诊断中发挥着越来越重要的作用。",
        "YOLO算法是一种高效的实时物体检测方法，广泛应用于计算机视觉。",
        "区块链技术在金融领域有着广泛的应用前景。",
        "ResNet网络架构解决了深度神经网络训练中的梯度消失问题。"
    ]
    
    try:
        # 获取最相关的3个段落
        results_list, reranked_texts = get_most_relevant_passages(query, passages, top_n=3)
        print(reranked_texts)
  
    except Exception as e:
        print(f"处理失败: {e}")
        print("\n请检查:")
        print("1. API密钥是否正确")
        print("2. 网络连接是否正常") 
        print("3. 智谱AI服务是否可用")


