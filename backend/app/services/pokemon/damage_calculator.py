"""
宝可梦伤害计算器

实现标准的伤害计算公式
"""

import random
from typing import Dict, Any


class DamageCalculator:
    """伤害计算器"""

    @staticmethod
    def calculate_damage(
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        move: Dict[str, Any],
        type_effectiveness: float = 1.0,
        stab: bool = False,
        critical: bool = False,
        random_factor: float = None,
    ) -> int:
        """
        计算伤害值

        公式: ((2 * Level / 5 + 2) * Power * A / D) / 50 + 2) * Modifiers

        Args:
            attacker: 攻击方数据 {level, atk/spa, types}
            defender: 防御方数据 {hp, def/spd, types}
            move: 技能数据 {power, type, category}
            type_effectiveness: 属性克制倍率
            stab: 是否享受本系加成
            critical: 是否暴击
            random_factor: 随机因子 (0.85-1.0), None 则随机生成

        Returns:
            伤害值
        """
        # 状态技能不造成伤害
        if move.get("category") == "status" or not move.get("power"):
            return 0

        level = attacker.get("level", 50)
        power = move["power"]

        # 获取攻击和防御数值
        if move["category"] == "physical":
            attack_stat = attacker.get("atk", 100)
            defense_stat = defender.get("def", 100)
        else:  # special
            attack_stat = attacker.get("spa", 100)
            defense_stat = defender.get("spd", 100)

        # 基础伤害计算
        damage = ((2 * level / 5 + 2) * power * attack_stat / defense_stat) / 50 + 2

        # 暴击修正 (1.5倍)
        if critical:
            damage *= 1.5

        # 随机因子 (85%-100%)
        if random_factor is None:
            random_factor = random.uniform(0.85, 1.0)
        damage *= random_factor

        # STAB 本系加成 (1.5倍)
        if stab:
            damage *= 1.5

        # 属性克制
        damage *= type_effectiveness

        # 向下取整，最少1点伤害
        return max(1, int(damage))

    @staticmethod
    def check_critical(critical_stage: int = 0) -> bool:
        """
        判断是否暴击

        Args:
            critical_stage: 暴击等级 (0-3+)

        Returns:
            是否暴击
        """
        # 暴击率：stage 0 = 1/24, stage 1 = 1/8, stage 2 = 1/2, stage 3+ = 100%
        crit_rates = {
            0: 1 / 24,
            1: 1 / 8,
            2: 1 / 2,
        }

        if critical_stage >= 3:
            return True

        rate = crit_rates.get(critical_stage, 1 / 24)
        return random.random() < rate

    @staticmethod
    def check_move_hit(accuracy: int, evasion_stage: int = 0, accuracy_stage: int = 0) -> bool:
        """
        判断技能是否命中

        Args:
            accuracy: 技能基础命中率 (0-100)
            evasion_stage: 回避等级 (-6 到 +6)
            accuracy_stage: 命中等级 (-6 到 +6)

        Returns:
            是否命中
        """
        if accuracy == 0:  # 必中技能
            return True

        # 计算命中修正
        evasion_mult = (3 + max(-6, min(6, evasion_stage))) / 3
        accuracy_mult = (3 + max(-6, min(6, accuracy_stage))) / 3

        final_accuracy = accuracy * accuracy_mult / evasion_mult
        return random.randint(1, 100) <= final_accuracy


# 便捷函数
def calculate_damage(
    attacker: Dict[str, Any],
    defender: Dict[str, Any],
    move: Dict[str, Any],
    type_effectiveness: float = 1.0,
    stab: bool = False,
    critical: bool = False,
) -> int:
    """计算伤害的便捷函数"""
    return DamageCalculator.calculate_damage(
        attacker, defender, move, type_effectiveness, stab, critical
    )
