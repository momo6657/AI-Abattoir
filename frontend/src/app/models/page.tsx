"use client";

import { useEffect, useState } from "react";
import { modelsApi } from "@/lib/api";
import { ErrorBanner, LoadingSpinner, Badge } from "@/components";

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", provider: "openai", model_id: "", api_key: "" });
  const [editingId, setEditingId] = useState<string | null>(null);

  const loadModels = async () => {
    try {
      setLoading(true);
      const r = await modelsApi.list();
      setModels(r.data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadModels(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingId) {
        await modelsApi.update(editingId, form);
      } else {
        await modelsApi.create(form);
      }
      await loadModels();
      setShowForm(false);
      setEditingId(null);
      setForm({ name: "", provider: "openai", model_id: "", api_key: "" });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "操作失败");
    }
  };

  const handleEdit = (model: Model) => {
    setForm({ name: model.name, provider: model.provider, model_id: model.model_id, api_key: "" });
    setEditingId(model.id);
    setShowForm(true);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确定删除此模型？")) return;
    try {
      await modelsApi.delete(id);
      await loadModels();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "删除失败");
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold">模型管理</h2>
        <button
          onClick={() => { setShowForm(!showForm); setEditingId(null); setForm({ name: "", provider: "openai", model_id: "", api_key: "" }); }}
          className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg"
        >
          添加模型
        </button>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

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
            placeholder={editingId ? "留空则不更新 API Key" : "API Key"}
            type="password"
            value={form.api_key}
            onChange={(e) => setForm({ ...form, api_key: e.target.value })}
            className="w-full bg-gray-800 rounded-lg px-4 py-2"
          />
          <div className="flex gap-2">
            <button type="submit" className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg">
              {editingId ? "更新" : "保存"}
            </button>
            <button type="button" onClick={() => { setShowForm(false); setEditingId(null); }} className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg">
              取消
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : (
        <div className="grid gap-4">
          {models.map((model) => (
            <div key={model.id} className="bg-gray-900 p-4 rounded-xl flex justify-between items-center">
              <div>
                <h3 className="font-semibold">{model.name}</h3>
                <p className="text-sm text-gray-400">{model.provider} / {model.model_id}</p>
              </div>
              <div className="flex items-center gap-3">
                <Badge text={model.status} variant={model.status === "online" ? "success" : "default"} size="md" />
                <button onClick={() => handleEdit(model)} className="text-gray-400 hover:text-blue-400 text-sm">编辑</button>
                <button onClick={() => handleDelete(model.id)} className="text-gray-400 hover:text-red-400 text-sm">删除</button>
              </div>
            </div>
          ))}
          {models.length === 0 && (
            <div className="text-center text-gray-500 py-12">暂无模型，点击"添加模型"开始</div>
          )}
        </div>
      )}
    </div>
  );
}
