"""Pokemon format-specific strategy service.

Provides format-specific strategies, rules, and recommendations
for different battle formats (VGC, OU, Random Battle, etc.).
"""

from __future__ import annotations

from typing import Any

from app.services.pokemon.format_catalog import pokemon_format_catalog


# Format-specific strategies and rules
FORMAT_STRATEGIES = {
    "vgc2024": {
        "name": "VGC 2024",
        "description": "官方双打对战格式",
        "team_size": 6,
        "brought": 4,
        "active": 2,
        "rules": [
            "选择 4 只宝可梦参战",
            "双打格式，同时上场 2 只",
            "禁止使用传说宝可梦",
            "太晶化机制生效",
        ],
        "key_strategies": [
            "首发选择：Fake Out + 攻击手 或 速度控制 + 攻击手",
            "保护技能：Protect 是核心技能，用于读取对手行动",
            "速度控制：Tailwind、Trick Room、Icy Wind 是关键",
            "集火攻击：双打中集火一个目标比分散攻击更有效",
            "换人时机：在对手集火时换入抗性好的宝可梦",
        ],
        "common_leads": [
            {"species": "Incineroar", "reason": "Fake Out + Intimidate，VGC 最强辅助"},
            {"species": "Rillaboom", "reason": "Fake Out + Grassy Terrain，场地控制"},
            {"species": "Flutter Mane", "reason": "高速特攻手，太晶化后极强"},
            {"species": "Tornadus", "reason": "Tailwind 用户，速度控制核心"},
        ],
        "threats": [
            {"species": "Flutter Mane", "threat": "高速特攻，难以防御"},
            {"species": "Urshifu", "threat": "无视保护的近身战"},
            {"species": "Calyrex-Shadow", "threat": "超高特攻和速度"},
        ],
    },
    "gen9ou": {
        "name": "Gen 9 OU",
        "description": "第九世代标准单打对战",
        "team_size": 6,
        "brought": 6,
        "active": 1,
        "rules": [
            "单打格式，一次上场 1 只",
            "禁止使用 Ubers 级宝可梦",
            "太晶化机制生效",
            "钉子（Stealth Rock）非常重要",
        ],
        "key_strategies": [
            "钉子控制：Stealth Rock 是单打最重要的技能之一",
            "速度线：了解常见宝可梦的速度线非常重要",
            "强化清场：Dragon Dance、Swords Dance 等强化技能是清场关键",
            "轮转读取：通过 U-turn、Volt Switch 等技能进行安全轮转",
            "状态异常：Toxic、Will-O-Wisp 是重要的消耗手段",
        ],
        "common_leads": [
            {"species": "Great Tusk", "reason": "高速地面格斗，清除钉子"},
            {"species": "Gholdengo", "reason": "钢幽灵，阻止对手除钉"},
            {"species": "Kingambit", "reason": "强化清场手，太晶化后极强"},
        ],
        "threats": [
            {"species": "Kingambit", "threat": "太晶化后 Supreme Overlord 极强"},
            {"species": "Gholdengo", "threat": "Good as Gold 特性免疫所有变化技能"},
            {"species": "Dragapult", "threat": "极高速度和特攻"},
        ],
    },
    "gen9randombattle": {
        "name": "Gen 9 Random Battle",
        "description": "随机对战格式",
        "team_size": 6,
        "brought": 6,
        "active": 1,
        "rules": [
            "随机分配宝可梦和配招",
            "单打格式",
            "太晶化机制生效",
            "无法预知对手队伍",
        ],
        "key_strategies": [
            "适应性：随机战需要快速适应随机的队伍",
            "技能识别：通过对手使用的技能推断其配招",
            "太晶化时机：选择最佳时机太晶化以获得优势",
            "保存实力：保留关键宝可梦应对对手的威胁",
            "属性克制：利用属性优势进行对位交换",
        ],
        "common_leads": [
            {"species": "随机分配", "reason": "根据分配的宝可梦选择首发"},
        ],
        "threats": [
            {"species": "未知", "threat": "无法预知对手队伍，需要灵活应对"},
        ],
    },
}


class PokemonFormatStrategy:
    """Provides format-specific strategies and recommendations."""

    def get_strategy(self, battle_format: str) -> dict[str, Any]:
        """Get strategy information for a format."""
        # Normalize format name
        normalized = battle_format.lower().replace(" ", "").replace("-", "")

        # Check direct match
        if normalized in FORMAT_STRATEGIES:
            return FORMAT_STRATEGIES[normalized]

        # Check aliases
        for key in FORMAT_STRATEGIES:
            if key in normalized or normalized in key:
                return FORMAT_STRATEGIES[key]

        # Default strategy
        return {
            "name": battle_format,
            "description": f"{battle_format} 对战格式",
            "team_size": 6,
            "brought": 6,
            "active": 1,
            "rules": ["遵循标准对战规则"],
            "key_strategies": ["根据队伍构成选择合适策略"],
            "common_leads": [],
            "threats": [],
        }

    def get_all_formats(self) -> list[dict[str, Any]]:
        """Get all available format strategies."""
        return [
            {
                "format_id": key,
                "name": strategy["name"],
                "description": strategy["description"],
                "team_size": strategy["team_size"],
                "brought": strategy["brought"],
                "active": strategy["active"],
            }
            for key, strategy in FORMAT_STRATEGIES.items()
        ]

    def get_lead_recommendations(
        self,
        battle_format: str,
        team: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Get lead recommendations for a format and team."""
        strategy = self.get_strategy(battle_format)
        recommendations = strategy.get("common_leads", [])

        # If we have team data, filter to team members
        if team:
            team_species = {p.get("species", "").lower() for p in team}
            filtered = [
                rec for rec in recommendations
                if rec["species"].lower() in team_species
            ]
            if filtered:
                return filtered

        return recommendations

    def get_threat_list(self, battle_format: str) -> list[dict[str, Any]]:
        """Get threat list for a format."""
        strategy = self.get_strategy(battle_format)
        return strategy.get("threats", [])

    def get_format_tips(self, battle_format: str) -> list[str]:
        """Get quick tips for a format."""
        strategy = self.get_strategy(battle_format)
        return strategy.get("key_strategies", [])


pokemon_format_strategy = PokemonFormatStrategy()
