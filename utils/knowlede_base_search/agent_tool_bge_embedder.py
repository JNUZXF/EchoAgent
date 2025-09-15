# type: ignore
# 文件路径: agent/utils/agent_tool_bge_embedder.py
# 功能: BGE-M3模型嵌入器工具，用于文本向量化

import os
import glob
import time
import pickle
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional, Union
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
import torch
import numpy as np
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. 定义模型名称和本地保存路径 ---
# BAAI/bge-m3 是它在Hugging Face Hub上的官方模型名称
model_name = "BAAI/bge-m3"
# 定义你希望保存模型的本地文件夹路径
local_model_path = "agent/models/bge-m3"

# 备选的本地模型路径
alternative_local_paths = [
    "agent/models/bge-m3",
    "agent/models/bge-reranker-v2-m3",
    "models/bge-m3",
    "models/bge-reranker-v2-m3"
]

# --- 2. 检查HuggingFace Hub缓存结构 ---
def check_huggingface_cache_structure(model_path: str) -> str:
    """
    检查是否是HuggingFace Hub缓存结构，并返回实际的模型路径。
    
    Args:
        model_path (str): 模型路径
        
    Returns:
        str: 实际的模型路径，如果不是缓存结构则返回原路径
    """
    # 检查是否是HuggingFace Hub缓存结构
    snapshots_dir = os.path.join(model_path, "snapshots")
    if os.path.exists(snapshots_dir):
        # 获取snapshots下的模型文件夹（通常是哈希值命名的）
        snapshot_folders = [f for f in os.listdir(snapshots_dir) 
                          if os.path.isdir(os.path.join(snapshots_dir, f))]
        if snapshot_folders:
            # 取最新的快照（按修改时间排序）
            snapshot_paths = [os.path.join(snapshots_dir, f) for f in snapshot_folders]
            latest_snapshot = max(snapshot_paths, key=os.path.getmtime)
            logger.info(f"发现HuggingFace Hub缓存结构，使用快照: {latest_snapshot}")
            return latest_snapshot
    
    return model_path

# --- 3. 检查本地模型是否存在的函数 ---
def check_local_model_exists(model_path: str) -> bool:
    """
    检查本地模型是否存在且完整。
    
    Args:
        model_path (str): 本地模型路径
        
    Returns:
        bool: 如果模型存在且完整则返回True，否则返回False
    """
    if not os.path.exists(model_path):
        return False
    
    # 首先检查是否是HuggingFace Hub缓存结构
    actual_model_path = check_huggingface_cache_structure(model_path)
    
    # 检查必要的模型文件是否存在
    required_files = ["config.json"]
    
    # 检查模型权重文件（支持多种格式）
    model_weight_files = [
        "pytorch_model.bin",
        "model.safetensors",
        "pytorch_model.safetensors"
    ]
    
    # 检查词汇表文件（支持多种格式）
    vocab_files = [
        "vocab.txt",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "sentencepiece.bpe.model"
    ]
    
    # 检查必需文件
    for file in required_files:
        file_path = os.path.join(actual_model_path, file)
        if not os.path.exists(file_path):
            logger.warning(f"本地模型缺少必要文件: {file_path}")
            return False
    
    # 检查模型权重文件（至少要有一个）
    has_model_weights = any(
        os.path.exists(os.path.join(actual_model_path, file)) 
        for file in model_weight_files
    )
    
    if not has_model_weights:
        logger.warning(f"本地模型缺少权重文件，检查的文件: {model_weight_files}")
        return False
    
    # 检查词汇表文件（至少要有一个）
    has_vocab_file = any(
        os.path.exists(os.path.join(actual_model_path, file)) 
        for file in vocab_files
    )
    
    if not has_vocab_file:
        logger.warning(f"本地模型缺少词汇表文件，检查的文件: {vocab_files}")
        return False
    
    logger.info(f"本地模型验证通过: {actual_model_path}")
    return True

