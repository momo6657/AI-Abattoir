import pytest
from unittest.mock import MagicMock

from app.services.game_engine import GameEngine


engine = GameEngine()


# ========== Werewolf role distribution ==========

class TestWerewolfRoles:
    def test_4_players(self):
        roles = engine._build_werewolf_roles(4)
        assert len(roles) == 4
        assert roles.count("werewolf") == 1
        assert roles.count("seer") == 1
        assert roles.count("witch") == 1
        assert roles.count("villager") == 1

    def test_5_players(self):
        roles = engine._build_werewolf_roles(5)
        assert len(roles) == 5
        assert roles.count("werewolf") == 1
        assert "seer" in roles
        assert "witch" in roles

    def test_6_players(self):
        roles = engine._build_werewolf_roles(6)
        assert len(roles) == 6
        assert roles.count("werewolf") == 2
        assert roles.count("hunter") == 1
        assert roles.count("seer") == 1
        assert roles.count("witch") == 1
        assert roles.count("villager") == 1

    def test_7_players(self):
        roles = engine._build_werewolf_roles(7)
        assert len(roles) == 7
        assert roles.count("werewolf") == 2
        assert roles.count("hunter") == 1

    def test_8_players(self):
        roles = engine._build_werewolf_roles(8)
        assert len(roles) == 8
        assert roles.count("werewolf") == 2
        assert roles.count("hunter") == 1
        assert roles.count("guard") == 1
        assert roles.count("villager") == 2

    def test_10_players(self):
        roles = engine._build_werewolf_roles(10)
        assert len(roles) == 10
        assert roles.count("werewolf") == 3
        assert roles.count("seer") == 1
        assert roles.count("witch") == 1
        assert roles.count("hunter") == 1
        assert roles.count("guard") == 1
        assert roles.count("villager") == 3

    def test_12_players(self):
        roles = engine._build_werewolf_roles(12)
        assert len(roles) == 12
        assert roles.count("werewolf") == 3
        assert roles.count("villager") == 5

    def test_invalid_player_count_too_few(self):
        with pytest.raises(ValueError, match="between 4 and 12"):
            engine._build_werewolf_roles(3)

    def test_invalid_player_count_too_many(self):
        with pytest.raises(ValueError, match="between 4 and 12"):
            engine._build_werewolf_roles(13)

    def test_special_roles_present_at_thresholds(self):
        # seer and witch always present
        for n in range(4, 13):
            roles = engine._build_werewolf_roles(n)
            assert "seer" in roles, f"seer missing at n={n}"
            assert "witch" in roles, f"witch missing at n={n}"

        # hunter appears at 6+
        for n in range(6, 13):
            roles = engine._build_werewolf_roles(n)
            assert "hunter" in roles, f"hunter missing at n={n}"

        # guard appears at 8+
        for n in range(8, 13):
            roles = engine._build_werewolf_roles(n)
            assert "guard" in roles, f"guard missing at n={n}"


# ========== Chess board ==========

class TestChessBoard:
    def test_initial_board_dimensions(self):
        board = engine._initial_board()
        assert len(board) == 8
        for row in board:
            assert len(row) == 8

    def test_initial_board_pieces(self):
        board = engine._initial_board()
        # Black back rank
        assert board[0] == ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"]
        # Black pawns
        assert board[1] == ["bP"] * 8
        # Empty middle
        for r in range(2, 6):
            assert board[r] == [""] * 8
        # White pawns
        assert board[6] == ["wP"] * 8
        # White back rank
        assert board[7] == ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"]

    def test_king_positions(self):
        board = engine._initial_board()
        # White king at e1 (row 7, col 4)
        assert board[7][4] == "wK"
        # Black king at e8 (row 0, col 4)
        assert board[0][4] == "bK"

    def test_total_piece_count(self):
        board = engine._initial_board()
        all_pieces = [p for row in board for p in row if p]
        assert len(all_pieces) == 32


# ========== Chess parse_square ==========

class TestParseSquare:
    def test_parse_e2(self):
        assert engine._parse_square("e2") == (6, 4)

    def test_parse_a1(self):
        assert engine._parse_square("a1") == (7, 0)

    def test_parse_h8(self):
        assert engine._parse_square("h8") == (0, 7)

    def test_parse_d4(self):
        assert engine._parse_square("d4") == (4, 3)

    def test_parse_case_insensitive(self):
        assert engine._parse_square("E2") == (6, 4)
        assert engine._parse_square("A1") == (7, 0)

    def test_parse_with_whitespace(self):
        assert engine._parse_square("  e2  ") == (6, 4)

    def test_parse_invalid_file(self):
        assert engine._parse_square("z1") is None

    def test_parse_invalid_rank(self):
        assert engine._parse_square("a9") is None

    def test_parse_too_short(self):
        assert engine._parse_square("a") is None
        assert engine._parse_square("") is None


# ========== Chess parse_move_response ==========

class TestParseMoveResponse:
    def test_parse_e2e4_format(self):
        board = engine._initial_board()
        move = engine._parse_move_response("e2e4", board, "white")
        assert move is not None
        assert move["from"] == (6, 4)
        assert move["to"] == (4, 4)
        assert move["piece"] == "wP"

    def test_parse_e2_e4_with_dash(self):
        board = engine._initial_board()
        move = engine._parse_move_response("e2-e4", board, "white")
        assert move is not None
        assert move["from"] == (6, 4)
        assert move["to"] == (4, 4)

    def test_parse_knight_move(self):
        board = engine._initial_board()
        move = engine._parse_move_response("Nf3", board, "white")
        assert move is not None
        assert move["to"] == (5, 5)  # f3
        assert move["piece"] == "wN"

    def test_parse_invalid_move_no_piece(self):
        board = engine._initial_board()
        # d4 has no piece on the initial board
        move = engine._parse_move_response("d4d5", board, "white")
        assert move is None

    def test_parse_pawn_double_advance(self):
        board = engine._initial_board()
        move = engine._parse_move_response("d2d4", board, "white")
        assert move is not None
        assert move["from"] == (6, 3)
        assert move["to"] == (4, 3)
        assert move["piece"] == "wP"


