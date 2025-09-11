"""
快速测试脚本
"""
import asyncio
import logging

# 设置基础日志
logging.basicConfig(level=logging.INFO)

async def test_import():
    """测试导入"""
    try:
        print("1. 测试配置模块...")
        from config.agent_settings import get_settings
        print("✅ 配置模块导入成功")
        
        print("2. 测试核心模块...")
        from core.exceptions import AgentException
        from core.cache_manager import get_cache_manager
        from core.metrics_collector import get_metrics_collector
        from core.health_manager import get_health_manager
        print("✅ 核心模块导入成功")
        
        print("3. 测试优化智能体...")
        from agent_frame_v6_optimized import OptimizedEchoAgent
        print("✅ 优化智能体导入成功")
        
        print("4. 创建配置...")
        settings = get_settings(
            user_id="test",
            main_model="test_model",
            tool_model="test_tool",
            flash_model="test_flash"
        )
        print(f"✅ 配置创建成功 - 用户: {settings.user_id}")
        
        print("\n🎉 所有导入测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_import())
    print(f"\n测试结果: {'通过' if result else '失败'}")