# --- 4. 寻找可用的本地模型路径 ---
def find_available_local_model() -> str:
    """
    在多个可能的路径中寻找可用的本地模型。
    
    Returns:
        str: 可用的本地模型路径，如果都不可用则返回None
    """
    for path in alternative_local_paths:
        abs_path = os.path.abspath(path)
        if check_local_model_exists(abs_path):
            logger.info(f"找到可用的本地模型: {abs_path}")
            return abs_path
    
    logger.info("未找到可用的本地模型")
    return None

# --- 5. 核心功能：加载或下载模型 ---
def get_bge_m3_model(model_path: str = None, force_download: bool = False) -> SentenceTransformer:
    """
    加载BGE-M3模型，优先从本地加载，如果本地不存在则从Hugging Face Hub下载。
    
    Args:
        model_path (str): 模型在本地的保存路径（可选）
        force_download (bool): 是否强制从网络下载，忽略本地模型
        
    Returns:
        SentenceTransformer: 加载好的模型实例
    """
    # 确定使用的设备
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    logger.info(f"当前使用的设备: {device}")
    
    # 如果不强制下载，优先尝试本地模型
    if not force_download:
        # 如果指定了路径，优先检查指定路径
        if model_path:
            abs_model_path = os.path.abspath(model_path)
            if check_local_model_exists(abs_model_path):
                try:
                    actual_path = check_huggingface_cache_structure(abs_model_path)
                    logger.info(f"从指定路径加载模型: {actual_path}")
                    model = SentenceTransformer(actual_path, device=device)
                    logger.info("指定路径的本地模型加载成功")
                    return model
                except Exception as e:
                    logger.warning(f"指定路径的本地模型加载失败: {str(e)}")
        
        # 在备选路径中寻找可用的本地模型
        available_path = find_available_local_model()
        if available_path:
            try:
                actual_path = check_huggingface_cache_structure(available_path)
                logger.info(f"从备选路径加载模型: {actual_path}")
                model = SentenceTransformer(actual_path, device=device)
                logger.info("备选路径的本地模型加载成功")
                return model
            except Exception as e:
                logger.warning(f"备选路径的本地模型加载失败: {str(e)}")
    
    # 如果本地模型不可用或强制下载，从网络加载
    try:
        logger.info(f"正在从Hugging Face Hub下载BGE-M3模型: {model_name}")
        logger.info("注意：这需要网络连接，如果没有VPN可能会失败")
        
        model = SentenceTransformer(model_name, device=device)
        
        # 保存模型到本地
        save_path = model_path or local_model_path
        abs_save_path = os.path.abspath(save_path)
        logger.info(f"将模型保存到本地路径: {abs_save_path}")
        os.makedirs(os.path.dirname(abs_save_path), exist_ok=True)
        model.save(abs_save_path)
        
        logger.info("模型下载并保存完成")
        return model
        
    except Exception as e:
        logger.error(f"模型加载失败: {str(e)}")
        logger.error("请检查网络连接或本地模型文件是否完整")
        logger.error("如果没有VPN连接，请确保本地模型文件完整")
        logger.error(f"已检查的本地路径: {alternative_local_paths}")
        raise

# --- 6. 基础文本嵌入函数 ---
def encode_text(model: SentenceTransformer, texts: Union[str, List[str]]) -> np.ndarray:
    """
    使用BGE-M3模型对文本进行嵌入编码。
    
    Args:
        model: 加载好的SentenceTransformer模型实例
        texts: 需要编码的文本或文本列表
        
    Returns:
        numpy.ndarray: 文本嵌入向量数组
    """
    if isinstance(texts, str):
        texts = [texts]
    
    logger.info(f"开始编码 {len(texts)} 个文本")
    
    # 执行嵌入编码
    embeddings = model.encode(texts, convert_to_tensor=False)
    
    logger.info(f"编码完成，嵌入维度: {embeddings.shape}")
    return embeddings

