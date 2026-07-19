export type ViewMode = "predicted" | "actual";
export type GroupBy = "year" | "team";

export interface PlayerStats {
  G: number | null;
  GM: number | null;
  Series_G: number | null;
  MP: number | null;
  PTS: number | null;
  TRB: number | null;
  AST: number | null;
  STL: number | null;
  BLK: number | null;
  TOV: number | null;
  "FG%": number | null;
  "3P%": number | null;
  "USG%": number | null;
  ORtg: number | null;
  DRtg: number | null;
}

export interface Candidate {
  player: string;
  mvpShare: number;
  probMvp: number;
  rank: number;
  isActualMvp: boolean;
  isPredicted: boolean;
  stats: PlayerStats;
}

export interface YearRow {
  year: number;
  team: string;
  teamAbbr: string;
  logoUrl: string;
  opponent: string;
  predictedPlayer: string;
  predictedShare: number;
  actualPlayer: string;
  actualShare: number;
  correct: boolean;
  candidates: Candidate[];
}

export interface FeatureWeight {
  name: string;
  weight: number;
}

export interface FinalsData {
  generatedFrom: string;
  minYear: number;
  maxYear: number;
  teams: string[];
  featureWeights: FeatureWeight[];
  years: YearRow[];
}

export type SortKey =
  | "year"
  | "team"
  | "player"
  | "share"
  | "correct";
