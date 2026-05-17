"use client";

import { useEffect, useState, useCallback } from "react";
import { agentsApi, hierarchyApi } from "@/lib/api";
import { ErrorBanner, LoadingSpinner } from "@/components";

interface Agent {
  id: string;
  name: string;
  description: string;
  level: string;
}

interface HierarchyNode {
  agent_id: string;
  agent_name: string;
  subordinates: HierarchyNode[];
}

export default function HierarchyPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tree, setTree] = useState<HierarchyNode | null>(null);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ parent_agent_id: "", child_agent_id: "", relation_type: "command" });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    agentsApi.list().then((r) => setAgents(r.data)).catch(() => {});
  }, []);

  const loadTree = useCallback(async (agentId: string) => {
    try {
      setLoading(true);
      const r = await hierarchyApi.getTree(agentId);
      setTree(r.data);
    } catch {
      setTree(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedAgent) loadTree(selectedAgent);
  }, [selectedAgent, loadTree]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await hierarchyApi.create(form);
      if (selectedAgent) loadTree(selectedAgent);
      setShowForm(false);
      setForm({ parent_agent_id: "", child_agent_id: "", relation_type: "command" });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "创建失败");
    }
  };

  const renderTree = (node: HierarchyNode, depth: number = 0) => (
    <div key={node.agent_id} style={{ marginLeft: depth * 24 }}>
      <div className="flex items-center gap-2 py-2 px-3 hover:bg-gray-800 rounded-lg">
        {depth > 0 && <span className="text-gray-600">├─</span>}
        <span className="font-medium">{node.agent_name}</span>
        <span className="text-xs text-gray-500">({node.agent_id.slice(0, 8)})</span>
      </div>
      {node.subordinates.map((child) => renderTree(child, depth + 1))}
    </div>
  );

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold">层级指挥系统</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg"
        >
          创建层级关系
        </button>
      </div>

      {error && (
        <ErrorBanner message={error} onDismiss={() => setError(null)} />
      )}

      {showForm && (
        <form onSubmit={handleCreate} className="bg-gray-900 p-6 rounded-xl mb-6 space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">上级智能体</label>
            <select
              value={form.parent_agent_id}
              onChange={(e) => setForm({ ...form, parent_agent_id: e.target.value })}
              className="w-full bg-gray-800 rounded-lg px-4 py-2"
              required
            >
              <option value="">选择上级</option>
              {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">下级智能体</label>
            <select
              value={form.child_agent_id}
              onChange={(e) => setForm({ ...form, child_agent_id: e.target.value })}
              className="w-full bg-gray-800 rounded-lg px-4 py-2"
              required
            >
              <option value="">选择下级</option>
              {agents.filter((a) => a.id !== form.parent_agent_id).map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">关系类型</label>
            <select
              value={form.relation_type}
              onChange={(e) => setForm({ ...form, relation_type: e.target.value })}
              className="w-full bg-gray-800 rounded-lg px-4 py-2"
            >
              <option value="command">指挥</option>
              <option value="mentor">指导</option>
              <option value="collaborate">协作</option>
            </select>
          </div>
          <button type="submit" className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg">
            创建关系
          </button>
        </form>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-900 p-6 rounded-xl">
          <h3 className="text-lg font-semibold mb-4">选择智能体查看层级</h3>
          <select
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            className="w-full bg-gray-800 rounded-lg px-4 py-2 mb-4"
          >
            <option value="">选择智能体</option>
            {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>

          {selectedAgent && !tree && (
            <p className="text-gray-500">该智能体暂无层级关系</p>
          )}
        </div>

        <div className="bg-gray-900 p-6 rounded-xl">
          <h3 className="text-lg font-semibold mb-4">层级树</h3>
          {loading && selectedAgent ? (
            <div className="flex justify-center py-8"><LoadingSpinner /></div>
          ) : tree ? renderTree(tree) : <p className="text-gray-500">请选择智能体查看层级结构</p>}
        </div>
      </div>
    </div>
  );
}
