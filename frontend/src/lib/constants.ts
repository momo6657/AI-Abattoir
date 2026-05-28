export const GAME_TYPES = [
  { value: 'werewolf', label: '狼人杀', desc: '智能体扮演角色，进行社交推理博弈', color: 'bg-red-600', icon: 'W', minPlayers: 4 },
  { value: 'debate', label: '辩论赛', desc: '正反方结构化辩论对决', color: 'bg-blue-600', icon: 'D', minPlayers: 2 },
  { value: 'chess', label: '棋类', desc: '国际象棋等策略对弈', color: 'bg-green-600', icon: 'C', minPlayers: 2 },
  { value: 'text_adventure', label: '文字冒险', desc: '合作解谜、探索未知世界', color: 'bg-purple-600', icon: 'A', minPlayers: 2 },
  { value: 'negotiation', label: '谈判', desc: '囚徒困境、资源分配等博弈论场景', color: 'bg-yellow-600', icon: 'N', minPlayers: 2 },
];

export function getGameTypeInfo(type: string) {
  return GAME_TYPES.find((t) => t.value === type) || GAME_TYPES[0];
}
