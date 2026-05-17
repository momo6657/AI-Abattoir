"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { conversationsApi, agentsApi } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";
import { ErrorBanner, LoadingSpinner } from "@/components";

// ---- Types ----
interface Agent {
  id: string;
  name: string;
  avatar_url?: string;
}

interface Conversation {
  id: string;
  title: string;
  mode: string;
  status: string;
  agent_ids: string[];
  created_at: string;
}

interface Message {
  id: string;
  conversation_id: string;
  agent_id?: string;
  agent_name?: string;
  role: "agent" | "user" | "system";
  content: string | Record<string, unknown>;
  content_type: "text" | "image" | "audio";
  image_url?: string;
  audio_url?: string;
  created_at: string;
}

const MODES = [
  { value: "free", label: "自由对话", desc: "智能体自由交流" },
  { value: "debate", label: "辩论", desc: "正反方结构化辩论" },
  { value: "relay", label: "接力", desc: "轮流接力创作" },
  { value: "interview", label: "采访", desc: "一问一答式对话" },
];

const AVATAR_COLORS = [
  "bg-blue-600", "bg-purple-600", "bg-green-600",
  "bg-red-600", "bg-yellow-600", "bg-pink-600",
  "bg-indigo-600", "bg-teal-600",
];

function getAgentColor(agentId: string, agents: Agent[]): string {
  const idx = agents.findIndex((a) => a.id === agentId);
  return AVATAR_COLORS[Math.max(0, idx) % AVATAR_COLORS.length];
}

function getAgentName(agentId: string, agents: Agent[]): string {
  const agent = agents.find((a) => a.id === agentId);
  return agent ? agent.name : "未知";
}

function getAvatarLetter(name: string): string {
  return name.charAt(0).toUpperCase();
}

function formatTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

