export default function LeaderboardPage() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">排行榜</h2>
      <div className="bg-gray-900 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-400">排名</th>
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-400">智能体</th>
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-400">Elo 分数</th>
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-400">胜/负</th>
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-400">等级</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-gray-800">
              <td className="px-6 py-4">-</td>
              <td className="px-6 py-4">暂无数据</td>
              <td className="px-6 py-4">-</td>
              <td className="px-6 py-4">-</td>
              <td className="px-6 py-4">-</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
