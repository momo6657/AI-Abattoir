"use client";

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { conversationsApi, agentsApi } from "@/lib/api";
import { extractErrorMessage } from "@/lib/errors";
import { useWebSocket } from "@/hooks/useWebSocket";
import { ErrorBanner, LoadingSpinner, ThinkingIndicator, ChatMessage } from "@/components";

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

function getAgentName(agentId: string, agents: Agent[]): string {
  const agent = agents.find((a) => a.id === agentId);
  return agent ? agent.name : "未知";
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
  const [errorRetryFn, setErrorRetryFn] = useState<(() => void) | null>(null);
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
      setErrorRetryFn(null);
    } catch (err) {
      setError(extractErrorMessage(err, "无法加载对话列表，请检查后端服务是否运行"));
      setErrorRetryFn(() => loadConversations);
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
    } catch (err) {
      setMessages([]);
      setError(extractErrorMessage(err, "无法加载消息，请检查后端服务是否运行"));
      setErrorRetryFn(() => () => loadMessages(convId));
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
    } catch (err) {
      setError(extractErrorMessage(err, "创建对话失败"));
    }
  };

  const handleStart = async () => {
    if (!selectedConvId) return;
    try {
      await conversationsApi.start(selectedConvId);
      setConvStatus("active");
    } catch (err) {
      setError(extractErrorMessage(err, "启动对话失败"));
    }
  };

  const handlePause = async () => {
    if (!selectedConvId) return;
    try {
      await conversationsApi.pause(selectedConvId);
      setConvStatus("paused");
    } catch (err) {
      setError(extractErrorMessage(err, "暂停对话失败"));
    }
  };

  const handleResume = async () => {
    if (!selectedConvId) return;
    try {
      await conversationsApi.resume(selectedConvId);
      setConvStatus("active");
    } catch (err) {
      setError(extractErrorMessage(err, "继续对话失败"));
    }
  };

  const handleEnd = async () => {
    if (!selectedConvId) return;
    try {
      await conversationsApi.end(selectedConvId);
      setConvStatus("ended");
    } catch (err) {
      setError(extractErrorMessage(err, "结束对话失败"));
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedConvId || !inputText.trim()) return;
    const messageText = inputText;
    setInputText("");
    try {
      await conversationsApi.sendMessage(selectedConvId, {
        content: messageText,
        role: "user",
        content_type: "text",
      });
    } catch (err) {
      setInputText(messageText);
      setError(extractErrorMessage(err, "发送消息失败，请重试"));
    }
  };

  const toggleAgent = (id: string) => {
    setSelectedAgentIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const selectedConv = conversations.find((c) => c.id === selectedConvId);

  return (
    <div className="flex gap-4 animate-fade-in" style={{ height: "calc(100vh - 180px)" }}>
      {/* Error Banner */}
      {error && (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-40 shadow-lg">
          <ErrorBanner
            message={error}
            onDismiss={() => { setError(null); setErrorRetryFn(null); }}
            onRetry={errorRetryFn || undefined}
          />
        </div>
      )}

      {/* Left Sidebar - Conversation List */}
      <div className="w-80 flex-shrink-0 flex flex-col">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold gradient-text">对话</h2>
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className={showCreateForm ? "btn-ghost text-sm" : "btn-primary text-sm px-3 py-1.5"}
          >
            {showCreateForm ? "取消" : "新建"}
          </button>
        </div>

        {/* Create Form */}
        {showCreateForm && (
          <form onSubmit={handleCreate} className="card p-4 mb-4 space-y-3 animate-slide-up">
            <input
              placeholder="对话标题"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="input-field"
              required
            />
            <select
              value={newMode}
              onChange={(e) => setNewMode(e.target.value)}
              className="input-field"
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
                  <label key={a.id} className="flex items-center gap-2 text-sm cursor-pointer hover:text-white transition-colors">
                    <input
                      type="checkbox"
                      checked={selectedAgentIds.includes(a.id)}
                      onChange={() => toggleAgent(a.id)}
                      className="rounded bg-surface-overlay border-border accent-accent"
                    />
                    {a.name}
                  </label>
                ))}
              </div>
            </div>
            <button
              type="submit"
              className="btn-primary w-full text-sm"
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
              className={`w-full text-left p-3 rounded-xl transition-all duration-200 ${
                selectedConvId === conv.id
                  ? "bg-accent/10 border border-accent/50 shadow-md shadow-accent/5"
                  : "card-hover"
              }`}
            >
              <div className="flex justify-between items-start">
                <h3 className="font-medium text-sm truncate">{conv.title || "未命名对话"}</h3>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ml-2 ${
                    conv.status === "active"
                      ? "bg-green-500/10 text-green-400 border border-green-500/20"
                      : conv.status === "paused"
                      ? "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20"
                      : "bg-surface-overlay text-gray-400 border border-border"
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
      <div className="flex-1 flex flex-col card overflow-hidden">
        {selectedConvId ? (
          <>
            {/* Chat Header */}
            <div className="border-b border-border px-5 py-3 flex justify-between items-center bg-surface-overlay/50">
              <div>
                <h3 className="font-semibold flex items-center gap-2">
                  {selectedConv?.title || "对话"}
                  <span
                    className={`w-2 h-2 rounded-full inline-block ${
                      wsConnected ? "bg-green-500 animate-pulse-slow" : "bg-gray-500"
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
                  <button onClick={handleStart} className="btn-primary text-xs px-3 py-1.5">
                    开始
                  </button>
                )}
                {convStatus === "active" && (
                  <button onClick={handlePause} className="btn-secondary text-xs px-3 py-1.5 !bg-yellow-500/10 !text-yellow-400 !border-yellow-500/30 hover:!bg-yellow-500/20">
                    暂停
                  </button>
                )}
                {convStatus === "paused" && (
                  <button onClick={handleResume} className="btn-primary text-xs px-3 py-1.5">
                    继续
                  </button>
                )}
                {(convStatus === "active" || convStatus === "paused") && (
                  <button onClick={handleEnd} className="btn-secondary text-xs px-3 py-1.5 !bg-red-500/10 !text-red-400 !border-red-500/30 hover:!bg-red-500/20">
                    结束
                  </button>
                )}
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {allMessages.length === 0 && (
                <div className="flex items-center justify-center h-full text-gray-600 text-sm">
                  对话尚无消息，发送第一条消息开始吧
                </div>
              )}
              {allMessages.map((msg) => {
                const isUser = msg.role === "user";
                const isSystem = msg.role === "system";
                const agentName = msg.agent_name || (msg.agent_id ? getAgentName(msg.agent_id, agents) : "用户");
                const agentIdx = msg.agent_id ? agents.findIndex((a) => a.id === msg.agent_id) : -1;

                return (
                  <ChatMessage
                    key={msg.id}
                    agentName={agentName}
                    content={msg.content}
                    contentType={msg.content_type}
                    imageUrl={msg.image_url}
                    audioUrl={msg.audio_url}
                    createdAt={msg.created_at}
                    agentIndex={agentIdx >= 0 ? agentIdx : 0}
                    isSystem={isSystem}
                    isUser={isUser}
                  />
                );
              })}

              {/* Thinking Indicator */}
              {thinkingAgent && (
                <ThinkingIndicator
                  agentName={getAgentName(thinkingAgent, agents)}
                  showAvatar
                  agentIndex={agents.findIndex((a) => a.id === thinkingAgent)}
                />
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <form onSubmit={handleSendMessage} className="border-t border-border p-4 flex gap-3 bg-surface-overlay/30">
              <input
                type="text"
                placeholder="输入消息..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                className="input-field flex-1"
              />
              <button
                type="submit"
                className="btn-primary text-sm px-5"
              >
                发送
              </button>
            </form>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-surface-overlay border border-border flex items-center justify-center">
                <svg className="w-8 h-8 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <p className="text-lg mb-1 font-medium">选择一个对话开始</p>
              <p className="text-sm text-gray-600">或创建新的对话</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