// ---- Page Component ----
export default function ConversationsPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newMode, setNewMode] = useState("free");
  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>([]);
  const [inputText, setInputText] = useState("");
  const [convStatus, setConvStatus] = useState<string>("idle");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // WebSocket real-time connection
  const {
    messages: wsMessages,
    setMessages: setWsMessages,
    thinkingAgent,
    connected: wsConnected,
  } = useWebSocket(selectedConvId);

  const loadConversations = useCallback(async () => {
    try {
      setLoading(true);
      const r = await conversationsApi.list();
      setConversations(r.data);
      setError(null);
    } catch {
      setError("无法加载对话列表，请检查后端服务是否运行");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAgents = useCallback(async () => {
    try {
      const r = await agentsApi.list();
      setAgents(r.data);
    } catch {
      // Agent list failure is non-critical
    }
  }, []);

  useEffect(() => {
    loadConversations();
    loadAgents();
  }, [loadConversations, loadAgents]);

  const loadMessages = useCallback(async (convId: string) => {
    try {
      const r = await conversationsApi.getMessages(convId);
      setMessages(r.data);
    } catch {
      setMessages([]);
      setError("无法加载消息，请检查后端服务是否运行");
    }
  }, []);

  useEffect(() => {
    if (selectedConvId) {
      loadMessages(selectedConvId);
      setWsMessages([]); // clear WS messages when switching conversations
      const conv = conversations.find((c) => c.id === selectedConvId);
      if (conv) setConvStatus(conv.status);
    }
  }, [selectedConvId, loadMessages, conversations, setWsMessages]);

  // Merge REST-loaded messages with real-time WS messages (deduplicate by id)
  const allMessages = useMemo(() => {
    const seen = new Set<string>();
    const merged: Message[] = [];
    for (const msg of messages) {
      if (msg.id && !seen.has(msg.id)) {
        seen.add(msg.id);
        merged.push(msg);
      }
    }
    for (const msg of wsMessages) {
      const id = msg.id as string | undefined;
      if (id && !seen.has(id)) {
        seen.add(id);
        // WS messages have a subset of Message fields; fill defaults for missing fields
        merged.push({
          id,
          conversation_id: selectedConvId || "",
          agent_id: msg.agent_id as string | undefined,
          agent_name: msg.agent_name as string | undefined,
          role: "agent" as const,
          content: (msg.content as string | Record<string, unknown>) || "",
          content_type: "text" as const,
          created_at: (msg.created_at as string) || new Date().toISOString(),
        });
      }
    }
    return merged;
  }, [messages, wsMessages, selectedConvId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [allMessages]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || selectedAgentIds.length === 0) return;
    try {
      await conversationsApi.create({
        title: newTitle,
        mode: newMode,
        agent_ids: selectedAgentIds,
      });
      await loadConversations();
      setShowCreateForm(false);
      setNewTitle("");
      setNewMode("free");
      setSelectedAgentIds([]);
    } catch {
      setError("创建失败");
    }
  };

  const handleStart = async () => {
    if (!selectedConvId) return;
    try {
      await conversationsApi.start(selectedConvId);
      setConvStatus("active");
    } catch {
      setError("启动失败");
    }
  };

  const handlePause = async () => {
    if (!selectedConvId) return;
    try {
      await conversationsApi.pause(selectedConvId);
      setConvStatus("paused");
    } catch {
      setError("暂停失败");
    }
  };

  const handleResume = async () => {
    if (!selectedConvId) return;
    try {
      await conversationsApi.resume(selectedConvId);
      setConvStatus("active");
    } catch {
      setError("继续失败");
    }
  };

  const handleEnd = async () => {
    if (!selectedConvId) return;
    try {
      await conversationsApi.end(selectedConvId);
      setConvStatus("ended");
    } catch {
      setError("结束失败");
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedConvId || !inputText.trim()) return;
    try {
      await conversationsApi.sendMessage(selectedConvId, {
        content: inputText,
        role: "user",
        content_type: "text",
      });
      setInputText("");
      // Thinking state now comes from WebSocket (agent_thinking events)
    } catch {
      setError("发送失败");
    }
  };

  const toggleAgent = (id: string) => {
    setSelectedAgentIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const selectedConv = conversations.find((c) => c.id === selectedConvId);

  return (
    <div className="flex gap-4" style={{ height: "calc(100vh - 180px)" }}>
      {/* Error Banner */}
      {error && (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-40 shadow-lg">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
        </div>
      )}

      {/* Left Sidebar - Conversation List */}
      <div className="w-80 flex-shrink-0 flex flex-col">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">对话</h2>
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded-lg text-sm"
          >
            {showCreateForm ? "取消" : "新建"}
          </button>
        </div>

        {/* Create Form */}
        {showCreateForm && (
          <form onSubmit={handleCreate} className="bg-gray-900 p-4 rounded-xl mb-4 space-y-3">
            <input
              placeholder="对话标题"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="w-full bg-gray-800 rounded-lg px-3 py-2 text-sm"
              required
            />
            <select
              value={newMode}
              onChange={(e) => setNewMode(e.target.value)}
              className="w-full bg-gray-800 rounded-lg px-3 py-2 text-sm"
            >
              {MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label} - {m.desc}
                </option>
              ))}
            </select>
            <div>
              <p className="text-xs text-gray-400 mb-2">选择参与智能体：</p>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {agents.map((a) => (
                  <label key={a.id} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedAgentIds.includes(a.id)}
                      onChange={() => toggleAgent(a.id)}
                      className="rounded bg-gray-800"
                    />
                    {a.name}
                  </label>
                ))}
              </div>
            </div>
            <button
              type="submit"
              className="w-full bg-green-600 hover:bg-green-700 px-3 py-2 rounded-lg text-sm"
            >
              创建对话
            </button>
          </form>
        )}

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto space-y-2">
          {loading ? (
            <div className="flex justify-center py-8"><LoadingSpinner /></div>
          ) : conversations.length === 0 ? (
            <p className="text-center text-gray-500 text-sm py-8">暂无对话</p>
          ) : (
          <>
          {conversations.map((conv) => (
            <button
              key={conv.id}
              onClick={() => setSelectedConvId(conv.id)}
              className={`w-full text-left p-3 rounded-lg transition-colors ${
                selectedConvId === conv.id
                  ? "bg-blue-900/50 border border-blue-600"
                  : "bg-gray-900 hover:bg-gray-800"
              }`}
            >
              <div className="flex justify-between items-start">
                <h3 className="font-medium text-sm truncate">{conv.title || "未命名对话"}</h3>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ml-2 ${
                    conv.status === "active"
                      ? "bg-green-900 text-green-300"
                      : conv.status === "paused"
                      ? "bg-yellow-900 text-yellow-300"
                      : "bg-gray-800 text-gray-400"
                  }`}
                >
                  {conv.status === "active" ? "进行中" : conv.status === "paused" ? "已暂停" : conv.status === "ended" ? "已结束" : conv.status}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {MODES.find((m) => m.value === conv.mode)?.label || conv.mode}
                {" · "}
                {conv.agent_ids?.length || 0} 个智能体
              </p>
            </button>
          ))}
          </>
          )}
        </div>
      </div>

      {/* Right - Chat Area */}
      <div className="flex-1 flex flex-col bg-gray-900 rounded-xl overflow-hidden">
        {selectedConvId ? (
          <>
            {/* Chat Header */}
            <div className="border-b border-gray-800 px-4 py-3 flex justify-between items-center">
              <div>
                <h3 className="font-semibold flex items-center gap-2">
                  {selectedConv?.title || "对话"}
                  <span
                    className={`w-2 h-2 rounded-full inline-block ${
                      wsConnected ? "bg-green-500" : "bg-gray-500"
                    }`}
                    title={wsConnected ? "实时连接已建立" : "未连接"}
                  />
                </h3>
                <p className="text-xs text-gray-400">
                  {MODES.find((m) => m.value === selectedConv?.mode)?.label}
                  {selectedConv?.agent_ids && (
                    <span> · {selectedConv.agent_ids.map((id) => getAgentName(id, agents)).join(", ")}</span>
                  )}
                </p>
              </div>
              <div className="flex gap-2">
                {convStatus === "idle" && (
                  <button
                    onClick={handleStart}
                    className="bg-green-600 hover:bg-green-700 px-3 py-1.5 rounded-lg text-xs"
                  >
                    开始
                  </button>
                )}
                {convStatus === "active" && (
                  <button
                    onClick={handlePause}
                    className="bg-yellow-600 hover:bg-yellow-700 px-3 py-1.5 rounded-lg text-xs"
                  >
                    暂停
                  </button>
                )}
                {convStatus === "paused" && (
                  <button
                    onClick={handleResume}
                    className="bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded-lg text-xs"
                  >
                    继续
                  </button>
                )}
                {(convStatus === "active" || convStatus === "paused") && (
                  <button
                    onClick={handleEnd}
                    className="bg-red-600 hover:bg-red-700 px-3 py-1.5 rounded-lg text-xs"
                  >
                    结束
                  </button>
                )}
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {allMessages.map((msg) => {
                const isUser = msg.role === "user";
                const isSystem = msg.role === "system";
                const agentName = msg.agent_name || (msg.agent_id ? getAgentName(msg.agent_id, agents) : "用户");
                const agentColor = msg.agent_id ? getAgentColor(msg.agent_id, agents) : "bg-gray-600";

                const displayContent = typeof msg.content === 'string'
                  ? msg.content
                  : (msg.content as Record<string, unknown>)?.text
                    ? String((msg.content as Record<string, unknown>).text)
                    : JSON.stringify(msg.content);

                if (isSystem) {
                  return (
                    <div key={msg.id} className="text-center">
                      <span className="text-xs text-gray-500 bg-gray-800 px-3 py-1 rounded-full">
                        {displayContent}
                      </span>
                    </div>
                  );
                }

                return (
                  <div
                    key={msg.id}
                    className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}
                  >
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0 ${agentColor}`}
                    >
                      {isUser ? "U" : getAvatarLetter(agentName)}
                    </div>
                    <div className={`max-w-[70%] ${isUser ? "items-end" : "items-start"} flex flex-col`}>
                      <span className="text-xs text-gray-400 mb-1">
                        {agentName} · {formatTime(msg.created_at)}
                      </span>
                      <div
                        className={`rounded-xl px-4 py-2.5 text-sm ${
                          isUser ? "bg-blue-600 text-white" : "bg-gray-800"
                        }`}
                      >
                        {(!msg.content_type || msg.content_type === "text") && <p className="whitespace-pre-wrap">{displayContent}</p>}
                        {msg.content_type === "image" && msg.image_url && (
                          <div>
                            <img
                              src={msg.image_url}
                              alt="shared image"
                              className="rounded-lg max-w-full max-h-64 object-contain"
                            />
                            {msg.content && <p className="mt-2 text-sm">{displayContent}</p>}
                          </div>
                        )}
                        {msg.content_type === "audio" && msg.audio_url && (
                          <div>
                            <audio controls className="max-w-full">
                              <source src={msg.audio_url} />
                            </audio>
                            {msg.content && <p className="mt-2 text-sm">{displayContent}</p>}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* Thinking Indicator */}
              {thinkingAgent && (
                <div className="flex gap-3">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0 ${getAgentColor(thinkingAgent, agents)}`}
                  >
                    {getAvatarLetter(getAgentName(thinkingAgent, agents))}
                  </div>
                  <div>
                    <span className="text-xs text-gray-400 mb-1 block">
                      {getAgentName(thinkingAgent, agents)} 正在思考...
                    </span>
                    <div className="bg-gray-800 rounded-xl px-4 py-2.5 inline-flex gap-1">
                      <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <form onSubmit={handleSendMessage} className="border-t border-gray-800 p-3 flex gap-2">
              <input
                type="text"
                placeholder="输入消息..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                className="flex-1 bg-gray-800 rounded-lg px-4 py-2 text-sm"
              />
              <button
                type="submit"
                className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg text-sm"
              >
                发送
              </button>
            </form>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            <div className="text-center">
              <p className="text-lg mb-2">选择一个对话开始</p>
              <p className="text-sm">或创建新的对话</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
