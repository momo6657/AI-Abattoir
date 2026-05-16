"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Conversation {
  id: string;
  title: string;
  mode: string;
  status: string;
  created_at: string;
}

export default function ConversationsPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);

  useEffect(() => {
    api.get("/conversations").then((r) => setConversations(r.data));
  }, []);

  const createConversation = async () => {
    const title = prompt("对话标题");
    if (!title) return;
    await api.post("/conversations", { title, mode: "free" });
    const r = await api.get("/conversations");
    setConversations(r.data);
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold">对话</h2>
        <button onClick={createConversation} className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg">
          新建对话
        </button>
      </div>

      <div className="grid gap-4">
        {conversations.map((conv) => (
          <div key={conv.id} className="bg-gray-900 p-4 rounded-xl flex justify-between items-center">
            <div>
              <h3 className="font-semibold">{conv.title || "未命名对话"}</h3>
              <p className="text-sm text-gray-400">模式: {conv.mode}</p>
            </div>
            <span className={`px-3 py-1 rounded-full text-sm ${conv.status === "active" ? "bg-green-900 text-green-300" : "bg-gray-800 text-gray-400"}`}>
              {conv.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
