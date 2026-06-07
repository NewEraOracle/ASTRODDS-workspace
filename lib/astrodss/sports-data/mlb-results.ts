import { findMlbTeamProfile } from "./mlb-teams";
import { addDaysIsoDate, normalizeText, safeNumber, todayIsoDate } from "./normalize";

export type MlbResultDateRange = {
  startDate?: string;
  endDate?: string;
};

export type MlbFinalResult = {
  gamePk: number;
  homeTeam: string;
  awayTeam: string;
  homeScore?: number;
  awayScore?: number;
  status: string;
  final: boolean;
  gameDate?: string;
  venue?: string;
};

export type AstroddsPaperTradeStatus = "PENDING" | "WIN" | "LOSS" | "VOID" | "UNKNOWN";

export type AstroddsPaperTrade = {
  id: string;
  sport: string;
  gameId?: string;
  gamePk?: number;
  homeTeam?: string;
  awayTeam?: string;
  game: string;
  market: string;
  marketType: string;
  pick: string;
  line?: number;
  entryPrice: number;
  stake: number;
  score: number;
  confidence: string;
  decision: string;
  why: string;
  status: AstroddsPaperTradeStatus;
  result?: string;
  pnl: number;
  roi: number;
  createdAt: string;
  resolvedAt?: string;
  sourceData?: unknown;
};

type MlbScheduleResponse = {
  dates?: Array<{
    games?: MlbScheduleGame[];
  }>;
};

type MlbScheduleGame = {
  gamePk?: number;
  gameDate?: string;
  status?: {
    abstractGameState?: string;
    detailedState?: string;
  };
  teams?: {
    away?: {
      team?: { name?: string };
      score?: number;
    };
    home?: {
      team?: { name?: string };
      score?: number;
    };
  };
  venue?: {
    name?: string;
  };
};

type ResolveOutcome = {
  status: AstroddsPaperTradeStatus;
  result: string;
};

const MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule";

function mlbResultsUrl(dateRange: MlbResultDateRange = {}) {
  const url = new URL(MLB_SCHEDULE_URL);
  url.searchParams.set("sportId", "1");
  url.searchParams.set("startDate", dateRange.startDate ?? addDaysIsoDate(-7));
  url.searchParams.set("endDate", dateRange.endDate ?? todayIsoDate());
  url.searchParams.set("hydrate", "venue,linescore");
  return url;
}

function normalizeMarketType(type?: string) {
  const text = normalizeText(type);
  if (text.includes("moneyline") || text === "ml") return "MONEYLINE";
  if (text.includes("run line") || text.includes("spread") || text.includes("runline")) return "RUN_LINE";
  if (text.includes("total") || text.includes("over") || text.includes("under")) return "TOTAL";
  if (text.includes("prop")) return "PROP";
  return "OTHER";
}

function tradeGamePk(trade: Pick<AstroddsPaperTrade, "gamePk" | "gameId">) {
  if (typeof trade.gamePk === "number") return trade.gamePk;
  const parsed = String(trade.gameId ?? "").match(/(\d{4,})/)?.[1];
  return parsed ? Number(parsed) : undefined;
}

function sameTeam(a?: string, b?: string) {
  const aProfile = findMlbTeamProfile(a);
  const bProfile = findMlbTeamProfile(b);
  if (aProfile && bProfile) return aProfile.canonicalName === bProfile.canonicalName;
  const normalizedA = normalizeText(a);
  const normalizedB = normalizeText(b);
  return Boolean(normalizedA && normalizedB && (normalizedA === normalizedB || normalizedA.includes(normalizedB) || normalizedB.includes(normalizedA)));
}

function statusText(game: MlbScheduleGame) {
  return `${game.status?.abstractGameState ?? ""} ${game.status?.detailedState ?? ""}`.trim() || "UNKNOWN";
}

function isFinalStatus(status: string) {
  const normalized = normalizeText(status);
  return normalized.includes("final") || normalized.includes("game over");
}

function toResult(game: MlbScheduleGame): MlbFinalResult | undefined {
  const gamePk = game.gamePk;
  const awayTeam = game.teams?.away?.team?.name;
  const homeTeam = game.teams?.home?.team?.name;
  if (!gamePk || !awayTeam || !homeTeam) return undefined;

  const status = statusText(game);

  return {
    gamePk,
    awayTeam,
    homeTeam,
    awayScore: game.teams?.away?.score,
    homeScore: game.teams?.home?.score,
    status,
    final: isFinalStatus(status),
    gameDate: game.gameDate,
    venue: game.venue?.name,
  };
}

function parseTotalLine(trade: AstroddsPaperTrade) {
  if (typeof trade.line === "number") return trade.line;
  const text = `${trade.pick} ${trade.market} ${trade.game}`;
  return safeNumber(text.match(/(?:o\/u|over\/under|total|over|under)\s*([0-9]+(?:\.[0-9]+)?)/i)?.[1]);
}

