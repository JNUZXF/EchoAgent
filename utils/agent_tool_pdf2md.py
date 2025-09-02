import os
import asyncio
import logging
from .agent_tool_vlm_img2txt_doubao import *

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """主函数"""
    # 配置参数
    image_folder_path = r"D:\AgentBuilding\FinAgent\agent\files\aier"
    max_concurrent_requests = 40  # 根据API限制调整
    batch_size = 100  # 批次大小
    
    # 检查文件夹是否存在
    if not os.path.exists(image_folder_path):
        logger.error(f"❌ 文件夹不存在: {image_folder_path}")
        return
    
    # 使用异步上下文管理器
    async with FastImageProcessor(
        max_concurrent_requests=max_concurrent_requests,
        max_retries=3
    ) as processor:
        
        # 批量处理图片
        results = await processor.process_images_batch(
            image_folder_path=image_folder_path,
            batch_size=batch_size
        )
        
        # 打印摘要
        processor.print_summary(results)
        
        # 保存详细报告
        await save_processing_report(results)


asyncio.run(main())

