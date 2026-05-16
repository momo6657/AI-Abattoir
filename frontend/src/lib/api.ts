import axios from "axios";

const baseURL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export const api = axios.create({ baseURL });

// ---- Agents ----
export const agentsApi = {
  list: () => api.get("/agents"),
  create: (data: Record<string, unknown>) => api.post("/agents", data),
  get: (id: string) => api.get(`/agents/${id}`),
  update: (id: string, data: Record<string, unknown>) => api.put(`/agents/${id}`, data),
  delete: (id: string) => api.delete(`/agents/${id}`),
  getEvolution: (id: string) => api.get(`/agents/${id}/evolution`),
  getExperiences: (id: string) => api.get(`/agents/${id}/experiences`),
};

// ---- Conversations ----
export const conversationsApi = {
  list: () => api.get("/conversations"),
  create: (data: Record<string, unknown>) => api.post("/conversations", data),
  get: (id: string) => api.get(`/conversations/${id}`),
  start: (id: string) => api.post(`/conversations/${id}/start`),
  pause: (id: string) => api.post(`/conversations/${id}/pause`),
  resume: (id: string) => api.post(`/conversations/${id}/resume`),
  end: (id: string) => api.post(`/conversations/${id}/end`),
  sendMessage: (id: string, data: Record<string, unknown>) =>
    api.post(`/conversations/${id}/messages`, data),
  getMessages: (id: string) => api.get(`/conversations/${id}/messages`),
};

// ---- Arena ----
export const arenaApi = {
  createMatch: (data: Record<string, unknown>) => api.post("/arena/matches", data),
  getMatch: (id: string) => api.get(`/arena/matches/${id}`),
  listMatches: () => api.get("/arena/matches"),
  vote: (matchId: string, data: Record<string, unknown>) =>
    api.post(`/arena/matches/${matchId}/vote`, data),
  getResults: (matchId: string) => api.get(`/arena/matches/${matchId}/results`),
  start: (matchId: string) => api.post(`/arena/matches/${matchId}/start`),
  finish: (matchId: string) => api.post(`/arena/matches/${matchId}/finish`),
};

// ---- Games ----
export const gamesApi = {
  list: () => api.get("/games"),
  create: (data: Record<string, unknown>) => api.post("/games", data),
  get: (id: string) => api.get(`/games/${id}`),
  start: (id: string) => api.post(`/games/${id}/start`),
  processTurn: (id: string) => api.post(`/games/${id}/turn`),
  getState: (id: string) => api.get(`/games/${id}/state`),
  end: (id: string) => api.post(`/games/${id}/end`),
};

// ---- Hierarchy ----
export const hierarchyApi = {
  create: (data: Record<string, unknown>) => api.post("/hierarchy", data),
  getTree: (id: string) => api.get(`/hierarchy/${id}`),
};

// ---- Leaderboard ----
export const leaderboardApi = {
  getRankings: (category?: string) =>
    api.get("/leaderboard", { params: category ? { category } : {} }),
};

// ---- Search ----
export const searchApi = {
  search: (query: string, maxResults?: number) =>
    api.get("/search", { params: { query, max_results: maxResults } }),
  fetchUrl: (url: string) => api.get("/search/fetch", { params: { url } }),
};

// ---- Spectator ----
export const spectatorApi = {
  replayConversation: (id: string) => api.get(`/replay/conversations/${id}`),
  replayGame: (id: string) => api.get(`/replay/games/${id}`),
};

// ---- Models ----
export const modelsApi = {
  list: () => api.get("/models"),
  create: (data: Record<string, unknown>) => api.post("/models", data),
  get: (id: string) => api.get(`/models/${id}`),
  update: (id: string, data: Record<string, unknown>) => api.put(`/models/${id}`, data),
  delete: (id: string) => api.delete(`/models/${id}`),
};
