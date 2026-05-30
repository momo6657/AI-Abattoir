"""Game engine for AI Abattoir — supports werewolf, debate, chess, text_adventure, negotiation."""

from __future__ import annotations

import asyncio
import enum
import logging
import random
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional

from app.models.game import GameType

logger = logging.getLogger(__name__)

TERMINAL_EVENT_TYPES = {
    "game_over",
    "max_turns_reached",
    "debate_result",
    "negotiation_scores",
    "negotiation_failed",
}

ERROR_EVENT_TYPES = {"error", "turn_error", "turn_timeout"}

WEREWOLF_ROLE_NAMES = {
    "werewolf": "狼人",
    "seer": "预言家",
    "guard": "守卫",
    "witch": "女巫",
    "hunter": "猎人",
    "villager": "村民",
}


# ==================== 辩题库 ====================

DEBATE_TOPICS = [
    {"topic": "人工智能是否会取代人类工作", "pro": "AI将创造更多就业机会", "con": "AI将导致大规模失业"},
    {"topic": "社交媒体对心理健康的影响", "pro": "社交媒体促进了人际连接", "con": "社交媒体加剧了焦虑和抑郁"},
    {"topic": "远程办公是否应该成为常态", "pro": "远程办公提升效率和幸福感", "con": "远程办公削弱团队协作"},
    {"topic": "应不应该给儿童布置家庭作业", "pro": "作业巩固学习效果", "con": "作业增加压力且效果有限"},
    {"topic": "大学教育是否值得其成本", "pro": "大学教育带来长远回报", "con": "大学教育成本过高且回报不确定"},
    {"topic": "自动驾驶汽车是否应该合法化", "pro": "自动驾驶减少交通事故", "con": "自动驾驶存在不可控风险"},
    {"topic": "动物实验是否应该被禁止", "pro": "动物实验不道德且可替代", "con": "动物实验对医学发展至关重要"},
    {"topic": "全民基本收入是否可行", "pro": "UBI消除贫困并激发创新", "con": "UBI不可持续且削弱工作动力"},
    {"topic": "太空探索的资金是否应该用于解决地球问题", "pro": "地球问题更紧迫", "con": "太空探索带来长远科技回报"},
    {"topic": "社交媒体平台是否应该审核用户内容", "pro": "审核阻止有害信息传播", "con": "审核侵犯言论自由"},
]


# ==================== 谈判场景模板 ====================

NEGOTIATION_SCENARIOS = [
    {
        "name": "资源分配",
        "description": "两国争夺一片争议领土上的资源",
        "resources": {"土地": 100, "矿产": 50, "水源": 30},
        "party_a": {"name": "北国", "priority": "矿产"},
        "party_b": {"name": "南国", "priority": "水源"},
    },
    {
        "name": "囚徒困境",
        "description": "两名嫌疑人被分开审讯，选择合作或背叛",
        "resources": {"刑期减免": 10},
        "party_a": {"name": "嫌疑人A", "options": ["合作（沉默）", "背叛（指控）"]},
        "party_b": {"name": "嫌疑人B", "options": ["合作（沉默）", "背叛（指控）"]},
    },
    {
        "name": "贸易谈判",
        "description": "两个公司协商技术合作协议",
        "resources": {"专利授权": 5, "市场准入": 3, "技术共享": 2},
        "party_a": {"name": "科技公司", "priority": "市场准入"},
        "party_b": {"name": "制造公司", "priority": "专利授权"},
    },
]


# ==================== 国际象棋规则引擎 ====================

class ChessRules:
    FILES = "abcdefgh"
    RANKS = "12345678"

    def initial_board(self) -> dict[str, tuple[str, str]]:
        """返回初始棋盘 {'a1': ('white', 'rook'), ...}"""
        board: dict[str, tuple[str, str]] = {}
        order = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"]
        for i, piece in enumerate(order):
            board[f"{self.FILES[i]}1"] = ("white", piece)
            board[f"{self.FILES[i]}2"] = ("white", "pawn")
            board[f"{self.FILES[i]}8"] = ("black", piece)
            board[f"{self.FILES[i]}7"] = ("black", "pawn")
        return board

    def empty_board(self) -> dict[str, tuple[str, str]]:
        return {}

    def get_valid_moves(self, square: str, board: dict[str, tuple[str, str]]) -> list[str]:
        """获取某个位置棋子的所有合法走法（考虑将军限制）"""
        if square not in board:
            return []
        color, _ = board[square]
        raw_moves = self._get_raw_moves(square, board)
        legal = []
        for move in raw_moves:
            test_board = self._simulate_move(board, square, move)
            if not self.is_in_check(test_board, color):
                legal.append(move)
        return legal

    def _get_raw_moves(self, square: str, board: dict[str, tuple[str, str]]) -> list[str]:
        """不考虑将军的原始走法"""
        if square not in board:
            return []
        color, piece_type = board[square]
        file_idx = self.FILES.index(square[0])
        rank = int(square[1])
        moves: list[str] = []

        if piece_type == "pawn":
            direction = 1 if color == "white" else -1
            start_rank = 2 if color == "white" else 7
            fwd = f"{square[0]}{rank + direction}"
            if 1 <= rank + direction <= 8 and fwd not in board:
                moves.append(fwd)
                if rank == start_rank:
                    fwd2 = f"{square[0]}{rank + 2 * direction}"
                    if fwd2 not in board:
                        moves.append(fwd2)
            for df in [-1, 1]:
                nf = file_idx + df
                if 0 <= nf < 8 and 1 <= rank + direction <= 8:
                    capture = f"{self.FILES[nf]}{rank + direction}"
                    if capture in board and board[capture][0] != color:
                        moves.append(capture)

        elif piece_type == "rook":
            moves = self._sliding_moves(square, board, [(0, 1), (0, -1), (1, 0), (-1, 0)])

        elif piece_type == "bishop":
            moves = self._sliding_moves(square, board, [(1, 1), (1, -1), (-1, 1), (-1, -1)])

        elif piece_type == "queen":
            moves = self._sliding_moves(square, board, [
                (0, 1), (0, -1), (1, 0), (-1, 0),
                (1, 1), (1, -1), (-1, 1), (-1, -1),
            ])

        elif piece_type == "king":
            for df in [-1, 0, 1]:
                for dr in [-1, 0, 1]:
                    if df == 0 and dr == 0:
                        continue
                    nf = file_idx + df
                    nr = rank + dr
                    if 0 <= nf < 8 and 1 <= nr <= 8:
                        target = f"{self.FILES[nf]}{nr}"
                        if target not in board or board[target][0] != color:
                            moves.append(target)

        elif piece_type == "knight":
            for df, dr in [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                           (1, -2), (1, 2), (2, -1), (2, 1)]:
                nf = file_idx + df
                nr = rank + dr
                if 0 <= nf < 8 and 1 <= nr <= 8:
                    target = f"{self.FILES[nf]}{nr}"
                    if target not in board or board[target][0] != color:
                        moves.append(target)

        return moves

    def _sliding_moves(
        self, square: str, board: dict[str, tuple[str, str]],
        directions: list[tuple[int, int]],
    ) -> list[str]:
        """滑行棋子（车、象、后）的走法"""
        color = board[square][0]
        file_idx = self.FILES.index(square[0])
        rank = int(square[1])
        moves: list[str] = []
        for df, dr in directions:
            nf, nr = file_idx + df, rank + dr
            while 0 <= nf < 8 and 1 <= nr <= 8:
                target = f"{self.FILES[nf]}{nr}"
                if target not in board:
                    moves.append(target)
                elif board[target][0] != color:
                    moves.append(target)
                    break
                else:
                    break
                nf += df
                nr += dr
        return moves

    def _simulate_move(
        self, board: dict[str, tuple[str, str]], from_sq: str, to_sq: str,
    ) -> dict[str, tuple[str, str]]:
        """模拟走一步后的棋盘"""
        new_board = dict(board)
        new_board[to_sq] = new_board.pop(from_sq)
        return new_board

    def is_in_check(self, board: dict[str, tuple[str, str]], color: str) -> bool:
        """检测 color 方是否被将军"""
        king_sq = None
        for sq, (c, p) in board.items():
            if c == color and p == "king":
                king_sq = sq
                break
        if not king_sq:
            return True
        opponent = "black" if color == "white" else "white"
        for sq, (c, _) in board.items():
            if c == opponent:
                raw = self._get_raw_moves(sq, board)
                if king_sq in raw:
                    return True
        return False

    def is_checkmate(self, board: dict[str, tuple[str, str]], color: str) -> bool:
        """检测 color 方是否被将杀"""
        if not self.is_in_check(board, color):
            return False
        for sq, (c, _) in board.items():
            if c == color:
                if self.get_valid_moves(sq, board):
                    return False
        return True

    def is_stalemate(self, board: dict[str, tuple[str, str]], color: str) -> bool:
        """检测是否僵局"""
        if self.is_in_check(board, color):
            return False
        for sq, (c, _) in board.items():
            if c == color:
                if self.get_valid_moves(sq, board):
                    return False
        return True


