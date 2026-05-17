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
        elif game.game_type == GameType.CHESS:
            await self._setup_chess(db, game)
        elif game.game_type == GameType.TEXT_ADVENTURE:
            await self._setup_text_adventure(db, game)
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
        elif game.game_type == GameType.CHESS:
            result = await self._process_chess_turn(db, game)
        elif game.game_type == GameType.TEXT_ADVENTURE:
            result = await self._process_adventure_turn(db, game)
        else:
            raise ValueError(f"Unsupported game type: {game.game_type}")

        winner = await self._check_winner(db, game)
        if winner:
            game.status = GameStatus.FINISHED
            game.state["winner"] = winner
            game.updated_at = datetime.now(timezone.utc)
            self._log_event(game, {
                "type": "game_over",
                "winner": winner,
                "message": f"游戏结束！{'村民' if winner == 'villagers' else '狼人'}阵营获胜！",
            })
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

        is_game_over = game.status == GameStatus.FINISHED

        player_list = []
        for p in players:
            agent = await db.get(Agent, p.agent_id)
            player_info = {
                "agent_id": str(p.agent_id),
                "agent_name": agent.name if agent else "Unknown",
                "is_alive": bool(p.is_alive),
            }
            # Only reveal roles if game is over
            if is_game_over:
                player_info["role"] = p.role
            else:
                player_info["role"] = None  # Hidden during gameplay
            player_list.append(player_info)

        state = game.state or {}
        events = state.pop("events", []) if state else []

        return {
            "game_id": str(game.id),
            "game_type": game.game_type,
            "status": game.status,
            "state": state,
            "players": player_list,
            "events": events,
            "winner_id": str(game.winner_id) if game.winner_id else None,
            "winner": state.get("winner") if is_game_over else None,
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
            "events": [],
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
                f"{(a.name if (a := await db.get(Agent, t.agent_id)) else 'Unknown')}(ID:{t.agent_id})"
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
                    target_agent = await db.get(Agent, next(t.agent_id for t in wolf_targets if str(t.agent_id) == target_id))
                    self._log_event(game, {
                        "type": "night_action",
                        "action": "wolf_kill",
                        "agent_id": str(wolf.agent_id),
                        "agent_name": agent.name,
                        "target_id": target_id,
                        "target_name": target_agent.name if target_agent else "Unknown",
                    })
            else:
                self._log_llm_failure(game, agent.name, "werewolf", "狼人击杀")
                # Default: pick a random target
                if wolf_targets:
                    fallback = random.choice(wolf_targets)
                    state["night_actions"]["wolf_target"] = str(fallback.agent_id)
                    self._log_event(game, {
                        "type": "system",
                        "action": "default_action",
                        "role": "werewolf",
                        "message": f"[系统] 狼人随机选择了目标",
                    })

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
                    f"{(a.name if (a := await db.get(Agent, t.agent_id)) else 'Unknown')}(ID:{t.agent_id})"
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
                            checked_agent = await db.get(Agent, checked_player.agent_id)
                            events.append({
                                "action": "seer_check",
                                "agent_id": str(seer.agent_id),
                                "agent_name": agent.name,
                                "target": check_id,
                                "target_name": checked_agent.name if checked_agent else "Unknown",
                                "result": "werewolf" if is_wolf else "villager",
                            })
                else:
                    self._log_llm_failure(game, agent.name, "seer", "预言家查验")
                    # Default: check a random target
                    fallback = random.choice(check_targets)
                    checked_player = next(
                        (p for p in players if p.agent_id == fallback.agent_id), None
                    )
                    if checked_player:
                        is_wolf = checked_player.role == "werewolf"
                        state["seer_results"][str(fallback.agent_id)] = is_wolf
                        state["night_actions"]["seer_check"] = str(fallback.agent_id)
                        events.append({
                            "action": "seer_check",
                            "agent_id": str(seer.agent_id),
                            "agent_name": agent.name,
                            "target": str(fallback.agent_id),
                            "target_name": "Unknown",
                            "result": "werewolf" if is_wolf else "villager",
                            "default": True,
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
                    events.append({
                        "action": "witch_save",
                        "agent_id": str(witch.agent_id),
                        "agent_name": agent.name,
                    })
                elif action.get("poison"):
                    poison_target = action["poison"]
                    state["night_actions"]["witch_poison"] = poison_target
                    state["witch_poison_used"] = True
                    poison_agent = await db.get(Agent, next((p.agent_id for p in players if str(p.agent_id) == poison_target), None))
                    events.append({
                        "action": "witch_poison",
                        "agent_id": str(witch.agent_id),
                        "agent_name": agent.name,
                        "target": poison_target,
                        "target_name": poison_agent.name if poison_agent else "Unknown",
                    })
                else:
                    events.append({
                        "action": "witch_skip",
                        "agent_id": str(witch.agent_id),
                        "agent_name": agent.name,
                    })
            else:
                self._log_llm_failure(game, agent.name, "witch", "女巫行动")
                events.append({
                    "action": "witch_skip",
                    "agent_id": str(witch.agent_id),
                    "agent_name": agent.name,
                    "default": True,
                })

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
            f"{(a.name if (a := await db.get(Agent, t.agent_id)) else 'Unknown')}(ID:{t.agent_id})"
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
                (a.name if (a := await db.get(Agent, p.agent_id)) else 'Unknown') for p in alive_players
            ]
            prompt = self._build_werewolf_prompt(
                agent, player.role, state, "day_discussion", alive_names
            )
            response = await self._call_llm(model, prompt)
            if response is None:
                self._log_llm_failure(game, agent.name, player.role, "白天讨论")
                response = "(沉默...)"
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
                f"{(a.name if (a := await db.get(Agent, p.agent_id)) else 'Unknown')}(ID:{p.agent_id})"
                for p in alive_players
                if p.agent_id != player.agent_id
            ]
            prompt = self._build_werewolf_prompt(
                agent, player.role, state, "day_vote", candidates
            )
            response = await self._call_llm(model, prompt)
            other_players = [p for p in alive_players if p.agent_id != player.agent_id]
            if response is not None:
                vote_target = self._extract_target_id(response, other_players)
                if vote_target:
                    votes[str(player.agent_id)] = vote_target
            else:
                self._log_llm_failure(game, agent.name, player.role, "白天投票")
                # Default: random vote
                if other_players:
                    fallback = random.choice(other_players)
                    votes[str(player.agent_id)] = str(fallback.agent_id)
                    self._log_event(game, {
                        "type": "system",
                        "action": "default_vote",
                        "agent_id": str(player.agent_id),
                        "agent_name": agent.name,
                        "message": f"[系统] {agent.name} 随机投票",
                    })

        # 统计投票
        vote_counts: Dict[str, int] = {}
        for voter, target in votes.items():
            vote_counts[target] = vote_counts.get(target, 0) + 1

        state["day_votes"] = {"votes": votes, "counts": vote_counts}

        # Log vote details
        vote_details = []
        for voter_id, target_id in votes.items():
            voter_agent = await db.get(Agent, voter_id)
            target_agent = await db.get(Agent, target_id)
            vote_details.append({
                "voter_id": voter_id,
                "voter_name": voter_agent.name if voter_agent else "Unknown",
                "target_id": target_id,
                "target_name": target_agent.name if target_agent else "Unknown",
            })
        events.append({
            "action": "vote_result",
            "votes": vote_details,
            "counts": vote_counts,
        })

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
                        "role": player.role,
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
        if game.game_type == GameType.CHESS:
            if game.state.get("finished"):
                return game.state.get("winner", "draw")
            return None
        if game.game_type == GameType.TEXT_ADVENTURE:
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

    def _log_event(self, game: Game, event: Dict[str, Any]):
        """Append an event to the game's event log."""
        if "events" not in game.state:
            game.state["events"] = []
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        game.state["events"].append(event)

    def _log_llm_failure(self, game: Game, agent_name: str, role: str, phase: str):
        """Log an LLM failure event and return a system message."""
        msg = f"[系统] {agent_name}({role}) 在{phase}阶段未能响应，已跳过"
        self._log_event(game, {
            "type": "system",
            "action": "llm_failure",
            "agent_name": agent_name,
            "role": role,
            "phase": phase,
            "message": msg,
        })
        logger.warning("LLM failure for %s(%s) in %s", agent_name, role, phase)
        return msg

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

    # ========== 国际象棋实现 ==========

    # Unicode chess pieces
    CHESS_PIECES = {
        "wK": "♔", "wQ": "♕", "wR": "♖", "wB": "♗", "wN": "♘", "wP": "♙",
        "bK": "♚", "bQ": "♛", "bR": "♜", "bB": "♝", "bN": "♞", "bP": "♟",
    }

    @staticmethod
    def _initial_board() -> List[List[str]]:
        """Return an 8x8 board in standard starting position."""
        return [
            ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"],
            ["bP", "bP", "bP", "bP", "bP", "bP", "bP", "bP"],
            ["", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "", ""],
            ["wP", "wP", "wP", "wP", "wP", "wP", "wP", "wP"],
            ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"],
        ]

    def _board_to_ascii(self, board: List[List[str]]) -> str:
        """Convert board state to an ASCII art representation."""
        lines = ["  a b c d e f g h"]
        for row in range(8):
            rank = 8 - row
            cells = []
            for col in range(8):
                piece = board[row][col]
                if piece:
                    cells.append(self.CHESS_PIECES.get(piece, "?"))
                else:
                    cells.append(".")
            lines.append(f"{rank} {' '.join(cells)} {rank}")
        lines.append("  a b c d e f g h")
        return "\n".join(lines)

    @staticmethod
    def _parse_square(text: str) -> Optional[tuple]:
        """Parse a square like 'e2' into (row, col). Returns None if invalid."""
        text = text.strip().lower()
        if len(text) < 2:
            return None
        file_char = text[0]
        rank_char = text[1]
        if file_char < 'a' or file_char > 'h':
            return None
        if rank_char < '1' or rank_char > '8':
            return None
        col = ord(file_char) - ord('a')
        row = 8 - int(rank_char)
        return (row, col)

    @staticmethod
    def _square_name(row: int, col: int) -> str:
        """Convert (row, col) to algebraic notation like 'e4'."""
        return f"{chr(ord('a') + col)}{8 - row}"

    async def _setup_chess(self, db: AsyncSession, game: Game):
        result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = result.scalars().all()

        if len(players) < 2:
            raise ValueError("Chess requires exactly 2 agents")

        players[0].role = "white"
        players[1].role = "black"

        game.state = {
            "round": 1,
            "phase": "chess",
            "board": self._initial_board(),
            "current_turn": "white",
            "move_history": [],
            "white_agent_id": str(players[0].agent_id),
            "black_agent_id": str(players[1].agent_id),
            "captured_pieces": {"white": [], "black": []},
            "finished": False,
            "winner": None,
        }

    def _parse_move_response(
        self, response: str, board: List[List[str]], color: str
    ) -> Optional[Dict[str, Any]]:
        """Parse an LLM move response into source/target squares.

        Supports formats like: e2e4, e2-e4, Nf3, Nf3e5, O-O, O-O-O, etc.
        Returns {"from": (r,c), "to": (r,c), "piece": str, "capture": bool} or None.
        """
        import re
        text = response.strip().upper()

        # Handle castling
        if "O-O-O" in text or "OOO" in text:
            row = 7 if color == "white" else 0
            king = board[row][4]
            rook = board[row][0]
            if (color == "white" and king == "wK" and rook == "wR") or \
               (color == "black" and king == "bK" and rook == "bR"):
                return {"from": (row, 4), "to": (row, 2), "piece": king, "capture": False,
                        "castle_rook_from": (row, 0), "castle_rook_to": (row, 3)}
        if "O-O" in text or "OO" in text:
            row = 7 if color == "white" else 0
            king = board[row][4]
            rook = board[row][7]
            if (color == "white" and king == "wK" and rook == "wR") or \
               (color == "black" and king == "bK" and rook == "bR"):
                return {"from": (row, 4), "to": (row, 6), "piece": king, "capture": False,
                        "castle_rook_from": (row, 7), "castle_rook_to": (row, 5)}

        prefix = color[0]  # 'w' or 'b'

        # Try "e2e4" or "e2-e4" format (4 chars with optional dash)
        clean = text.replace("-", "").replace("X", "").replace(" ", "")
        sq_pattern = r"([A-H][1-8])"
        squares_found = re.findall(sq_pattern, clean)
        if len(squares_found) >= 2:
            src = self._parse_square(squares_found[0])
            dst = self._parse_square(squares_found[1])
            if src and dst:
                piece = board[src[0]][src[1]]
                if piece and piece[0] == prefix:
                    target = board[dst[0]][dst[1]]
                    is_capture = bool(target and target[0] != prefix)
                    return {"from": src, "to": dst, "piece": piece, "capture": is_capture}

        # Try standard algebraic: Nf3, Bxe5, Qd1, e4, etc.
        # Extract the move part after any leading description
        # Look for patterns like [NBKQR]?x?[a-h][1-8]
        san_match = re.search(r"([NBKQR])?([A-H])?([1-8])?X?([A-H])([1-8])", clean)
        if not san_match:
            # Try simple pawn move like E4
            san_match = re.search(r"([A-H])([1-8])", clean)
            if san_match and len(clean) <= 4:
                dst_col = ord(san_match.group(1)) - ord('A')
                dst_row = 8 - int(san_match.group(2))
                # Find a pawn of the right color that can reach this square
                direction = -1 if color == "white" else 1
                for dr in [1, 2]:
                    src_row = dst_row + dr * direction
                    if 0 <= src_row <= 7:
                        piece = board[src_row][dst_col]
                        if piece == f"{prefix}P":
                            target = board[dst_row][dst_col]
                            is_capture = bool(target and target[0] != prefix)
                            return {"from": (src_row, dst_col), "to": (dst_row, dst_col),
                                    "piece": piece, "capture": is_capture}
                return None

        piece_letter = san_match.group(1)
        dst_col = ord(san_match.group(4)) - ord('A')
        dst_row = 8 - int(san_match.group(5))

        if piece_letter:
            # Piece move
            piece_map = {"K": "K", "Q": "Q", "R": "R", "B": "B", "N": "N"}
            piece_type = piece_map.get(piece_letter, "")
            full_piece = f"{prefix}{piece_type}"
            # Find the piece on the board
            candidates = []
            for r in range(8):
                for c in range(8):
                    if board[r][c] == full_piece:
                        candidates.append((r, c))
            if len(candidates) == 1:
                src = candidates[0]
            elif len(candidates) > 1:
                # Disambiguate using hint columns/rows
                hint_col = None
                hint_row = None
                if san_match.group(2):
                    hint_col = ord(san_match.group(2)) - ord('A')
                if san_match.group(3):
                    hint_row = 8 - int(san_match.group(3))
                filtered = candidates
                if hint_col is not None:
                    filtered = [c for c in filtered if c[1] == hint_col]
                if hint_row is not None:
                    filtered = [c for c in filtered if c[0] == hint_row]
                src = filtered[0] if filtered else candidates[0]
            else:
                return None
            target = board[dst_row][dst_col]
            is_capture = bool(target and target[0] != prefix)
            return {"from": src, "to": (dst_row, dst_col), "piece": full_piece, "capture": is_capture}
        else:
            # Pawn move or capture
            hint_col = None
            if san_match.group(2):
                hint_col = ord(san_match.group(2)) - ord('A')
            if hint_col is not None:
                # Pawn capture: source column is given
                src_row_candidates = []
                direction = -1 if color == "white" else 1
                for dr in [1, 2]:
                    sr = dst_row + dr * direction
                    if 0 <= sr <= 7 and board[sr][hint_col] == f"{prefix}P":
                        src_row_candidates.append(sr)
                if src_row_candidates:
                    src_row = src_row_candidates[0]
                    target = board[dst_row][dst_col]
                    return {"from": (src_row, hint_col), "to": (dst_row, dst_col),
                            "piece": f"{prefix}P", "capture": bool(target)}
            else:
                # Simple pawn move forward
                direction = -1 if color == "white" else 1
                for dr in [1, 2]:
                    sr = dst_row + dr * direction
                    if 0 <= sr <= 7 and board[sr][dst_col] == f"{prefix}P":
                        # For 2-square move, check starting row
                        if dr == 2:
                            start_row = 6 if color == "white" else 1
                            if sr != start_row:
                                continue
                        target = board[dst_row][dst_col]
                        return {"from": (sr, dst_col), "to": (dst_row, dst_col),
                                "piece": f"{prefix}P", "capture": bool(target)}

        return None

    def _validate_pawn_move(self, src: tuple, dst: tuple, color: str, board: List[List[str]]) -> bool:
        """Basic pawn move validation."""
        direction = -1 if color == "white" else 1
        start_row = 6 if color == "white" else 1
        dr = dst[0] - src[0]
        dc = dst[1] - src[1]

        # Forward one square
        if dc == 0 and dr == direction and not board[dst[0]][dst[1]]:
            return True
        # Forward two squares from start
        if dc == 0 and dr == 2 * direction and src[0] == start_row and \
           not board[src[0] + direction][src[1]] and not board[dst[0]][dst[1]]:
            return True
        # Diagonal capture
        if abs(dc) == 1 and dr == direction and board[dst[0]][dst[1]]:
            return True
        return False

    def _validate_move(
        self, move: Dict[str, Any], board: List[List[str]], color: str
    ) -> bool:
        """Basic move validation. Returns True if the move looks legal."""
        src = move["from"]
        dst = move["to"]
        piece = move["piece"]

        # Source must have the piece
        if board[src[0]][src[1]] != piece:
            return False
        # Can't capture own piece
        target = board[dst[0]][dst[1]]
        if target and target[0] == color[0]:
            return False
        # Can't stay in place
        if src == dst:
            return False

        # Basic pawn validation
        if piece[1] == "P":
            return self._validate_pawn_move(src, dst, color, board)

        # For other pieces, basic checks only (leave complex rules to LLM)
        piece_type = piece[1]
        dr = abs(dst[0] - src[0])
        dc = abs(dst[1] - src[1])

        if piece_type == "N":
            # Knight: L-shape
            return (dr == 2 and dc == 1) or (dr == 1 and dc == 2)
        elif piece_type == "K":
            # King: one square any direction
            return dr <= 1 and dc <= 1
        elif piece_type == "R":
            # Rook: straight lines (simplified - no path check)
            return dr == 0 or dc == 0
        elif piece_type == "B":
            # Bishop: diagonal (simplified)
            return dr == dc
        elif piece_type == "Q":
            # Queen: straight or diagonal (simplified)
            return dr == 0 or dc == 0 or dr == dc

        return True

    def _apply_move(self, board: List[List[str]], move: Dict[str, Any]) -> tuple:
        """Apply a move to the board. Returns (new_board, captured_piece)."""
        new_board = [row[:] for row in board]
        src = move["from"]
        dst = move["to"]
        captured = new_board[dst[0]][dst[1]] or None

        new_board[dst[0]][dst[1]] = new_board[src[0]][src[1]]
        new_board[src[0]][src[1]] = ""

        # Handle castling rook
        if "castle_rook_from" in move:
            rook_src = move["castle_rook_from"]
            rook_dst = move["castle_rook_to"]
            new_board[rook_dst[0]][rook_dst[1]] = new_board[rook_src[0]][rook_src[1]]
            new_board[rook_src[0]][rook_src[1]] = ""

        # Pawn promotion: auto-promote to queen
        piece = new_board[dst[0]][dst[1]]
        if piece and piece[1] == "P":
            if (piece[0] == "w" and dst[0] == 0) or (piece[0] == "b" and dst[0] == 7):
                new_board[dst[0]][dst[1]] = piece[0] + "Q"

        return new_board, captured

    def _check_king_captured(self, board: List[List[str]]) -> Optional[str]:
        """Check if either king is missing (simplified checkmate detection)."""
        white_king = False
        black_king = False
        for row in board:
            for cell in row:
                if cell == "wK":
                    white_king = True
                elif cell == "bK":
                    black_king = True
        if not white_king:
            return "black"
        if not black_king:
            return "white"
        return None

    async def _process_chess_turn(
        self, db: AsyncSession, game: Game
    ) -> Dict[str, Any]:
        state = game.state
        board = state["board"]
        current_turn = state["current_turn"]
        move_history = state.get("move_history", [])

        if state.get("finished"):
            return {"round": state.get("round"), "phase": "chess", "events": [], "finished": True}

        # Get current player agent
        agent_id_key = f"{current_turn}_agent_id"
        current_agent_id = state[agent_id_key]
        agent = await db.get(Agent, current_agent_id)
        model = await db.get(Model, agent.model_id)

        # Build prompt
        board_ascii = self._board_to_ascii(board)
        color_label = "白方(White)" if current_turn == "white" else "黑方(Black)"
        recent_moves = move_history[-10:] if move_history else []
        moves_text = ", ".join(recent_moves) if recent_moves else "（尚无走棋记录）"

        prompt = f"""你是 {agent.name}，正在下国际象棋。
你是 {color_label}，使用 {color_label.split('(')[1].rstrip(')')} 方的棋子。

当前棋盘：
{board_ascii}

走棋记录：{moves_text}

轮到你走棋。请用标准代数记谱法回复你的走法。
格式示例：
- e2e4（兵从e2走到e4）
- Nf3（马走到f3）
- Bxe5（象吃掉e5的棋子）
- O-O（王翼易位）
- O-O-O（后翼易位）

请只回复走法，不要有其他文字。"""

        max_retries = 3
        move = None
        last_error = ""

        for attempt in range(max_retries):
            if attempt > 0:
                retry_prompt = prompt + f"\n\n你上次的走法无效：{last_error}，请重新选择走法。"
                response = await self._call_llm(model, retry_prompt)
            else:
                response = await self._call_llm(model, prompt)

            if not response:
                last_error = "未收到回复"
                continue

            parsed = self._parse_move_response(response, board, current_turn)
            if not parsed:
                last_error = f"无法解析走法 '{response.strip()}'"
                continue

            if not self._validate_move(parsed, board, current_turn):
                last_error = f"走法不合法: {self._square_name(*parsed['from'])}-{self._square_name(*parsed['to'])}"
                continue

            move = parsed
            break

        if not move:
            # If all retries failed, skip this turn
            return {
                "round": state.get("round", 1),
                "phase": "chess",
                "events": [{
                    "action": "invalid_move",
                    "agent_id": current_agent_id,
                    "agent_name": agent.name,
                    "error": last_error,
                }],
            }

        # Apply the move
        new_board, captured = self._apply_move(board, move)
        move_notation = f"{self._square_name(*move['from'])}-{self._square_name(*move['to'])}"
        if captured:
            move_notation += f" (吃{captured})"

        state["board"] = new_board
        move_history.append(move_notation)
        state["move_history"] = move_history

        # Track captured pieces
        if captured:
            captured_color = "black" if current_turn == "white" else "white"
            state["captured_pieces"][captured_color].append(captured)

        # Check for king capture (simplified checkmate)
        winner_color = self._check_king_captured(new_board)
        event = {
            "action": "move",
            "agent_id": current_agent_id,
            "agent_name": agent.name,
            "color": current_turn,
            "move": move_notation,
            "board": self._board_to_ascii(new_board),
        }
        if captured:
            event["captured"] = captured

        if winner_color:
            state["finished"] = True
            state["winner"] = winner_color
            winner_agent_id = state[f"{winner_color}_agent_id"]
            game.winner_id = winner_agent_id
            event["checkmate"] = True

        # Switch turns
        state["current_turn"] = "black" if current_turn == "white" else "white"
        state["round"] = state.get("round", 1) + 1

        return {
            "round": state.get("round", 1),
            "phase": "chess",
            "events": [event],
        }

    # ========== 文字冒险实现 ==========

    ADVENTURE_MAX_TURNS = 30

    async def _setup_text_adventure(self, db: AsyncSession, game: Game):
        result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = result.scalars().all()

        if len(players) < 2:
            raise ValueError("Text adventure requires at least 2 agents")

        config = game.config or {}
        starting_scene = config.get("starting_scene", "a mysterious dungeon entrance")
        max_turns = config.get("max_turns", self.ADVENTURE_MAX_TURNS)
        goal = config.get("goal", "find the legendary treasure hidden deep within")

        # First agent is narrator/game master, rest are explorers
        narrator = players[0]
        narrator.role = "narrator"
        explorer_ids = []
        for player in players[1:]:
            player.role = "explorer"
            explorer_ids.append(str(player.agent_id))

        game.state = {
            "round": 1,
            "phase": "adventure",
            "scene": starting_scene,
            "inventory": {str(p.agent_id): [] for p in players[1:]},
            "hp": {str(p.agent_id): 100 for p in players[1:]},
            "turn_count": 0,
            "narrator_agent_id": str(narrator.agent_id),
            "explorer_agents": explorer_ids,
            "events": [],
            "max_turns": max_turns,
            "goal": goal,
            "current_explorer_index": 0,
            "narrator_rotation_counter": 0,
            "finished": False,
            "winner": None,
        }

    async def _process_adventure_turn(
        self, db: AsyncSession, game: Game
    ) -> Dict[str, Any]:
        state = game.state

        if state.get("finished"):
            return {"round": state.get("round"), "phase": "adventure", "events": [], "finished": True}

        turn_count = state.get("turn_count", 0)
        phase = state.get("phase", "adventure")

        players_result = await db.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id)
        )
        players = players_result.scalars().all()

        if phase == "adventure":
            # Narrator describes the scene and presents choices
            result = await self._adventure_narrator_phase(db, game, players)
            state["phase"] = "adventure_choice"
            return result
        else:
            # Explorers choose actions
            result = await self._adventure_explorer_phase(db, game, players)
            state["phase"] = "adventure"
            state["turn_count"] = turn_count + 1
            return result

    async def _adventure_narrator_phase(
        self, db: AsyncSession, game: Game, players: List[GamePlayer]
    ) -> Dict[str, Any]:
        state = game.state
        narrator_id = state["narrator_agent_id"]
        narrator_agent = await db.get(Agent, narrator_id)
        narrator_model = await db.get(Model, narrator_agent.model_id)

        scene = state.get("scene", "")
        events = state.get("events", [])
        recent_events = events[-5:] if events else []
        explorer_agents = state["explorer_agents"]
        goal = state.get("goal", "")

        # Build explorer status
        explorer_status = []
        for eid in explorer_agents:
            agent = await db.get(Agent, eid)
            hp = state["hp"].get(eid, 0)
            inv = state["inventory"].get(eid, [])
            explorer_status.append(f"- {agent.name}: HP={hp}, 物品={inv if inv else '无'}")

        events_text = ""
        if recent_events:
            event_lines = []
            for evt in recent_events:
                event_lines.append(f"- {evt.get('description', str(evt))}")
            events_text = "\n".join(event_lines)

        prompt = f"""你是 {narrator_agent.name}，作为地下城主/叙述者引导一场文字冒险。

冒险目标：{goal}
当前场景：{scene}

冒险者状态：
{chr(10).join(explorer_status)}

近期事件：
{events_text if events_text else '（冒险刚开始）'}

请描述当前场景（150字以内），并给出 2-3 个可选行动。
格式要求：
SCENE: <场景描述>
CHOICE1: <选项1描述>
CHOICE2: <选项2描述>
CHOICE3: <选项3描述（可选）>"""

        response = await self._call_llm(narrator_model, prompt)
        content = response or "(叙述者沉默了...)"

        # Parse scene and choices
        scene_text = content
        choices = []
        for line in content.split("\n"):
            line = line.strip()
            upper = line.upper()
            if upper.startswith("SCENE:"):
                scene_text = line[6:].strip()
            elif upper.startswith("CHOICE"):
                colon_idx = line.find(":")
                if colon_idx >= 0:
                    choices.append(line[colon_idx + 1:].strip())

        if not choices:
            choices = ["继续前进", "仔细观察周围", "休息一下"]

        state["scene"] = scene_text
        state["current_choices"] = choices

        event_entry = {
            "type": "narration",
            "agent_id": narrator_id,
            "agent_name": narrator_agent.name,
            "scene": scene_text,
            "choices": choices,
            "description": f"[叙述者 {narrator_agent.name}] {scene_text}",
        }
        events.append(event_entry)
        state["events"] = events

        return {
            "round": state.get("round", 1),
            "phase": "adventure",
            "events": [event_entry],
        }

    async def _adventure_explorer_phase(
        self, db: AsyncSession, game: Game, players: List[GamePlayer]
    ) -> Dict[str, Any]:
        state = game.state
        explorer_agents = state["explorer_agents"]
        choices = state.get("current_choices", [])
        scene = state.get("scene", "")
        events = state.get("events", [])

        # Each explorer votes/describes their action
        explorer_actions = []
        alive_explorers = [
            eid for eid in explorer_agents if state["hp"].get(eid, 0) > 0
        ]

        for eid in alive_explorers:
            agent = await db.get(Agent, eid)
            model = await db.get(Model, agent.model_id)
            hp = state["hp"].get(eid, 0)
            inv = state["inventory"].get(eid, [])

            choices_text = "\n".join(f"{i+1}. {c}" for i, c in enumerate(choices))
            prompt = f"""你是 {agent.name}，一名冒险者。
当前场景：{scene}
你的HP：{hp}
你的物品：{inv if inv else '无'}

可选行动：
{choices_text}

你也可以描述自己的独特行动。
请回复选项编号（1/2/3）或描述你的行动（50字以内）。"""

            response = await self._call_llm(model, prompt)
            action_text = response or "观察四周"
            explorer_actions.append({
                "agent_id": eid,
                "agent_name": agent.name,
                "action": action_text,
            })

        # Narrator resolves actions
        narrator_id = state["narrator_agent_id"]
        narrator_agent = await db.get(Agent, narrator_id)
        narrator_model = await db.get(Model, narrator_agent.model_id)

        actions_summary = "\n".join(
            f"- {a['agent_name']}: {a['action']}" for a in explorer_actions
        )

        prompt = f"""你是 {narrator_agent.name}，作为地下城主。

当前场景：{scene}

冒险者的行动：
{actions_summary}

请描述行动的结果（150字以内）。可以包含：
- HP 变化（用 HP:+10 或 HP:-20 表示）
- 发现物品（用 ITEM:<agent名字>:<物品名> 表示）
- 是否到达目标（用 GOAL_REACHED 表示）
- 是否有人死亡（用 DEATH:<agent名字> 表示）

格式：
RESULT: <结果描述>
HP:<agent名字>:<变化量>（可多行）
ITEM:<agent名字>:<物品名>（可多行）"""

        response = await self._call_llm(narrator_model, prompt)
        content = response or "(结果未知...)"

        # Parse result
        result_text = content
        hp_changes = {}
        items_found = {}
        goal_reached = False
        deaths = []

        for line in content.split("\n"):
            line = line.strip()
            upper = line.upper()
            if upper.startswith("RESULT:"):
                result_text = line[7:].strip()
            elif upper.startswith("HP:"):
                parts = line[3:].split(":")
                if len(parts) >= 2:
                    name = parts[0].strip()
                    try:
                        change = int(parts[1].strip())
                        hp_changes[name] = change
                    except ValueError:
                        pass
            elif upper.startswith("ITEM:"):
                parts = line[5:].split(":")
                if len(parts) >= 2:
                    name = parts[0].strip()
                    item = parts[1].strip()
                    items_found[name] = item
            elif "GOAL_REACHED" in upper:
                goal_reached = True
            elif upper.startswith("DEATH:"):
                name = line[6:].strip()
                deaths.append(name)

        # Apply HP changes
        for name, change in hp_changes.items():
            for eid in explorer_agents:
                agent = await db.get(Agent, eid)
                if agent and agent.name == name:
                    state["hp"][eid] = max(0, min(100, state["hp"].get(eid, 0) + change))

        # Apply item discoveries
        for name, item in items_found.items():
            for eid in explorer_agents:
                agent = await db.get(Agent, eid)
                if agent and agent.name == name:
                    if eid not in state["inventory"]:
                        state["inventory"][eid] = []
                    state["inventory"][eid].append(item)

        # Apply deaths
        for name in deaths:
            for eid in explorer_agents:
                agent = await db.get(Agent, eid)
                if agent and agent.name == name:
                    state["hp"][eid] = 0

        # Check win/loss conditions
        all_dead = all(state["hp"].get(eid, 0) <= 0 for eid in explorer_agents)
        max_turns = state.get("max_turns", self.ADVENTURE_MAX_TURNS)
        turn_count = state.get("turn_count", 0)

        if goal_reached:
            state["finished"] = True
            state["winner"] = "explorers"
        elif all_dead:
            state["finished"] = True
            state["winner"] = "dungeon"
        elif turn_count + 1 >= max_turns:
            state["finished"] = True
            state["winner"] = "timeout"

        # Rotate narrator every 3 turns
        state["narrator_rotation_counter"] = state.get("narrator_rotation_counter", 0) + 1
        if state["narrator_rotation_counter"] >= 3 and not state.get("finished"):
            state["narrator_rotation_counter"] = 0
            # Find next alive explorer to become narrator
            current_narrator = state["narrator_agent_id"]
            alive_explorers = [
                eid for eid in explorer_agents if state["hp"].get(eid, 0) > 0
            ]
            if alive_explorers:
                next_narrator = alive_explorers[0]
                state["narrator_agent_id"] = next_narrator
                state["explorer_agents"] = [eid for eid in explorer_agents if eid != next_narrator] + [current_narrator]

        # Update scene for next narration
        state["scene"] = result_text

        event_entry = {
            "type": "resolution",
            "narrator_id": narrator_id,
            "narrator_name": narrator_agent.name,
            "actions": explorer_actions,
            "result": result_text,
            "hp_changes": hp_changes,
            "items_found": items_found,
            "description": f"[结果] {result_text}",
        }
        events.append(event_entry)
        state["events"] = events

        # Advance round
        state["round"] = state.get("round", 1) + 1

        return {
            "round": state.get("round", 1),
            "phase": "adventure",
            "events": [event_entry],
        }


game_engine = GameEngine()
