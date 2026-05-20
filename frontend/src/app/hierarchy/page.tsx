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
    <div key={node.agent_id} style={{ marginLeft: depth * 28 }}>
      <div className="flex items-center gap-2 py-2.5 px-3 hover:bg-surface-overlay rounded-xl transition-colors group">
        {depth > 0 && <span className="text-gray-600 font-mono">├─</span>}
        <div className="w-7 h-7 rounded-lg bg-accent/10 flex items-center justify-center text-xs font-bold text-accent-hover">
          {node.agent_name.charAt(0)}
        </div>
        <span className="font-medium group-hover:text-white transition-colors">{node.agent_name}</span>
        <span className="text-xs text-gray-600">({node.agent_id.slice(0, 8)})</span>
      </div>
      {node.subordinates.map((child) => renderTree(child, depth + 1))}
    </div>
  );

  return (
    <div className="animate-fade-in">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h2 className="text-2xl font-bold">层级指挥系统</h2>
          <p className="text-sm text-gray-400 mt-1">管理智能体之间的上下级关系</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="btn-primary"
        >
          创建层级关系
        </button>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {showForm && (
        <form onSubmit={handleCreate} className="card p-6 mb-6 space-y-4 animate-slide-up">
          <h3 className="font-semibold">创建层级关系</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">上级智能体</label>
              <select
                value={form.parent_agent_id}
                onChange={(e) => setForm({ ...form, parent_agent_id: e.target.value })}
                className="input-field"
                required
              >
                <option value="">选择上级</option>
                {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">下级智能体</label>
              <select
                value={form.child_agent_id}
                onChange={(e) => setForm({ ...form, child_agent_id: e.target.value })}
                className="input-field"
                required
              >
                <option value="">选择下级</option>
                {agents.filter((a) => a.id !== form.parent_agent_id).map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">关系类型</label>
              <select
                value={form.relation_type}
                onChange={(e) => setForm({ ...form, relation_type: e.target.value })}
                className="input-field"
              >
                <option value="command">指挥</option>
                <option value="mentor">指导</option>
                <option value="collaborate">协作</option>
              </select>
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button type="submit" className="btn-primary">创建关系</button>
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">取消</button>
          </div>
        </form>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4">选择智能体查看层级</h3>
          <select
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            className="input-field mb-4"
          >
            <option value="">选择智能体</option>
            {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>

          {selectedAgent && !tree && !loading && (
            <div className="text-center py-8">
              <p className="text-gray-500">该智能体暂无层级关系</p>
            </div>
          )}
        </div>

        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4">层级树</h3>
          {loading && selectedAgent ? (
            <div className="flex justify-center py-8"><LoadingSpinner /></div>
          ) : tree ? (
            <div className="animate-slide-up">{renderTree(tree)}</div>
          ) : (
            <div className="text-center py-12">
              <div className="w-12 h-12 rounded-xl bg-surface-overlay flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                </svg>
              </div>
              <p className="text-gray-500 text-sm">请选择智能体查看层级结构</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
