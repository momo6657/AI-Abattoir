"""
宝可梦属性克制系统

实现属性克制关系的查询和计算
"""

from typing import Dict, List


class TypeChart:
    """属性克制表"""

    # 属性克制关系表
    # key: 攻击属性, value: {防御属性: 倍率}
    EFFECTIVENESS: Dict[str, Dict[str, float]] = {
        "Normal": {
            "Rock": 0.5,
            "Ghost": 0.0,
            "Steel": 0.5,
        },
        "Fire": {
            "Fire": 0.5,
            "Water": 0.5,
            "Grass": 2.0,
            "Ice": 2.0,
            "Bug": 2.0,
            "Rock": 0.5,
            "Dragon": 0.5,
            "Steel": 2.0,
        },
        "Water": {
            "Fire": 2.0,
            "Water": 0.5,
            "Grass": 0.5,
            "Ground": 2.0,
            "Rock": 2.0,
            "Dragon": 0.5,
        },
        "Electric": {
            "Water": 2.0,
            "Electric": 0.5,
            "Grass": 0.5,
            "Ground": 0.0,
            "Flying": 2.0,
            "Dragon": 0.5,
        },
        "Grass": {
            "Fire": 0.5,
            "Water": 2.0,
            "Grass": 0.5,
            "Poison": 0.5,
            "Ground": 2.0,
            "Flying": 0.5,
            "Bug": 0.5,
            "Rock": 2.0,
            "Dragon": 0.5,
            "Steel": 0.5,
        },
        "Ice": {
            "Fire": 0.5,
            "Water": 0.5,
            "Grass": 2.0,
            "Ice": 0.5,
            "Ground": 2.0,
            "Flying": 2.0,
            "Dragon": 2.0,
            "Steel": 0.5,
        },
        "Fighting": {
            "Normal": 2.0,
            "Ice": 2.0,
            "Poison": 0.5,
            "Flying": 0.5,
            "Psychic": 0.5,
            "Bug": 0.5,
            "Rock": 2.0,
            "Ghost": 0.0,
            "Dark": 2.0,
            "Steel": 2.0,
            "Fairy": 0.5,
        },
        "Poison": {
            "Grass": 2.0,
            "Poison": 0.5,
            "Ground": 0.5,
            "Rock": 0.5,
            "Ghost": 0.5,
            "Steel": 0.0,
            "Fairy": 2.0,
        },
        "Ground": {
            "Fire": 2.0,
            "Electric": 2.0,
            "Grass": 0.5,
            "Poison": 2.0,
            "Flying": 0.0,
            "Bug": 0.5,
            "Rock": 2.0,
            "Steel": 2.0,
        },
        "Flying": {
            "Electric": 0.5,
            "Grass": 2.0,
            "Fighting": 2.0,
            "Bug": 2.0,
            "Rock": 0.5,
            "Steel": 0.5,
        },
        "Psychic": {
            "Fighting": 2.0,
            "Poison": 2.0,
            "Psychic": 0.5,
            "Dark": 0.0,
            "Steel": 0.5,
        },
        "Bug": {
            "Fire": 0.5,
            "Grass": 2.0,
            "Fighting": 0.5,
            "Poison": 0.5,
            "Flying": 0.5,
            "Psychic": 2.0,
            "Ghost": 0.5,
            "Dark": 2.0,
            "Steel": 0.5,
            "Fairy": 0.5,
        },
        "Rock": {
            "Fire": 2.0,
            "Ice": 2.0,
            "Fighting": 0.5,
            "Ground": 0.5,
            "Flying": 2.0,
            "Bug": 2.0,
            "Steel": 0.5,
        },
        "Ghost": {
            "Normal": 0.0,
            "Psychic": 2.0,
            "Ghost": 2.0,
            "Dark": 0.5,
        },
        "Dragon": {
            "Dragon": 2.0,
            "Steel": 0.5,
            "Fairy": 0.0,
        },
        "Dark": {
            "Fighting": 0.5,
            "Psychic": 2.0,
            "Ghost": 2.0,
            "Dark": 0.5,
            "Fairy": 0.5,
        },
        "Steel": {
            "Fire": 0.5,
            "Water": 0.5,
            "Electric": 0.5,
            "Ice": 2.0,
            "Rock": 2.0,
            "Steel": 0.5,
            "Fairy": 2.0,
        },
        "Fairy": {
            "Fire": 0.5,
            "Fighting": 2.0,
            "Poison": 0.5,
            "Dragon": 2.0,
            "Dark": 2.0,
            "Steel": 0.5,
        },
    }

    @classmethod
    def get_effectiveness(cls, attack_type: str, defense_type: str) -> float:
        """
        获取单属性克制倍率

        Args:
            attack_type: 攻击属性
            defense_type: 防御属性

        Returns:
            克制倍率 (0.0, 0.5, 1.0, 2.0)
        """
        if attack_type not in cls.EFFECTIVENESS:
            return 1.0

        return cls.EFFECTIVENESS[attack_type].get(defense_type, 1.0)

    @classmethod
    def get_dual_type_effectiveness(cls, attack_type: str, defense_types: List[str]) -> float:
        """
        获取对双属性的克制倍率

        Args:
            attack_type: 攻击属性
            defense_types: 防御属性列表（最多2个）

        Returns:
            总克制倍率（各个属性倍率相乘）
        """
        if not defense_types:
            return 1.0

        total = 1.0
        for defense_type in defense_types:
            total *= cls.get_effectiveness(attack_type, defense_type)

        return total

    @classmethod
    def get_all_effectiveness(cls, attack_type: str) -> Dict[str, float]:
        """
        获取某个攻击属性对所有防御属性的克制关系

        Args:
            attack_type: 攻击属性

        Returns:
            {防御属性: 倍率} 字典
        """
        return cls.EFFECTIVENESS.get(attack_type, {})


# 便捷函数
def get_type_effectiveness(attack_type: str, defense_types: List[str]) -> float:
    """获取属性克制倍率的便捷函数"""
    return TypeChart.get_dual_type_effectiveness(attack_type, defense_types)
