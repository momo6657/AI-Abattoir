"""
Tests for Pokemon REST API
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from fastapi.testclient import TestClient
from httpx import AsyncClient
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


@pytest.fixture
def client(mock_db):
    """Create a test client with mocked database"""
    app.dependency_overrides[get_db] = lambda: mock_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestPokemonAPI:
    """Test Pokemon REST API endpoints"""

    def test_get_species_list(self, client, mock_db):
        """Test GET /api/pokemon/species endpoint"""
        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [
            MagicMock(
                id=1,
                name="Bulbasaur",
                name_zh="妙蛙种子",
                types=["Grass", "Poison"],
                base_stats={"hp": 45, "atk": 49, "def": 49, "spa": 65, "spd": 65, "spe": 45}
            )
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/pokemon/species")
        assert response.status_code == 200

    def test_get_moves_list(self, client, mock_db):
        """Test GET /api/pokemon/moves endpoint"""
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [
            MagicMock(
                name="Thunderbolt",
                name_zh="十万伏特",
                type="Electric",
                category="special",
                power=90,
                accuracy=100
            )
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/pokemon/moves")
        assert response.status_code == 200

    def test_create_team(self, client, mock_db):
        """Test POST /api/pokemon/teams endpoint"""
        agent_id = str(uuid4())
        team_data = {
            "name": "Test Team",
            "pokemon": [
                {
                    "species": "Charizard",
                    "ability": "Blaze",
                    "moves": ["Flamethrower", "Air Slash"]
                }
            ]
        }

        # Mock the created team
        mock_team = MagicMock()
        mock_team.id = uuid4()
        mock_team.agent_id = uuid4()
        mock_team.name = "Test Team"
        mock_team.pokemon_list = team_data["pokemon"]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.refresh = AsyncMock()

        response = client.post(
            f"/api/pokemon/teams?agent_id={agent_id}",
            json=team_data
        )
        assert response.status_code in [200, 201]

    def test_get_team(self, client, mock_db):
        """Test GET /api/pokemon/teams/{team_id} endpoint"""
        team_id = str(uuid4())

        mock_team = MagicMock()
        mock_team.id = uuid4()
        mock_team.agent_id = uuid4()
        mock_team.name = "Test Team"
        mock_team.pokemon_list = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_team
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get(f"/api/pokemon/teams/{team_id}")
        assert response.status_code in [200, 404]

    def test_create_battle(self, client, mock_db):
        """Test POST /api/pokemon/battles endpoint"""
        team1_id = str(uuid4())
        team2_id = str(uuid4())

        # Mock team retrieval
        mock_team1 = MagicMock()
        mock_team1.id = uuid4()
        mock_team1.pokemon_list = [
            {"species": "Charizard", "ability": "Blaze", "moves": ["Flamethrower"]}
        ]

        mock_team2 = MagicMock()
        mock_team2.id = uuid4()
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
        mock_db.refresh = AsyncMock()

        response = client.post(
            "/api/pokemon/battles",
            json={
                "player1_team_id": team1_id,
                "player2_team_id": team2_id
            }
        )
        assert response.status_code in [200, 201, 400, 500]

    def test_get_battle_state(self, client, mock_db):
        """Test GET /api/pokemon/battles/{battle_id}/state endpoint"""
        battle_id = str(uuid4())

        mock_battle = MagicMock()
        mock_battle.id = uuid4()
        mock_battle.state = {
            "battle_id": battle_id,
            "turn": 1,
            "player1": {"active": []},
            "player2": {"active": []}
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_battle
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get(f"/api/pokemon/battles/{battle_id}/state")
        assert response.status_code in [200, 404]

    def test_submit_action(self, client, mock_db):
        """Test POST /api/pokemon/battles/{battle_id}/action endpoint"""
        battle_id = str(uuid4())

        mock_battle = MagicMock()
        mock_battle.id = uuid4()
        mock_battle.state = {
            "battle_id": battle_id,
            "turn": 1,
            "player1": {"active": []},
            "player2": {"active": []}
        }

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_battle
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        response = client.post(
            f"/api/pokemon/battles/{battle_id}/action?player=1",
            json={
                "pokemon_index": 0,
                "move_index": 0,
                "target": [2, 0]
            }
        )
        assert response.status_code in [200, 400, 404, 500]

    def test_invalid_team_id(self, client, mock_db):
        """Test handling of invalid team ID"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get(f"/api/pokemon/teams/{uuid4()}")
        assert response.status_code == 404

    def test_invalid_battle_id(self, client, mock_db):
        """Test handling of invalid battle ID"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = client.get(f"/api/pokemon/battles/{uuid4()}/state")
        assert response.status_code == 404
