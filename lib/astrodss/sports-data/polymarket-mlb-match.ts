import { findMlbTeamProfile, mlbTeamHits } from "./mlb-teams";
import type { AstroddsGameScan } from "./types";
import type { PolymarketMlbMoneylineMarket, PolymarketMlbOutcomeProbability } from "./polymarket-mlb-markets";

export type PolymarketMlbMatchConfidence = "high" | "medium" | "low" | "none";

export type PolymarketMlbMatchedGameMarket = {
  gameId: string;
  homeTeam?: string;
  awayTeam?: string;
  matchedMarketId?: string;
  matchedMarketQuestion?: string;
  matchedMarketSlug?: string;
  matchedOutcome?: string;
  marketProbability: number | null;
  matchConfidence: PolymarketMlbMatchConfidence;
  matchReasons: string[];
  matchWarnings: string[];
  diagnosticRawEdge?: number;
  diagnosticRawEdgePct?: number;
  diagnosticOnly: true;
  diagnosticEdgeAllowed: boolean;
  officialEdgeAllowed: false;
  officialEdgeBlockReasons: string[];
};

export type PolymarketMlbMatchDiagnostics = {
  gamesEvaluated: number;
  marketsEvaluated: number;
  highConfidenceMatches: number;
  mediumConfidenceMatches: number;
  lowConfidenceMatches: number;
  unmatchedGames: number;
  diagnosticEdgesCalculated: number;
  warnings: string[];
  matches: PolymarketMlbMatchedGameMarket[];
};

type BuildDiagnosticsOptions = {
  calibrationQuality?: string;
  modelProbabilitiesByGameId?: Record<string, number | undefined>;
};

type Candidate = {
  market: PolymarketMlbMoneylineMarket;
  confidence: PolymarketMlbMatchConfidence;
  score: number;
  reasons: string[];
  warnings: string[];
  outcome?: PolymarketMlbOutcomeProbability;
};

function canonicalTeam(team?: string) {
  return findMlbTeamProfile(team)?.canonicalName ?? team;
}

function teamMatches(team?: string, marketText = "") {
  const profile = findMlbTeamProfile(team);
  if (!profile) return false;
  return mlbTeamHits(marketText).some((hit) => hit.profile.canonicalName === profile.canonicalName);
}

function marketText(market: PolymarketMlbMoneylineMarket) {
  return [market.eventTitle, market.question, market.title, market.slug, market.detectedTeams.join(" "), market.outcomes.join(" ")]
    .filter(Boolean)
    .join(" ");
}

function timestamp(value?: string) {
  if (!value) return undefined;
  const parsed = new Date(value).getTime();
  return Number.isFinite(parsed) ? parsed : undefined;
}

function dateDistanceHours(game: AstroddsGameScan, market: PolymarketMlbMoneylineMarket) {
  const gameTs = timestamp(game.startTime);
  const marketTs = timestamp(market.gameDate ?? market.endDate);
  if (typeof gameTs !== "number" || typeof marketTs !== "number") return undefined;
  return Math.abs(gameTs - marketTs) / 36e5;
}

function sideOutcome(market: PolymarketMlbMoneylineMarket, preferredTeam?: string) {
  const preferred = canonicalTeam(preferredTeam);
  if (preferred) {
    const exact = market.outcomeProbabilities.find((outcome) => canonicalTeam(outcome.mappedTeam) === preferred);
    if (exact) return exact;
  }

  return market.outcomeProbabilities.find((outcome) => outcome.marketProbability !== null) ?? market.outcomeProbabilities[0];
}

function confidenceFor(game: AstroddsGameScan, market: PolymarketMlbMoneylineMarket): Candidate {
  const text = marketText(market);
  const away = canonicalTeam(game.awayTeam);
  const home = canonicalTeam(game.homeTeam);
  const awayMatched = teamMatches(away, text) || market.detectedTeams.map(canonicalTeam).includes(away);
  const homeMatched = teamMatches(home, text) || market.detectedTeams.map(canonicalTeam).includes(home);
  const distanceHours = dateDistanceHours(game, market);
  const reasons: string[] = [];
  const warnings: string[] = [];
  let score = 0;

  if (awayMatched) {
    score += 0.4;
    reasons.push(`Away team matched: ${away}`);
  }
  if (homeMatched) {
    score += 0.4;
    reasons.push(`Home team matched: ${home}`);
  }

  if (typeof distanceHours === "number") {
    if (distanceHours <= 36) {
      score += 0.2;
      reasons.push(`Game date is within ${Math.round(distanceHours)} hours of market date.`);
    } else if (distanceHours <= 72) {
      score += 0.08;
      warnings.push(`Market date is ${Math.round(distanceHours)} hours from MLB game start.`);
    } else {
      score -= 0.25;
      warnings.push(`Market date is too far from MLB game start (${Math.round(distanceHours)} hours).`);
    }
  } else {
    score += awayMatched && homeMatched ? 0.08 : 0;
    warnings.push("Game/market date proximity unavailable.");
  }

  if (market.closed || !market.active) warnings.push("Market is not active or is already closed.");
  if (!awayMatched || !homeMatched) warnings.push("Both MLB teams were not confidently detected in the market text.");
  if (!market.outcomeProbabilities.some((outcome) => outcome.marketProbability !== null)) warnings.push("Market probability unavailable.");

  const confidence: PolymarketMlbMatchConfidence = awayMatched && homeMatched && score >= 0.85
    ? "high"
    : awayMatched && homeMatched && score >= 0.65
      ? "medium"
      : awayMatched || homeMatched
        ? "low"
        : "none";

  return {
    market,
    confidence,
    score,
    reasons,
    warnings,
    outcome: sideOutcome(market, game.modelPick?.modelLeanTeam),
  };
}