function parseTotalSide(trade: AstroddsPaperTrade) {
  const text = normalizeText(`${trade.pick} ${trade.market}`);
  if (text.includes("over")) return "OVER" as const;
  if (text.includes("under")) return "UNDER" as const;
  return undefined;
}

function parseRunLine(trade: AstroddsPaperTrade) {
  const text = `${trade.pick} ${trade.market}`;
  const spread = safeNumber(text.match(/([+-]\s*\d+(?:\.\d+)?)/)?.[1]?.replace(/\s+/g, ""));
  if (typeof spread !== "number") return undefined;
  const teamText = text.replace(/[+-]\s*\d+(?:\.\d+)?/, " ").replace(/\b(run line|spread)\b/gi, " ");
  return { teamText, spread };
}

function pickedTeamScore(trade: AstroddsPaperTrade, gameResult: MlbFinalResult) {
  if (sameTeam(trade.pick, gameResult.homeTeam)) {
    return {
      pickedTeam: gameResult.homeTeam,
      pickedScore: gameResult.homeScore,
      opponentScore: gameResult.awayScore,
    };
  }

  if (sameTeam(trade.pick, gameResult.awayTeam)) {
    return {
      pickedTeam: gameResult.awayTeam,
      pickedScore: gameResult.awayScore,
      opponentScore: gameResult.homeScore,
    };
  }

  return undefined;
}

function withPnl(trade: AstroddsPaperTrade, outcome: ResolveOutcome, gameResult?: MlbFinalResult): AstroddsPaperTrade {
  if (trade.status !== "PENDING") return trade;
  if (outcome.status === "PENDING") return { ...trade, result: outcome.result, sourceData: gameResult };

  const stake = trade.stake || 50;
  const entryPrice = trade.entryPrice;
  let pnl = 0;

  if (outcome.status === "WIN") {
    pnl = entryPrice > 0 ? stake / entryPrice - stake : 0;
  } else if (outcome.status === "LOSS") {
    pnl = -stake;
  }

  return {
    ...trade,
    status: outcome.status,
    result: outcome.result,
    pnl,
    roi: stake > 0 ? pnl / stake : 0,
    resolvedAt: new Date().toISOString(),
    sourceData: gameResult,
  };
}

