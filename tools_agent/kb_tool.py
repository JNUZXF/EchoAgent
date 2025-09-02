"""
知识库工具类

将Milvus知识库功能封装为工具类，可以集成到主智能体框架中。
提供知识库查询、文档导入等功能。

文件路径: Agent进阶-搭建更聪明的智能体/tools/kb_tool.py
"""

import os
import logging
from typing import List, Dict, Any, Generator, Optional

from .milvus_knowledge_base import MilvusKnowledgeBase
from .embedding_doubao import DoubaoEmbedding

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("KnowledgeBaseTool")

class KnowledgeBaseTool:
    """知识库工具类
    
    封装知识库操作为智能体工具，提供文档导入、知识检索等功能。
    """
    
    def __init__(
        self,
        kb_host: str = "localhost",
        kb_port: str = "19530",
        embedding_dim: int = 1536,
        kb_collection: str = "agent_knowledge_base"
    ):
        """初始化知识库工具
        
        Args:
            kb_host: Milvus服务器主机
            kb_port: Milvus服务器端口
            embedding_dim: 嵌入向量维度
            kb_collection: 知识库集合名称
        """
        self.kb_host = kb_host
        self.kb_port = kb_port
        self.embedding_dim = embedding_dim
        self.kb_collection = kb_collection
        
        # 初始化嵌入模型
        self.embedding_model = DoubaoEmbedding()
        
        # 初始化知识库
        self.kb = MilvusKnowledgeBase(
            host=kb_host,
            port=kb_port,
            embedding_dim=embedding_dim,
            default_collection=kb_collection
        )
        
        # 设置嵌入函数
        self.kb.set_embedding_function(self._get_embeddings)
        
        # 确保知识库集合存在
        self._ensure_collection()
        
        logger.info(f"知识库工具初始化完成: {kb_collection}")
    
    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """文本嵌入函数
        
        Args:
            texts: 文本列表
            
        Returns:
            List[List[float]]: 嵌入向量列表
        """
        return [self.embedding_model.get_embedding(text) for text in texts]
    
    def _ensure_collection(self) -> None:
        """确保知识库集合存在
        
        如果集合不存在，则创建新集合
        """
        try:
            collections = self.kb.list_collections()
            if self.kb_collection not in collections:
                logger.info(f"创建新的知识库集合: {self.kb_collection}")
                self.kb.create_collection()
            else:
                logger.info(f"使用现有知识库集合: {self.kb_collection}")
        except Exception as e:
            logger.error(f"确保知识库集合存在时出错: {str(e)}")
            raise RuntimeError(f"无法初始化知识库集合: {str(e)}")
    
    def execute(self, **kwargs):
        """执行知识库工具
        
        支持的操作:
        - action=query: 查询知识库
        - action=add: 添加知识到知识库
        - action=import: 导入文档到知识库
        - action=delete: 删除知识
        
        Args:
            **kwargs: 操作参数
            
        Returns:
            查询结果或操作状态
        """
        action = kwargs.get("action", "query")
        user_id = kwargs.get("userID", "default_user")
        
        # 根据操作类型执行不同功能
        if action == "query":
            return self._execute_query(**kwargs)
        elif action == "add":
            return self._execute_add(**kwargs)
        elif action == "import":
            return self._execute_import(**kwargs)
        elif action == "delete":
            return self._execute_delete(**kwargs)
        else:
            error_msg = f"不支持的操作: {action}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def _execute_query(self, **kwargs):
        """执行知识库查询
        
        Args:
            query: 查询文本
            userID: 用户ID
            top_k: 返回结果数量
            
        Returns:
            Dict: 查询结果
        """
        query = kwargs.get("query", "")
        user_id = kwargs.get("userID", "default_user")
        top_k = kwargs.get("top_k", 5)
        
        if not query:
            return {"status": "error", "message": "查询文本不能为空"}
        
        try:
            # 执行查询
            results = self.kb.search_by_text(
                query_text=query,
                user_id=user_id,
                top_k=top_k
            )
            
            # 格式化结果
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "text": result.get("text", ""),
                    "metadata": result.get("metadata", {}),
                    "similarity": result.get("similarity", 0)
                })
            
            return {
                "status": "success",
                "query": query,
                "results_count": len(formatted_results),
                "results": formatted_results
            }
            
        except Exception as e:
            error_msg = f"知识库查询失败: {str(e)}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def _execute_add(self, **kwargs):
        """添加知识到知识库
        
        Args:
            texts: 文本列表或单个文本
            userID: 用户ID
            metadata: 元数据(单个文本时)或元数据列表(多个文本时)
            
        Returns:
            Dict: 操作结果
        """
        texts = kwargs.get("texts", [])
        user_id = kwargs.get("userID", "default_user")
        metadata = kwargs.get("metadata", None)
        
        # 处理单个文本情况
        if isinstance(texts, str):
            texts = [texts]
            if metadata and not isinstance(metadata, list):
                metadata = [metadata]
        
        if not texts:
            return {"status": "error", "message": "文本不能为空"}
        
        try:
            # 添加文本
            ids = self.kb.add_texts(
                texts=texts,
                user_id=user_id,
                metadatas=metadata
            )
            
            return {
                "status": "success",
                "message": f"成功添加 {len(ids)} 条知识",
                "ids": ids
            }
            
        except Exception as e:
            error_msg = f"添加知识失败: {str(e)}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def _execute_import(self, **kwargs):
        """导入文档到知识库
        
        Args:
            file_paths: 文件路径列表
            userID: 用户ID
            chunk_size: 文本分块大小
            chunk_overlap: 文本分块重叠大小
            
        Returns:
            Dict: 操作结果
        """
        file_paths = kwargs.get("file_paths", [])
        user_id = kwargs.get("userID", "default_user")
        chunk_size = kwargs.get("chunk_size", 1000)
        chunk_overlap = kwargs.get("chunk_overlap", 200)
        
        if not file_paths:
            return {"status": "error", "message": "文件路径不能为空"}
        
        # 处理单个文件路径情况
        if isinstance(file_paths, str):
            file_paths = [file_paths]
        
        try:
            # 验证文件路径
            valid_paths = []
            for path in file_paths:
                if os.path.exists(path):
                    valid_paths.append(path)
                else:
                    logger.warning(f"文件不存在: {path}")
            
            if not valid_paths:
                return {"status": "error", "message": "没有有效的文件路径"}
            
            # 导入文档
            ids = self.kb.import_from_files(
                file_paths=valid_paths,
                user_id=user_id,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            
            return {
                "status": "success",
                "message": f"成功导入 {len(ids)} 个文档片段",
                "files_count": len(valid_paths),
                "chunks_count": len(ids)
            }
            
        except Exception as e:
            error_msg = f"导入文档失败: {str(e)}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def _execute_delete(self, **kwargs):
        """删除知识
        
        Args:
            delete_type: 删除类型 (user/ids)
            userID: 用户ID (当delete_type=user时)
            ids: ID列表 (当delete_type=ids时)
            
        Returns:
            Dict: 操作结果
        """
        delete_type = kwargs.get("delete_type", "user")
        user_id = kwargs.get("userID", "default_user")
        ids = kwargs.get("ids", [])
        
        try:
            if delete_type == "user":
                # 删除用户的所有知识
                count = self.kb.delete_by_user_id(user_id)
                return {
                    "status": "success",
                    "message": f"成功删除用户 {user_id} 的 {count} 条知识记录"
                }
            elif delete_type == "ids":
                # 删除特定ID的知识
                if not ids:
                    return {"status": "error", "message": "ID列表不能为空"}
                
                # 处理单个ID情况
                if isinstance(ids, str):
                    ids = [ids]
                
                count = self.kb.delete_by_ids(ids)
                return {
                    "status": "success",
                    "message": f"成功删除 {count} 条知识记录"
                }
            else:
                return {"status": "error", "message": f"不支持的删除类型: {delete_type}"}
                
        except Exception as e:
            error_msg = f"删除知识失败: {str(e)}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
    
    def close(self):
        """关闭知识库连接"""
        try:
            self.kb.disconnect()
            logger.info("已关闭知识库连接")
        except Exception as e:
            logger.error(f"关闭知识库连接失败: {str(e)}")


# 单独测试
if __name__ == "__main__":
    # 初始化工具
    kb_tool = KnowledgeBaseTool(kb_collection="test_kb_tool")
    
    # 添加测试知识
    add_result = kb_tool.execute(
        action="add",
        texts=["Milvus是一个开源的向量数据库，专为嵌入相似度搜索和AI应用设计。",
               "知识库工具可以帮助智能体记忆和检索相关信息。"],
        userID="test_user",
        metadata=[{"source": "测试"}, {"source": "测试"}]
    )
    print("添加结果:", add_result)
    
    # 查询测试
    query_result = kb_tool.execute(
        action="query",
        query="什么是Milvus?",
        userID="test_user",
        top_k=2
    )
    print("\n查询结果:", query_result)
    
    # 关闭连接
    kb_tool.close() 