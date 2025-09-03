

from agent_frame import *


async def main():
    model_configs_doubao = {
        "user_id": "sam",
        "main_model": "doubao-seed-1-6-250615",
        "tool_model": "doubao-seed-1-6-250615",
        "flash_model": "doubao-seed-1-6-250615"
    }

    config = AgentConfig(
        **model_configs_doubao
    )
    agent = EchoAgent(config)

    question = f"你好，你能做什么？"

    async for response_chunk in agent.process_query(question):
        print(response_chunk, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())