# ========== Chess move validation ==========

class TestValidateMove:
    def test_pawn_forward_one(self):
        board = engine._initial_board()
        move = {"from": (6, 4), "to": (5, 4), "piece": "wP", "capture": False}
        assert engine._validate_move(move, board, "white") is True

    def test_pawn_forward_two_from_start(self):
        board = engine._initial_board()
        move = {"from": (6, 4), "to": (4, 4), "piece": "wP", "capture": False}
        assert engine._validate_move(move, board, "white") is True

    def test_pawn_invalid_backward(self):
        board = engine._initial_board()
        move = {"from": (6, 4), "to": (7, 4), "piece": "wP", "capture": False}
        assert engine._validate_move(move, board, "white") is False

    def test_knight_valid_l_shape(self):
        board = engine._initial_board()
        move = {"from": (7, 1), "to": (5, 2), "piece": "wN", "capture": False}
        assert engine._validate_move(move, board, "white") is True

    def test_knight_invalid_straight(self):
        board = engine._initial_board()
        move = {"from": (7, 1), "to": (5, 1), "piece": "wN", "capture": False}
        assert engine._validate_move(move, board, "white") is False

    def test_cannot_capture_own_piece(self):
        board = engine._initial_board()
        # White pawn at e2 trying to capture white pawn at d3 (hypothetical)
        board[5][3] = "wP"
        move = {"from": (6, 4), "to": (5, 3), "piece": "wP", "capture": True}
        assert engine._validate_move(move, board, "white") is False

    def test_cannot_stay_in_place(self):
        board = engine._initial_board()
        move = {"from": (6, 4), "to": (6, 4), "piece": "wP", "capture": False}
        assert engine._validate_move(move, board, "white") is False


# ========== Square name helper ==========

class TestSquareName:
    def test_a1(self):
        assert engine._square_name(7, 0) == "a1"

    def test_e4(self):
        assert engine._square_name(4, 4) == "e4"

    def test_h8(self):
        assert engine._square_name(0, 7) == "h8"


# ========== Apply move ==========

class TestApplyMove:
    def test_simple_pawn_move(self):
        board = engine._initial_board()
        move = {"from": (6, 4), "to": (4, 4), "piece": "wP", "capture": False}
        new_board, captured = engine._apply_move(board, move)
        assert new_board[6][4] == ""
        assert new_board[4][4] == "wP"
        assert captured is None

    def test_capture(self):
        board = engine._initial_board()
        # Place a black piece where white pawn can capture
        board[5][3] = "bP"
        move = {"from": (6, 4), "to": (5, 3), "piece": "wP", "capture": True}
        new_board, captured = engine._apply_move(board, move)
        assert captured == "bP"
        assert new_board[5][3] == "wP"

    def test_does_not_mutate_original(self):
        board = engine._initial_board()
        original_row = board[6][:]
        move = {"from": (6, 4), "to": (4, 4), "piece": "wP", "capture": False}
        engine._apply_move(board, move)
        assert board[6] == original_row


# ========== Witch action parsing ==========

class TestParseWitchAction:
    def test_save(self):
        result = engine._parse_witch_action("SAVE", {})
        assert result["save"] is True

    def test_skip(self):
        result = engine._parse_witch_action("SKIP", {})
        assert result["skip"] is True

    def test_poison(self):
        uid = "12345678-1234-1234-1234-123456789abc"
        result = engine._parse_witch_action(f"POISON:{uid}", {})
        assert result["poison"] == uid

    def test_poison_case_insensitive(self):
        uid = "12345678-1234-1234-1234-123456789abc"
        result = engine._parse_witch_action(f"poison:{uid}", {})
        assert result["poison"] == uid

    def test_unrecognized_defaults_to_skip(self):
        result = engine._parse_witch_action("I don't know", {})
        assert result["skip"] is True


# ========== Extract target ID ==========

class TestExtractTargetId:
    def test_valid_uuid(self):
        uid = "12345678-1234-1234-1234-123456789abc"
        candidate = MagicMock()
        candidate.agent_id = uid
        result = engine._extract_target_id(f"I choose {uid}", [candidate])
        assert result == uid

    def test_no_valid_uuid_returns_first_candidate(self):
        candidate = MagicMock()
        candidate.agent_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        result = engine._extract_target_id("I choose the first one", [candidate])
        assert result == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def test_invalid_uuid_not_in_candidates(self):
        candidate = MagicMock()
        candidate.agent_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        result = engine._extract_target_id(
            "I choose 00000000-0000-0000-0000-000000000000",
            [candidate],
        )
        # Falls back to first candidate
        assert result == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def test_empty_candidates(self):
        result = engine._extract_target_id("anything", [])
        assert result is None


# ========== King captured check ==========

class TestCheckKingCaptured:
    def test_both_kings_present(self):
        board = engine._initial_board()
        assert engine._check_king_captured(board) is None

    def test_white_king_missing(self):
        board = engine._initial_board()
        board[7][4] = ""  # remove white king
        assert engine._check_king_captured(board) == "black"

    def test_black_king_missing(self):
        board = engine._initial_board()
        board[0][4] = ""  # remove black king
        assert engine._check_king_captured(board) == "white"
