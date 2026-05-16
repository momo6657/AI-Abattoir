"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Model {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  is_active: boolean;
  status: string;
}

export default function ModelsPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", provider: "openai", model_id: "", api_key: "" });

  useEffect(() => {
    api.get("/models").then((r) => setModels(r.data));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post("/models", form);
    const r = await api.get("/models");
    setModels(r.data);
    setShowForm(false);
    setForm({ name: "", provider: "openai", model_id: "", api_key: "" });
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold">模型管理</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg"
        >
          添加模型
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-gray-900 p-6 rounded-xl mb-6 space-y-4">
          <input
            placeholder="模型名称"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full bg-gray-800 rounded-lg px-4 py-2"
            required
          />
          <select
            value={form.provider}
            onChange={(e) => setForm({ ...form, provider: e.target.value })}
            className="w-full bg-gray-800 rounded-lg px-4 py-2"
          >
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="google">Google</option>
            <option value="deepseek">DeepSeek</option>
          </select>
          <input
            placeholder="模型 ID (如 gpt-4o)"
            value={form.model_id}
            onChange={(e) => setForm({ ...form, model_id: e.target.value })}
            className="w-full bg-gray-800 rounded-lg px-4 py-2"
            required
          />
          <input
            placeholder="API Key"
            type="password"
            value={form.api_key}
            onChange={(e) => setForm({ ...form, api_key: e.target.value })}
            className="w-full bg-gray-800 rounded-lg px-4 py-2"
          />
          <button type="submit" className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg">
            保存
          </button>
        </form>
      )}

      <div className="grid gap-4">
        {models.map((model) => (
          <div key={model.id} className="bg-gray-900 p-4 rounded-xl flex justify-between items-center">
            <div>
              <h3 className="font-semibold">{model.name}</h3>
              <p className="text-sm text-gray-400">{model.provider} / {model.model_id}</p>
            </div>
            <span className={`px-3 py-1 rounded-full text-sm ${model.status === "online" ? "bg-green-900 text-green-300" : "bg-gray-800 text-gray-400"}`}>
              {model.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
