"""Pokemon weather and terrain effects service.

Tracks weather conditions, terrain effects, and their
impact on battle mechanics.
"""

from __future__ import annotations

from typing import Any


# Weather effects
WEATHER_EFFECTS = {
    "sun": {
        "name": "晴天",
        "description": "阳光强烈",
        "fire_boost": 1.5,
        "water_reduction": 0.5,
        "solar_moves": "instant",  # Solar Beam, Solar Blade
        "abilities": {
            "chlorophyll": "速度翻倍",
            "flower_gift": "攻击和特防提升",
            "forecast": "变为火属性",
            "leaf_guard": "免疫异常状态",
            "solar_power": "特攻提升但每回合损失HP",
        },
        "items": {
            "heat rock": "延长晴天回合数",
        },
    },
    "rain": {
        "name": "雨天",
        "description": "下着大雨",
        "water_boost": 1.5,
        "fire_reduction": 0.5,
        "thunder_perfect": True,  # Thunder never misses
        "abilities": {
            "swift swim": "速度翻倍",
            "rain dish": "每回合恢复HP",
            "forecast": "变为水属性",
            "hydration": "每回合治愈异常状态",
        },
        "items": {
            "damp rock": "延长雨天回合数",
        },
    },
    "sandstorm": {
        "name": "沙暴",
        "description": "沙暴肆虐",
        "rock_spd_boost": 1.5,  # Rock type SpDef boost
        "damage_per_turn": 1/16,  # Non-immune types take damage
        "immune_types": ["Rock", "Ground", "Steel"],
        "abilities": {
            "sand veil": "闪避率提升",
            "sand rush": "速度翻倍",
            "sand force": "岩石地面钢属性招式威力提升",
        },
        "items": {
            "smooth rock": "延长沙暴回合数",
        },
    },
    "hail": {
        "name": "冰雹",
        "description": "冰雹纷飞",
        "damage_per_turn": 1/16,  # Non-immune types take damage
        "immune_types": ["Ice"],
        "abilities": {
            "ice body": "每回合恢复HP",
            "snow cloak": "闪避率提升",
            "slush rush": "速度翻倍",
        },
        "items": {
            "icy rock": "延长冰雹回合数",
        },
        "moves": {
            "blizzard": "在冰雹中必中",
        },
    },
}

# Terrain effects
TERRAIN_EFFECTS = {
    "electric": {
        "name": "电气场地",
        "description": "地面充满电气",
        "boosted_type": "Electric",
        "boost": 1.3,
        "grounded_only": True,  # Only grounded Pokemon get boost
        "sleep_immunity": True,  # Grounded Pokemon can't sleep
        "abilities": {
            "surge surfer": "速度翻倍",
        },
        "items": {
            "terrain extender": "延长场地回合数",
        },
        "seeds": {
            "electric seed": "提升防御",
        },
    },
    "grassy": {
        "name": "青草场地",
        "description": "地面长满青草",
        "boosted_type": "Grass",
        "boost": 1.3,
        "grounded_only": True,
        "heal_per_turn": 1/16,  # Grounded Pokemon heal each turn
        "moves": {
            "earthquake": "威力减半",
            "bulldoze": "威力减半",
            "magnitude": "威力减半",
        },
        "items": {
            "terrain extender": "延长场地回合数",
        },
        "seeds": {
            "grassy seed": "提升特防",
        },
    },
    "misty": {
        "name": "薄雾场地",
        "description": "地面笼罩薄雾",
        "boosted_type": "Fairy",
        "boost": 1.3,
        "grounded_only": True,
        "status_immunity": True,  # Grounded Pokemon can't get status
        "dragon_reduction": 0.5,  # Dragon moves deal half damage to grounded
        "items": {
            "terrain extender": "延长场地回合数",
        },
        "seeds": {
            "misty seed": "提升特防",
        },
    },
    "psychic": {
        "name": "精神场地",
        "description": "地面充满精神力量",
        "boosted_type": "Psychic",
        "boost": 1.3,
        "grounded_only": True,
        "priority_immunity": True,  # Grounded Pokemon immune to priority moves
        "abilities": {
            "psychic surge": "自动设置精神场地",
        },
        "items": {
            "terrain extender": "延长场地回合数",
        },
        "seeds": {
            "psychic seed": "提升特防",
        },
    },
}


