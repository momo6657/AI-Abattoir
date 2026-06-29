import axios from "axios";

const PRODUCTION_API = "https://backend-production-b399b.up.railway.app/api";
const LOCAL_API = "http://localhost:8000/api";
const PROXY_API = "/api/backend/api";

function resolveBaseURL(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined") {
    const localHostnames = new Set(["localhost", "127.0.0.1", "::1"]);
    const isLocalFrontend = localHostnames.has(window.location.hostname);
    if (isLocalFrontend) {
      if (envUrl?.includes("localhost") || envUrl?.includes("127.0.0.1")) return envUrl;
      if (envUrl && envUrl.length > 0) return PROXY_API;
      return LOCAL_API;
    }
    if (envUrl && envUrl.length > 0) return PROXY_API;
    return window.location.protocol === "https:" ? PRODUCTION_API : LOCAL_API;
  }
  if (envUrl && envUrl.length > 0) return envUrl;
  return LOCAL_API;
}

const baseURL = resolveBaseURL();
const appRootURL = baseURL.replace(/\/api\/?$/, "");

export const apiBaseURL = baseURL;
export const apiRootURL = appRootURL;

export function resolveWebSocketURL(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (typeof window === "undefined") {
    return `ws://localhost:8000${normalizedPath}`;
  }

  const root = new URL(appRootURL || "/", window.location.href);
  root.protocol = root.protocol === "https:" ? "wss:" : "ws:";
  return `${root.origin}${normalizedPath}`;
}

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

// ---- Games ---- (backend: /api/games with new endpoints)
export const gamesApi = {
  list: () => api.get("/games"),
  create: (data: Record<string, unknown>) => api.post("/games", data),
  get: (id: string) => api.get(`/games/${id}`),
  start: (id: string) => api.post(`/games/${id}/start`),
  pause: (id: string) => api.post(`/games/${id}/pause`),
  resume: (id: string) => api.post(`/games/${id}/resume`),
  processTurn: (id: string) => api.post(`/games/${id}/turn`),
  getState: (id: string) => api.get(`/games/${id}/state`),
  end: (id: string, winnerId?: string) =>
    api.post(`/games/${id}/end`, winnerId ? { winner_id: winnerId } : {}),
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
  replayArena: (id: string) => api.get(`/replay/arena/${id}`),
};

// ---- Models ---- (backend: /api/models/ with slash)
export const modelsApi = {
  list: () => api.get("/models/"),
  create: (data: Record<string, unknown>) => api.post("/models/", data),
  discover: (data: Record<string, unknown>) => api.post("/models/discover", data),
  update: (id: string, data: Record<string, unknown>) => api.put(`/models/${id}`, data),
  delete: (id: string) => api.delete(`/models/${id}`),
};

