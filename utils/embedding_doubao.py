# 文件功能：豆包向量化文本处理工具
# 文件路径：utils/embedding_doubao.py
# 提供文本向量化、批量处理、相似度计算和快速检索功能
# type: ignore

import os
import time
import pickle
import logging
import numpy as np
import pandas as pd
from tqdm import tqdm
from functools import wraps
from typing import List, Tuple, Callable, Any, Union
from concurrent.futures import ThreadPoolExecutor, as_completed 
from volcenginesdkarkruntime import Ark
from scipy.spatial.distance import cosine

# 【模块化设计】【性能优化】延迟导入BGE嵌入器相关模块，避免启动时耗时
BGE_AVAILABLE = None  # 延迟检测
BGE_OPTIMIZED_AVAILABLE = None  # 延迟检测

def _check_bge_availability():
    """【性能优化】延迟检测BGE模块可用性"""
    global BGE_AVAILABLE
    if BGE_AVAILABLE is None:
        try:
            from .agent_tool_bge_embedder import get_bge_m3_model, encode_text, BGEBatchEmbedder
            BGE_AVAILABLE = True
            logger.info("BGE嵌入器模块导入成功")
        except ImportError as e:
            BGE_AVAILABLE = False
            logger.warning(f"BGE嵌入器模块导入失败: {e}")
    return BGE_AVAILABLE

def _check_bge_optimized_availability():
    """【性能优化】延迟检测优化版BGE模块可用性"""
    global BGE_OPTIMIZED_AVAILABLE
    if BGE_OPTIMIZED_AVAILABLE is None:
        try:
            from .agent_tool_bge_embedder_optimized import fast_encode_texts
            BGE_OPTIMIZED_AVAILABLE = True
            logger.info("优化版BGE嵌入器模块导入成功")
        except ImportError as e:
            BGE_OPTIMIZED_AVAILABLE = False
            logger.warning(f"优化版BGE嵌入器模块导入失败: {e}")
    return BGE_OPTIMIZED_AVAILABLE