class PokemonWeatherTerrain:
    """Tracks and analyzes weather and terrain effects."""

    def get_weather_effects(self, weather: str) -> dict[str, Any] | None:
        """Get effects for a weather condition."""
        normalized = weather.lower().replace(" ", "")
        for key, effects in WEATHER_EFFECTS.items():
            if key in normalized or normalized in key:
                return effects
        return None

    def get_terrain_effects(self, terrain: str) -> dict[str, Any] | None:
        """Get effects for a terrain condition."""
        normalized = terrain.lower().replace(" ", "").replace("terrain", "")
        for key, effects in TERRAIN_EFFECTS.items():
            if key in normalized or normalized in key:
                return effects
        return None

    def analyze_weather_impact(
        self,
        weather: str,
        team: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyze how weather affects a team."""
        effects = self.get_weather_effects(weather)
        if not effects:
            return {"weather": weather, "impact": "none", "details": []}

        details = []
        benefits = []
        drawbacks = []

        for pokemon in team:
            types = pokemon.get("types", [])
            ability = pokemon.get("ability", "").lower()
            species = pokemon.get("species") or pokemon.get("name", "Unknown")

            # Check type-based effects
            if weather == "sun":
                if "Fire" in types:
                    benefits.append(f"{species}: 火属性招式威力提升 50%")
                if "Water" in types:
                    drawbacks.append(f"{species}: 水属性招式威力降低 50%")
            elif weather == "rain":
                if "Water" in types:
                    benefits.append(f"{species}: 水属性招式威力提升 50%")
                if "Fire" in types:
                    drawbacks.append(f"{species}: 火属性招式威力降低 50%")
            elif weather == "sandstorm":
                if "Rock" in types:
                    benefits.append(f"{species}: 特防提升 50%")
                elif any(t in types for t in ["Rock", "Ground", "Steel"]):
                    benefits.append(f"{species}: 免受沙暴伤害")
                else:
                    drawbacks.append(f"{species}: 每回合受到沙暴伤害")
            elif weather == "hail":
                if "Ice" in types:
                    benefits.append(f"{species}: 免受冰雹伤害")
                else:
                    drawbacks.append(f"{species}: 每回合受到冰雹伤害")

            # Check ability-based effects
            weather_abilities = effects.get("abilities", {})
            for ability_name, ability_effect in weather_abilities.items():
                if ability_name in ability:
                    benefits.append(f"{species}: {ability_effect}")

        return {
            "weather": effects.get("name", weather),
            "description": effects.get("description", ""),
            "benefits": benefits,
            "drawbacks": drawbacks,
            "net_impact": "positive" if len(benefits) > len(drawbacks) else "negative" if len(drawbacks) > len(benefits) else "neutral",
        }

    def analyze_terrain_impact(
        self,
        terrain: str,
        team: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyze how terrain affects a team."""
        effects = self.get_terrain_effects(terrain)
        if not effects:
            return {"terrain": terrain, "impact": "none", "details": []}

        details = []
        benefits = []
        drawbacks = []

        boosted_type = effects.get("boosted_type")
        for pokemon in team:
            types = pokemon.get("types", [])
            species = pokemon.get("species") or pokemon.get("name", "Unknown")

            if boosted_type and boosted_type in types:
                benefits.append(f"{species}: {boosted_type} 属性招式威力提升 30%")

            # Check for seed items
            item = pokemon.get("item", "").lower()
            seeds = effects.get("seeds", {})
            for seed_name, seed_effect in seeds.items():
                if seed_name in item:
                    benefits.append(f"{species}: {seed_effect}")

        return {
            "terrain": effects.get("name", terrain),
            "description": effects.get("description", ""),
            "boosted_type": boosted_type,
            "benefits": benefits,
            "drawbacks": drawbacks,
            "net_impact": "positive" if benefits else "neutral",
        }

    def get_all_weather(self) -> list[dict[str, Any]]:
        """Get all weather conditions."""
        return [
            {
                "id": key,
                "name": effects["name"],
                "description": effects["description"],
            }
            for key, effects in WEATHER_EFFECTS.items()
        ]

    def get_all_terrain(self) -> list[dict[str, Any]]:
        """Get all terrain conditions."""
        return [
            {
                "id": key,
                "name": effects["name"],
                "description": effects["description"],
                "boosted_type": effects.get("boosted_type"),
            }
            for key, effects in TERRAIN_EFFECTS.items()
        ]


pokemon_weather_terrain = PokemonWeatherTerrain()
