export type SportKey = "mlb" | "nfl" | string;

export type GameStatus =
  | "scheduled"
  | "live"
  | "final"
  | "postponed"
  | "cancelled"
  | "unknown";

export type SportCapabilities = {
  moneyline: boolean;
  spread: boolean;
  totals: boolean;
  player_props: boolean;
  live: boolean;
  standings: boolean;
  injuries: boolean;
  weather: boolean;
};

export type SportGame = {
  sport: SportKey;
  game_id: string;
  away_team: string;
  home_team: string;
  start_time: string;
  status: GameStatus;
  away_score?: number | null;
  home_score?: number | null;
  venue?: string | null;
  metadata?: Record<string, unknown>;
};

export type MarketPrediction = {
  market_type: string;
  selection?: string | null;
  confidence?: number | null;
  line?: number | null;
  projected_value?: number | null;
  recommendation?: string | null;
  explanation?: string | null;
  factor_ids?: string[];
  metadata?: Record<string, unknown>;
};

export type SportPrediction = {
  sport: SportKey;
  game_id: string;
  pick?: string | null;
  confidence?: number | null;
  recommendation?: string | null;
  factors: Array<Record<string, unknown>>;
  timeline: Array<Record<string, unknown>>;
  markets: MarketPrediction[] | Record<string, unknown>;
  explanation: Record<string, unknown>;
  model_version?: string | null;
  shadow_prediction?: Record<string, unknown> | null;
  metadata?: Record<string, unknown>;
};

export type SportGameEnvelope = {
  game: SportGame;
  prediction: SportPrediction;
};

export type SportHomeResponse = {
  sport: SportKey;
  display_name: string;
  date: string;
  capabilities: SportCapabilities;
  game_count: number;
  games: SportGameEnvelope[];
  provider: Record<string, unknown>;
};