export async function fetchMLBFinalResults(dateRange: MlbResultDateRange = {}, signal?: AbortSignal) {
  const url = mlbResultsUrl(dateRange);
  const response = await fetch(url, {
    signal,
    next: { revalidate: 300 },
    headers: { accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`MLB StatsAPI returned ${response.status}`);
  }

  const data = (await response.json()) as MlbScheduleResponse;
  return (data.dates?.flatMap((date) => date.games ?? []) ?? []).flatMap((game) => {
    const result = toResult(game);
    return result ? [result] : [];
  });
}

export function findResultForPaperTrade(trade: AstroddsPaperTrade, results: MlbFinalResult[]) {
  const gamePk = tradeGamePk(trade);
  if (gamePk) {
    const exact = results.find((result) => result.gamePk === gamePk);
    if (exact) return exact;
  }

  return results.find((result) => {
    const homeMatches = sameTeam(trade.homeTeam, result.homeTeam) || normalizeText(trade.game).includes(normalizeText(result.homeTeam));
    const awayMatches = sameTeam(trade.awayTeam, result.awayTeam) || normalizeText(trade.game).includes(normalizeText(result.awayTeam));
    return homeMatches && awayMatches;
  });
}

export function resolveMLBMoneyline(trade: AstroddsPaperTrade, gameResult: MlbFinalResult): ResolveOutcome {
  const scores = pickedTeamScore(trade, gameResult);
  if (!scores || typeof scores.pickedScore !== "number" || typeof scores.opponentScore !== "number") {
    return { status: "UNKNOWN", result: "Moneyline pick could not be mapped to either MLB team." };
  }

  if (scores.pickedScore > scores.opponentScore) return { status: "WIN", result: `${scores.pickedTeam} won ${scores.pickedScore}-${scores.opponentScore}.` };
  if (scores.pickedScore < scores.opponentScore) return { status: "LOSS", result: `${scores.pickedTeam} lost ${scores.pickedScore}-${scores.opponentScore}.` };
  return { status: "VOID", result: "Final score was tied or abnormal for a moneyline market." };
}

export function resolveMLBTotal(trade: AstroddsPaperTrade, gameResult: MlbFinalResult): ResolveOutcome {
  const line = parseTotalLine(trade);
  const side = parseTotalSide(trade);
  if (typeof line !== "number" || !side) return { status: "UNKNOWN", result: "Total pick or line could not be parsed." };
  if (typeof gameResult.homeScore !== "number" || typeof gameResult.awayScore !== "number") return { status: "UNKNOWN", result: "Final MLB score is missing." };

  const finalTotal = gameResult.homeScore + gameResult.awayScore;
  if (finalTotal === line) return { status: "VOID", result: `Push: final total ${finalTotal} landed exactly on ${line}.` };
  if (side === "OVER") {
    return finalTotal > line
      ? { status: "WIN", result: `Over ${line} won. Final total: ${finalTotal}.` }
      : { status: "LOSS", result: `Over ${line} lost. Final total: ${finalTotal}.` };
  }

  return finalTotal < line
    ? { status: "WIN", result: `Under ${line} won. Final total: ${finalTotal}.` }
    : { status: "LOSS", result: `Under ${line} lost. Final total: ${finalTotal}.` };
}

export function resolveMLBRunLine(trade: AstroddsPaperTrade, gameResult: MlbFinalResult): ResolveOutcome {
  const runLine = parseRunLine(trade);
  if (!runLine) return { status: "UNKNOWN", result: "Run line spread could not be parsed." };
  const teamTrade = { ...trade, pick: runLine.teamText };
  const scores = pickedTeamScore(teamTrade, gameResult);
  if (!scores || typeof scores.pickedScore !== "number" || typeof scores.opponentScore !== "number") {
    return { status: "UNKNOWN", result: "Run line team could not be mapped to either MLB team." };
  }

  const adjustedMargin = scores.pickedScore + runLine.spread - scores.opponentScore;
  if (adjustedMargin > 0) return { status: "WIN", result: `${scores.pickedTeam} ${runLine.spread > 0 ? "+" : ""}${runLine.spread} covered.` };
  if (adjustedMargin < 0) return { status: "LOSS", result: `${scores.pickedTeam} ${runLine.spread > 0 ? "+" : ""}${runLine.spread} did not cover.` };
  return { status: "VOID", result: `Push: ${scores.pickedTeam} margin landed exactly on ${runLine.spread}.` };
}

export function resolveMLBPaperTrade(trade: AstroddsPaperTrade, gameResult?: MlbFinalResult): AstroddsPaperTrade {
  if (trade.status !== "PENDING") return trade;
  if (!gameResult) return { ...trade, result: "No matching MLB result found yet." };
  if (!gameResult.final) return { ...trade, result: `Game is not final yet: ${gameResult.status}.`, sourceData: gameResult };

  const marketType = normalizeMarketType(trade.marketType);
  const outcome =
    marketType === "MONEYLINE"
      ? resolveMLBMoneyline(trade, gameResult)
      : marketType === "TOTAL"
        ? resolveMLBTotal(trade, gameResult)
        : marketType === "RUN_LINE"
          ? resolveMLBRunLine(trade, gameResult)
          : { status: "UNKNOWN" as const, result: `Resolver does not support market type ${trade.marketType}.` };

  return withPnl(trade, outcome, gameResult);
}

export function summarizePaperPerformance(trades: AstroddsPaperTrade[]) {
  const wins = trades.filter((trade) => trade.status === "WIN").length;
  const losses = trades.filter((trade) => trade.status === "LOSS").length;
  const voids = trades.filter((trade) => trade.status === "VOID").length;
  const pending = trades.filter((trade) => trade.status === "PENDING").length;
  const unknown = trades.filter((trade) => trade.status === "UNKNOWN").length;
  const pnl = trades.reduce((total, trade) => total + (trade.pnl || 0), 0);
  const riskedStake = trades.filter((trade) => trade.status === "WIN" || trade.status === "LOSS").reduce((total, trade) => total + (trade.stake || 0), 0);
  const settled = wins + losses;
  const totalTrades = trades.length;

  function groupedBy(field: keyof AstroddsPaperTrade) {
    return trades.reduce<Record<string, { trades: number; wins: number; losses: number; voids: number; pnl: number }>>((groups, trade) => {
      const key = String(trade[field] ?? "UNKNOWN");
      const existing = groups[key] ?? { trades: 0, wins: 0, losses: 0, voids: 0, pnl: 0 };
      existing.trades += 1;
      if (trade.status === "WIN") existing.wins += 1;
      if (trade.status === "LOSS") existing.losses += 1;
      if (trade.status === "VOID") existing.voids += 1;
      existing.pnl += trade.pnl || 0;
      groups[key] = existing;
      return groups;
    }, {});
  }

  return {
    bankroll: 1000 + pnl,
    totalTrades,
    pending,
    wins,
    losses,
    voids,
    unknown,
    winRate: settled ? wins / settled : 0,
    pnl,
    roi: riskedStake ? pnl / riskedStake : 0,
    recordByDecision: groupedBy("decision"),
    recordByMarketType: groupedBy("marketType"),
    recordByConfidence: groupedBy("confidence"),
    recordBySport: groupedBy("sport"),
  };
}
