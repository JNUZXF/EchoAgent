"""
BGE Reranker工具类
功能：提供文本重排序功能，使用BGE-reranker-v2-m3模型对文本段落进行相关性排序
路径：agent/utils/agent_tool_bge_reranker.py
支持从HuggingFace Hub缓存结构或直接模型文件夹加载本地模型
"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import numpy as np
from typing import List, Tuple, Optional
import logging
import os
import glob

# 全局变量，用于缓存reranker实例
_reranker_instance = None

class BGEReranker:
    def __init__(self, 
                 model_name: str = "BAAI/bge-reranker-v2-m3", 
                 local_model_path: Optional[str] = None,
                 cache_dir: Optional[str] = None,
                 device: Optional[str] = None):
        """
        【模块化设计】初始化BGE Reranker模型
        
        Args:
            model_name: 模型名称，默认为BGE-reranker-v2-m3
            local_model_path: 本地模型路径，支持HuggingFace Hub缓存结构
            cache_dir: 缓存目录，模型下载后保存的位置
            device: 设备类型，如果为None则自动选择
        """
        self.model_name = model_name
        self.local_model_path = local_model_path
        self.cache_dir = cache_dir
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = None
        self.model = None
        self._model_loaded = False
        
    def load_model(self):
        """
        【延迟加载】加载模型和tokenizer
        """
        if self._model_loaded:
            return
            
        logging.info(f"开始加载BGE Reranker模型...")
        logging.info(f"设备类型: {self.device}")
        
        # 【分层架构】分离模型路径解析逻辑
        model_path = self._resolve_model_path(self.local_model_path, self.model_name, self.cache_dir)
        
        # 加载tokenizer和模型
        try:
            logging.info(f"从路径加载模型: {model_path}")
            
            if self.local_model_path and os.path.exists(self.local_model_path):
                # 本地加载
                self.tokenizer = AutoTokenizer.from_pretrained(model_path)
                self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
            else:
                # 在线加载，指定缓存目录
                self.tokenizer = AutoTokenizer.from_pretrained(
                    model_path, 
                    cache_dir=self.cache_dir
                )
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    model_path, 
                    cache_dir=self.cache_dir
                )
            
            self.model.to(self.device)
            self.model.eval()
            self._model_loaded = True
            logging.info(f"模型已成功加载到 {self.device}")
            
        except Exception as e:
            logging.error(f"模型加载失败: {e}")
            logging.error(f"尝试的模型路径: {model_path}")
            raise
    
    def _resolve_model_path(self, local_model_path: Optional[str], model_name: str, cache_dir: Optional[str]) -> str:
        """
        【单一职责原则】解析模型路径，支持HuggingFace Hub缓存结构
        
        Args:
            local_model_path: 本地模型路径
            model_name: 模型名称
            cache_dir: 缓存目录
            
        Returns:
            str: 解析后的模型路径
        """
        if local_model_path and os.path.exists(local_model_path):
            # 检查是否是HuggingFace Hub缓存结构
            snapshots_dir = os.path.join(local_model_path, "snapshots")
            if os.path.exists(snapshots_dir):
                # 获取snapshots下的模型文件夹（通常是哈希值命名的）
                snapshot_folders = [f for f in os.listdir(snapshots_dir) 
                                  if os.path.isdir(os.path.join(snapshots_dir, f))]
                if snapshot_folders:
                    # 取最新的快照（按修改时间排序）
                    snapshot_paths = [os.path.join(snapshots_dir, f) for f in snapshot_folders]
                    latest_snapshot = max(snapshot_paths, key=os.path.getmtime)
                    
                    # 验证是否包含必要的模型文件
                    if self._is_valid_model_dir(latest_snapshot):
                        logging.info(f"从HuggingFace Hub缓存加载模型: {latest_snapshot}")
                        return latest_snapshot
                    else:
                        logging.warning(f"快照目录不包含有效模型文件: {latest_snapshot}")
            
            # 检查是否是直接的模型文件夹
            if self._is_valid_model_dir(local_model_path):
                logging.info(f"从本地路径加载模型: {local_model_path}")
                return local_model_path
            else:
                logging.warning(f"本地模型路径不包含有效模型文件: {local_model_path}")
        
        # 使用在线模型
        logging.info(f"从HuggingFace Hub加载模型: {model_name}")
        return model_name
    
    def _is_valid_model_dir(self, model_dir: str) -> bool:
        """
        【单一职责原则】检查目录是否包含有效的模型文件
        
        Args:
            model_dir: 模型目录路径
            
        Returns:
            bool: 是否包含有效模型文件
        """
        required_files = ["config.json"]
        model_files = ["model.safetensors", "pytorch_model.bin"]
        
        # 检查必需文件
        for file in required_files:
            if not os.path.exists(os.path.join(model_dir, file)):
                logging.warning(f"缺少必需文件: {file}")
                return False
        
        # 检查模型文件（至少有一个）
        has_model_file = any(os.path.exists(os.path.join(model_dir, file)) for file in model_files)
        if not has_model_file:
            logging.warning(f"缺少模型文件: {model_files}")
            return False
        
        return True

    def rerank_passages(
        self, 
        query: str, 
        passages: List[str], 
        top_k: Optional[int] = None,
        batch_size: int = 32,
        max_length: int = 512
    ) -> List[Tuple[str, float, int]]:
        """对段落进行重排序"""
        if not self._model_loaded:
            self.load_model()
            
        if not passages:
            return []
        
        pairs = [[query, passage] for passage in passages]
        scores = []
        
        with torch.no_grad():
            for i in range(0, len(pairs), batch_size):
                batch_pairs = pairs[i:i + batch_size]
                
                inputs = self.tokenizer(
                    batch_pairs,
                    padding=True,
                    truncation=True,
                    return_tensors='pt',
                    max_length=max_length
                ).to(self.device)
                
                outputs = self.model(**inputs)
                batch_scores = outputs.logits.view(-1).float()
                scores.extend(batch_scores.cpu().numpy())
        
        results = [
            (passages[i], float(scores[i]), i) 
            for i in range(len(passages))
        ]
        
        results.sort(key=lambda x: x[1], reverse=True)
        
        if top_k is not None:
            results = results[:top_k]
            
        return results


def get_reranker_instance(local_model_path: Optional[str] = None, device: Optional[str] = None) -> BGEReranker:
    """
    【单例模式】获取BGEReranker的单例
    
    Args:
        local_model_path: 本地模型路径
        device: 设备类型
        
    Returns:
        BGEReranker: reranker实例
    """
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = BGEReranker(local_model_path=local_model_path, device=device)
    return _reranker_instance

def rerank_with_local_bge(
    query: str, 
    passages: List[str], 
    local_model_path: str = "agent/models/bge-reranker-v2-m3",
    top_k: Optional[int] = None,
    device: Optional[str] = None
) -> List[Tuple[str, float, int]]:
    """
    【便捷函数】使用本地BGE reranker对段落进行重排序
    
    Args:
        query: 查询文本
        passages: 待排序的段落列表
        local_model_path: 本地模型路径，支持HuggingFace Hub缓存结构
        top_k: 返回前k个结果
        device: 设备类型
        
    Returns:
        List[Tuple[str, float, int]]: 排序后的结果列表
    """
    reranker = get_reranker_instance(local_model_path=local_model_path, device=device)
    return reranker.rerank_passages(query, passages, top_k)


def download_and_save_model(
    model_name: str = "BAAI/bge-reranker-v2-m3",
    save_path: str = "./models/bge-reranker-v2-m3"
):
    """
    【便捷函数】下载并保存BGE reranker模型到本地
    
    Args:
        model_name: 要下载的模型名称
        save_path: 保存路径
        
    Returns:
        str: 保存路径
    """
    try:
        os.makedirs(save_path, exist_ok=True)
        print(f"正在下载模型 {model_name} 到 {save_path}...")
        
        # 下载tokenizer
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        tokenizer.save_pretrained(save_path)
        
        # 下载模型
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        model.save_pretrained(save_path)
        
        print(f"模型已成功保存到: {save_path}")
        return save_path
        
    except Exception as e:
        print(f"下载模型失败: {e}")
        raise


# 使用示例
if __name__ == "__main__":
    # 【配置外置】指定本地模型路径
    LOCAL_MODEL_PATH = "agent/models/bge-reranker-v2-m3"  # 支持HuggingFace Hub缓存结构
    MODEL_SAVE_PATH = "models/bge-reranker-v2-m3"  # 直接模型文件结构
    
    # 示例数据
    query = "什么是人工智能？"
    passages = [
        "人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。",
        "机器学习是人工智能的一个子集，使计算机能够在没有明确编程的情况下学习和改进。",
        "深度学习是机器学习的一种方法，使用神经网络来模拟人脑的工作方式。",
        "自然语言处理是人工智能的一个领域，专注于计算机和人类语言之间的交互。",
        "今天天气很好，适合外出游玩。"
    ]
    
    try:
        # 【日志】记录开始信息
        print("开始BGE Reranker测试...")
        
        # 方法1：优先尝试从本地HuggingFace Hub缓存加载
        if os.path.exists(LOCAL_MODEL_PATH):
            print("从本地HuggingFace Hub缓存加载模型...")
            reranker = get_reranker_instance(local_model_path=LOCAL_MODEL_PATH)
        elif os.path.exists(MODEL_SAVE_PATH):
            print("从本地模型文件夹加载模型...")
            reranker = get_reranker_instance(local_model_path=MODEL_SAVE_PATH)
        else:
            print("本地模型不存在，先下载并保存...")
            download_and_save_model(save_path=MODEL_SAVE_PATH)
            reranker = get_reranker_instance(local_model_path=MODEL_SAVE_PATH)
        
        # 执行重排序
        import time
        start_time = time.time()
        results = reranker.rerank_passages(query, passages, top_k=3)
        end_time = time.time()
        
        # 【日志】显示结果
        print(f"重排序完成，耗时: {end_time - start_time:.2f}秒")
        print("重排序结果：")
        for i, (passage, score, original_idx) in enumerate(results, 1):
            print(f"{i}. [分数: {score:.4f}] [原始索引: {original_idx}] {passage}")
            
        print("\n" + "="*50 + "\n")
        
        # 方法2：使用便捷函数
        print("使用便捷函数测试...")
        start_time = time.time()
        results2 = rerank_with_local_bge(query, passages, LOCAL_MODEL_PATH, top_k=3)
        end_time = time.time()
        
        print(f"便捷函数重排序完成，耗时: {end_time - start_time:.2f}秒")
        print("便捷函数结果：")
        for i, (passage, score, original_idx) in enumerate(results2, 1):
            print(f"{i}. [分数: {score:.4f}] [原始索引: {original_idx}] {passage}")
            
    except Exception as e:
        print(f"执行出错: {e}")
        import traceback
        traceback.print_exc()
