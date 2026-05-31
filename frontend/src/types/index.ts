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
  api_base?: string | null;
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
  game_type: GameType;
  title: string;
  status: GameStatus;
  config: Record<string, unknown>;
  players: GamePlayer[];
  current_turn: number;
  max_turns: number;
  winner_id: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface GamePlayer {
  agent_id: string;
  name: string;
  agent_name?: string;  // backward compat alias for name
  role?: string;
  alive?: boolean;
  eliminated_turn?: number;
}

export type GameType = 'werewolf' | 'debate' | 'chess' | 'text_adventure' | 'negotiation';
export type GameStatus = 'waiting' | 'in_progress' | 'paused' | 'finished' | 'cancelled';

export interface ArenaMatch {
  id: string;
  match_type: string;
  title: string;
  prompt: string;
  status: string;
  agent_a_id: string;
  agent_b_id: string;
  agent_a_name?: string;
  agent_b_name?: string;
  result_a?: string;
  result_b?: string;
  image_a_url?: string;
  image_b_url?: string;
  audio_a_url?: string;
  audio_b_url?: string;
  participant_a_id?: string;
  participant_b_id?: string;
  votes_a: number;
  votes_b: number;
  winner_id?: string;
  created_at: string;
  updated_at?: string;
  creator_id?: string;
  config?: Record<string, unknown>;
}

export interface ArenaParticipant {
  id: string;
  match_id: string;
  agent_id: string;
  agent_name: string;
  response_content?: {
    response?: string;
    image_url?: string;
    audio_url?: string;
    prompt?: string;
    transcript?: string;
    error?: string;
  };
  vote_count?: number;
  created_at?: string;
}