// ---- Pokemon ----
export const pokemonApi = {
  init: () => api.post("/pokemon/init"),
  dashboard: (username = "PokemonBot") =>
    api.get("/pokemon/dashboard", { params: { username } }),
  listFormats: () => api.get("/pokemon/formats"),
  getFormatStrategy: (formatId: string) => api.get(`/pokemon/formats/${formatId}/strategy`),
  getFormatLeads: (formatId: string) => api.get(`/pokemon/formats/${formatId}/leads`),
  getFormatThreats: (formatId: string) => api.get(`/pokemon/formats/${formatId}/threats`),
  listSpecies: () => api.get("/pokemon/species"),
  listMoves: () => api.get("/pokemon/moves"),
  listTeams: (agentId: string) => api.get("/pokemon/teams", { params: { agent_id: agentId } }),
  buildTeam: (agentId: string, battleFormat = "vgc2024") =>
    api.post("/pokemon/teams/build", null, {
      params: { agent_id: agentId, battle_format: battleFormat },
    }),
  createBattle: (data: Record<string, unknown>) => api.post("/pokemon/battles", data),
  getBattle: (id: string) => api.get(`/pokemon/battles/${id}`),
  getBattleState: (id: string) => api.get(`/pokemon/battles/${id}/state`),
  submitTurn: (id: string, data: Record<string, unknown>) =>
    api.post(`/pokemon/battles/${id}/turn`, data),
  analyzeBattle: (id: string) => api.get(`/pokemon/battles/${id}/analysis`),
  finalizeBattle: (id: string, winnerAgentId?: string) =>
    api.post(
      `/pokemon/battles/${id}/finalize`,
      null,
      winnerAgentId ? { params: { winner_agent_id: winnerAgentId } } : undefined
    ),
  getHistory: (limit = 10, agentId?: string) =>
    api.get("/pokemon/battles/history", {
      params: agentId ? { limit, agent_id: agentId } : { limit },
    }),
  getBattleReplays: (agentId?: string, limit = 10) =>
    api.get("/pokemon/battles/replays", {
      params: agentId ? { agent_id: agentId, limit } : { limit },
    }),
  getBattleReplay: (battleId: string) =>
    api.get(`/pokemon/battles/${battleId}/replay`),
  knowledgeSearch: (queryType: string, queryKey: string, maxResults = 5, battleFormat?: string) =>
    api.get("/pokemon/knowledge/search", {
      params: {
        query_type: queryType,
        query_key: queryKey,
        max_results: maxResults,
        ...(battleFormat ? { battle_format: battleFormat } : {}),
      },
    }),
  teamKnowledge: (species: string[], queryType = "species_usage", maxResults = 3) =>
    api.post("/pokemon/knowledge/team", { species, query_type: queryType, max_results: maxResults }),
  parseShowdown: (payload: string) => api.post("/pokemon/showdown/parse", { payload }),
  buildShowdownCommands: (data: Record<string, unknown>) => api.post("/pokemon/showdown/commands", data),
  planShowdownDecision: (data: Record<string, unknown>) => api.post("/pokemon/showdown/decision", data),
  listShowdownLearningProfiles: () => api.get("/pokemon/showdown/learning/profiles"),
  getShowdownLearningProfile: (username: string, battleFormat = "vgc2024") =>
    api.get("/pokemon/showdown/learning/profile", { params: { username, battle_format: battleFormat } }),
  listShowdownMastery: (battleFormat?: string, limit = 5) =>
    api.get("/pokemon/showdown/learning/mastery", {
      params: battleFormat ? { battle_format: battleFormat, limit } : { limit },
    }),
  listPokemonLeaderboard: (battleFormat?: string, limit = 20) =>
    api.get("/pokemon/leaderboard", {
      params: battleFormat ? { battle_format: battleFormat, limit } : { limit },
    }),
  getAgentPokemonRating: (agentId: string) =>
    api.get(`/pokemon/agent/${agentId}/rating`),
  getAgentPokemonStats: (agentId: string) =>
    api.get(`/pokemon/agent/${agentId}/stats`),
  getGlobalPokemonStats: () =>
    api.get("/pokemon/stats/global"),
  getFormatPokemonStats: (battleFormat: string) =>
    api.get(`/pokemon/stats/format/${battleFormat}`),
  getSpeciesUsageStats: (battleFormat?: string, limit = 20) =>
    api.get("/pokemon/stats/species", {
      params: battleFormat ? { battle_format: battleFormat, limit } : { limit },
    }),
  getSpeciesPerformance: (speciesName: string) =>
    api.get(`/pokemon/stats/species/${encodeURIComponent(speciesName)}`),
  analyzeTeam: (teamId: string) =>
    api.get(`/pokemon/teams/${teamId}/analysis`),
  comprehensiveTeamAnalysis: (teamId: string) =>
    api.get(`/pokemon/teams/${teamId}/comprehensive-analysis`),
  predictBattle: (player1AgentId: string, player2AgentId: string, player1TeamId?: string, player2TeamId?: string) =>
    api.post("/pokemon/battles/predict", null, {
      params: {
        player1_agent_id: player1AgentId,
        player2_agent_id: player2AgentId,
        ...(player1TeamId ? { player1_team_id: player1TeamId } : {}),
        ...(player2TeamId ? { player2_team_id: player2TeamId } : {}),
      },
    }),
  listShowdownFormatCapabilities: (username = "PokemonBot", includeLearning = true) =>
    api.get("/pokemon/showdown/formats/capabilities", {
      params: { username, include_learning: includeLearning },
    }),
  getShowdownTacticalBriefing: (
    username = "PokemonBot",
    battleFormat = "vgc2024",
    mode = "auto",
    includeKnowledge = false,
    maxResults = 3
  ) =>
    api.get("/pokemon/showdown/tactical-briefing", {
      params: {
        username,
        battle_format: battleFormat,
        mode,
        include_knowledge: includeKnowledge,
        max_results: maxResults,
      },
    }),
  createShowdownSession: (data: Record<string, unknown>) => api.post("/pokemon/showdown/sessions", data),
  planShowdownMission: (data: Record<string, unknown>) => api.post("/pokemon/showdown/mission/plan", data),
  startShowdownMission: (data: Record<string, unknown>) => api.post("/pokemon/showdown/mission", data),
  runShowdownTrainingChain: (data: Record<string, unknown>) => api.post("/pokemon/showdown/training-chain", data),
  runShowdownTrainingLoop: (data: Record<string, unknown>) => api.post("/pokemon/showdown/training-loop", data),
    planShowdownTrainingProgram: (data: Record<string, unknown>) => api.post("/pokemon/showdown/training-program/plan", data),
    runShowdownTrainingProgram: (data: Record<string, unknown>) => api.post("/pokemon/showdown/training-program", data),
    runShowdownTrainingProgramPipeline: (data: Record<string, unknown>) => api.post("/pokemon/showdown/training-program/pipeline", data),
    runShowdownTrainingProgramAutopilot: (data: Record<string, unknown>) => api.post("/pokemon/showdown/training-program/autopilot", data),
    startShowdownSearch: (sessionId: string) => api.post(`/pokemon/showdown/sessions/${sessionId}/search`),
  cancelShowdownSearch: (sessionId: string) => api.post(`/pokemon/showdown/sessions/${sessionId}/cancel-search`),
  acceptShowdownChallenge: (sessionId: string, username?: string) =>
    api.post(`/pokemon/showdown/sessions/${sessionId}/accept-challenge`, null, username ? { params: { username } } : undefined),
  rejectShowdownChallenge: (sessionId: string, username?: string) =>
    api.post(`/pokemon/showdown/sessions/${sessionId}/reject-challenge`, null, username ? { params: { username } } : undefined),
  connectShowdownSession: (sessionId: string, sendPending = true) =>
    api.post(`/pokemon/showdown/sessions/${sessionId}/connect`, null, { params: { send_pending: sendPending } }),
  flushShowdownSession: (sessionId: string) => api.post(`/pokemon/showdown/sessions/${sessionId}/flush`),
  processShowdownSessionMessage: (sessionId: string, data: Record<string, unknown>) =>
    api.post(`/pokemon/showdown/sessions/${sessionId}/message`, data),
  researchShowdownSessionTeam: (sessionId: string, maxResults = 3) =>
    api.post(`/pokemon/showdown/sessions/${sessionId}/knowledge`, null, { params: { max_results: maxResults } }),
  analyzeShowdownSession: (sessionId: string) => api.get(`/pokemon/showdown/sessions/${sessionId}/analysis`),
  getShowdownSessionReadiness: (sessionId: string) => api.get(`/pokemon/showdown/sessions/${sessionId}/readiness`),
  getShowdownSessionMatchupBriefing: (
    sessionId: string,
    roomId?: string,
    includeKnowledge = false,
    maxResults = 3
  ) =>
    api.get(`/pokemon/showdown/sessions/${sessionId}/matchup-briefing`, {
      params: {
        ...(roomId ? { room_id: roomId } : {}),
        include_knowledge: includeKnowledge,
        max_results: maxResults,
      },
    }),
  runShowdownSessionOnce: (sessionId: string, data: Record<string, unknown>) =>
    api.post(`/pokemon/showdown/sessions/${sessionId}/run-once`, data),
  runShowdownSessionUntil: (sessionId: string, data: Record<string, unknown>) =>
    api.post(`/pokemon/showdown/sessions/${sessionId}/run-until`, data),
  autopilotShowdownSession: (sessionId: string, data: Record<string, unknown>) =>
    api.post(`/pokemon/showdown/sessions/${sessionId}/autopilot`, data),
  executeShowdownNextAction: (sessionId: string, data: Record<string, unknown>) =>
    api.post(`/pokemon/showdown/sessions/${sessionId}/next-action`, data),
  superviseShowdownSession: (sessionId: string, data: Record<string, unknown>) =>
    api.post(`/pokemon/showdown/sessions/${sessionId}/supervise`, data),
  closeShowdownSession: (sessionId: string) => api.post(`/pokemon/showdown/sessions/${sessionId}/close`),
  deleteShowdownSession: (sessionId: string) => api.delete(`/pokemon/showdown/sessions/${sessionId}`),
};

// ---- System ----
export const healthApi = {
  get: () => axios.get(`${appRootURL}/health`, { timeout: 8000 }),
};