# 【性能优化】配置日志 - 只在需要时创建文件
logger = logging.getLogger(__name__)
if not logger.handlers:
    # 创建一个简单的控制台处理器，避免创建不必要的日志文件
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # 只显示警告和错误
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.setLevel(logging.WARNING)


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff_factor: float = 2.0):
    """
    重试装饰器，在函数执行失败时自动重试
    
    参数:
    max_retries: 最大重试次数
    delay: 初始延迟时间（秒）
    backoff_factor: 延迟时间的增长因子
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"函数 {func.__name__} 在第 {attempt + 1} 次尝试时成功")
                    return result
                    
                except Exception as e:
                    last_exception = e
                    logger.warning(f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {str(e)}")
                    
                    if attempt < max_retries:
                        logger.info(f"等待 {current_delay} 秒后重试...")
                        time.sleep(current_delay)
                        current_delay *= backoff_factor
                    else:
                        logger.error(f"函数 {func.__name__} 在 {max_retries + 1} 次尝试后仍然失败")
                        raise last_exception
            
            return None  # 这行代码实际上不会执行，因为上面的循环会抛出异常
        return wrapper
    return decorator

@retry_on_failure(max_retries=3, delay=1.0, backoff_factor=2.0)
def get_multimodal_embedding(text, model):
    """
    获取多模态嵌入向量，支持重试机制
    
    参数:
    text: 输入文本
    model: 模型名称
    
    返回:
    embedding: 嵌入向量
    """
    api_key = os.environ.get("DOUBAO_API_KEY")
    client = Ark(api_key=api_key)
    resp = client.multimodal_embeddings.create(
        model=model,
        input=[
            {
                "type":"text",
                "text":text
            }
            
        ]
    )
    return resp.data["embedding"]

# ========== 向量化和相似度计算函数 ==========
@retry_on_failure(max_retries=3, delay=1.0, backoff_factor=2.0)
def get_doubao_embedding(text, model="doubao-embedding-text-240715"):
    """获取文本的向量表示，支持重试机制
    model:doubao-embedding-text-240715
    model:doubao-embedding-vision-250328
    """
    
    # 检查API密钥是否存在
    api_key = os.environ.get("DOUBAO_API_KEY")
    if not api_key:
        logger.error("未找到DOUBAO_API_KEY环境变量，请设置API密钥")
        print("错误：未找到DOUBAO_API_KEY环境变量，请设置API密钥")
        print("设置方法：")
        print("Windows: set DOUBAO_API_KEY=your_api_key")
        print("或在Python中: os.environ['DOUBAO_API_KEY'] = 'your_api_key'")
        return None
    
    client = Ark(api_key=api_key)
    if model.startswith("doubao-embedding-vision"):
        return get_multimodal_embedding(text, model)
    else:
        resp = client.embeddings.create(
            model=model,
            input=[text],
            encoding_format="float",
        )
        embed = resp.data[0].embedding
        return embed

def cosine_similarity(vec1, vec2):
    """计算余弦相似度"""
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    
    # 计算余弦相似度
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0
    
    return dot_product / (norm1 * norm2)

# ========== 批量向量化和保存 ==========
class VectorDatabase:
    def __init__(self, save_path="vectors_db.pkl"):
        self.save_path = save_path
        self.texts = []
        self.vectors = []
        
    def batch_vectorize(self, 
                       texts: List[str], 
                       max_workers=10, 
                       batch_size=100, 
                       model="doubao-embedding-text-240715",
                       model_type="doubao",
                       bge_model_path=None,
                       bge_batch_size=32):
        """
        【模块化设计】【单一职责原则】批量向量化文本，支持多种模型类型
        
        参数:
        texts: 文本列表
        max_workers: 最大线程数
        batch_size: 每批处理的文本数量（针对API调用）
        model: 模型名称
        model_type: 模型类型，支持 "doubao" 或 "bge" 
        bge_model_path: BGE模型本地路径（可选）
        bge_batch_size: BGE模型批处理大小
        """
        print(f"开始向量化 {len(texts)} 个文本，使用模型类型: {model_type}")
        
        if model_type == "doubao":
            # 【依赖倒置】使用Doubao API进行向量化
            self._batch_vectorize_doubao(texts, max_workers, batch_size, model)
        elif model_type == "bge":
            # 【依赖倒置】使用本地BGE模型进行向量化
            self._batch_vectorize_bge(texts, max_workers, bge_batch_size, bge_model_path)
        else:
            logger.error(f"不支持的模型类型: {model_type}")
            print(f"错误：不支持的模型类型: {model_type}，支持的类型: 'doubao', 'bge'")
            return
        
        print(f"成功向量化 {len(self.texts)} 个文本")
    
    def _batch_vectorize_doubao(self, texts: List[str], max_workers: int, batch_size: int, model: str):
        """
        【单一职责原则】使用Doubao API进行批量向量化
        """        
        # 检查API密钥
        if not os.environ.get("DOUBAO_API_KEY"):
            logger.error("未设置DOUBAO_API_KEY环境变量")
            print("错误：未设置DOUBAO_API_KEY环境变量")
            return
        
        # 用于存储结果的列表
        results = [None] * len(texts)
        
        def process_text(idx, text):
            """处理单个文本"""
            embedding = get_doubao_embedding(text, model=model)
            return idx, text, embedding
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_idx = {
                executor.submit(process_text, idx, text): idx 
                for idx, text in enumerate(texts)
            }
            
            # 使用进度条显示处理进度
            with tqdm(total=len(texts), desc="Doubao向量化进度") as pbar:
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        idx, text, embedding = future.result()
                        if embedding is not None:
                            results[idx] = (text, embedding) # type: ignore
                    except Exception as e:
                        logger.error(f"处理索引 {idx} 的文本时出错: {e}")
                        print(f"Error processing text at index {idx}: {e}")
                    pbar.update(1)
        
        # 过滤掉失败的结果
        valid_results = [result for result in results if result is not None]
        
        if not valid_results:
            logger.error("没有成功向量化的文本")
            print("错误：没有成功向量化的文本，请检查API密钥配置")
            return
        
        # 分离文本和向量
        self.texts = [text for text, _ in valid_results] # type: ignore
        self.vectors = [vec for _, vec in valid_results] # type: ignore
    
    def _batch_vectorize_bge(self, texts: List[str], max_workers: int, batch_size: int, model_path: str = None):
        """
        【单一职责原则】【性能设计】使用本地BGE模型进行批量向量化（优化版）
        """
        # 【性能设计】优先使用优化版BGE嵌入器
        if _check_bge_optimized_availability():            
            try:
                # 【性能设计】使用优化版快速嵌入器
                from .agent_tool_bge_embedder_optimized import fast_encode_texts
                results = fast_encode_texts(
                    texts=texts,
                    model_path=model_path,
                    enable_cache=True,
                    show_progress=True,
                    custom_batch_size=batch_size
                )
                
                # 提取结果
                self.texts = results['texts']
                self.vectors = results['embeddings'].tolist()

                return
                
            except Exception as e:
                logger.error(f"优化版BGE向量化失败，回退到原版: {str(e)}")
                print(f"警告：优化版BGE向量化失败，回退到原版: {str(e)}")
        
        # 【容错设计】回退到原版BGE嵌入器
        if not _check_bge_availability():
            logger.error("BGE嵌入器模块不可用")
            print("错误：BGE嵌入器模块不可用，请确保agent_tool_bge_embedder.py文件存在")
            return
                
        try:
            # 【性能设计】使用原版BGE批处理嵌入器
            from .agent_tool_bge_embedder import BGEBatchEmbedder
            embedder = BGEBatchEmbedder(
                model_path=model_path,
                batch_size=batch_size,
                max_workers=max_workers,
                cache_results=True,
                show_progress=True
            )
            
            # 批量编码
            results = embedder.batch_encode(texts)
            
            # 提取结果
            self.texts = results['texts']
            self.vectors = results['embeddings'].tolist()
            
        except Exception as e:
            logger.error(f"BGE向量化过程中发生错误: {str(e)}")
            print(f"错误：BGE向量化失败: {str(e)}")
            return
        
    def save_to_file(self):
        """保存向量数据库到文件"""
        if not self.texts or not self.vectors:
            print("错误：没有数据可保存")
            return
            
        data = {
            'texts': self.texts,
            'vectors': np.array(self.vectors)
        }
        
        with open(self.save_path, 'wb') as f:
            pickle.dump(data, f)
        
        print(f"向量数据库已保存到 {self.save_path}")
        
    def save_to_csv(self, csv_path="vectors.csv"):
        """保存到CSV文件（备选方案）"""
        if not self.texts or not self.vectors:
            print("错误：没有数据可保存")
            return
            
        # 将向量转换为字符串以便存储在CSV中
        df_data = []
        for text, vector in zip(self.texts, self.vectors):
            df_data.append({
                'text': text,
                'vector': ','.join(map(str, vector))
            })
        
        df = pd.DataFrame(df_data)
        df.to_csv(csv_path, index=False, encoding='utf-8')
        print(f"向量数据已保存到 {csv_path}")

# ========== 快速查询 ==========
class VectorSearcher:
    def __init__(self, db_path, model, model_type="doubao", bge_model_path=None):
        """
        【模块化设计】初始化向量搜索器，支持多种模型类型
        
        参数:
        db_path: 向量数据库文件路径
        model: 模型名称
        model_type: 模型类型，支持 "doubao" 或 "bge"
        bge_model_path: BGE模型本地路径（当model_type为"bge"时使用）
        """
        self.db_path = db_path
        self.texts = None
        self.vectors = None
        self.model = model
        self.model_type = model_type
        self.bge_model_path = bge_model_path
        
        # 【依赖倒置】根据模型类型初始化相应的模型
        self.bge_model_instance = None
        if model_type == "bge" and _check_bge_availability():
            try:
                from .agent_tool_bge_embedder import get_bge_m3_model
                self.bge_model_instance = get_bge_m3_model(bge_model_path)
            except Exception as e:
                print(f"警告：BGE模型初始化失败，将回退到Doubao API: {e}")
        
    def load_database(self):
        """加载向量数据库"""
        if not os.path.exists(self.db_path):
            print(f"错误：向量数据库文件 {self.db_path} 不存在")
            return False
            
        print("加载向量数据库...")
        try:
            with open(self.db_path, 'rb') as f:
                data = pickle.load(f)
            
            self.texts = data['texts']
            self.vectors = data['vectors']
            print(f"已加载 {len(self.texts)} 个向量")
            return True
        except Exception as e:
            print(f"加载向量数据库失败: {e}")
            return False
        
    def load_from_csv(self, csv_path="vectors.csv"):
        """从CSV文件加载（备选方案）"""
        if not os.path.exists(csv_path):
            print(f"错误：CSV文件 {csv_path} 不存在")
            return False
            
        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            self.texts = df['text'].tolist()
            self.vectors = np.array([
                np.array(list(map(float, vec.split(','))))
                for vec in df['vector']
            ])
            print(f"从CSV加载了 {len(self.texts)} 个向量")
            return True
        except Exception as e:
            print(f"从CSV加载失败: {e}")
            return False
        
    def search(self, query: str, top_k=5, threshold=0.5):
        """
        【模块化设计】搜索最相似的文本，支持多种模型类型
        
        参数:
        query: 查询文本
        top_k: 返回最相似的前k个结果
        threshold: 相似度阈值
        
        返回:
        List[Tuple[str, float]]: (文本, 相似度分数) 列表
        """
        if self.texts is None or self.vectors is None:
            print("错误：向量数据库未加载")
            return []
        
        query_vector = self._get_query_vector(query)
        
        if query_vector is None:
            print("查询向量计算失败")
            return []
        
        query_vector = np.array(query_vector)
        
        # 批量计算相似度（使用numpy的矩阵运算加速）
        start_time = time.time()
        
        # 标准化向量以便使用点积计算余弦相似度
        query_norm = query_vector / np.linalg.norm(query_vector)
        vectors_norm = self.vectors / np.linalg.norm(self.vectors, axis=1, keepdims=True)
        
        # 使用矩阵乘法批量计算余弦相似度
        similarities = np.dot(vectors_norm, query_norm)
        
        # 获取top_k个最相似的索引
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # 过滤低于阈值的结果
        results = []
        for idx in top_indices:
            if similarities[idx] >= threshold:
                results.append((self.texts[idx], float(similarities[idx])))
        
        end_time = time.time()        
        return results
    
    def _get_query_vector(self, query: str) -> Union[List[float], np.ndarray, None]:
        """
        【单一职责原则】【性能设计】根据模型类型获取查询向量（优化版）
        
        参数:
        query: 查询文本
        
        返回:
        查询向量或None（如果失败）
        """
        try:
            if self.model_type == "doubao":
                # 使用Doubao API
                return get_doubao_embedding(query, model=self.model)
            
            elif self.model_type == "bge":
                # 【性能设计】优先使用优化版BGE嵌入器
                if _check_bge_optimized_availability():
                    try:
                        from .agent_tool_bge_embedder_optimized import fast_encode_texts
                        results = fast_encode_texts(
                            texts=[query],
                            model_path=self.bge_model_path,
                            enable_cache=True,
                            show_progress=False
                        )
                        return results['embeddings'][0]
                    except Exception as e:
                        logger.warning(f"优化版BGE查询向量计算失败，回退到原版: {e}")
                
                # 【容错设计】回退到原版BGE模型
                if not _check_bge_availability():
                    logger.error("BGE模块不可用，回退到Doubao API")
                    print("警告：BGE模块不可用，回退到Doubao API")
                    return get_doubao_embedding(query, model=self.model)
                
                if self.bge_model_instance is None:
                    logger.warning("BGE模型实例不可用，尝试重新初始化")
                    try:
                        from .agent_tool_bge_embedder import get_bge_m3_model
                        self.bge_model_instance = get_bge_m3_model(self.bge_model_path)
                    except Exception as e:
                        logger.error(f"BGE模型重新初始化失败: {e}")
                        print(f"警告：BGE模型不可用，回退到Doubao API: {e}")
                        return get_doubao_embedding(query, model=self.model)
                
                # 使用原版BGE模型进行编码
                from .agent_tool_bge_embedder import encode_text
                embeddings = encode_text(self.bge_model_instance, [query])
                return embeddings[0]
            
            else:
                logger.error(f"不支持的模型类型: {self.model_type}")
                print(f"错误：不支持的模型类型: {self.model_type}")
                return None
                
        except Exception as e:
            logger.error(f"获取查询向量时发生错误: {e}")
            print(f"错误：获取查询向量失败: {e}")
            return None

# ========== 使用示例 ==========
def vectorize_and_save_example():
    """向量化并保存示例"""
    # 假设你有一个paras列表
    paras = [
        "大熊猫是中国的国宝，主要生活在四川等地的竹林中。",
        "人工智能正在改变我们的生活方式。",
        "Python是一种流行的编程语言。",
        "机器学习是人工智能的一个重要分支。",
        "深度学习在图像识别领域取得了巨大成功。",
        # ... 更多文本
    ]
    
    # 创建向量数据库
    db = VectorDatabase()
    
    # 批量向量化
    db.batch_vectorize(paras, max_workers=5)
    
    # 保存到文件
    db.save_to_file()
    
    # 也可以保存到CSV
    db.save_to_csv()

def search_example():
    """搜索示例"""
    # 创建搜索器
    searcher = VectorSearcher()
    
    # 加载数据库
    if not searcher.load_database():
        print("无法加载向量数据库，搜索示例跳过")
        return
    
    # 搜索查询
    query = "熊猫的生活习性"
    results = searcher.search(query, top_k=3, threshold=0.3)
    
    # 打印结果
    print(f"\n查询: {query}")
    print("搜索结果:")
    for i, (text, score) in enumerate(results, 1):
        print(f"{i}. 相似度: {score:.4f}")
        print(f"   文本: {text}")
        print()

def bge_vectorize_and_search_example():
    """
    【模块化设计】【性能设计】使用BGE模型进行向量化和搜索的示例（优化版）
    """
    print("\n=== BGE模型向量化和搜索示例（优化版） ===")
    
    # 检查BGE模块可用性
    if _check_bge_optimized_availability():
        print("✅ 优化版BGE模块可用")
    elif _check_bge_availability():
        print("⚠️ 原版BGE模块可用，优化版不可用")
    else:
        print("❌ BGE模块不可用，跳过BGE示例")
        return
    
    # 示例文本
    paras = [
        "大熊猫是中国的国宝，主要生活在四川等地的竹林中。",
        "人工智能正在改变我们的生活方式。",
        "Python是一种流行的编程语言。",
        "机器学习是人工智能的一个重要分支。",
        "深度学习在图像识别领域取得了巨大成功。",
        "自然语言处理是AI的重要应用领域。",
        "计算机视觉技术在自动驾驶中发挥重要作用。",
        "区块链技术在金融领域有重要应用。",
        "物联网连接了各种智能设备。",
        "5G网络提供了更快的数据传输速度。"
    ] * 10  # 扩展到100个文本用于性能测试
    
    # 【模块化设计】使用BGE模型创建向量数据库
    save_path = "bge_vectors_optimized_example.pkl"
    db = VectorDatabase(save_path=save_path)
    
    print(f"使用BGE模型进行批量向量化（{len(paras)} 个文本）...")
    start_time = time.time()
    
    db.batch_vectorize(
        texts=paras,
        max_workers=4,  # 增加线程数
        model_type="bge",  # 指定使用BGE模型
        bge_batch_size=64,  # 增大批处理大小
        bge_model_path=None  # 使用默认路径
    )
    
    vectorize_time = time.time() - start_time
    print(f"向量化总时间: {vectorize_time:.2f}秒")
    
    # 保存向量数据库
    db.save_to_file()
    
    # 【模块化设计】使用BGE模型进行搜索
    print("\n使用BGE模型进行搜索...")
    searcher = VectorSearcher(
        db_path=save_path,
        model="bge-m3",  # 模型名称（用于日志）
        model_type="bge",  # 指定使用BGE模型
        bge_model_path=None  # 使用默认路径
    )
    
    # 加载数据库
    if searcher.load_database():
        # 执行多个搜索查询测试
        queries = [
            "人工智能的应用",
            "动物保护",
            "编程语言特性",
            "网络技术发展"
        ]
        
        search_start = time.time()
        for query in queries:
            print(f"\n查询: {query}")
            results = searcher.search(query, top_k=3, threshold=0.3)
            
            # 打印结果
            print("BGE模型搜索结果:")
            for i, (text, score) in enumerate(results, 1):
                print(f"{i}. 相似度: {score:.4f}")
                print(f"   文本: {text[:50]}...")
        
        search_time = time.time() - search_start
        print(f"\n搜索总时间: {search_time:.2f}秒")
    
    # 清理示例文件
    try:
        import os
        if os.path.exists(save_path):
            os.remove(save_path)
            print(f"已清理示例文件: {save_path}")
    except Exception as e:
        print(f"清理示例文件失败: {e}")

def mixed_model_comparison_example():
    """
    【测试策略】混合模型对比示例：同时使用Doubao和BGE模型进行对比
    """
    print("\n=== 混合模型对比示例 ===")
    
    # 检查必要条件
    if not _check_bge_availability():
        print("BGE模块不可用，跳过对比示例")
        return
    
    if not os.environ.get("DOUBAO_API_KEY"):
        print("DOUBAO_API_KEY未设置，跳过对比示例")
        return
    
    # 示例文本
    test_texts = [
        "机器学习是人工智能的核心技术之一。",
        "深度神经网络在图像识别方面表现优异。",
        "自然语言处理技术正在快速发展。"
    ]
    
    query = "AI技术的发展"
    
    # 【性能设计】分别使用两种模型进行处理
    for model_type in ["doubao", "bge"]:
        try:
            print(f"\n--- 使用 {model_type.upper()} 模型 ---")
            
            # 创建向量数据库
            save_path = f"{model_type}_comparison_vectors.pkl"
            db = VectorDatabase(save_path=save_path)
            
            # 向量化
            if model_type == "doubao":
                db.batch_vectorize(
                    texts=test_texts,
                    max_workers=2,
                    model_type="doubao",
                    model="doubao-embedding-text-240715"
                )
            else:
                db.batch_vectorize(
                    texts=test_texts,
                    max_workers=2,
                    model_type="bge",
                    bge_batch_size=2
                )
            
            # 保存和搜索
            db.save_to_file()
            
            searcher = VectorSearcher(
                db_path=save_path,
                model="test_model",
                model_type=model_type
            )
            
            if searcher.load_database():
                results = searcher.search(query, top_k=2, threshold=0.0)
                
                print(f"查询: {query}")
                print(f"{model_type.upper()}搜索结果:")
                for i, (text, score) in enumerate(results, 1):
                    print(f"  {i}. 相似度: {score:.4f} | 文本: {text}")
            
            # 清理文件
            try:
                import os
                if os.path.exists(save_path):
                    os.remove(save_path)
            except:
                pass
                
        except Exception as e:
            print(f"{model_type}模型处理失败: {e}")
            continue

def setup_api_key_example():
    """设置API密钥示例"""
    print("=== API密钥设置说明 ===")
    print("请先设置豆包API密钥：")
    print("方法1 - 在代码中设置：")
    print("os.environ['DOUBAO_API_KEY'] = 'your_api_key_here'")
    print("\n方法2 - 在命令行设置：")
    print("Windows: set DOUBAO_API_KEY=your_api_key_here")
    print("Linux/Mac: export DOUBAO_API_KEY=your_api_key_here")
    print("\n如果你有API密钥，请取消下面这行的注释并填入你的密钥：")
    print("# os.environ['DOUBAO_API_KEY'] = 'your_api_key_here'")