# ==================== 狼人杀规则引擎 ====================

class WerewolfRules:
    def assign_roles(self, player_ids: list[str]) -> dict[str, str]:
        """随机分配角色。小局也保留核心神职，避免只有村民和狼人。"""
        n = len(player_ids)
        if n <= 0:
            return {}

        werewolf_count = 1 if n < 7 else max(2, n // 4)
        roles = ["werewolf"] * min(werewolf_count, n)

        specials: list[str] = []
        if n >= 4:
            specials.extend(["seer", "guard"])
        elif n >= 3:
            specials.append("seer")
        if n >= 5:
            specials.append("witch")
        if n >= 6:
            specials.append("hunter")

        for role in specials:
            if len(roles) < n:
                roles.append(role)

        roles.extend(["villager"] * (n - len(roles)))
        random.shuffle(roles)
        return dict(zip(player_ids, roles))

    def is_valid_guard_target(self, guard_id: str, target_id: str) -> bool:
        """守卫不能守护自己"""
        return guard_id != target_id

    def resolve_vote_tie(self, tied_players: list[str]) -> str:
        """平票随机放逐一人"""
        return random.choice(tied_players)

    def check_win_condition(self, alive_players: dict[str, str]) -> str | None:
        """检查胜利条件：狼人全死=村民胜，狼人>=好人=狼人胜"""
        werewolves = [p for p, r in alive_players.items() if r == "werewolf"]
        villagers = [p for p, r in alive_players.items() if r != "werewolf"]
        if not werewolves:
            return "village"
        if len(werewolves) >= len(villagers):
            return "werewolf"
        return None


# ==================== 游戏引擎主类 ====================

class GameEngine:
    """游戏引擎 — 支持5种游戏类型的完整规则和自动运行。"""

    def __init__(
        self,
        game_type: str,
        agent_ids: list[str],
        config: dict,
        llm_service: Any = None,
        spectator_service: Any = None,
    ):
        self.game_type = game_type
        self.agent_ids = agent_ids
        self.config = config
        self.llm_service = llm_service
        self.spectator_service = spectator_service
        self.max_turns = config.get("max_turns", 20)
        self.current_turn = 0
        self.is_paused = False
        self.is_stopped = False
        self.turn_delay = config.get("turn_delay", 3.0)

    # ==================== 自动运行引擎 ====================

    def _game_type_value(self) -> str:
        if isinstance(self.game_type, enum.Enum):
            return str(self.game_type.value)
        return str(self.game_type)

    async def auto_run(self) -> AsyncGenerator[dict, None]:
        """自动运行游戏，yield 每个回合的事件。各 run_* 方法内部处理自己的循环。"""
        # 暂停等待
        if self.is_paused:
            yield {"type": "paused", "turn": self.current_turn}
            while self.is_paused and not self.is_stopped:
                await asyncio.sleep(0.5)
            if self.is_stopped:
                return
            yield {"type": "resumed", "turn": self.current_turn}

        agents = getattr(self, "agents", []) or []
        game_type = self._game_type_value()
        terminal_seen = False
        error_seen = False

        async def emit(event: dict):
            nonlocal terminal_seen, error_seen
            event_type = event.get("type")
            if event_type in TERMINAL_EVENT_TYPES:
                terminal_seen = True
            if event_type in ERROR_EVENT_TYPES:
                error_seen = True
            return event

        async def maybe_delay(event: dict):
            event_type = event.get("type")
            if event_type not in TERMINAL_EVENT_TYPES and event_type not in ERROR_EVENT_TYPES and not self.is_stopped:
                await asyncio.sleep(max(0.0, float(self.turn_delay)))

        try:
            if game_type in ("werewolf", GameType.WEREWOLF):
                async for event in self.run_werewolf(agents):
                    if self.is_stopped:
                        break
                    yield await emit(event)
                    await maybe_delay(event)
            elif game_type in ("chess", GameType.CHESS):
                async for event in self.run_chess():
                    if self.is_stopped:
                        break
                    yield await emit(event)
                    await maybe_delay(event)
            elif game_type in ("debate", GameType.DEBATE):
                async for event in self.run_debate(agents):
                    if self.is_stopped:
                        break
                    yield await emit(event)
                    await maybe_delay(event)
            elif game_type in ("text_adventure", GameType.TEXT_ADVENTURE):
                async for event in self.run_text_adventure(agents):
                    if self.is_stopped:
                        break
                    yield await emit(event)
                    await maybe_delay(event)
            elif game_type in ("negotiation", GameType.NEGOTIATION):
                async for event in self.run_negotiation(agents):
                    if self.is_stopped:
                        break
                    yield await emit(event)
                    await maybe_delay(event)
            else:
                yield await emit({"type": "error", "data": {"message": f"Unknown game type: {self.game_type}"}})
        except asyncio.TimeoutError:
            yield await emit({"type": "turn_timeout", "turn": self.current_turn})
        except Exception as e:
            logger.exception("Game engine failed for game_type=%s", self.game_type)
            yield await emit({"type": "turn_error", "turn": self.current_turn, "data": {"message": str(e)}})

        if not self.is_stopped and not terminal_seen and not error_seen and self.current_turn >= self.max_turns:
            yield {"type": "max_turns_reached", "turn": self.current_turn}

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def stop(self):
        self.is_stopped = True

    async def _execute_game_turn(self) -> AsyncGenerator[dict, None]:
        """执行一个游戏回合，由具体游戏类型实现"""
        agents = getattr(self, "agents", []) or []
        game_type = self._game_type_value()

        if game_type in ("werewolf", GameType.WEREWOLF):
            async for event in self.run_werewolf(agents):
                yield event
        elif game_type in ("chess", GameType.CHESS):
            async for event in self.run_chess():
                yield event
        elif game_type in ("debate", GameType.DEBATE):
            async for event in self.run_debate(agents):
                yield event
        elif game_type in ("text_adventure", GameType.TEXT_ADVENTURE):
            async for event in self.run_text_adventure(agents):
                yield event
        elif game_type in ("negotiation", GameType.NEGOTIATION):
            async for event in self.run_negotiation(agents):
                yield event
        else:
            yield {"type": "error", "data": {"message": f"Unknown game type: {self.game_type}"}}

    # ==================== LLM 辅助 ====================

    async def _call_llm(self, agent_id: str, prompt: str) -> str:
        """调用 LLM，带超时保护。通过 agent_id 查找模型配置。"""
        if not self.llm_service:
            return self._fallback_llm_response(prompt)

        # 从 agents 列表查找 agent
        agents = getattr(self, "agents", []) or []
        agent = next((a for a in agents if str(a.id) == agent_id), None)
        if not agent:
            logger.warning("Agent %s not found, skipping LLM call", agent_id)
            return self._fallback_llm_response(prompt)

        # 从 models 缓存查找模型配置
        models_cache = getattr(self, "_models_cache", {})
        model = models_cache.get(str(agent.model_id))

        if not model:
            # 从数据库加载模型
            try:
                from app.core.database import async_session
                from app.models.model import Model as ModelORM
                from sqlalchemy import select
                async with async_session() as db:
                    result = await db.execute(
                        select(ModelORM).where(ModelORM.id == agent.model_id)
                    )
                    model = result.scalar_one_or_none()
                    if model:
                        if not hasattr(self, "_models_cache"):
                            self._models_cache = {}
                        self._models_cache[str(agent.model_id)] = model
            except Exception as e:
                logger.error("Failed to load model for agent %s: %s", agent_id, e)
                return self._fallback_llm_response(prompt)

        if not model:
            return self._fallback_llm_response(prompt)

        try:
            response = await asyncio.wait_for(
                self.llm_service.chat(
                    model_id=model.model_id,
                    messages=[{"role": "user", "content": prompt}],
                    api_key=model.api_key,
                    api_base=model.api_base,
                    temperature=0.8,
                    max_tokens=1024,
                ),
                timeout=60.0,
            )
            content = response.get("content", "").strip()
            return content or self._fallback_llm_response(prompt)
        except asyncio.TimeoutError:
            logger.warning("LLM call timeout for agent %s", agent_id)
            return self._fallback_llm_response(prompt)
        except Exception as e:
            logger.error("LLM call failed for agent %s: %s", agent_id, str(e)[:200])
            return self._fallback_llm_response(prompt)

    def _fallback_llm_response(self, prompt: str) -> str:
        """LLM 不可用时给规则引擎一个可解析的本地回应，避免整局瞬间失败。"""
        if "SCENE:" in prompt and "OPTION_A" in prompt:
            return (
                "SCENE: 你们站在起始之地，前方有一条发光的小径，旁边有一座旧石碑。\n"
                "OPTION_A: 沿着发光小径前进\n"
                "OPTION_B: 检查旧石碑\n"
                "OPTION_C: 原地整理装备"
            )
        if "ACTION:" in prompt:
            return "ACTION: A"
        if "RESULT:" in prompt and "HP_CHANGE:" in prompt:
            return (
                "RESULT: 你谨慎前行，发现了一枚刻着符号的铜币，周围暂时没有危险。\n"
                "HP_CHANGE: 0\n"
                "ITEM: 铜币\n"
                "LOCATION: 微光小径"
            )
        if "PROPOSAL:" in prompt and "ACTION:" in prompt:
            return "PROPOSAL: 双方各让一步，先共享基础资源，再按贡献分配收益。\nACTION: 提出新提案\nREASON: 这样能降低冲突并保留继续谈判空间。"
        if "评分" in prompt and "A方得分" in prompt:
            return "A方得分（1-10）：6\nB方得分（1-10）：6\n公平性（1-10）：7\n评价：协议仍需细化，但基本公平。"
        if "辩论" in prompt and "评分" in prompt:
            return "正方论据力度：6\n正方逻辑性：6\n正方表达力：6\n反方论据力度：6\n反方逻辑性：6\n反方表达力：6\n获胜方：正方\n理由：双方表现接近，正方结构略清晰。"
        if "VOTE:" in prompt:
            return "VOTE: "
        if "KILL:" in prompt:
            return "KILL: "
        if "TARGET:" in prompt:
            return "TARGET: "
        if "GUARD:" in prompt:
            return "GUARD: "
        if "CHECK:" in prompt:
            return "CHECK: "
        if "SAVE:" in prompt:
            return "SAVE: NO"
        if "POISON:" in prompt:
            return "POISON: NONE"
        if "SHOOT:" in prompt:
            return "SHOOT: NONE"
        if "SPEAK:" in prompt:
            return "SPEAK: 我会结合昨晚信息、发言逻辑和投票动机谨慎判断。"
        return "我会采取稳妥策略，先观察局势，再做下一步行动。"

    def _extract_target_id(self, response: str, candidates: list[str]) -> str | None:
        """从 LLM 回复中提取目标 ID"""
        if not response:
            return random.choice(candidates) if candidates else None
        # 精确匹配
        for candidate in candidates:
            if candidate in response:
                return candidate
        # UUID 格式匹配
        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        found = re.findall(uuid_pattern, response.lower())
        for f in found:
            for candidate in candidates:
                if f == candidate.lower():
                    return candidate
        # 回退：随机选择
        return random.choice(candidates) if candidates else None

    def _player_name_map(self, agents: list, player_ids: list[str]) -> dict[str, str]:
        """构建玩家 ID 到可读名称的映射。"""
        names: dict[str, str] = {}
        for player in self.config.get("players", []) or []:
            player_id = str(player.get("agent_id") or player.get("id") or "")
            if player_id:
                names[player_id] = str(player.get("name") or player.get("agent_name") or player_id[:8])
        for agent in agents or []:
            names[str(agent.id)] = getattr(agent, "name", None) or str(agent.id)[:8]
        for player_id in player_ids:
            names.setdefault(player_id, player_id[:8])
        return names

    def _player_snapshot(
        self,
        player_ids: list[str],
        roles: dict[str, str],
        alive_players: dict[str, str],
        player_names: dict[str, str],
    ) -> list[dict[str, Any]]:
        """生成前端和回放可直接消费的玩家快照。"""
        return [
            {
                "agent_id": player_id,
                "name": player_names.get(player_id, player_id[:8]),
                "role": roles.get(player_id, "unknown"),
                "role_name": WEREWOLF_ROLE_NAMES.get(roles.get(player_id, ""), roles.get(player_id, "unknown")),
                "alive": player_id in alive_players,
            }
            for player_id in player_ids
        ]

    def _format_candidates(self, candidates: list[str], player_names: dict[str, str]) -> str:
        return "；".join(f"{player_names.get(player_id, player_id[:8])}({player_id})" for player_id in candidates)

    def _target_details(
        self,
        target_ids: list[str],
        roles: dict[str, str],
        player_names: dict[str, str],
        reason: str = "",
    ) -> list[dict[str, str]]:
        return [
            {
                "agent_id": player_id,
                "name": player_names.get(player_id, player_id[:8]),
                "role": roles.get(player_id, "unknown"),
                "role_name": WEREWOLF_ROLE_NAMES.get(roles.get(player_id, ""), roles.get(player_id, "unknown")),
                "reason": reason,
            }
            for player_id in target_ids
        ]

    def _parse_speech(self, response: str) -> str:
        match = re.search(r"SPEAK:\s*(.+)", response or "", re.IGNORECASE | re.DOTALL)
        content = match.group(1).strip() if match else (response or "").strip()
        return content[:280] or "我会继续观察局势，结合发言和投票再做判断。"

    # ==================== 国际象棋 ====================

    async def run_chess(self) -> AsyncGenerator[dict, None]:
        """国际象棋 — 使用规则引擎验证走法"""
        rules = ChessRules()
        board = rules.initial_board()
        current_color = "white"
        game_over = False

        for turn in range(1, self.max_turns + 1):
            if self.is_stopped or game_over:
                break

            self.current_turn = turn

            # 获取当前颜色所有合法走法
            all_moves: dict[str, list[str]] = {}
            for sq, (color, _) in board.items():
                if color == current_color:
                    valid = rules.get_valid_moves(sq, board)
                    if valid:
                        all_moves[sq] = valid

            if not all_moves:
                opponent = "black" if current_color == "white" else "white"
                if rules.is_in_check(board, current_color):
                    yield {"type": "game_over", "turn": turn, "data": {"winner": opponent, "reason": "checkmate"}}
                else:
                    yield {"type": "game_over", "turn": turn, "data": {"winner": None, "reason": "stalemate"}}
                game_over = True
                break

            # 选择当前方 agent
            agent_idx = 0 if current_color == "white" else min(1, len(self.agent_ids) - 1)
            agent_id = self.agent_ids[agent_idx] if self.agent_ids else ""

            # 构造 prompt
            board_str = self._board_to_string(board)
            legal_moves_str = "\n".join(
                f"{sq} -> {', '.join(moves)}" for sq, moves in all_moves.items()
            )
            check_status = ""
            if rules.is_in_check(board, current_color):
                check_status = "YOU ARE IN CHECK! You must escape check.\n"

            prompt = f"""You are playing chess as {current_color}.

Board state:
{board_str}

{check_status}Your legal moves:
{legal_moves_str}

Choose your move in format: MOVE: from_square to_square
Example: MOVE: e2 e4"""

            response = await self._call_llm(agent_id, prompt)
            from_sq, to_sq = self._parse_chess_move(response, all_moves)

            if from_sq and to_sq:
                board = rules._simulate_move(board, from_sq, to_sq)
                opponent_color = "black" if current_color == "white" else "white"
                in_check = rules.is_in_check(board, opponent_color)

                yield {
                    "type": "turn_result",
                    "turn": turn,
                    "data": {
                        "color": current_color,
                        "from": from_sq,
                        "to": to_sq,
                        "piece": board.get(to_sq, (current_color, "pawn"))[1],
                        "in_check": in_check,
                        "board": board,
                        "last_move": {"from": from_sq, "to": to_sq},
                    },
                }

                # 检查将杀/僵局
                if rules.is_checkmate(board, opponent_color):
                    yield {"type": "game_over", "turn": turn, "data": {"winner": current_color, "reason": "checkmate"}}
                    game_over = True
                    break
                elif rules.is_stalemate(board, opponent_color):
                    yield {"type": "game_over", "turn": turn, "data": {"winner": None, "reason": "stalemate"}}
                    game_over = True
                    break
            else:
                # LLM 未给出合法走法，随机选一个
                from_sq = random.choice(list(all_moves.keys()))
                to_sq = random.choice(all_moves[from_sq])
                board = rules._simulate_move(board, from_sq, to_sq)

                yield {
                    "type": "invalid_move",
                    "turn": turn,
                    "data": {"color": current_color, "response": response, "fallback": f"{from_sq}->{to_sq}"},
                }

            current_color = "black" if current_color == "white" else "white"

        if not game_over:
            yield {"type": "max_turns_reached", "turn": self.current_turn}

    def _board_to_string(self, board: dict[str, tuple[str, str]]) -> str:
        """棋盘转字符串"""
        piece_symbols = {
            "king": "K", "queen": "Q", "rook": "R",
            "bishop": "B", "knight": "N", "pawn": "P",
        }
        lines = []
        for rank in range(8, 0, -1):
            row = f"{rank} "
            for file_idx in range(8):
                sq = f"{ChessRules.FILES[file_idx]}{rank}"
                if sq in board:
                    color, piece = board[sq]
                    symbol = piece_symbols.get(piece, "?")
                    row += f"{'w' if color == 'white' else 'b'}{symbol} "
                else:
                    row += ".  "
            lines.append(row)
        lines.append("   a  b  c  d  e  f  g  h")
        return "\n".join(lines)

    def _parse_chess_move(
        self, response: str, all_moves: dict[str, list[str]],
    ) -> tuple[str | None, str | None]:
        """解析 LLM 回复中的走法"""
        if not response:
            return None, None
        # 匹配 MOVE: e2 e4 格式
        match = re.search(r"MOVE:\s*([a-h][1-8])\s+([a-h][1-8])", response, re.IGNORECASE)
        if match:
            from_sq, to_sq = match.group(1).lower(), match.group(2).lower()
            if from_sq in all_moves and to_sq in all_moves[from_sq]:
                return from_sq, to_sq
        # 尝试更宽松的匹配
        squares = re.findall(r"[a-h][1-8]", response.lower())
        if len(squares) >= 2:
            from_sq, to_sq = squares[0], squares[1]
            if from_sq in all_moves and to_sq in all_moves[from_sq]:
                return from_sq, to_sq
        return None, None

    # ==================== 狼人杀 ====================

    async def run_werewolf(self, agents: list) -> AsyncGenerator[dict, None]:
        """狼人杀 — 完整机制"""
        rules = WerewolfRules()
        player_ids = [str(a.id) for a in agents] if agents else self.agent_ids
        roles = rules.assign_roles(player_ids)
        alive_players: dict[str, str] = dict(roles)
        player_names = self._player_name_map(agents, player_ids)
        role_state = {"witch_antidote": True, "witch_poison": True}

        yield {
            "type": "game_start",
            "turn": 0,
            "data": {
                "player_count": len(player_ids),
                "roles_hidden": True,
                "role_names": WEREWOLF_ROLE_NAMES,
                "players": self._player_snapshot(player_ids, roles, alive_players, player_names),
                "message": f"狼人杀开始：{len(player_ids)} 名玩家入场。",
            },
        }

        for turn in range(1, self.max_turns + 1):
            if self.is_stopped:
                break

            self.current_turn = turn

            # === 夜晚阶段 ===
            werewolf_ids = [p for p, r in alive_players.items() if r == "werewolf"]
            non_werewolf_ids = [p for p in alive_players if p not in werewolf_ids]

            if not werewolf_ids or not non_werewolf_ids:
                break

            kill_target = None
            night_actions: dict[str, Any] = {
                "werewolf_discussion": [],
                "kill_target": None,
                "guard_target": None,
                "seer_check": None,
                "witch_save": False,
                "witch_poison_target": None,
                "hunter_shot": None,
            }

            if len(werewolf_ids) > 1:
                # 多狼人讨论
                discussion = []
                for ww_id in werewolf_ids:
                    resp = await self._call_llm(
                        ww_id,
                        f"你是狼人。存活非狼人：{self._format_candidates(non_werewolf_ids, player_names)}\n讨论：{discussion}\n击杀谁？回复 TARGET: player_id",
                    )
                    discussion.append(f"{player_names.get(ww_id, ww_id[:8])}: {resp}")
                    night_actions["werewolf_discussion"].append({
                        "agent_id": ww_id,
                        "name": player_names.get(ww_id, ww_id[:8]),
                        "content": resp,
                    })

                # 最后一只狼人做决策
                last_resp = await self._call_llm(
                    werewolf_ids[-1],
                    f"你是最后发言的狼人。讨论：{discussion}\n决定击杀谁？回复 TARGET: player_id",
                )
                kill_target = self._extract_target_id(last_resp, non_werewolf_ids) or random.choice(non_werewolf_ids)
            else:
                # 单狼人
                resp = await self._call_llm(
                    werewolf_ids[0],
                    f"你是狼人。可击杀目标：{self._format_candidates(non_werewolf_ids, player_names)}\n回复 TARGET: player_id",
                )
                kill_target = self._extract_target_id(resp, non_werewolf_ids) or random.choice(non_werewolf_ids)
            night_actions["kill_target"] = {
                "agent_id": kill_target,
                "name": player_names.get(kill_target, kill_target[:8]) if kill_target else None,
            }

            # 守卫守护
            guard_id = next((p for p, r in alive_players.items() if r == "guard"), None)
            guard_target = None
            if guard_id:
                candidates = [p for p in alive_players if p != guard_id]
                if candidates:
                    resp = await self._call_llm(
                        guard_id,
                        f"你是守卫。守护对象（不能守护自己）：{self._format_candidates(candidates, player_names)}\n回复 GUARD: player_id",
                    )
                    guard_target = self._extract_target_id(resp, candidates) or random.choice(candidates)
                    night_actions["guard_target"] = {
                        "agent_id": guard_target,
                        "name": player_names.get(guard_target, guard_target[:8]),
                    }

            # 预言家查验
            seer_id = next((p for p, r in alive_players.items() if r == "seer"), None)
            if seer_id:
                candidates = [p for p in alive_players if p != seer_id]
                if candidates:
                    resp = await self._call_llm(
                        seer_id,
                        f"你是预言家。查验对象：{self._format_candidates(candidates, player_names)}\n回复 CHECK: player_id",
                    )
                    check_target = self._extract_target_id(resp, candidates) or random.choice(candidates)
                    night_actions["seer_check"] = {
                        "seer_id": seer_id,
                        "seer_name": player_names.get(seer_id, seer_id[:8]),
                        "target_id": check_target,
                        "target_name": player_names.get(check_target, check_target[:8]),
                        "is_werewolf": alive_players.get(check_target) == "werewolf",
                    }

            # 女巫解药/毒药
            witch_id = next((p for p, r in alive_players.items() if r == "witch"), None)
            witch_saved = False
            poison_target = None
            if witch_id:
                if kill_target and role_state["witch_antidote"]:
                    resp = await self._call_llm(
                        witch_id,
                        f"你是女巫。今晚被袭击的是 {player_names.get(kill_target, kill_target[:8])}({kill_target})。是否使用解药？回复 SAVE: YES 或 SAVE: NO",
                    )
                    witch_saved = "YES" in resp.upper() or "是" in resp or "救" in resp
                    if witch_saved:
                        role_state["witch_antidote"] = False
                        night_actions["witch_save"] = True
                if role_state["witch_poison"]:
                    candidates = [p for p in alive_players if p != witch_id and p != kill_target]
                    if candidates:
                        resp = await self._call_llm(
                            witch_id,
                            f"你是女巫。可毒杀对象：{self._format_candidates(candidates, player_names)}。不使用请回复 POISON: NONE；使用请回复 POISON: player_id",
                        )
                        if "NONE" not in resp.upper() and "不" not in resp:
                            poison_target = self._extract_target_id(resp, candidates)
                        if poison_target:
                            role_state["witch_poison"] = False
                            night_actions["witch_poison_target"] = {
                                "agent_id": poison_target,
                                "name": player_names.get(poison_target, poison_target[:8]),
                            }

            # 夜晚结算
            night_deaths = []
            death_reasons: dict[str, str] = {}
            if kill_target and kill_target != guard_target and not witch_saved:
                night_deaths.append(kill_target)
                death_reasons[kill_target] = "werewolf_kill"
            if poison_target and poison_target not in night_deaths:
                night_deaths.append(poison_target)
                death_reasons[poison_target] = "witch_poison"

            for dead_id in night_deaths:
                alive_players.pop(dead_id, None)

            hunter_deaths = [p for p in night_deaths if roles.get(p) == "hunter"]
            for hunter_id in hunter_deaths:
                candidates = [p for p in alive_players if p != hunter_id]
                if candidates:
                    resp = await self._call_llm(
                        hunter_id,
                        f"你是猎人，死亡时可以开枪带走一人。候选人：{self._format_candidates(candidates, player_names)}。不开枪回复 SHOOT: NONE；开枪回复 SHOOT: player_id",
                    )
                    shot_target = None if "NONE" in resp.upper() or "不" in resp else self._extract_target_id(resp, candidates)
                    if shot_target:
                        alive_players.pop(shot_target, None)
                        night_deaths.append(shot_target)
                        death_reasons[shot_target] = "hunter_shot"
                        night_actions["hunter_shot"] = {
                            "hunter_id": hunter_id,
                            "hunter_name": player_names.get(hunter_id, hunter_id[:8]),
                            "target_id": shot_target,
                            "target_name": player_names.get(shot_target, shot_target[:8]),
                        }

            # === 白天阶段 ===
            death_names = [player_names.get(dead_id, dead_id[:8]) for dead_id in night_deaths]
            day_message = f"昨晚 {'、'.join(death_names)} 死亡。" if death_names else "昨晚是平安夜。"

            yield {
                "type": "night_result",
                "turn": turn,
                "data": {
                    "phase": "day",
                    "deaths": night_deaths,
                    "death_names": death_names,
                    "deaths_detail": [
                        {
                            **detail,
                            "reason": death_reasons.get(detail["agent_id"], "unknown"),
                        }
                        for detail in self._target_details(night_deaths, roles, player_names)
                    ],
                    "night_actions": night_actions,
                    "message": day_message,
                    "alive_count": len(alive_players),
                    "players": self._player_snapshot(player_ids, roles, alive_players, player_names),
                },
            }

            # 检查胜负
            win = rules.check_win_condition(alive_players)
            if win:
                yield {
                    "type": "game_over",
                    "turn": turn,
                    "data": {
                        "winner": win,
                        "roles": roles,
                        "role_names": WEREWOLF_ROLE_NAMES,
                        "players": self._player_snapshot(player_ids, roles, alive_players, player_names),
                        "message": "村民阵营获胜。" if win == "village" else "狼人阵营获胜。",
                    },
                }
                break

            # 白天讨论
            alive_list = list(alive_players.keys())
            speeches = []
            for speaker_id in alive_list:
                resp = await self._call_llm(
                    speaker_id,
                    (
                        f"白天讨论阶段。你的身份是 {WEREWOLF_ROLE_NAMES.get(roles.get(speaker_id, ''), roles.get(speaker_id, '未知'))}。\n"
                        f"{day_message}\n"
                        f"存活玩家：{self._format_candidates(alive_list, player_names)}\n"
                        "请发表一段发言，说明你的观察、怀疑对象或自证逻辑。回复 SPEAK: 发言内容"
                    ),
                )
                speeches.append({
                    "agent_id": speaker_id,
                    "name": player_names.get(speaker_id, speaker_id[:8]),
                    "role": roles.get(speaker_id, "unknown"),
                    "role_name": WEREWOLF_ROLE_NAMES.get(roles.get(speaker_id, ""), roles.get(speaker_id, "unknown")),
                    "content": self._parse_speech(resp),
                })

            discussion_summary = "；".join(f"{s['name']}：{s['content']}" for s in speeches)
            yield {
                "type": "day_discussion",
                "turn": turn,
                "data": {
                    "phase": "day",
                    "speeches": speeches,
                    "summary": discussion_summary,
                    "message": f"白天讨论完成，共 {len(speeches)} 名玩家发言。",
                    "players": self._player_snapshot(player_ids, roles, alive_players, player_names),
                },
            }

            # 投票放逐
            voter_results: dict[str, str] = {}
            for voter_id in alive_list:
                candidates = [p for p in alive_list if p != voter_id]
                if not candidates:
                    continue
                resp = await self._call_llm(
                    voter_id,
                    (
                        f"白天讨论已完成。昨夜信息：{day_message}\n"
                        f"发言摘要：{discussion_summary}\n"
                        f"候选人：{self._format_candidates(candidates, player_names)}\n"
                        "投票放逐谁？回复 VOTE: player_id"
                    ),
                )
                vote = self._extract_target_id(resp, candidates) or random.choice(candidates)
                voter_results[voter_id] = vote

            # 计票
            vote_counts = Counter(voter_results.values())
            if not vote_counts:
                continue
            max_votes = max(vote_counts.values())
            top_voted = [p for p, v in vote_counts.items() if v == max_votes]

            if len(top_voted) > 1:
                exiled = rules.resolve_vote_tie(top_voted)
            else:
                exiled = top_voted[0]

            if exiled in alive_players:
                del alive_players[exiled]

            hunter_shot = None
            if roles.get(exiled) == "hunter":
                candidates = [p for p in alive_players if p != exiled]
                if candidates:
                    resp = await self._call_llm(
                        exiled,
                        f"你是猎人，被放逐时可以开枪带走一人。候选人：{self._format_candidates(candidates, player_names)}。不开枪回复 SHOOT: NONE；开枪回复 SHOOT: player_id",
                    )
                    shot_target = None if "NONE" in resp.upper() or "不" in resp else self._extract_target_id(resp, candidates)
                    if shot_target:
                        alive_players.pop(shot_target, None)
                        hunter_shot = {
                            "hunter_id": exiled,
                            "hunter_name": player_names.get(exiled, exiled[:8]),
                            "target_id": shot_target,
                            "target_name": player_names.get(shot_target, shot_target[:8]),
                        }

            vote_count_names = {
                player_names.get(player_id, player_id[:8]): count
                for player_id, count in vote_counts.items()
            }
            vote_details = [
                {
                    "voter_id": voter_id,
                    "voter_name": player_names.get(voter_id, voter_id[:8]),
                    "target_id": target_id,
                    "target_name": player_names.get(target_id, target_id[:8]),
                }
                for voter_id, target_id in voter_results.items()
            ]
            exiled_name = player_names.get(exiled, exiled[:8])

            yield {
                "type": "vote_result",
                "turn": turn,
                "data": {
                    "votes": voter_results,
                    "vote_details": vote_details,
                    "vote_counts": dict(vote_counts),
                    "vote_count_names": vote_count_names,
                    "exiled": exiled,
                    "exiled_name": exiled_name,
                    "exiled_role": roles.get(exiled, "unknown"),
                    "exiled_role_name": WEREWOLF_ROLE_NAMES.get(roles.get(exiled, ""), roles.get(exiled, "unknown")),
                    "hunter_shot": hunter_shot,
                    "message": f"投票结果：{exiled_name} 被放逐。" + (
                        f" 猎人带走了 {hunter_shot['target_name']}。" if hunter_shot else ""
                    ),
                    "players": self._player_snapshot(player_ids, roles, alive_players, player_names),
                },
            }

            # 检查胜负
            win = rules.check_win_condition(alive_players)
            if win:
                yield {
                    "type": "game_over",
                    "turn": turn,
                    "data": {
                        "winner": win,
                        "roles": roles,
                        "role_names": WEREWOLF_ROLE_NAMES,
                        "players": self._player_snapshot(player_ids, roles, alive_players, player_names),
                        "message": "村民阵营获胜。" if win == "village" else "狼人阵营获胜。",
                    },
                }
                break

    # ==================== 辩论赛 ====================

    async def run_debate(self, agents: list) -> AsyncGenerator[dict, None]:
        """辩论赛 — 立论+质询+总结+评委评分"""
        if len(agents) < 2 and len(self.agent_ids) < 2:
            yield {"type": "error", "data": {"message": "辩论赛至少需要2个智能体"}}
            return

        config = self.config
        topic_data = config.get("topic")
        if not topic_data:
            topic_data = random.choice(DEBATE_TOPICS)

        topic = topic_data["topic"] if isinstance(topic_data, dict) else str(topic_data)

        agent_ids = self.agent_ids if self.agent_ids else [str(a.id) for a in agents]
        pro_id = agent_ids[0]
        con_id = agent_ids[1] if len(agent_ids) > 1 else agent_ids[0]

        # 阶段1：开篇立论
        pro_opening = await self._call_llm(
            pro_id,
            f"辩论主题：{topic}\n你是正方。请阐述你的立场和核心论据。200字以内。",
        )
        con_opening = await self._call_llm(
            con_id,
            f"辩论主题：{topic}\n你是反方。请阐述你的立场和核心论据。200字以内。",
        )

        yield {
            "type": "debate_opening",
            "turn": 1,
            "data": {"topic": topic, "pro": pro_opening, "con": con_opening},
        }

        # 阶段2：交叉质询
        pro_cross = await self._call_llm(
            pro_id, f"对方观点：{con_opening}\n请提出你的质询问题。"
        )
        con_response = await self._call_llm(
            con_id, f"对方质询：{pro_cross}\n请回应并反击。"
        )
        con_cross = await self._call_llm(
            con_id, f"对方观点：{pro_opening}\n请提出你的质询问题。"
        )
        pro_response = await self._call_llm(
            pro_id, f"对方质询：{con_cross}\n请回应并反击。"
        )

        yield {
            "type": "debate_cross",
            "turn": 2,
            "data": {
                "pro_question": pro_cross, "con_answer": con_response,
                "con_question": con_cross, "pro_answer": pro_response,
            },
        }

        # 阶段3：总结陈词
        pro_closing = await self._call_llm(
            pro_id,
            f"辩论总结。回顾：正方立论：{pro_opening}，对方：{con_opening}，质询：{pro_cross}/{con_response}和{con_cross}/{pro_response}。\n请做最终总结。150字以内。",
        )
        con_closing = await self._call_llm(
            con_id,
            f"辩论总结。回顾：反方立论：{con_opening}，对方：{pro_opening}，质询：{con_cross}/{pro_response}和{pro_cross}/{con_response}。\n请做最终总结。150字以内。",
        )

        yield {
            "type": "debate_closing",
            "turn": 3,
            "data": {"pro": pro_closing, "con": con_closing},
        }

        # 评委评分
        judge_prompt = f"""你是辩论赛评委。请对以下辩论评分。

主题：{topic}

正方立论：{pro_opening}
正方质询：{pro_cross}
正方回应：{pro_response}
正方总结：{pro_closing}

反方立论：{con_opening}
反方质询：{con_cross}
反方回应：{con_response}
反方总结：{con_closing}

请按以下格式评分（每项1-10分）：
正方论据力度：X
正方逻辑性：X
正方表达力：X
反方论据力度：X
反方逻辑性：X
反方表达力：X
获胜方：正方/反方
理由：一句话"""

        judge_result = await self._call_llm(pro_id, judge_prompt)
        scores = self._parse_debate_scores(judge_result)
        scores["topic"] = topic

        yield {"type": "debate_result", "turn": 4, "data": scores}

    def _parse_debate_scores(self, judge_response: str) -> dict:
        """解析评委评分"""
        scores: dict[str, Any] = {}
        patterns = {
            "pro_arguments": r"正方论据力度[：:]\s*(\d+)",
            "pro_logic": r"正方逻辑性[：:]\s*(\d+)",
            "pro_expression": r"正方表达力[：:]\s*(\d+)",
            "con_arguments": r"反方论据力度[：:]\s*(\d+)",
            "con_logic": r"反方逻辑性[：:]\s*(\d+)",
            "con_expression": r"反方表达力[：:]\s*(\d+)",
            "winner": r"获胜方[：:]\s*(正方|反方)",
            "reason": r"理由[：:]\s*(.+)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, judge_response)
            if match:
                if key in ("pro_arguments", "pro_logic", "pro_expression",
                           "con_arguments", "con_logic", "con_expression"):
                    scores[key] = int(match.group(1))
                else:
                    scores[key] = match.group(1)
            else:
                scores[key] = None

        scores["pro_total"] = (scores.get("pro_arguments") or 0) + \
                              (scores.get("pro_logic") or 0) + \
                              (scores.get("pro_expression") or 0)
        scores["con_total"] = (scores.get("con_arguments") or 0) + \
                              (scores.get("con_logic") or 0) + \
                              (scores.get("con_expression") or 0)
        if not scores.get("winner"):
            scores["winner"] = "正方" if scores["pro_total"] >= scores["con_total"] else "反方"

        return scores

    # ==================== 文字冒险 ====================

    async def run_text_adventure(self, agents: list) -> AsyncGenerator[dict, None]:
        """文字冒险 — 叙述者+探险者"""
        agent_ids = self.agent_ids if self.agent_ids else [str(a.id) for a in agents]
        if len(agent_ids) < 2:
            yield {"type": "error", "data": {"message": "文字冒险至少需要2个智能体（叙述者+探险者）"}}
            return

        narrator_id = agent_ids[0]
        explorer_id = agent_ids[1]

        state = {
            "hp": 100,
            "max_hp": 100,
            "inventory": [],
            "current_location": "起始之地",
            "explored_locations": ["起始之地"],
        }

        for turn in range(1, self.max_turns + 1):
            if self.is_stopped:
                break
            self.current_turn = turn

            # 叙述者描述场景
            narrator_prompt = f"""你是文字冒险的叙述者。

状态：HP {state['hp']}/{state['max_hp']}，位置：{state['current_location']}，已探索：{state['explored_locations']}，物品：{state['inventory']}
回合 {turn}/{self.max_turns}

描述场景并提供选项：
SCENE: [场景描述，50字以内]
OPTION_A: [行动选项A]
OPTION_B: [行动选项B]
OPTION_C: [行动选项C]（可选）

规则：单次HP变化不超±20，HP≤0才死亡。"""

            narration = await self._call_llm(narrator_id, narrator_prompt)
            scene, options = self._parse_adventure_narration(narration)

            yield {
                "type": "scene",
                "turn": turn,
                "data": {"scene": scene, "options": options, "state": dict(state)},
            }

            # 探险者选择
            options_text = "\n".join(f"- {k}: {v}" for k, v in options.items())
            choice_resp = await self._call_llm(
                explorer_id,
                f"场景：{scene}\n可选行动：\n{options_text}\n\n状态：HP {state['hp']}/{state['max_hp']}\n选择一个行动。回复 ACTION: 选项字母(A/B/C)",
            )
            chosen = self._parse_adventure_choice(choice_resp, options)

            # 叙述者推进剧情
            result_resp = await self._call_llm(
                narrator_id,
                f"探险者选择了：{chosen}\n当前HP：{state['hp']}\n描述结果：\nRESULT: [结果描述]\nHP_CHANGE: [+/-数字，不超20]\nITEM: [获得物品或NONE]\nLOCATION: [新位置或CURRENT]",
            )
            hp_change, item, location, result_desc = self._parse_adventure_result(result_resp)

            # 应用状态变化
            if hp_change:
                state["hp"] = max(0, min(state["max_hp"], state["hp"] + hp_change))
            if item and item.upper() != "NONE":
                state["inventory"].append(item)
            if location and location.upper() != "CURRENT":
                state["current_location"] = location
                if location not in state["explored_locations"]:
                    state["explored_locations"].append(location)

            yield {
                "type": "action_result",
                "turn": turn,
                "data": {
                    "choice": chosen,
                    "result": result_desc,
                    "hp_change": hp_change,
                    "item": item,
                    "new_location": location if location and location.upper() != "CURRENT" else None,
                    "state": dict(state),
                },
            }

            if state["hp"] <= 0:
                yield {"type": "game_over", "turn": turn, "data": {"result": "death", "state": state}}
                break

    def _parse_adventure_narration(self, text: str) -> tuple[str, dict[str, str]]:
        """解析叙述者的场景和选项"""
        scene_match = re.search(r"SCENE:\s*(.+?)(?=\nOPTION_|$)", text, re.DOTALL)
        scene = scene_match.group(1).strip() if scene_match else text[:100]
        if not scene:
            scene = "你站在起始之地，周围安静而陌生，前方有几条可探索的道路。"
        options: dict[str, str] = {}
        for key in ["OPTION_A", "OPTION_B", "OPTION_C"]:
            match = re.search(rf"{key}:\s*(.+?)(?=\nOPTION_|$)", text, re.DOTALL)
            if match:
                options[key] = match.group(1).strip()
        if not options:
            options = {"OPTION_A": "继续前进", "OPTION_B": "四处探索"}
        return scene, options

    def _parse_adventure_choice(self, text: str, options: dict[str, str]) -> str:
        """解析探险者的选择"""
        match = re.search(r"ACTION:\s*([ABC])", text, re.IGNORECASE)
        if match:
            key = f"OPTION_{match.group(1).upper()}"
            return options.get(key, list(options.values())[0])
        return list(options.values())[0]

    def _parse_adventure_result(self, text: str) -> tuple[int | None, str | None, str | None, str]:
        """解析行动结果"""
        hp_match = re.search(r"HP_CHANGE:\s*([+-]?\d+)", text)
        hp_change = int(hp_match.group(1)) if hp_match else None
        if hp_change and abs(hp_change) > 20:
            hp_change = 20 if hp_change > 0 else -20

        item_match = re.search(r"ITEM:\s*(.+?)(?=\n|$)", text)
        item = item_match.group(1).strip() if item_match else None

        loc_match = re.search(r"LOCATION:\s*(.+?)(?=\n|$)", text)
        location = loc_match.group(1).strip() if loc_match else None

        desc_match = re.search(r"RESULT:\s*(.+?)(?=\nHP_CHANGE|\nITEM|\nLOCATION|$)", text, re.DOTALL)
        description = desc_match.group(1).strip() if desc_match else text[:200]
        if not description:
            description = "你谨慎地推进了一步，局势暂时保持稳定。"

        return hp_change, item, location, description

    # ==================== 谈判博弈 ====================

    async def run_negotiation(self, agents: list) -> AsyncGenerator[dict, None]:
        """谈判博弈 — 提案锚定+资源量化+独立评分"""
        agent_ids = self.agent_ids if self.agent_ids else [str(a.id) for a in agents]
        if len(agent_ids) < 2:
            yield {"type": "error", "data": {"message": "谈判博弈至少需要2个智能体"}}
            return

        scenario = self.config.get("scenario")
        if not scenario:
            scenario = random.choice(NEGOTIATION_SCENARIOS)

        party_a_id = agent_ids[0]
        party_b_id = agent_ids[1]
        current_proposal: str | None = None
        deal_reached = False

        for turn in range(1, self.max_turns + 1):
            if self.is_stopped or deal_reached:
                break
            self.current_turn = turn

            # A 方提案/回应
            a_prompt = f"""你是{scenario.get('party_a', {}).get('name', '甲方')}。
谈判场景：{scenario['description']}
可用资源：{scenario.get('resources', {})}
{"当前提案：" + current_proposal if current_proposal else "这是第一轮，请提出你的初始提案。"}

回复格式：
PROPOSAL: [你的提案]
ACTION: [提出新提案 / 接受当前提案 / 拒绝]
REASON: [理由]"""

            a_response = await self._call_llm(party_a_id, a_prompt)
            a_parsed = self._parse_negotiation_response(a_response)

            yield {"type": "negotiation_turn", "turn": turn, "data": {"party": "A", **a_parsed}}

            if a_parsed.get("action") == "accept" and current_proposal:
                yield {"type": "deal_reached", "turn": turn, "data": {"proposal": current_proposal}}
                deal_reached = True
                break

            if a_parsed.get("proposal"):
                current_proposal = a_parsed["proposal"]

            # B 方提案/回应
            b_prompt = f"""你是{scenario.get('party_b', {}).get('name', '乙方')}。
谈判场景：{scenario['description']}
可用资源：{scenario.get('resources', {})}
当前提案：{current_proposal}

回复格式：
PROPOSAL: [你的反提案或修改]
ACTION: [提出新提案 / 接受当前提案 / 拒绝]
REASON: [理由]"""

            b_response = await self._call_llm(party_b_id, b_prompt)
            b_parsed = self._parse_negotiation_response(b_response)

            yield {"type": "negotiation_turn", "turn": turn, "data": {"party": "B", **b_parsed}}

            if b_parsed.get("action") == "accept":
                yield {"type": "deal_reached", "turn": turn, "data": {"proposal": current_proposal}}
                deal_reached = True
                break

            if b_parsed.get("proposal"):
                current_proposal = b_parsed["proposal"]

        if not deal_reached:
            yield {"type": "negotiation_failed", "turn": self.current_turn, "data": {"last_proposal": current_proposal}}

        # 独立评分
        judge_prompt = f"""你是谈判评估专家。
场景：{scenario['description']}
最终提案：{current_proposal}
可用资源：{scenario.get('resources', {})}

评分：
A方得分（1-10）：X
B方得分（1-10）：X
公平性（1-10）：X
评价：一句话"""

        judge_result = await self._call_llm(party_a_id, judge_prompt)
        scores = self._parse_negotiation_scores(judge_result)

        yield {"type": "negotiation_scores", "turn": self.current_turn, "data": scores}

    def _parse_negotiation_response(self, text: str) -> dict:
        """解析谈判回应"""
        proposal_match = re.search(r"PROPOSAL:\s*(.+?)(?=\nACTION:|$)", text, re.DOTALL)
        action_match = re.search(r"ACTION:\s*(.+?)(?=\nREASON:|$)", text, re.DOTALL)
        reason_match = re.search(r"REASON:\s*(.+?)$", text, re.DOTALL)

        action_text = action_match.group(1).strip().lower() if action_match else "propose"
        if "接受" in action_text or "accept" in action_text:
            action = "accept"
        elif "拒绝" in action_text or "reject" in action_text:
            action = "reject"
        else:
            action = "propose"

        return {
            "proposal": proposal_match.group(1).strip() if proposal_match else (text[:100] or "双方先交换底线，再寻找可接受的折中方案。"),
            "action": action,
            "reason": reason_match.group(1).strip() if reason_match else "",
        }

    def _parse_negotiation_scores(self, text: str) -> dict:
        """解析谈判评分"""
        scores: dict[str, Any] = {}
        a_match = re.search(r"A方得分[（(]1-10[)）][：:]\s*(\d+)", text)
        b_match = re.search(r"B方得分[（(]1-10[)）][：:]\s*(\d+)", text)
        fair_match = re.search(r"公平性[（(]1-10[)）][：:]\s*(\d+)", text)
        eval_match = re.search(r"评价[：:]\s*(.+?)$", text, re.DOTALL)

        scores["party_a_score"] = int(a_match.group(1)) if a_match else 5
        scores["party_b_score"] = int(b_match.group(1)) if b_match else 5
        scores["fairness"] = int(fair_match.group(1)) if fair_match else 5
        scores["evaluation"] = eval_match.group(1).strip() if eval_match else ""
        return scores