# --- 7. 高效批处理嵌入器类 ---
class BGEBatchEmbedder:
    """
    【模块化设计】BGE-M3模型的高效批处理嵌入器
    支持多线程、批处理、进度显示和结果缓存
    """
    
    def __init__(self, 
                 model_path: str = None,
                 batch_size: int = 32,
                 max_workers: int = 4,
                 cache_results: bool = True,
                 show_progress: bool = True):
        """
        初始化批处理嵌入器
        
        Args:
            model_path: 模型路径（可选）
            batch_size: 每批处理的文本数量
            max_workers: 最大线程数
            cache_results: 是否缓存结果
            show_progress: 是否显示进度条
        """
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.cache_results = cache_results
        self.show_progress = show_progress
        
        # 【日志】加载模型
        logger.info(f"初始化BGE批处理嵌入器 - 批次大小: {batch_size}, 线程数: {max_workers}")
        self.model = get_bge_m3_model(model_path)
        
        # 结果缓存
        self.embedding_cache = {}
        self.cache_lock = threading.Lock()
        
        # 统计信息
        self.stats = {
            'total_texts': 0,
            'processed_texts': 0,
            'cache_hits': 0,
            'processing_time': 0,
            'embeddings_per_second': 0
        }
    
    def _get_text_hash(self, text: str) -> str:
        """
        【单一职责原则】获取文本的哈希值用于缓存
        """
        import hashlib
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _process_batch(self, batch_texts: List[str], batch_idx: int) -> List[Tuple[int, str, np.ndarray]]:
        """
        【单一职责原则】处理单个批次的文本
        
        Args:
            batch_texts: 批次文本列表
            batch_idx: 批次索引
            
        Returns:
            List[Tuple[int, str, np.ndarray]]: (原始索引, 文本, 嵌入向量) 的列表
        """
        results = []
        
        # 检查缓存
        if self.cache_results:
            cached_results = []
            uncached_texts = []
            uncached_indices = []
            
            with self.cache_lock:
                for i, text in enumerate(batch_texts):
                    text_hash = self._get_text_hash(text)
                    if text_hash in self.embedding_cache:
                        cached_results.append((i, text, self.embedding_cache[text_hash]))
                        self.stats['cache_hits'] += 1
                    else:
                        uncached_texts.append(text)
                        uncached_indices.append(i)
            
            # 处理未缓存的文本
            if uncached_texts:
                try:
                    embeddings = self.model.encode(uncached_texts, convert_to_tensor=False)
                    
                    # 缓存新结果
                    if self.cache_results:
                        with self.cache_lock:
                            for i, text in enumerate(uncached_texts):
                                text_hash = self._get_text_hash(text)
                                self.embedding_cache[text_hash] = embeddings[i]
                    
                    # 合并结果
                    for i, embedding in enumerate(embeddings):
                        original_idx = uncached_indices[i]
                        results.append((original_idx, uncached_texts[i], embedding))
                
                except Exception as e:
                    logger.error(f"批次 {batch_idx} 处理失败: {str(e)}")
                    return []
            
            # 添加缓存结果
            results.extend(cached_results)
        
        else:
            # 不使用缓存，直接处理
            try:
                embeddings = self.model.encode(batch_texts, convert_to_tensor=False)
                for i, embedding in enumerate(embeddings):
                    results.append((i, batch_texts[i], embedding))
            except Exception as e:
                logger.error(f"批次 {batch_idx} 处理失败: {str(e)}")
                return []
        
        return results
    
    def batch_encode(self, texts: List[str]) -> Dict[str, Union[List[str], np.ndarray, Dict]]:
        """
        【性能设计】批量编码文本列表
        
        Args:
            texts: 文本列表
            
        Returns:
            Dict: 包含文本列表、嵌入向量数组和统计信息的字典
        """
        start_time = time.time()
        self.stats['total_texts'] = len(texts)
        self.stats['processed_texts'] = 0
        self.stats['cache_hits'] = 0
        
        logger.info(f"开始批量编码 {len(texts)} 个文本...")
        
        # 创建批次
        batches = []
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i + self.batch_size]
            batches.append((batch_texts, i // self.batch_size))
        
        logger.info(f"创建了 {len(batches)} 个批次，使用 {self.max_workers} 个线程")
        
        # 存储结果
        all_results = [None] * len(texts)
        
        # 使用线程池处理批次
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有批次任务
            future_to_batch = {
                executor.submit(self._process_batch, batch_texts, batch_idx): (batch_texts, batch_idx)
                for batch_texts, batch_idx in batches
            }
            
            # 显示进度条
            if self.show_progress:
                progress_bar = tqdm(total=len(texts), desc="编码进度", unit="文本")
            
            # 处理完成的任务
            for future in as_completed(future_to_batch):
                batch_texts, batch_idx = future_to_batch[future]
                
                try:
                    batch_results = future.result()
                    
                    # 将批次结果放入正确位置
                    batch_start_idx = batch_idx * self.batch_size
                    for local_idx, text, embedding in batch_results:
                        global_idx = batch_start_idx + local_idx
                        all_results[global_idx] = (text, embedding)
                        self.stats['processed_texts'] += 1
                    
                    if self.show_progress:
                        progress_bar.update(len(batch_results))
                    
                except Exception as e:
                    logger.error(f"批次 {batch_idx} 处理异常: {str(e)}")
                    if self.show_progress:
                        progress_bar.update(len(batch_texts))
            
            if self.show_progress:
                progress_bar.close()
        
        # 过滤掉失败的结果
        valid_results = [result for result in all_results if result is not None]
        
        if not valid_results:
            logger.error("所有文本处理都失败了")
            return {
                'texts': [],
                'embeddings': np.array([]),
                'stats': self.stats
            }
        
        # 分离文本和嵌入向量
        final_texts = [text for text, _ in valid_results]
        final_embeddings = np.array([embedding for _, embedding in valid_results])
        
        # 更新统计信息
        end_time = time.time()
        self.stats['processing_time'] = end_time - start_time
        self.stats['embeddings_per_second'] = len(final_texts) / self.stats['processing_time']
        
        logger.info(f"批量编码完成: {len(final_texts)}/{len(texts)} 成功")
        logger.info(f"处理时间: {self.stats['processing_time']:.2f}秒")
        logger.info(f"处理速度: {self.stats['embeddings_per_second']:.2f} 文本/秒")
        logger.info(f"缓存命中: {self.stats['cache_hits']} 次")
        
        return {
            'texts': final_texts,
            'embeddings': final_embeddings,
            'stats': self.stats.copy()
        }
    
    def save_results(self, results: Dict, save_path: str):
        """
        【配置外置】保存批处理结果到文件
        
        Args:
            results: batch_encode返回的结果字典
            save_path: 保存路径
        """
        try:
            with open(save_path, 'wb') as f:
                pickle.dump(results, f)
            logger.info(f"结果已保存到: {save_path}")
        except Exception as e:
            logger.error(f"保存结果失败: {str(e)}")
    
    def load_results(self, load_path: str) -> Dict:
        """
        【配置外置】从文件加载批处理结果
        
        Args:
            load_path: 加载路径
            
        Returns:
            Dict: 结果字典
        """
        try:
            with open(load_path, 'rb') as f:
                results = pickle.load(f)
            logger.info(f"结果已从 {load_path} 加载")
            return results
        except Exception as e:
            logger.error(f"加载结果失败: {str(e)}")
            return {}
    
    def clear_cache(self):
        """
        【配置外置】清空缓存
        """
        with self.cache_lock:
            self.embedding_cache.clear()
        logger.info("缓存已清空")

# --- 8. 便捷函数 ---
def batch_encode_texts(texts: List[str], 
                      model_path: str = None,
                      batch_size: int = 32,
                      max_workers: int = 4,
                      cache_results: bool = True,
                      show_progress: bool = True) -> Dict[str, Union[List[str], np.ndarray, Dict]]:
    """
    【便捷函数】批量编码文本的便捷函数
    
    Args:
        texts: 文本列表
        model_path: 模型路径
        batch_size: 批次大小
        max_workers: 最大线程数
        cache_results: 是否缓存结果
        show_progress: 是否显示进度条
        
    Returns:
        Dict: 包含文本、嵌入向量和统计信息的字典
    """
    embedder = BGEBatchEmbedder(
        model_path=model_path,
        batch_size=batch_size,
        max_workers=max_workers,
        cache_results=cache_results,
        show_progress=show_progress
    )
    
    return embedder.batch_encode(texts)

# --- 9. 便捷函数：检查本地模型状态 ---
def check_local_model_status():
    """
    检查并显示本地模型的状态信息。
    """
    print("="*60)
    print("BGE-M3 本地模型状态检查")
    print("="*60)
    
    for i, path in enumerate(alternative_local_paths, 1):
        abs_path = os.path.abspath(path)
        print(f"{i}. 检查路径: {abs_path}")
        
        if not os.path.exists(abs_path):
            print(f"   状态: 路径不存在")
        else:
            is_valid = check_local_model_exists(abs_path)
            if is_valid:
                actual_path = check_huggingface_cache_structure(abs_path)
                print(f"   状态: ✓ 可用")
                print(f"   实际路径: {actual_path}")
                
                # 显示模型文件信息
                files = os.listdir(actual_path)
                model_files = [f for f in files if f.endswith(('.bin', '.safetensors'))]
                config_files = [f for f in files if f.endswith('.json')]
                print(f"   模型文件: {model_files}")
                print(f"   配置文件: {config_files}")
            else:
                print(f"   状态: ✗ 不完整或无效")
        print()
    
    available_path = find_available_local_model()
    if available_path:
        print(f"推荐使用的本地模型路径: {available_path}")
    else:
        print("未找到可用的本地模型，将需要从网络下载")
    print("="*60)

# --- 10. 示例使用 ---
if __name__ == "__main__":

    model_path = "models/bge-m3"
    # 强制下载
    force_download = True
    if force_download:
        get_bge_m3_model(model_path, force_download=True)
    # 首先检查本地模型状态
    check_local_model_status()
    
    print("\n" + "="*60)
    print("BGE-M3 批处理嵌入器测试")
    print("="*60)
    
    # 示例文本
    texts = [
        "这是一个测试文本",
        "BGE-M3是一个强大的多语言嵌入模型",
        "人工智能在各行各业都有广泛应用",
        "深度学习技术正在快速发展",
        "自然语言处理是AI的重要分支",
        "机器学习算法需要大量数据训练",
        "神经网络可以学习复杂的模式",
        "文本嵌入向量可以表示语义信息",
        "相似的文本会有相似的向量表示",
        "向量检索可以快速找到相关内容"
    ]
    
    try:
        print(f"准备处理 {len(texts)} 个文本...")
        
        # 方法1：使用便捷函数
        print("\n--- 方法1：使用便捷函数 ---")
        results = batch_encode_texts(
            texts=texts,
            batch_size=4,
            max_workers=2,
            cache_results=True,
            show_progress=True
        )
        
        print(f"成功处理: {len(results['texts'])} 个文本")
        print(f"嵌入维度: {results['embeddings'].shape}")
        print(f"统计信息: {results['stats']}")
        
        # 方法2：使用批处理器类
        print("\n--- 方法2：使用批处理器类 ---")
        embedder = BGEBatchEmbedder(
            batch_size=6,
            max_workers=3,
            cache_results=True,
            show_progress=True
        )
        
        results2 = embedder.batch_encode(texts)
        print(f"成功处理: {len(results2['texts'])} 个文本")
        print(f"嵌入维度: {results2['embeddings'].shape}")
        print(f"统计信息: {results2['stats']}")
        
        # 计算文本相似性示例
        print("\n--- 文本相似性计算 ---")
        from sklearn.metrics.pairwise import cosine_similarity
        
        # 使用第一个结果计算相似性
        similarity_matrix = cosine_similarity(results['embeddings'])
        print("前5个文本的相似性矩阵:")
        for i in range(min(5, len(texts))):
            print(f"文本{i+1}: {texts[i][:30]}...")
        print(f"相似性矩阵 (前5x5):\n{similarity_matrix[:5, :5]}")
        
        # 保存结果示例
        print("\n--- 保存和加载结果 ---")
        save_path = "bge_embeddings_test.pkl"
        embedder.save_results(results, save_path)
        
        # 加载结果
        loaded_results = embedder.load_results(save_path)
        print(f"加载的结果包含 {len(loaded_results.get('texts', []))} 个文本")
        
        # 清理测试文件
        if os.path.exists(save_path):
            os.remove(save_path)
            print(f"清理测试文件: {save_path}")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)







