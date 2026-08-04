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

export type NflReviewCoverage = {
  team_health: number;
  team_intelligence: number;
  prediction_waterfall: number;
  complete_games: number;
};

export type NflReviewResponse = {
  sport: "nfl";
  review_version: string;
  date?: string | null;
  game_count: number;
  average_confidence?: number | null;
  confidence_range: {
    minimum?: number | null;
    maximum?: number | null;
  };
  coverage: NflReviewCoverage;
  context: {
    preseason_games: number;
    market_available_games: number;
    guardrail_applied_games: number;
    quarterbacks_announced_games: number;
  };
  readiness_distribution: Record<string, number>;
  market_signal_distribution: Record<string, number>;
  attention: {
    review_required_games: number;
    high_priority_games: number;
    disposition_counts: Record<string, number>;
    queue: Array<{
      game_id?: string | null;
      matchup: string;
      away_team: string;
      home_team: string;
      pick?: string | null;
      confidence?: number | null;
      priority_score: number;
      priority_level: "high" | "medium" | "low" | string;
      reasons: string[];
      review_required: boolean;
      disposition: "ready" | "watch" | "hold" | string;
      disposition_label: string;
      recommended_action: string;
    }>;
  };
  prediction_impact: Record<string, boolean>;
  status: "ready_for_review" | "partial" | string;
};
