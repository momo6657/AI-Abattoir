"""Seed script: register models and agents.

Usage:
  cd backend && python seed.py

Requires: DATABASE_URL in .env, database running.
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.models")  # Load model API keys

from app.core.database import async_session, engine, Base
from app.models.model import Model, ModelCapability, CapabilityType
from app.models.agent import Agent, AgentProfile


MODELS = [
    {
        "name": "GPT-5.4",
        "provider": "openai",
        "model_id": "openai/gpt-5.4",
        "api_key_env": "GPT54_API_KEY",
        "api_base_env": "LLM_API_BASE",
        "capabilities": [
            CapabilityType.TEXT_GENERATION,
            CapabilityType.IMAGE_UNDERSTANDING,
            CapabilityType.CODE_EXECUTION,
        ],
    },
    {
        "name": "DeepSeek-V4-Pro",
        "provider": "deepseek",
        "model_id": "openai/deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "api_base_env": "LLM_API_BASE",
        "capabilities": [
            CapabilityType.TEXT_GENERATION,
            CapabilityType.CODE_EXECUTION,
        ],
    },
]

AGENTS = [
    {
        "name": "谋略家",
        "description": "擅长分析和制定策略，能够在复杂局势中找到最优解",
        "model_name": "GPT-5.4",
        "profile": {
            "persona": "你是一位深谋远虑的谋略家，善于从全局视角分析问题",
            "personality": "冷静、理性、善于洞察本质，具有前瞻性思维",
            "speaking_style": "逻辑严密，条理清晰，善用类比和历史典故来阐述观点",
            "background_story": "曾参与过无数次重大决策，每次都能在迷雾中找到破局之路",
            "strengths": ["战略分析", "风险评估", "局势判断", "长远规划"],
        },
    },
    {
        "name": "创意大师",
        "description": "天马行空的想象力，善于创造新颖的解决方案",
        "model_name": "DeepSeek-V4-Pro",
        "profile": {
            "persona": "你是一位充满创意的大脑，总能提出令人眼前一亮的新想法",
            "personality": "好奇、开放、富有想象力、不拘一格",
            "speaking_style": "生动活泼，善用比喻和故事，偶尔冒出诗意的表达",
            "background_story": "从小就在艺术和科技的交叉点上探索，相信创意可以改变世界",
            "strengths": ["创意构思", "跨界联想", "故事创作", "视觉想象"],
        },
    },
    {
        "name": "谈判专家",
        "description": "精通博弈论和沟通技巧，擅长达成共识",
        "model_name": "GPT-5.4",
        "profile": {
            "persona": "你是一位经验丰富的谈判专家，能够在对立中找到共同利益",
            "personality": "善于倾听、有同理心、灵活应变、追求双赢",
            "speaking_style": "温和但有力，善用提问引导对方，偶尔使用幽默化解紧张",
            "background_story": "处理过无数复杂的商业谈判和国际争端，深知沟通的艺术",
            "strengths": ["谈判技巧", "情绪管理", "利益分析", "共识构建"],
        },
    },
    {
        "name": "执行者",
        "description": "高效执行任务，注重细节，追求完美落地",
        "model_name": "DeepSeek-V4-Pro",
        "profile": {
            "persona": "你是一位雷厉风行的执行者，以高效和精确著称",
            "personality": "果断、务实、注重细节，追求可量化的目标",
            "speaking_style": "简洁明了，直击要点，喜欢用数据和事实说话",
            "background_story": "经手的每一项任务都能按时保质完成，是团队中最可靠的基石",
            "strengths": ["任务分解", "进度管控", "质量保证", "资源协调"],
        },
    },
]


async def seed():
    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # Check if already seeded
        from sqlalchemy import select, func
        count = await db.execute(select(func.count()).select_from(Model))
        if count.scalar() > 0:
            print("Database already has models. Skipping seed.")
            return

        # Create models
        model_map = {}
        for m in MODELS:
            api_key = os.getenv(m["api_key_env"], "")
            api_base = os.getenv(m["api_base_env"], "")

            model = Model(
                name=m["name"],
                provider=m["provider"],
                model_id=m["model_id"],
                api_key=api_key,
                api_base=api_base,
                is_active=True,
                status="online",
            )
            db.add(model)
            await db.flush()

            # Add capabilities
            for cap in m["capabilities"]:
                db.add(ModelCapability(model_id=model.id, capability=cap))

            model_map[m["name"]] = model.id
            print(f"  Created model: {m['name']} ({m['model_id']})")

        # Create agents
        for a in AGENTS:
            model_id = model_map.get(a["model_name"])
            if not model_id:
                print(f"  Skipping agent {a['name']}: model {a['model_name']} not found")
                continue

            agent = Agent(
                name=a["name"],
                description=a["description"],
                model_id=model_id,
            )
            db.add(agent)
            await db.flush()

            profile = a["profile"]
            db.add(AgentProfile(
                agent_id=agent.id,
                persona=profile["persona"],
                personality=profile["personality"],
                speaking_style=profile["speaking_style"],
                background_story=profile["background_story"],
                strengths=profile["strengths"],
            ))
            print(f"  Created agent: {a['name']} (model: {a['model_name']})")

        await db.commit()
        print("\nSeed completed!")


if __name__ == "__main__":
    asyncio.run(seed())
