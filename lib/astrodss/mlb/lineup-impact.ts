import type { AstroddsGameScan, AstroddsMarketScan } from "../sports-data/types";

export type MLBLineupStatus = "confirmed" | "projected" | "missing";

export type MLBLineupImpact = {
  lineupStatus: MLBLineupStatus;
  lineupImpactScore: number;
  lineupConfidence: number;
  lineupReasons: string[];
  downgradeReasons: string[];
};

type LineupSignal = {
  status: MLBLineupStatus;
  score: number;
  confidence: number;
  reasons: string[];
  downgrades: string[];
};

const negativeLineupTerms = ["scratched", "scratch", "out", "injury", "injured", "rest", "resting", "illness", "late swap", "unavailable"];
const positiveLineupTerms = ["confirmed", "posted", "starting lineup", "lineup confirmed", "available", "full lineup"];

function clamp01(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

function unique(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function statusFromSummary(summary?: string): MLBLineupStatus {
  const text = (summary ?? "").toLowerCase();
  if (!text || text.includes("not connected") || text.includes("source needed") || text.includes("unavailable")) return "missing";
  if (positiveLineupTerms.some((term) => text.includes(term))) return "confirmed";
  if (text.includes("projected") || text.includes("probable") || text.includes("partial")) return "projected";
  return "projected";
}

function baseLineupSignal(game: AstroddsGameScan): LineupSignal {
  const summary = game.lineups?.summary?.trim();
  const sourceStatus = game.lineups?.status ?? "NOT_CONNECTED";
  const inferredStatus = statusFromSummary(summary);

  if (sourceStatus === "CONNECTED" && inferredStatus === "confirmed") {
    return {
      status: "confirmed",
      score: 0.74,
      confidence: 0.76,
      reasons: ["Lineup source is connected", summary ? `Lineup note: ${summary}` : "Confirmed lineup context is available"],
      downgrades: [],
    };
  }

  if (sourceStatus === "PARTIAL" || inferredStatus === "projected") {
    return {
      status: "projected",
      score: 0.58,
      confidence: 0.56,
      reasons: [summary ? `Lineup note: ${summary}` : "Projected lineup context only"],
      downgrades: ["Lineup not confirmed yet"],
    };
  }

  return {
    status: "missing",
    score: 0.38,
    confidence: 0.32,
    reasons: ["Lineup data unavailable"],
    downgrades: ["Lineup not confirmed yet", "Official pick eligibility downgraded until lineup source connects"],
  };
}

export function calculateMLBLineupImpact(game: AstroddsGameScan, market?: AstroddsMarketScan): MLBLineupImpact {
  const signal = baseLineupSignal(game);
  const summary = `${game.lineups?.summary ?? ""} ${game.injuries?.summary ?? ""}`.toLowerCase();
  const reasons = [...signal.reasons];
  const downgrades = [...signal.downgrades];
  let score = signal.score;
  let confidence = signal.confidence;

  if (signal.status === "confirmed") {
    if (market?.betType === "TOTAL") reasons.push("Confirmed lineup supports totals modeling");
    if (market?.betType === "MONEYLINE" || market?.betType === "SPREAD") reasons.push("Confirmed lineup supports side modeling");
    score += 0.04;
    confidence += 0.04;
  }

  if (signal.status === "projected") {
    if (market?.betType === "TOTAL") downgrades.push("Totals need confirmed bats before official aggression");
    score -= 0.03;
  }

  if (negativeLineupTerms.some((term) => summary.includes(term))) {
    score -= 0.18;
    confidence -= 0.14;
    downgrades.push("No Bet - lineup downgrade");
  }

  if (positiveLineupTerms.some((term) => summary.includes(term)) && signal.status !== "missing") {
    score += 0.04;
    confidence += 0.03;
  }

  return {
    lineupStatus: signal.status,
    lineupImpactScore: clamp01(score),
    lineupConfidence: clamp01(confidence),
    lineupReasons: unique(reasons).slice(0, 4),
    downgradeReasons: unique(downgrades).slice(0, 4),
  };
}

export function lineupStatusLabel(status: MLBLineupStatus) {
  if (status === "confirmed") return "Confirmed";
  if (status === "projected") return "Projected";
  return "Missing";
}
