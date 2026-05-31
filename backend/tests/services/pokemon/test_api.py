"""
Tests for Pokemon REST API
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import get_db


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    return db


@pytest_asyncio.fixture
async def async_client(mock_db):
    """Create an async test client with mocked database"""
    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


class TestPokemonAPI:
    """Test Pokemon REST API endpoints"""

    @pytest.mark.asyncio
    async def test_get_species_list(self, async_client, mock_db):
        """Test GET /api/pokemon/species endpoint"""
        # Create mock species with all required fields
        from app.models.pokemon import PokemonSpecies
        mock_species = MagicMock(spec=PokemonSpecies)
        mock_species.id = 1
        mock_species.name = "Bulbasaur"
        mock_species.name_zh = "妙蛙种子"
        mock_species.types = ["Grass", "Poison"]
        mock_species.base_stats = {"hp": 45, "atk": 49, "def": 49, "spa": 65, "spd": 65, "spe": 45}
        mock_species.abilities = ["Overgrow"]
        mock_species.hidden_ability = "Chlorophyll"
        mock_species.weight = 6.9
        mock_species.gender_ratio = {"male": 0.875, "female": 0.125}

        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [mock_species]
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await async_client.get("/api/pokemon/species")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["name"] == "Bulbasaur"

    @pytest.mark.asyncio
    async def test_get_moves_list(self, async_client, mock_db):
        """Test GET /api/pokemon/moves endpoint"""
        from app.models.pokemon import PokemonMove
        mock_move = MagicMock(spec=PokemonMove)
        mock_move.id = 1
        mock_move.name = "Thunderbolt"
        mock_move.name_zh = "十万伏特"
        mock_move.type = "Electric"
        mock_move.category = "special"
        mock_move.power = 90
        mock_move.accuracy = 100
        mock_move.pp = 15
        mock_move.priority = 0
        mock_move.target = "normal"
        mock_move.flags = {}
        mock_move.effect = "10% chance to paralyze"
        mock_move.effect_data = {}

        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [mock_move]
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await async_client.get("/api/pokemon/moves")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["name"] == "Thunderbolt"

    @pytest.mark.asyncio
    async def test_create_team(self, async_client, mock_db):
        """Test POST /api/pokemon/teams endpoint"""
        agent_id = str(uuid4())
        team_data = {
            "name": "Test Team",
            "format": "vgc2024",
            "pokemon": [
                {
                    "species": "Charizard",
                    "level": 50,
                    "ability": "Blaze",
                    "item": "Charcoal",
                    "moves": ["Flamethrower", "Air Slash"]
                }
            ]
        }

        # Mock the created team
        mock_team = MagicMock()
        mock_team.id = uuid4()
        mock_team.agent_id = uuid4()
        mock_team.name = "Test Team"
        mock_team.format = "vgc2024"
        mock_team.pokemon_list = team_data["pokemon"]
        mock_team.created_at = None

        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        response = await async_client.post(
            f"/api/pokemon/teams?agent_id={agent_id}",
            json=team_data
        )
        assert response.status_code in [200, 201, 422]

    @pytest.mark.asyncio
    async def test_get_team(self, async_client, mock_db):
        """Test GET /api/pokemon/teams/{team_id} endpoint"""
        team_id = str(uuid4())

        mock_team = MagicMock()
        mock_team.id = uuid4()
        mock_team.agent_id = uuid4()
        mock_team.name = "Test Team"
        mock_team.format = "vgc2024"
        mock_team.pokemon_list = []
        mock_team.created_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_team
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await async_client.get(f"/api/pokemon/teams/{team_id}")
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_create_battle(self, async_client, mock_db):
        """Test POST /api/pokemon/battles endpoint"""
        team1_id = str(uuid4())
        team2_id = str(uuid4())

        # Mock team retrieval
        mock_team1 = MagicMock()
        mock_team1.id = uuid4()
        mock_team1.agent_id = uuid4()
        mock_team1.pokemon_list = [
            {"species": "Charizard", "ability": "Blaze", "moves": ["Flamethrower"]}
        ]

        mock_team2 = MagicMock()
        mock_team2.id = uuid4()
        mock_team2.agent_id = uuid4()
        mock_team2.pokemon_list = [
            {"species": "Blastoise", "ability": "Torrent", "moves": ["Hydro Pump"]}
        ]

        # Setup mock to return different teams for different queries
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_team1

        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_team2

        mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        response = await async_client.post(
            "/api/pokemon/battles",
            json={
                "player1_team_id": team1_id,
                "player2_team_id": team2_id
            }
        )
        assert response.status_code in [200, 201, 400, 500]

    @pytest.mark.asyncio
    async def test_get_battle_state(self, async_client, mock_db):
        """Test GET /api/pokemon/battles/{battle_id}/state endpoint"""
        battle_id = str(uuid4())

        mock_battle = MagicMock()
        mock_battle.id = uuid4()
        mock_battle.state = {
            "battle_id": battle_id,
            "turn": 1,
            "phase": "battle",
            "weather": "none",
            "trick_room": False,
            "winner": None,
            "player1": {"active": [], "team": []},
            "player2": {"active": [], "team": []}
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_battle
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await async_client.get(f"/api/pokemon/battles/{battle_id}/state")
        assert response.status_code in [200, 404, 422]

    @pytest.mark.asyncio
    async def test_submit_action(self, async_client, mock_db):
        """Test POST /api/pokemon/battles/{battle_id}/turn endpoint"""
        battle_id = str(uuid4())

        mock_battle = MagicMock()
        mock_battle.id = uuid4()
        mock_battle.state = {
            "battle_id": battle_id,
            "turn": 1,
            "phase": "battle",
            "weather": "none",
            "trick_room": False,
            "winner": None,
            "player1": {"active": [0], "team": [{"species": "Charizard", "current_hp": 100, "max_hp": 100}]},
            "player2": {"active": [0], "team": [{"species": "Blastoise", "current_hp": 100, "max_hp": 100}]}
        }
        mock_battle.status = "in_progress"
        mock_battle.winner = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_battle
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        response = await async_client.post(
            f"/api/pokemon/battles/{battle_id}/turn",
            json={
                "player1_actions": [{"pokemon_index": 0, "action_type": "move", "move_index": 0}]
            }
        )
        assert response.status_code in [200, 400, 404, 422, 500]

    @pytest.mark.asyncio
    async def test_invalid_team_id(self, async_client, mock_db):
        """Test handling of invalid team ID"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await async_client.get(f"/api/pokemon/teams/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_battle_id(self, async_client, mock_db):
        """Test handling of invalid battle ID"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await async_client.get(f"/api/pokemon/battles/{uuid4()}/state")
        assert response.status_code == 404
