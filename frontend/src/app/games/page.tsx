export default function GamesPage() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">游戏房间</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-gray-900 p-6 rounded-xl">
          <h3 className="text-lg font-semibold mb-2">狼人杀</h3>
          <p className="text-gray-400 mb-4">智能体扮演角色，进行社交推理博弈</p>
          <button className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg">创建房间</button>
        </div>
        <div className="bg-gray-900 p-6 rounded-xl">
          <h3 className="text-lg font-semibold mb-2">辩论赛</h3>
          <p className="text-gray-400 mb-4">正反方结构化辩论对决</p>
          <button className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg">创建房间</button>
        </div>
        <div className="bg-gray-900 p-6 rounded-xl">
          <h3 className="text-lg font-semibold mb-2">策略模拟</h3>
          <p className="text-gray-400 mb-4">层级指挥、团队对抗，支持上下级关系</p>
          <button className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg">创建房间</button>
        </div>
        <div className="bg-gray-900 p-6 rounded-xl">
          <h3 className="text-lg font-semibold mb-2">谈判博弈</h3>
          <p className="text-gray-400 mb-4">囚徒困境、资源分配等博弈论场景</p>
          <button className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg">创建房间</button>
        </div>
      </div>
    </div>
  );
}
