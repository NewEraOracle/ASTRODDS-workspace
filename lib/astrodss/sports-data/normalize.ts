import type {
  AstroddsBetType,
  AstroddsDataStatus,
  AstroddsDecision,
  AstroddsLiveStatus,
  AstroddsMarketStatus,
  AstroddsSport,
  RawPolymarketMarket,
} from "./types";

export const SPORTS: Array<{ label: string; value: AstroddsSport | "ALL" }> = [
  { label: "All Sports", value: "ALL" },
  { label: "MLB", value: "MLB" },
  { label: "NFL", value: "NFL" },
  { label: "NBA", value: "NBA" },
  { label: "NHL", value: "NHL" },
  { label: "Soccer", value: "SOCCER" },
  { label: "Tennis", value: "TENNIS" },
  { label: "MMA/UFC", value: "MMA" },
];

export const SCAN_STEPS = [
  "Pulling Polymarket markets",
  "Pulling sport data",
  "Pulling lineups",
  "Pulling injuries",
  "Pulling pitchers/goalies",
  "Pulling weather",
  "Matching games to markets",
  "Running ASTRODDS decision engine",
  "Ranking best picks",
] as const;

const sportKeywords: Record<AstroddsSport, string[]> = {
  MLB: [
    "mlb",
    "baseball",
    "diamondbacks",
    "braves",
    "orioles",
    "red sox",
    "cubs",
    "white sox",
    "reds",
    "guardians",
    "rockies",
    "tigers",
    "astros",
    "royals",
    "angels",
    "dodgers",
    "marlins",
    "brewers",
    "twins",
    "mets",
    "yankees",
    "athletics",
    "phillies",
    "pirates",
    "padres",
    "giants",
    "mariners",
    "cardinals",
    "rays",
    "rangers",
    "blue jays",
    "nationals",
  ],
  NFL: ["nfl", "football", "super bowl", "chiefs", "eagles", "bills", "cowboys", "packers"],
  NBA: ["nba", "basketball", "celtics", "lakers", "knicks", "warriors", "thunder", "nuggets"],
  NHL: ["nhl", "hockey", "rangers", "bruins", "oilers", "panthers", "leafs", "hurricanes"],
  SOCCER: ["soccer", "football", "premier league", "champions league", "mls", "world cup", "epl"],
  TENNIS: ["tennis", "atp", "wta", "wimbledon", "roland garros", "us open", "australian open"],
  MMA: ["mma", "ufc", "fight", "bout", "fighter"],
  OTHER: [],
};

export function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

export function addDaysIsoDate(days: number) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

export function safeNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

export function safeArray<T = unknown>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[];
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value) as unknown;
      return Array.isArray(parsed) ? (parsed as T[]) : [];
    } catch {
      return [];
    }
  }
  return [];
}

export function normalizeText(value?: string) {
  return (value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function detectSport(text: string): AstroddsSport | "OTHER" {
  const normalized = normalizeText(text);
  const match = (Object.keys(sportKeywords) as AstroddsSport[]).find((sport) =>
    sportKeywords[sport].some((keyword) => normalized.includes(keyword)),
  );

  return match ?? "OTHER";
}

export function inferBetType(title: string): AstroddsBetType {
  const raw = title.toLowerCase();
  const text = normalizeText(title);
  if (text.includes("spread") || text.includes("run line") || /[+-]\s*\d+(\.\d+)?/.test(raw)) return "SPREAD";
  if (text.includes("over") || text.includes("under") || text.includes("total") || /\bo\s*\/?\s*u\b/.test(raw) || /\bo\s+u\b/.test(text)) return "TOTAL";
  if (text.includes("winner") || text.includes("game winner") || text.includes("win") || text.includes("moneyline") || text.includes("ml")) return "MONEYLINE";
  if (text.includes("points") || text.includes("goals") || text.includes("runs") || text.includes("score") || text.includes("strikeouts")) return "PROP";
  if (text.includes("yes") || text.includes("no")) return "YES_NO";
  return "OTHER";
}

export function inferMarketStatus(market: Pick<RawPolymarketMarket, "active" | "closed" | "acceptingOrders">): AstroddsMarketStatus {
  if (market.closed) return "RESOLVED";
  if (market.active || market.acceptingOrders) return "ACTIVE";
  if (market.active === false && market.closed === false) return "PENDING";
  return "UNKNOWN";
}

export function liveStatusFromText(status?: string): AstroddsLiveStatus {
  const text = normalizeText(status);
  if (!text) return "UNKNOWN";
  if (text.includes("final") || text.includes("complete") || text.includes("finished")) return "FINAL";
  if (text.includes("live") || text.includes("in progress") || text.includes("progress") || text.includes("inning") || text.includes("period")) return "LIVE";
  if (text.includes("scheduled") || text.includes("preview") || text.includes("pre")) return "PRE_GAME";
  return "UNKNOWN";
}

export function dataStatusRank(statuses: AstroddsDataStatus[]): AstroddsDataStatus {
  if (!statuses.length) return "NOT_CONNECTED";
  if (statuses.every((status) => status === "CONNECTED")) return "CONNECTED";
  if (statuses.every((status) => status === "WALLET_LED")) return "WALLET_LED";
  if (statuses.every((status) => status === "DEMO_FALLBACK")) return "DEMO_FALLBACK";
  if (statuses.some((status) => status === "CONNECTED" || status === "PARTIAL" || status === "WALLET_LED" || status === "DEMO_FALLBACK")) {
    return "PARTIAL";
  }
  return "NOT_CONNECTED";
}

export function compactId(value: string) {
  return normalizeText(value).replace(/\s/g, "-").slice(0, 80) || `astro-${Math.random().toString(36).slice(2)}`;
}

export function tokenMatchScore(gameText: string, marketText: string) {
  const gameTokens = normalizeText(gameText).split(" ").filter((token) => token.length > 2);
  const market = normalizeText(marketText);
  if (!gameTokens.length || !market) return 0;
  const matches = gameTokens.filter((token) => market.includes(token)).length;
  return matches / gameTokens.length;
}

export function displayDecision(decision?: AstroddsDecision) {
  if (!decision) return "WAIT";
  return decision.replace(/_/g, " ");
}
