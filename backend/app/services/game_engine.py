import logging
import traceback
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
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)


class GameEngine:
    """通用游戏引擎，支持狼人杀、辩论、谈判等多种游戏类型"""

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
            game.state["round"] = 1
            game.state["phase"] = "night"
        elif game.game_type == GameType.DEBATE:
            await self._setup_debate(db, game)
        elif game.game_type == GameType.NEGOTIATION:
            await self._setup_negotiation(db, game)
        else:
            raise ValueError(f"Unsupported game type: {game.game_type}")

        game.status = GameStatus.IN_PROGRESS
        await db.commit()
        await db.refresh(game)

        await ws_manager.broadcast_to_conversation(game.id, "game_started", {
            "game_id": str(game.id),
            "game_type": game.game_type,
        })
        return game

    async def process_turn(self, db: AsyncSession, game_id: str) -> Dict[str, Any]:
        game = await db.get(Game, game_id)
        if not game:
            raise ValueError("Game not found")
        if game.status != GameStatus.IN_PROGRESS:
            raise ValueError("Game is not in progress")

        if game.game_type == GameType.WEREWOLF:
            result = await self._process_werewolf_turn(db, game)
        elif game.game_type == GameType.DEBATE:
            result = await self._process_debate_turn(db, game)
        elif game.game_type == GameType.NEGOTIATION:
            result = await self._process_negotiation_turn(db, game)
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

        # Broadcast the turn result to any watchers
        await ws_manager.broadcast_to_conversation(game.id, "game_turn", {
            "game_id": str(game.id),
            "result": result,
        })

        if result.get("game_over"):
            await ws_manager.broadcast_to_conversation(game.id, "game_over", {
                "game_id": str(game.id),
                "winner": result.get("winner"),
            })

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

    @staticmethod
    def _build_werewolf_roles(num_players: int) -> List[str]:
        """Build a role list scaled to the number of players (4-12)."""
        if num_players < 4 or num_players > 12:
            raise ValueError("Werewolf requires between 4 and 12 players")

        if num_players <= 5:
            wolves = 1
        elif num_players <= 7:
            wolves = 2
        elif num_players <= 9:
            wolves = 2
        else:
            wolves = 3

        roles = ["werewolf"] * wolves + ["seer", "witch"]

        if num_players >= 6:
            roles.append("hunter")
        if num_players >= 8:
            roles.append("guard")

        # Fill remaining slots with villagers
        remaining = num_players - len(roles)
        roles += ["villager"] * remaining
        return roles

    async def _setup_werewolf(self, db: AsyncSession, game: Game):
        result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = result.scalars().all()

        roles = self._build_werewolf_roles(len(players))
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
            if response is not None:
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
                if response is not None:
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
            if response is not None:
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

        hunter_deaths = []
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
                if player.role == "hunter":
                    hunter_deaths.append(player)

        # 猎人夜间死亡时开枪
        for hunter_player in hunter_deaths:
            shoot_event = await self._hunter_shoot(db, players, hunter_player, state)
            if shoot_event:
                events.append(shoot_event)

        state["night_actions"] = {}
        return events

    async def _hunter_shoot(
        self, db: AsyncSession, all_players: List[GamePlayer],
        hunter_player: GamePlayer, state: dict,
    ) -> Optional[Dict[str, Any]]:
        """When a hunter dies, use LLM to pick a target and kill them."""
        alive_targets = [p for p in all_players if p.is_alive and p.agent_id != hunter_player.agent_id]
        if not alive_targets:
            return None

        agent = await db.get(Agent, hunter_player.agent_id)
        model = await db.get(Model, agent.model_id)
        if not model:
            return None

        target_names = [
            f"{(await db.get(Agent, t.agent_id)).name}(ID:{t.agent_id})"
            for t in alive_targets
        ]
        prompt = self._build_werewolf_prompt(
            agent, "hunter", state, "hunter_shoot", target_names
        )
        response = await self._call_llm(model, prompt)
        if response is not None:
            target_id = self._extract_target_id(response, alive_targets)
        else:
            target_id = None

        if target_id:
            shot_player = next(
                (p for p in all_players if str(p.agent_id) == target_id), None
            )
            if shot_player:
                shot_player.is_alive = False
                shot_agent = await db.get(Agent, shot_player.agent_id)
                state["dead_players"].append({
                    "agent_id": target_id,
                    "role": shot_player.role,
                    "round": state.get("round"),
                    "phase": state.get("phase", "unknown"),
                })
                return {
                    "action": "hunter_shoot",
                    "hunter_id": str(hunter_player.agent_id),
                    "hunter_name": agent.name if agent else "Unknown",
                    "target_id": target_id,
                    "target_name": shot_agent.name if shot_agent else "Unknown",
                }
        return None

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
                "message": response or "",
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
            if response is not None:
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

                    # 猎人被放逐时开枪
                    if player.role == "hunter":
                        shoot_event = await self._hunter_shoot(db, players, player, state)
                        if shoot_event:
                            events.append(shoot_event)
            else:
                events.append({
                    "action": "tie_vote",
                    "candidates": top_targets,
                })

        return events

    async def _check_winner(
        self, db: AsyncSession, game: Game
    ) -> Optional[str]:
        if game.game_type == GameType.DEBATE:
            if game.state.get("finished"):
                return game.state.get("winner", "undetermined")
            return None
        if game.game_type == GameType.NEGOTIATION:
            if game.state.get("finished"):
                return game.state.get("winner", "completed")
            return None

        # Werewolf: check alive counts
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
            "guard": "你是守卫，每个夜晚可以守护一名玩家使其免受狼人击杀（不能连续两晚守护同一人）。",
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

        elif phase == "hunter_shoot":
            base += f"""你已死亡，作为猎人你可以开枪带走一名玩家。
可选目标：{', '.join(targets)}
请直接回复你想带走的玩家 ID（UUID 格式）。"""

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

    async def _call_llm(self, model: Model, prompt: str) -> Optional[str]:
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
            logger.error(
                "LLM call failed for model=%s prompt_preview=%s\n%s",
                model.model_id,
                prompt[:100],
                traceback.format_exc(),
            )
            return None

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
        # 回退：选择第一个有效候选目标（非随机）
        if candidates:
            logger.warning(
                "LLM response did not contain a valid target ID, "
                "falling back to first candidate. response=%s", response[:200]
            )
            return str(candidates[0].agent_id)
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

    # ========== 辩论赛实现 ==========

    DEBATE_ROUNDS = 5  # 1=opening, 2-4=rebuttal, 5=closing

    async def _setup_debate(self, db: AsyncSession, game: Game):
        result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = result.scalars().all()

        if len(players) < 2:
            raise ValueError("Debate requires at least 2 agents (pro and con)")

        # First agent = pro, second = con, optional third = judge
        players[0].role = "pro"
        players[0].config = {**(players[0].config or {}), "side": "pro"}
        players[1].role = "con"
        players[1].config = {**(players[1].config or {}), "side": "con"}

        judge_agent_id = None
        if len(players) >= 3:
            players[2].role = "judge"
            players[2].config = {**(players[2].config or {}), "side": "judge"}
            judge_agent_id = str(players[2].agent_id)

        game.state = {
            "round": 1,
            "phase": "debate",
            "topic": game.config.get("topic", "待定辩题"),
            "total_rounds": self.DEBATE_ROUNDS,
            "current_speaker_index": 0,
            "arguments": [],
            "judge_agent_id": judge_agent_id,
            "finished": False,
        }

    async def _process_debate_turn(
        self, db: AsyncSession, game: Game
    ) -> Dict[str, Any]:
        state = game.state
        round_num = state.get("round", 1)
        total_rounds = state.get("total_rounds", self.DEBATE_ROUNDS)
        topic = state.get("topic", "")
        arguments = state.get("arguments", [])

        if state.get("finished"):
            return {"round": round_num, "phase": "debate", "events": [], "finished": True}

        # Determine which side speaks this turn:
        # Turn order alternates pro/con each round.
        # Each round both sides speak (2 turns per round).
        turns_per_round = 2
        total_turns = total_rounds * turns_per_round
        current_turn = len(arguments)

        if current_turn >= total_turns:
            # All debate turns done - judge
            result = await self._judge_debate(db, game)
            state["finished"] = True
            return {"round": round_num, "phase": "debate_judgment", "events": [result]}

        # Determine current round and side
        current_round = (current_turn // turns_per_round) + 1
        side_index = current_turn % turns_per_round  # 0=pro, 1=con
        current_side = "pro" if side_index == 0 else "con"

        # Find the player for this side
        players_result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = players_result.scalars().all()
        speaker = next((p for p in players if p.role == current_side), None)
        if not speaker:
            # Skip if side missing
            arguments.append({
                "round": current_round,
                "side": current_side,
                "agent_id": None,
                "content": "(缺席)",
            })
            state["arguments"] = arguments
            return {"round": current_round, "phase": "debate", "events": []}

        agent = await db.get(Agent, speaker.agent_id)
        model = await db.get(Model, agent.model_id)

        # Build prompt
        prompt = self._build_debate_prompt(
            agent, current_side, topic, current_round, total_rounds, arguments
        )
        response = await self._call_llm(model, prompt)
        content = response or "(无回应)"

        argument_entry = {
            "round": current_round,
            "side": current_side,
            "agent_id": str(speaker.agent_id),
            "agent_name": agent.name,
            "content": content,
        }
        arguments.append(argument_entry)
        state["arguments"] = arguments

        # Update round display
        state["round"] = current_round

        return {
            "round": current_round,
            "phase": "debate",
            "events": [argument_entry],
        }

    def _build_debate_prompt(
        self,
        agent: Agent,
        side: str,
        topic: str,
        current_round: int,
        total_rounds: int,
        arguments: List[Dict[str, Any]],
    ) -> str:
        side_label = "正方(支持)" if side == "pro" else "反方(反对)"

        if current_round == 1:
            phase_desc = "开篇立论：阐述你的立场和核心论点"
        elif current_round == total_rounds:
            phase_desc = "总结陈词：总结你的论点，做最终陈述"
        else:
            phase_desc = "反驳轮：针对对方的论点进行反驳，并强化自己的观点"

        history = ""
        if arguments:
            recent = arguments[-4:]  # Show last 4 arguments for context
            lines = []
            for arg in recent:
                s_label = "正方" if arg["side"] == "pro" else "反方"
                lines.append(f"[{s_label}] {arg['content'][:300]}")
            history = "\n".join(lines)

        prompt = f"""你是 {agent.name}，参与一场辩论。
辩题：{topic}
你的立场：{side_label}
当前：第 {current_round}/{total_rounds} 轮 - {phase_desc}

"""
        if history:
            prompt += f"""前序论点：
{history}

"""
        prompt += f"""请以{side_label}的立场发表论述，200字以内。要求：
- 论点清晰，逻辑严密
- {'针对对方论点进行有力反驳' if current_round > 1 and current_round < total_rounds else ''}
- 用事实和推理支撑你的观点"""

        return prompt

    async def _judge_debate(
        self, db: AsyncSession, game: Game
    ) -> Dict[str, Any]:
        state = game.state
        topic = state.get("topic", "")
        arguments = state.get("arguments", [])
        judge_agent_id = state.get("judge_agent_id")

        # Build argument summary
        pro_args = [a for a in arguments if a["side"] == "pro"]
        con_args = [a for a in arguments if a["side"] == "con"]

        pro_summary = "\n".join(
            f"[第{a['round']}轮] {a['content']}" for a in pro_args
        )
        con_summary = "\n".join(
            f"[第{a['round']}轮] {a['content']}" for a in con_args
        )

        if judge_agent_id:
            # Use the judge agent
            judge_agent = await db.get(Agent, judge_agent_id)
            judge_model = await db.get(Model, judge_agent.model_id)
            prompt = f"""你是本场辩论的评委。
辩题：{topic}

正方论述：
{pro_summary}

反方论述：
{con_summary}

请评判哪一方获胜，并给出理由（100字以内）。
格式：WINNER:pro 或 WINNER:con，然后是你的评语。"""
            response = await self._call_llm(judge_model, prompt)
            if response and "WINNER:pro" in response.upper():
                winner = "pro"
            elif response and "WINNER:con" in response.upper():
                winner = "con"
            else:
                winner = "undetermined"
            judgment = response or "评委未给出评语"
        else:
            # LLM-as-judge: use the first player's model
            players_result = await db.execute(
                select(GamePlayer).where(GamePlayer.game_id == game.id)
            )
            players = players_result.scalars().all()
            any_player = players[0]
            agent = await db.get(Agent, any_player.agent_id)
            model = await db.get(Model, agent.model_id)
            prompt = f"""请作为中立评委评判以下辩论。
辩题：{topic}

正方论述：
{pro_summary}

反方论述：
{con_summary}

请评判哪一方获胜，并给出理由（100字以内）。
格式：WINNER:pro 或 WINNER:con，然后是你的评语。"""
            response = await self._call_llm(model, prompt)
            if response and "WINNER:pro" in response.upper():
                winner = "pro"
            elif response and "WINNER:con" in response.upper():
                winner = "con"
            else:
                winner = "undetermined"
            judgment = response or "无法生成评语"

        # Set the winning agent as game winner
        players_result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = players_result.scalars().all()
        winner_player = next((p for p in players if p.role == winner), None)
        if winner_player:
            game.winner_id = winner_player.agent_id

        return {
            "action": "debate_judgment",
            "winner_side": winner,
            "winner_agent_id": str(winner_player.agent_id) if winner_player else None,
            "judgment": judgment,
        }

    # ========== 谈判博弈实现 ==========

    NEGOTIATION_MAX_ROUNDS = 10

    async def _setup_negotiation(self, db: AsyncSession, game: Game):
        result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = result.scalars().all()

        if len(players) < 2:
            raise ValueError("Negotiation requires at least 2 agents")

        config = game.config or {}
        hidden_goals = config.get("hidden_goals", {})
        resources = config.get("resources", {})

        # Assign hidden goals to each player
        for i, player in enumerate(players):
            agent_id_str = str(player.agent_id)
            player_goals = hidden_goals.get(agent_id_str, hidden_goals.get(str(i), {}))
            player.config = {
                **(player.config or {}),
                "hidden_goals": player_goals,
                "resources": resources.get(agent_id_str, resources.get(str(i), {})),
            }
            player.role = f"negotiator_{i}"

        game.state = {
            "round": 1,
            "phase": "negotiation",
            "max_rounds": config.get("max_rounds", self.NEGOTIATION_MAX_ROUNDS),
            "current_player_index": 0,
            "proposals": [],
            "agreements": [],
            "consensus_reached": False,
            "finished": False,
        }

    async def _process_negotiation_turn(
        self, db: AsyncSession, game: Game
    ) -> Dict[str, Any]:
        state = game.state

        if state.get("finished"):
            return {"round": state.get("round"), "phase": "negotiation", "events": [], "finished": True}

        players_result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = players_result.scalars().all()

        current_index = state.get("current_player_index", 0)
        current_player = players[current_index % len(players)]
        agent = await db.get(Agent, current_player.agent_id)
        model = await db.get(Model, agent.model_id)

        round_num = state.get("round", 1)
        max_rounds = state.get("max_rounds", self.NEGOTIATION_MAX_ROUNDS)
        proposals = state.get("proposals", [])

        # Build context of all proposals so far
        history_lines = []
        for prop in proposals[-6:]:  # Show last 6 for context
            history_lines.append(
                f"[{prop.get('agent_name', 'Unknown')}]: {prop.get('content', '')[:300]}"
            )
        history = "\n".join(history_lines) if history_lines else "（尚无提案）"

        # Get player's hidden goals
        player_config = current_player.config or {}
        hidden_goals = player_config.get("hidden_goals", {})
        goals_desc = ", ".join(
            f"{k}: {v}" for k, v in hidden_goals.items()
        ) if hidden_goals else "无特定目标"

        prompt = f"""你是 {agent.name}，参与一场谈判。
当前第 {round_num}/{max_rounds} 轮。

你的隐藏目标：{goals_desc}

前序提案：
{history}

请提出你的方案或对前序提案做出回应。要求：
- 明确表达你愿意接受或拒绝的条件
- 提出具体的交易方案
- 150字以内
- 如果你同意当前方案，请以 AGREE: 开头回复
- 如果不同意，请提出你的反提案"""

        response = await self._call_llm(model, prompt)
        content = response or "(无回应)"
        agrees = content.upper().startswith("AGREE:")

        proposal_entry = {
            "round": round_num,
            "agent_id": str(current_player.agent_id),
            "agent_name": agent.name,
            "content": content,
            "agrees": agrees,
        }
        proposals.append(proposal_entry)
        state["proposals"] = proposals

        # Check for consensus
        if agrees:
            state["agreements"].append(str(current_player.agent_id))

        # Consensus = all players agree
        all_agent_ids = {str(p.agent_id) for p in players}
        agreed_ids = set(state.get("agreements", []))

        # Only count agreements that reference the latest proposal
        # Reset agreements if latest is not an agreement
        if not agrees:
            state["agreements"] = []
        elif agreed_ids >= all_agent_ids:
            state["consensus_reached"] = True
            state["finished"] = True
            scores = await self._score_negotiation(db, game)
            return {
                "round": round_num,
                "phase": "negotiation",
                "events": [proposal_entry, {"action": "consensus", "scores": scores}],
                "finished": True,
            }

        # Advance to next player
        next_index = (current_index + 1) % len(players)
        state["current_player_index"] = next_index

        # Advance round when we've gone through all players
        if next_index == 0:
            state["round"] = round_num + 1
            if round_num + 1 > max_rounds:
                state["finished"] = True
                scores = await self._score_negotiation(db, game)
                return {
                    "round": round_num,
                    "phase": "negotiation",
                    "events": [proposal_entry, {"action": "max_rounds_reached", "scores": scores}],
                    "finished": True,
                }

        return {
            "round": round_num,
            "phase": "negotiation",
            "events": [proposal_entry],
        }

    async def _score_negotiation(
        self, db: AsyncSession, game: Game
    ) -> Dict[str, Any]:
        """Score each agent based on how well the final deal matches their hidden goals."""
        state = game.state
        proposals = state.get("proposals", [])

        # Get the last proposal as the "final deal"
        final_deal = proposals[-1]["content"] if proposals else ""

        players_result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = players_result.scalars().all()

        scores = {}
        best_score = -1
        best_agent_id = None

        for player in players:
            agent = await db.get(Agent, player.agent_id)
            model = await db.get(Model, agent.model_id)
            player_config = player.config or {}
            hidden_goals = player_config.get("hidden_goals", {})
            goals_desc = ", ".join(
                f"{k}: {v}" for k, v in hidden_goals.items()
            ) if hidden_goals else "无特定目标"

            prompt = f"""评估以下谈判结果对该参与者的满足程度。
参与者：{agent.name}
隐藏目标：{goals_desc}
最终方案：{final_deal[:500]}

请给出 0-100 的分数，仅回复数字。"""

            response = await self._call_llm(model, prompt)
            try:
                score = int("".join(c for c in (response or "0") if c.isdigit()) or "0")
                score = max(0, min(100, score))
            except (ValueError, TypeError):
                score = 0

            agent_id_str = str(player.agent_id)
            scores[agent_id_str] = {
                "agent_name": agent.name,
                "score": score,
                "hidden_goals": hidden_goals,
            }

            if score > best_score:
                best_score = score
                best_agent_id = player.agent_id

        # Set winner to highest scorer
        if best_agent_id:
            game.winner_id = best_agent_id

        return scores


game_engine = GameEngine()
