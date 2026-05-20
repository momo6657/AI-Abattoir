import axios from "axios";

const PRODUCTION_API = "https://backend-production-b399b.up.railway.app/api";
const LOCAL_API = "http://localhost:8000/api";

function resolveBaseURL(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (envUrl && envUrl.length > 0) return envUrl;
  if (typeof window !== "undefined") {
    return window.location.protocol === "https:" ? PRODUCTION_API : LOCAL_API;
  }
  return LOCAL_API;
}

const baseURL = resolveBaseURL();

const api = axios.create({ baseURL, timeout: 30000 });

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      console.warn("Unauthorized request");
    }
    return Promise.reject(error);
  }
);

// ---- Agents ---- (backend: /api/agents/ with slash, sub-routes without)
export const agentsApi = {
  list: () => api.get("/agents/"),
  create: (data: Record<string, unknown>) => api.post("/agents/", data),
  update: (id: string, data: Record<string, unknown>) => api.put(`/agents/${id}`, data),
  delete: (id: string) => api.delete(`/agents/${id}`),
  getEvolution: (id: string) => api.get(`/agents/${id}/evolution`),
  getExperiences: (id: string) => api.get(`/agents/${id}/experiences`),
};

// ---- Conversations ---- (backend: /api/conversations/ with slash, sub-routes without)
export const conversationsApi = {
  list: () => api.get("/conversations/"),
  create: (data: Record<string, unknown>) => api.post("/conversations/", data),
  get: (id: string) => api.get(`/conversations/${id}`),
  start: (id: string) => api.post(`/conversations/${id}/start`),
  pause: (id: string) => api.post(`/conversations/${id}/pause`),
  resume: (id: string) => api.post(`/conversations/${id}/resume`),
  end: (id: string) => api.post(`/conversations/${id}/end`),
  sendMessage: (id: string, data: Record<string, unknown>) =>
    api.post(`/conversations/${id}/messages`, data),
  getMessages: (id: string) => api.get(`/conversations/${id}/messages`),
};

// ---- Arena ---- (backend: /api/arena/matches without slash)
export const arenaApi = {
  createMatch: (data: Record<string, unknown>) => api.post("/arena/matches", data),
  getMatch: (id: string) => api.get(`/arena/matches/${id}`),
  listMatches: () => api.get("/arena/matches"),
  startMatch: (id: string) => api.post(`/arena/matches/${id}/start`),
  vote: (matchId: string, data: Record<string, unknown>) =>
    api.post(`/arena/matches/${matchId}/vote`, data),
};

// ---- Games ---- (backend: /api/games without slash)
export const gamesApi = {
  list: () => api.get("/games"),
  create: (data: Record<string, unknown>) => api.post("/games", data),
  get: (id: string) => api.get(`/games/${id}`),
  start: (id: string) => api.post(`/games/${id}/start`),
  processTurn: (id: string) => api.post(`/games/${id}/turn`),
  getState: (id: string) => api.get(`/games/${id}/state`),
  end: (id: string) => api.post(`/games/${id}/end`),
};

// ---- Hierarchy ---- (backend: /api/hierarchy without slash)
export const hierarchyApi = {
  create: (data: Record<string, unknown>) => api.post("/hierarchy", data),
  getTree: (id: string) => api.get(`/hierarchy/${id}`),
};

// ---- Leaderboard ---- (backend: /api/leaderboard/ with slash)
export const leaderboardApi = {
  getRankings: (category?: string) =>
    api.get("/leaderboard/", { params: category ? { category } : {} }),
};

// ---- Search ---- (backend: /api/search/ with slash, /api/search/fetch without)
export const searchApi = {
  search: (query: string, maxResults?: number) =>
    api.get("/search/", { params: { query, max_results: maxResults } }),
  fetchUrl: (url: string) => api.get("/search/fetch", { params: { url } }),
};

// ---- Spectator ----
export const spectatorApi = {
  replayConversation: (id: string) => api.get(`/replay/conversations/${id}`),
  replayGame: (id: string) => api.get(`/replay/games/${id}`),
};

// ---- Models ---- (backend: /api/models/ with slash)
export const modelsApi = {
  list: () => api.get("/models/"),
  create: (data: Record<string, unknown>) => api.post("/models/", data),
  update: (id: string, data: Record<string, unknown>) => api.put(`/models/${id}`, data),
  delete: (id: string) => api.delete(`/models/${id}`),
};
