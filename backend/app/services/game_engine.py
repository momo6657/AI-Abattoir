import logging
import uuid
import random
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.game import Game, GamePlayer, GameType, GameStatus
from app.models.agent import Agent
from app.models.model import Model
from app.services.llm_adapter import llm_adapter

logger = logging.getLogger(__name__)


class GameEngine:
    """通用游戏引擎，支持狼人杀等多种游戏类型"""

    async def create_game(
        self, db: AsyncSession, game_type: str, config: dict, agent_ids: List[str]
    ) -> Game:
        game = Game(
            game_type=game_type,
            config=config,
            state={"round": 0, "phase": "setup"},
        )
        db.add(game)
        await db.flush()

        for agent_id in agent_ids:
            player = GamePlayer(game_id=game.id, agent_id=agent_id)
            db.add(player)

        await db.commit()
        await db.refresh(game)
        return game

    async def start_game(self, db: AsyncSession, game_id: str) -> Game:
        game = await db.get(Game, game_id)
        if not game:
            raise ValueError("Game not found")
        if game.status != GameStatus.WAITING:
            raise ValueError(f"Game is already {game.status}")

        if game.game_type == GameType.WEREWOLF:
            await self._setup_werewolf(db, game)
        else:
            raise ValueError(f"Unsupported game type: {game.game_type}")

        game.status = GameStatus.IN_PROGRESS
        game.state["round"] = 1
        game.state["phase"] = "night"
        await db.commit()
        await db.refresh(game)
        return game

    async def process_turn(self, db: AsyncSession, game_id: str) -> Dict[str, Any]:
        game = await db.get(Game, game_id)
        if not game:
            raise ValueError("Game not found")
        if game.status != GameStatus.IN_PROGRESS:
            raise ValueError("Game is not in progress")

        if game.game_type == GameType.WEREWOLF:
            result = await self._process_werewolf_turn(db, game)
        else:
            raise ValueError(f"Unsupported game type: {game.game_type}")

        winner = await self._check_winner(db, game)
        if winner:
            game.status = GameStatus.FINISHED
            game.state["winner"] = winner
            game.updated_at = datetime.now(timezone.utc)
            await db.commit()
            result["game_over"] = True
            result["winner"] = winner

        await db.commit()
        await db.refresh(game)
        return result

    async def get_game_state(self, db: AsyncSession, game_id: str) -> Dict[str, Any]:
        game = await db.get(Game, game_id)
        if not game:
            raise ValueError("Game not found")

        result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = result.scalars().all()

        player_list = []
        for p in players:
            agent = await db.get(Agent, p.agent_id)
            player_list.append({
                "agent_id": str(p.agent_id),
                "agent_name": agent.name if agent else "Unknown",
                "role": p.role,
                "is_alive": bool(p.is_alive),
                "config": p.config or {},
            })

        return {
            "game_id": str(game.id),
            "game_type": game.game_type,
            "status": game.status,
            "state": game.state or {},
            "players": player_list,
            "winner_id": str(game.winner_id) if game.winner_id else None,
            "created_at": game.created_at.isoformat() if game.created_at else None,
        }

    async def end_game(
        self, db: AsyncSession, game_id: str, winner_id: Optional[str] = None
    ) -> Game:
        game = await db.get(Game, game_id)
        if not game:
            raise ValueError("Game not found")

        game.status = GameStatus.FINISHED
        if winner_id:
            game.winner_id = winner_id
        game.state["ended_at"] = datetime.now(timezone.utc).isoformat()
        game.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(game)
        return game

    # ========== 狼人杀实现 ==========

    WEREWOLF_ROLES = ["werewolf", "werewolf", "seer", "witch", "hunter", "villager"]

    async def _setup_werewolf(self, db: AsyncSession, game: Game):
        result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = result.scalars().all()

        if len(players) != 6:
            raise ValueError("Werewolf requires exactly 6 players")

        roles = self.WEREWOLF_ROLES.copy()
        random.shuffle(roles)

        for player, role in zip(players, roles):
            player.role = role
            player.is_alive = True

        game.state = {
            "round": 1,
            "phase": "night",
            "night_actions": {},
            "day_votes": {},
            "discussion": [],
            "dead_players": [],
            "witch_save_used": False,
            "witch_poison_used": False,
            "seer_results": {},
        }

    async def _process_werewolf_turn(
        self, db: AsyncSession, game: Game
    ) -> Dict[str, Any]:
        phase = game.state.get("phase", "night")
        round_num = game.state.get("round", 1)

        if phase == "night":
            result = await self._werewolf_night_phase(db, game)
            game.state["phase"] = "day"
            return {"round": round_num, "phase": "night", "events": result}
        else:
            result = await self._werewolf_day_phase(db, game)
            game.state["phase"] = "night"
            game.state["round"] = round_num + 1
            return {"round": round_num, "phase": "day", "events": result}

    async def _werewolf_night_phase(
        self, db: AsyncSession, game: Game
    ) -> List[Dict[str, Any]]:
        events = []
        state = game.state

        players_result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = players_result.scalars().all()

        alive_players = [p for p in players if p.is_alive]
        alive_by_role = {}
        for p in alive_players:
            alive_by_role.setdefault(p.role, []).append(p)

        wolf_targets = [p for p in alive_players if p.role != "werewolf"]
        if not wolf_targets:
            return events

        # 狼人选择击杀目标
        wolves = alive_by_role.get("werewolf", [])
        if wolves:
            wolf = wolves[0]
            agent = await db.get(Agent, wolf.agent_id)
            model = await db.get(Model, agent.model_id)
            target_names = [
                f"{(await db.get(Agent, t.agent_id)).name}(ID:{t.agent_id})"
                for t in wolf_targets
            ]
            prompt = self._build_werewolf_prompt(
                agent, "werewolf", state, "night_kill", target_names
            )
            response = await self._call_llm(model, prompt)
            target_id = self._extract_target_id(response, wolf_targets)

            if target_id:
                state["night_actions"]["wolf_target"] = target_id

        # 预言家查验
        seers = alive_by_role.get("seer", [])
        if seers:
            seer = seers[0]
            agent = await db.get(Agent, seer.agent_id)
            model = await db.get(Model, agent.model_id)
            check_targets = [
                p for p in alive_players if p.agent_id != seer.agent_id
            ]
            if check_targets:
                target_names = [
                    f"{(await db.get(Agent, t.agent_id)).name}(ID:{t.agent_id})"
                    for t in check_targets
                ]
                prompt = self._build_werewolf_prompt(
                    agent, "seer", state, "night_check", target_names
                )
                response = await self._call_llm(model, prompt)
                check_id = self._extract_target_id(response, check_targets)
                if check_id:
                    checked_player = next(
                        (p for p in players if str(p.agent_id) == check_id), None
                    )
                    if checked_player:
                        is_wolf = checked_player.role == "werewolf"
                        state["seer_results"][check_id] = is_wolf
                        state["night_actions"]["seer_check"] = check_id
                        events.append({
                            "action": "seer_check",
                            "target": check_id,
                            "result": "werewolf" if is_wolf else "villager",
                        })

        # 女巫行动
        witches = alive_by_role.get("witch", [])
        if witches:
            witch = witches[0]
            agent = await db.get(Agent, witch.agent_id)
            model = await db.get(Model, agent.model_id)
            wolf_target = state["night_actions"].get("wolf_target")
            context = {
                "wolf_target": wolf_target,
                "can_save": not state.get("witch_save_used", False),
                "can_poison": not state.get("witch_poison_used", False),
            }
            prompt = self._build_werewolf_prompt(
                agent, "witch", state, "night_witch", [], context
            )
            response = await self._call_llm(model, prompt)
            action = self._parse_witch_action(response, state)

            if action.get("save"):
                state["night_actions"].pop("wolf_target", None)
                state["witch_save_used"] = True
                events.append({"action": "witch_save"})
            elif action.get("poison"):
                state["night_actions"]["witch_poison"] = action["poison"]
                state["witch_poison_used"] = True
                events.append({"action": "witch_poison", "target": action["poison"]})

        # 结算夜晚死亡
        deaths = []
        wolf_target = state["night_actions"].get("wolf_target")
        if wolf_target:
            deaths.append(wolf_target)

        witch_poison = state["night_actions"].get("witch_poison")
        if witch_poison:
            deaths.append(witch_poison)

        for death_id in deaths:
            player = next(
                (p for p in players if str(p.agent_id) == death_id), None
            )
            if player:
                player.is_alive = False
                agent = await db.get(Agent, player.agent_id)
                state["dead_players"].append({
                    "agent_id": death_id,
                    "role": player.role,
                    "round": state.get("round"),
                    "phase": "night",
                })
                events.append({
                    "action": "death",
                    "agent_id": death_id,
                    "agent_name": agent.name if agent else "Unknown",
                })

        state["night_actions"] = {}
        return events

    async def _werewolf_day_phase(
        self, db: AsyncSession, game: Game
    ) -> List[Dict[str, Any]]:
        events = []
        state = game.state

        players_result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = players_result.scalars().all()
        alive_players = [p for p in players if p.is_alive]

        # 讨论阶段：每个存活玩家发言
        discussion_messages = []
        for player in alive_players:
            agent = await db.get(Agent, player.agent_id)
            model = await db.get(Model, agent.model_id)
            alive_names = [
                (await db.get(Agent, p.agent_id)).name for p in alive_players
            ]
            prompt = self._build_werewolf_prompt(
                agent, player.role, state, "day_discussion", alive_names
            )
            response = await self._call_llm(model, prompt)
            discussion_messages.append({
                "agent_id": str(player.agent_id),
                "agent_name": agent.name,
                "role": player.role,
                "message": response,
            })

        state["discussion"] = discussion_messages
        events.append({"action": "discussion", "messages": discussion_messages})

        # 投票阶段
        votes = {}
        for player in alive_players:
            agent = await db.get(Agent, player.agent_id)
            model = await db.get(Model, agent.model_id)
            candidates = [
                f"{(await db.get(Agent, p.agent_id)).name}(ID:{p.agent_id})"
                for p in alive_players
                if p.agent_id != player.agent_id
            ]
            prompt = self._build_werewolf_prompt(
                agent, player.role, state, "day_vote", candidates
            )
            response = await self._call_llm(model, prompt)
            vote_target = self._extract_target_id(response, [
                p for p in alive_players if p.agent_id != player.agent_id
            ])
            if vote_target:
                votes[str(player.agent_id)] = vote_target

        # 统计投票
        vote_counts: Dict[str, int] = {}
        for voter, target in votes.items():
            vote_counts[target] = vote_counts.get(target, 0) + 1

        state["day_votes"] = {"votes": votes, "counts": vote_counts}

        # 放逐得票最多者
        if vote_counts:
            max_votes = max(vote_counts.values())
            top_targets = [
                t for t, v in vote_counts.items() if v == max_votes
            ]
            if len(top_targets) == 1:
                exiled_id = top_targets[0]
                player = next(
                    (p for p in players if str(p.agent_id) == exiled_id), None
                )
                if player:
                    player.is_alive = False
                    agent = await db.get(Agent, player.agent_id)
                    state["dead_players"].append({
                        "agent_id": exiled_id,
                        "role": player.role,
                        "round": state.get("round"),
                        "phase": "day",
                    })
                    events.append({
                        "action": "exile",
                        "agent_id": exiled_id,
                        "agent_name": agent.name if agent else "Unknown",
                        "votes": vote_counts[exiled_id],
                    })

                    # 猎人被放逐时可以开枪
                    if player.role == "hunter":
                        events.append({
                            "action": "hunter_trigger",
                            "agent_id": exiled_id,
                        })
            else:
                events.append({
                    "action": "tie_vote",
                    "candidates": top_targets,
                })

        return events

    async def _check_winner(
        self, db: AsyncSession, game: Game
    ) -> Optional[str]:
        result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = result.scalars().all()

        alive = [p for p in players if p.is_alive]
        alive_werewolves = [p for p in alive if p.role == "werewolf"]
        alive_villagers = [p for p in alive if p.role != "werewolf"]

        if not alive_werewolves:
            return "villagers"
        if len(alive) <= 2 and alive_werewolves:
            return "werewolves"
        return None

    # ========== Prompt 构建 ==========

    def _build_werewolf_prompt(
        self,
        agent: Agent,
        role: str,
        state: dict,
        phase: str,
        targets: List[str],
        context: Optional[dict] = None,
    ) -> str:
        role_desc = {
            "werewolf": "你是狼人，你的目标是消灭所有村民。每个夜晚你和同伴选择一名玩家击杀。",
            "seer": "你是预言家，每个夜晚可以查验一名玩家的身份（是否为狼人）。",
            "witch": "你是女巫，你有一瓶解药（可以救活被狼人击杀的人）和一瓶毒药（可以毒杀一人）。整局游戏各只能使用一次。",
            "hunter": "你是猎人，当你死亡时可以开枪带走一名玩家。",
            "villager": "你是普通村民，没有特殊能力，但你的推理和投票至关重要。",
        }

        round_num = state.get("round", 1)
        dead = state.get("dead_players", [])
        dead_info = ""
        if dead:
            recent_dead = [d for d in dead if d.get("round", 0) >= round_num - 1]
            if recent_dead:
                dead_info = "近期死亡: " + ", ".join(
                    f"{d['agent_id']}" for d in recent_dead
                )

        base = f"""你是 {agent.name}，一名狼人杀玩家。
角色：{role} - {role_desc.get(role, '')}
当前第 {round_num} 轮。

{dead_info}

"""

        if phase == "night_kill":
            base += f"""夜晚阶段 - 狼人选择击杀目标。
可选目标：{', '.join(targets)}
请直接回复目标的 ID（UUID 格式），不要有多余文字。"""

        elif phase == "night_check":
            base += f"""夜晚阶段 - 预言家查验身份。
可查验的玩家：{', '.join(targets)}
请直接回复你想查验的玩家 ID（UUID 格式）。"""

        elif phase == "night_witch":
            c = context or {}
            base += f"""夜晚阶段 - 女巫行动。
可使用解药：{'是' if c.get('can_save') else '否'}
可使用毒药：{'是' if c.get('can_poison') else '否'}
"""
            if c.get("wolf_target") and c.get("can_save"):
                base += f"今晚被击杀的是 {c['wolf_target']}，是否使用解药？\n"
            if c.get("can_poison"):
                base += "是否使用毒药？如使用请回复 POISON:<目标ID>，否则回复 SKIP。\n"
            base += "格式：SAVE 或 POISON:<ID> 或 SKIP"

        elif phase == "day_discussion":
            seer_results = state.get("seer_results", {})
            my_id = str(agent.id)
            extra = ""
            if role == "seer" and seer_results:
                checks = ", ".join(
                    f"{k}={'狼人' if v else '好人'}"
                    for k, v in seer_results.items()
                )
                extra = f"\n你查验过的结果：{checks}"
            base += f"""白天讨论阶段 - 所有存活玩家：{', '.join(targets)}
{extra}
请发表你的看法，推理谁可能是狼人，100字以内。"""

        elif phase == "day_vote":
            base += f"""白天投票阶段 - 放逐一名玩家。
候选人：{', '.join(targets)}
请直接回复你想投票放逐的玩家 ID（UUID 格式）。"""

        return base

    # ========== 辅助方法 ==========

    async def _call_llm(self, model: Model, prompt: str) -> str:
        try:
            response = await llm_adapter.chat(
                model_id=model.model_id,
                messages=[{"role": "user", "content": prompt}],
                api_key=model.api_key,
                api_base=model.api_base,
                temperature=0.8,
                max_tokens=500,
            )
            return response.get("content", "").strip()
        except Exception:
            logger.exception(
                "LLM call failed for model=%s prompt_preview=%s",
                model.model_id,
                prompt[:100],
            )
            return ""

    def _extract_target_id(
        self, response: str, candidates: List[GamePlayer]
    ) -> Optional[str]:
        import re
        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        match = re.search(uuid_pattern, response, re.IGNORECASE)
        if match:
            found_id = match.group(0)
            valid_ids = {str(p.agent_id) for p in candidates}
            if found_id in valid_ids:
                return found_id
        # 回退：随机选一个
        if candidates:
            return str(random.choice(candidates).agent_id)
        return None

    def _parse_witch_action(
        self, response: str, state: dict
    ) -> Dict[str, Any]:
        upper = response.upper().strip()
        if upper.startswith("SAVE"):
            return {"save": True}
        elif upper.startswith("POISON:"):
            target = response.split(":", 1)[1].strip()
            import re
            uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
            match = re.search(uuid_pattern, target, re.IGNORECASE)
            if match:
                return {"poison": match.group(0)}
        return {"skip": True}


game_engine = GameEngine()
