export default function ArenaPage() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">竞技场</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-gray-900 p-6 rounded-xl">
          <h3 className="text-lg font-semibold mb-2">问答 PK</h3>
          <p className="text-gray-400 mb-4">同一问题，多个模型分别作答，投票选出最佳</p>
          <button className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg">开始 PK</button>
        </div>
        <div className="bg-gray-900 p-6 rounded-xl">
          <h3 className="text-lg font-semibold mb-2">生图对决</h3>
          <p className="text-gray-400 mb-4">同一 prompt，各模型生成图片，投票评选</p>
          <button className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg">开始对决</button>
        </div>
        <div className="bg-gray-900 p-6 rounded-xl">
          <h3 className="text-lg font-semibold mb-2">代码竞赛</h3>
          <p className="text-gray-400 mb-4">编程题自动评测，运行测试用例评分</p>
          <button className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg">开始竞赛</button>
        </div>
        <div className="bg-gray-900 p-6 rounded-xl">
          <h3 className="text-lg font-semibold mb-2">配音 PK</h3>
          <p className="text-gray-400 mb-4">同一文本，各 TTS 模型生成语音，比较效果</p>
          <button className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg">开始 PK</button>
        </div>
      </div>
    </div>
  );
}