function bestCandidate(game: AstroddsGameScan, markets: PolymarketMlbMoneylineMarket[]) {
  return markets
    .map((market) => confidenceFor(game, market))
    .filter((candidate) => candidate.confidence !== "none")
    .sort((a, b) => b.score - a.score || (b.market.volume ?? 0) - (a.market.volume ?? 0))[0];
}

function blockReasons(calibrationQuality?: string) {
  const reasons = ["Diagnostic-only market comparison", "Official edge gate remains closed", "No calibrated probability mapping available", "Paper-only safety gate"];
  if (calibrationQuality === "weak") reasons.unshift("Calibration weak - diagnostic only");
  else if (!calibrationQuality || calibrationQuality === "missing" || calibrationQuality === "not_enough_history") reasons.unshift("Calibration not ready for official edge");
  return Array.from(new Set(reasons));
}

export function buildPolymarketMlbMatchDiagnostics(
  games: AstroddsGameScan[],
  markets: PolymarketMlbMoneylineMarket[],
  options: BuildDiagnosticsOptions = {},
): PolymarketMlbMatchDiagnostics {
  const mlbGames = games.filter((game) => game.sport === "MLB" && !game.source.toLowerCase().includes("market-only"));
  const warnings = new Set<string>();
  const matches = mlbGames.map((game) => {
    const candidate = bestCandidate(game, markets);
    const modelProbability = options.modelProbabilitiesByGameId?.[game.id];

    if (!candidate) {
      return {
        gameId: game.id,
        homeTeam: game.homeTeam,
        awayTeam: game.awayTeam,
        marketProbability: null,
        matchConfidence: "none" as const,
        matchReasons: [],
        matchWarnings: ["No matching Polymarket MLB moneyline market found for this game."],
        diagnosticOnly: true as const,
        diagnosticEdgeAllowed: false,
        officialEdgeAllowed: false as const,
        officialEdgeBlockReasons: blockReasons(options.calibrationQuality),
      };
    }

    const marketProbability = candidate.outcome?.marketProbability ?? null;
    const canUseForDiagnosticEdge = (candidate.confidence === "high" || candidate.confidence === "medium") && typeof modelProbability === "number" && marketProbability !== null;
    const diagnosticRawEdge = canUseForDiagnosticEdge ? modelProbability - marketProbability : undefined;
    const matchWarnings = [...candidate.warnings];

    if (candidate.confidence === "low") matchWarnings.push("Low-confidence market match; edge calculation blocked.");
    if (typeof modelProbability !== "number") matchWarnings.push("Model probability unavailable.");
    if (marketProbability === null) matchWarnings.push("Market probability unavailable.");
    if (!canUseForDiagnosticEdge) warnings.add(`Diagnostic edge unavailable for ${game.game}.`);

    return {
      gameId: game.id,
      homeTeam: game.homeTeam,
      awayTeam: game.awayTeam,
      matchedMarketId: candidate.market.marketId,
      matchedMarketQuestion: candidate.market.question,
      matchedMarketSlug: candidate.market.slug ?? candidate.market.eventSlug,
      matchedOutcome: candidate.outcome?.outcome,
      marketProbability,
      matchConfidence: candidate.confidence,
      matchReasons: candidate.reasons,
      matchWarnings,
      diagnosticRawEdge,
      diagnosticRawEdgePct: typeof diagnosticRawEdge === "number" ? diagnosticRawEdge * 100 : undefined,
      diagnosticOnly: true as const,
      diagnosticEdgeAllowed: typeof diagnosticRawEdge === "number",
      officialEdgeAllowed: false as const,
      officialEdgeBlockReasons: blockReasons(options.calibrationQuality),
    };
  });

  if (!markets.length) warnings.add("No Polymarket MLB moneyline markets available for game matching.");
  if (!mlbGames.length) warnings.add("No MLB games available for Polymarket market matching.");
  if (options.calibrationQuality === "weak") warnings.add("Calibration weak - diagnostic only; official edge remains blocked.");

  return {
    gamesEvaluated: mlbGames.length,
    marketsEvaluated: markets.length,
    highConfidenceMatches: matches.filter((match) => match.matchConfidence === "high").length,
    mediumConfidenceMatches: matches.filter((match) => match.matchConfidence === "medium").length,
    lowConfidenceMatches: matches.filter((match) => match.matchConfidence === "low").length,
    unmatchedGames: matches.filter((match) => match.matchConfidence === "none").length,
    diagnosticEdgesCalculated: matches.filter((match) => typeof match.diagnosticRawEdge === "number").length,
    warnings: Array.from(warnings).slice(0, 25),
    matches,
  };
}