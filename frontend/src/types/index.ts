export interface Agent {
  id: string;
  name: string;
  description?: string;
  model_id: string;
  model_name?: string;
  avatar_url?: string;
  persona?: string;
  personality?: string;
  speaking_style?: string;
  backstory?: string;
  specialties?: string[];
  system_prompt?: string;
  level: string;
  experience_points: number;
  max_experience?: number;
  created_at: string;
}

export interface Model {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  is_active: boolean;
  status: string;
}

export interface Conversation {
  id: string;
  title: string;
  mode: string;
  status: string;
  agent_ids?: string[];
  created_at: string;
}

export interface Game {
  id: string;
  game_type: string;
  title: string;
  status: string;
  current_turn?: number;
  max_turns?: number;
  players?: GamePlayer[];
  config?: Record<string, unknown>;
  created_at: string;
}

export interface GamePlayer {
  agent_id: string;
  agent_name: string;
  role: string;
  alive: boolean;
  eliminated_turn?: number;
}
