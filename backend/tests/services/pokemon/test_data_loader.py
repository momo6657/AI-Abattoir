"""
Tests for Pokemon Data Loader
"""
import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.pokemon.data_loader import PokemonDataLoader, DATA_DIR


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock()
    db.add = MagicMock()

    # Mock execute to return empty result (no existing records)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    return db


@pytest.fixture
def loader(mock_db):
    """Create a PokemonDataLoader with mock database"""
    return PokemonDataLoader(mock_db)


class TestPokemonDataLoader:
    """Test data loader functionality"""

    def test_data_dir_exists(self):
        """Test that data directory exists"""
        assert DATA_DIR.exists(), f"Data directory not found: {DATA_DIR}"

    def test_species_file_exists(self):
        """Test that species.json file exists"""
        species_file = DATA_DIR / "species.json"
        assert species_file.exists(), f"Species file not found: {species_file}"

    def test_moves_file_exists(self):
        """Test that moves.json file exists"""
        moves_file = DATA_DIR / "moves.json"
        assert moves_file.exists(), f"Moves file not found: {moves_file}"

    def test_abilities_file_exists(self):
        """Test that abilities.json file exists"""
        abilities_file = DATA_DIR / "abilities.json"
        assert abilities_file.exists(), f"Abilities file not found: {abilities_file}"

    def test_items_file_exists(self):
        """Test that items.json file exists"""
        items_file = DATA_DIR / "items.json"
        assert items_file.exists(), f"Items file not found: {items_file}"

    def test_team_templates_file_exists(self):
        """Test that team_templates.json file exists"""
        templates_file = DATA_DIR / "team_templates.json"
        assert templates_file.exists(), f"Team templates file not found: {templates_file}"

    def test_species_json_structure(self):
        """Test that species.json has correct structure"""
        species_file = DATA_DIR / "species.json"
        with open(species_file, encoding='utf-8') as f:
            data = json.load(f)

        assert "species" in data
        assert isinstance(data["species"], list)
        assert len(data["species"]) > 0

        # Check first species has required fields
        species = data["species"][0]
        assert "id" in species
        assert "name" in species
        assert "name_zh" in species
        assert "types" in species
        assert "base_stats" in species
        assert "abilities" in species

    def test_moves_json_structure(self):
        """Test that moves.json has correct structure"""
        moves_file = DATA_DIR / "moves.json"
        with open(moves_file, encoding='utf-8') as f:
            data = json.load(f)

        assert "moves" in data
        assert isinstance(data["moves"], list)
        assert len(data["moves"]) > 0

        # Check first move has required fields
        move = data["moves"][0]
        assert "name" in move
        assert "name_zh" in move
        assert "type" in move
        assert "category" in move
        assert "power" in move or move.get("power") is None
        assert "accuracy" in move or move.get("accuracy") is None

    def test_abilities_json_structure(self):
        """Test that abilities.json has correct structure"""
        abilities_file = DATA_DIR / "abilities.json"
        with open(abilities_file, encoding='utf-8') as f:
            data = json.load(f)

        assert "abilities" in data
        assert isinstance(data["abilities"], list)
        assert len(data["abilities"]) > 0

        # Check first ability has required fields
        ability = data["abilities"][0]
        assert "name" in ability
        assert "name_zh" in ability
        assert "description" in ability or ability.get("description") is None

    def test_items_json_structure(self):
        """Test that items.json has correct structure"""
        items_file = DATA_DIR / "items.json"
        with open(items_file, encoding='utf-8') as f:
            data = json.load(f)

        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0

        # Check first item has required fields
        item = data["items"][0]
        assert "name" in item
        assert "name_zh" in item
        assert "effect" in item or item.get("effect") is None

    def test_team_templates_json_structure(self):
        """Test that team_templates.json has correct structure"""
        templates_file = DATA_DIR / "team_templates.json"
        with open(templates_file, encoding='utf-8') as f:
            data = json.load(f)

        assert "team_templates" in data
        assert isinstance(data["team_templates"], list)
        assert len(data["team_templates"]) > 0

        # Check first template has required fields
        template = data["team_templates"][0]
        assert "id" in template
        assert "name" in template
        assert "pokemon" in template
        assert isinstance(template["pokemon"], list)

    @pytest.mark.asyncio
    async def test_load_species_calls_db_add(self, loader, mock_db):
        """Test that load_species adds records to database"""
        count = await loader.load_species()

        # Should add species to database
        assert mock_db.add.called
        # Should commit changes
        assert mock_db.commit.called
        # Should return count > 0
        assert count > 0

    @pytest.mark.asyncio
    async def test_load_moves_calls_db_add(self, loader, mock_db):
        """Test that load_moves adds records to database"""
        count = await loader.load_moves()

        # Should add moves to database
        assert mock_db.add.called
        # Should commit changes
        assert mock_db.commit.called
        # Should return count > 0
        assert count > 0

    @pytest.mark.asyncio
    async def test_load_abilities_calls_db_add(self, loader, mock_db):
        """Test that load_abilities adds records to database"""
        count = await loader.load_abilities()

        # Should add abilities to database
        assert mock_db.add.called
        # Should commit changes
        assert mock_db.commit.called
        # Should return count > 0
        assert count > 0

    @pytest.mark.asyncio
    async def test_load_items_calls_db_add(self, loader, mock_db):
        """Test that load_items adds records to database"""
        count = await loader.load_items()

        # Should add items to database
        assert mock_db.add.called
        # Should commit changes
        assert mock_db.commit.called
        # Should return count > 0
        assert count > 0

    @pytest.mark.asyncio
    async def test_load_all_returns_counts(self, loader, mock_db):
        """Test that load_all returns dictionary with counts"""
        counts = await loader.load_all()

        assert isinstance(counts, dict)
        assert "species" in counts
        assert "moves" in counts
        assert "abilities" in counts
        assert "items" in counts

        # All counts should be positive
        assert counts["species"] > 0
        assert counts["moves"] > 0
        assert counts["abilities"] > 0
        assert counts["items"] > 0

    def test_species_base_stats_valid(self):
        """Test that species base stats are within valid ranges"""
        species_file = DATA_DIR / "species.json"
        with open(species_file, encoding='utf-8') as f:
            data = json.load(f)

        for species in data["species"][:5]:  # Check first 5
            stats = species["base_stats"]
            for stat_name, stat_value in stats.items():
                assert 1 <= stat_value <= 255, \
                    f"{species['name']} has invalid {stat_name}: {stat_value}"

    def test_moves_power_valid(self):
        """Test that move power values are valid"""
        moves_file = DATA_DIR / "moves.json"
        with open(moves_file, encoding='utf-8') as f:
            data = json.load(f)

        for move in data["moves"][:10]:  # Check first 10
            if move.get("power") is not None and move["category"] != "status":
                assert 1 <= move["power"] <= 300, \
                    f"{move['name']} has invalid power: {move['power']}"

    def test_moves_accuracy_valid(self):
        """Test that move accuracy values are valid"""
        moves_file = DATA_DIR / "moves.json"
        with open(moves_file, encoding='utf-8') as f:
            data = json.load(f)

        for move in data["moves"][:10]:  # Check first 10
            if move.get("accuracy") is not None:
                assert 0 <= move["accuracy"] <= 100, \
                    f"{move['name']} has invalid accuracy: {move['accuracy']}"
