"""
Integration tests for Pokemon battle system
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import get_db, engine, Base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import uuid


@pytest.fixture
async def async_client():
    """Create async test client"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def db_session():
    """Create test database session"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.mark.asyncio
async def test_pokemon_species_list(async_client: AsyncClient):
    """Test fetching Pokemon species list"""
    response = await async_client.get("/api/pokemon/species")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_pokemon_moves_list(async_client: AsyncClient):
    """Test fetching Pokemon moves list"""
    response = await async_client.get("/api/pokemon/moves")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_create_team(async_client: AsyncClient):
    """Test creating a Pokemon team"""
    agent_id = str(uuid.uuid4())
    team_data = {
        "name": "Test Team",
        "pokemon": [
            {
                "species": "Pikachu",
                "level": 50,
                "moves": ["Thunderbolt", "Quick Attack"],
                "ability": "Static",
                "item": "Light Ball"
            },
            {
                "species": "Charizard",
                "level": 50,
                "moves": ["Flamethrower", "Air Slash"],
                "ability": "Blaze",
                "item": "Charcoal"
            }
        ]
    }

    response = await async_client.post(
        f"/api/pokemon/teams?agent_id={agent_id}",
        json=team_data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Team"
    assert len(data["pokemon"]) == 2


@pytest.mark.asyncio
async def test_get_team(async_client: AsyncClient):
    """Test getting a team by ID"""
    agent_id = str(uuid.uuid4())
    team_data = {
        "name": "Test Team",
        "pokemon": [
            {
                "species": "Bulbasaur",
                "level": 50,
                "moves": ["Vine Whip"],
                "ability": "Overgrow",
                "item": "None"
            }
        ]
    }

    # Create team
    create_response = await async_client.post(
        f"/api/pokemon/teams?agent_id={agent_id}",
        json=team_data
    )
    team_id = create_response.json()["id"]

    # Get team
    response = await async_client.get(f"/api/pokemon/teams/{team_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == team_id
    assert data["name"] == "Test Team"


@pytest.mark.asyncio
async def test_create_battle(async_client: AsyncClient):
    """Test creating a battle"""
    agent_id1 = str(uuid.uuid4())
    agent_id2 = str(uuid.uuid4())

    # Create two teams
    team1_data = {
        "name": "Team 1",
        "pokemon": [
            {
                "species": "Pikachu",
                "level": 50,
                "moves": ["Thunderbolt"],
                "ability": "Static",
                "item": "None"
            }
        ]
    }
    team2_data = {
        "name": "Team 2",
        "pokemon": [
            {
                "species": "Charmander",
                "level": 50,
                "moves": ["Ember"],
                "ability": "Blaze",
                "item": "None"
            }
        ]
    }

    team1_response = await async_client.post(
        f"/api/pokemon/teams?agent_id={agent_id1}",
        json=team1_data
    )
    team2_response = await async_client.post(
        f"/api/pokemon/teams?agent_id={agent_id2}",
        json=team2_data
    )

    team1_id = team1_response.json()["id"]
    team2_id = team2_response.json()["id"]

    # Create battle
    battle_data = {
        "team1_id": team1_id,
        "team2_id": team2_id
    }
    response = await async_client.post("/api/pokemon/battles", json=battle_data)
    assert response.status_code == 200
    data = response.json()
    assert "battle_id" in data
    assert "initial_state" in data


@pytest.mark.asyncio
async def test_submit_action(async_client: AsyncClient):
    """Test submitting a battle action"""
    agent_id1 = str(uuid.uuid4())
    agent_id2 = str(uuid.uuid4())

    # Create teams and battle
    team1_data = {
        "name": "Team 1",
        "pokemon": [{"species": "Pikachu", "level": 50, "moves": ["Thunderbolt"], "ability": "Static", "item": "None"}]
    }
    team2_data = {
        "name": "Team 2",
        "pokemon": [{"species": "Charmander", "level": 50, "moves": ["Ember"], "ability": "Blaze", "item": "None"}]
    }

    team1_response = await async_client.post(f"/api/pokemon/teams?agent_id={agent_id1}", json=team1_data)
    team2_response = await async_client.post(f"/api/pokemon/teams?agent_id={agent_id2}", json=team2_data)

    battle_response = await async_client.post("/api/pokemon/battles", json={
        "team1_id": team1_response.json()["id"],
        "team2_id": team2_response.json()["id"]
    })
    battle_id = battle_response.json()["battle_id"]

    # Submit action
    action_data = {
        "pokemon_index": 0,
        "move_index": 0
    }
    response = await async_client.post(
        f"/api/pokemon/battles/{battle_id}/action?player=1",
        json=action_data
    )
    assert response.status_code == 200
    data = response.json()
    assert "success" in data


@pytest.mark.asyncio
async def test_get_battle_state(async_client: AsyncClient):
    """Test getting battle state"""
    agent_id1 = str(uuid.uuid4())
    agent_id2 = str(uuid.uuid4())

    # Create teams and battle
    team1_data = {
        "name": "Team 1",
        "pokemon": [{"species": "Pikachu", "level": 50, "moves": ["Thunderbolt"], "ability": "Static", "item": "None"}]
    }
    team2_data = {
        "name": "Team 2",
        "pokemon": [{"species": "Charmander", "level": 50, "moves": ["Ember"], "ability": "Blaze", "item": "None"}]
    }

    team1_response = await async_client.post(f"/api/pokemon/teams?agent_id={agent_id1}", json=team1_data)
    team2_response = await async_client.post(f"/api/pokemon/teams?agent_id={agent_id2}", json=team2_data)

    battle_response = await async_client.post("/api/pokemon/battles", json={
        "team1_id": team1_response.json()["id"],
        "team2_id": team2_response.json()["id"]
    })
    battle_id = battle_response.json()["battle_id"]

    # Get battle state
    response = await async_client.get(f"/api/pokemon/battles/{battle_id}/state")
    assert response.status_code == 200
    data = response.json()
    assert "turn" in data
    assert "player1" in data
    assert "player2" in data


@pytest.mark.asyncio
async def test_init_pokemon_data(async_client: AsyncClient):
    """Test initializing Pokemon data"""
    response = await async_client.post("/api/pokemon/init")
    assert response.status_code == 200
    data = response.json()
    assert "species_loaded" in data
    assert "moves_loaded" in data
    assert "abilities_loaded" in data
    assert "items_loaded" in data
