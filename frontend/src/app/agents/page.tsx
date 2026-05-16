"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Agent {
  id: string;
  name: string;
  description: string;
  model_id: string;
  level: string;
  experience_points: number;
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", model_id: "" });

  useEffect(() => {
    api.get("/agents").then((r) => setAgents(r.data));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/agents", form);
    const r = await api.get("/agents");
    setAgents(r.data);
    setShowForm(false);
    setForm({ name: "", description: "", model_id: "" });
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold">智能体管理</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg"
        >
          创建智能体
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-gray-900 p-6 rounded-xl mb-6 space-y-4">
          <input
            placeholder="智能体名称"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full bg-gray-800 rounded-lg px-4 py-2"
            required
          />
          <textarea
            placeholder="描述 / 人设"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="w-full bg-gray-800 rounded-lg px-4 py-2 h-24"
          />
          <input
            placeholder="绑定的模型 ID"
            value={form.model_id}
            onChange={(e) => setForm({ ...form, model_id: e.target.value })}
            className="w-full bg-gray-800 rounded-lg px-4 py-2"
            required
          />
          <button type="submit" className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg">
            创建
          </button>
        </form>
      )}

      <div className="grid gap-4">
        {agents.map((agent) => (
          <div key={agent.id} className="bg-gray-900 p-4 rounded-xl flex justify-between items-center">
            <div>
              <h3 className="font-semibold">{agent.name}</h3>
              <p className="text-sm text-gray-400">{agent.description || "暂无描述"}</p>
            </div>
            <div className="text-right">
              <span className="text-sm text-yellow-400">{agent.level}</span>
              <p className="text-xs text-gray-500">XP: {agent.experience_points}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
