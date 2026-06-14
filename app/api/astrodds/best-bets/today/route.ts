import { NextResponse } from "next/server";
import { access } from "node:fs/promises";
import path from "node:path";

import { loadPythonMlbPredictions, type PythonMlbPrediction } from "@/lib/astrodss/mlb/python-predictions";
import { loadStrongBuyLedgerStatus } from "@/lib/astrodss/mlb/strong-buy-ledger";
import { findMlbTeamProfile } from "@/lib/astrodss/sports-data/mlb-teams";
import { fetchConfiguredSportsOdds } from "@/lib/astrodss/sports-data/odds";
import { scanAstroddsSport } from "@/lib/astrodss/sports-data/scanner";
import { compactId, inferBetType, normalizeText } from "@/lib/astrodss/sports-data/normalize";
import type {
  AstroddsConfidence,
  AstroddsDataQuality,
  AstroddsDecision,
  AstroddsGameScan,
  AstroddsMarketScan,
  AstroddsMlbModelPick,
  AstroddsProbabilityAssessment,
} from "@/lib/astrodss/sports-data/types";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type BestBetStatus = "strong_buy" | "daily_pick" | "buy" | "watch" | "blocked";
type BestBetRiskLevel = "low" | "medium" | "high" | "unknown";

type BestBetGameStatus = "pre_game" | "live" | "final" | "blocked" | "unknown";

type BestBetRowResponse = {
  bestBetId: string;
  gameId?: string;
  date?: string;
  homeTeam?: string;
  awayTeam?: string;
  gameStatusValidation?: AstroddsGameScan["gameStatusValidation"];
  mlbStatus?: string;
  gameStatusBlockReasons?: string[];
  selectedSide?: string;
  marketType: "moneyline";
  status: BestBetStatus;
  statusRank: number;
  calibratedProbability?: number | null;

  modelProbabilityGapPct?: number | null;
  marketProbability?: number | null;
  diagnosticRawEdgePct?: number | null;
  diagnosticCalibratedEdge?: number | null;
  diagnosticCalibratedEdgePct?: number | null;
  matchConfidence?: "high" | "medium" | "low" | "none";
  riskLevel: BestBetRiskLevel;
  riskScore: number;
  bankroll: number;
  stakePercent: number;
  stakeAmount: number;
  totalOpenExposurePercent: number;
  exposureLabel: string;
  reasons: string[];
  mainReason?: string;
  whyNotStrongBuy?: string;
  whyDailyPick?: string;
  warnings: string[];
  blockReasons: string[];
  downgradeReasons: string[];
  telegramEligible: boolean;
  saveEligible?: boolean;
  stakeRecommendation?: string;
  priceSourceUsed?: PriceSourceUsed;
  manualOnly: true;
  paperOnly: true;
  realMoneyDisabled: true;
  marketConnected?: boolean;
};

type MoneylineCandidateStatus = "official_pick" | "moneyline_lean" | "no_bet";

type MoneylineCandidateResponse = {
  bestBetId: string;
  gameId?: string;
  date?: string;
  homeTeam?: string;
  awayTeam?: string;
  selectedSide?: string;
  marketType: "moneyline";
  status: MoneylineCandidateStatus;
  gameStatus: BestBetGameStatus;
  marketConnected: boolean;
  marketProbability: number | null;
  calibratedProbability: number | null;

  modelProbabilityGapPct?: number | null;
  edge: number | null;
  matchConfidence: "high" | "medium" | "low" | "none";
  riskLevel: BestBetRiskLevel;
  modelScore: number;
  dataQuality: string;
  keyReasons: string[];
  whyNotOfficialYet: string[];
  mainReason?: string;
  warnings: string[];
  blockReasons: string[];
  stakeRecommendation?: string;
  priceSourceUsed?: PriceSourceUsed;
  paperOnly: true;
  realMoneyDisabled: true;
};

type OddsOnlyWatchResponse = {
  bestBetId: string;
  gameId?: string;
  date?: string;
  homeTeam?: string;
  awayTeam?: string;
  selectedSide?: string;
  marketType: "moneyline";
  status: "odds_only_watch";
  marketProbability: number;
  calibratedProbability: null;
  edge: null;
  matchConfidence: "medium" | "low";
  riskLevel: BestBetRiskLevel;
  mainReason?: string;
  warnings: string[];
  blockReasons: string[];
  priceSourceUsed: PriceSourceUsed;
};

type RejectionCounts = {
  noCleanMoneylineMarket: number;
  selectedSideNotTeam: number;
  marketProbabilityMissing: number;
  calibratedProbabilityMissing: number;
  edgeTooLow: number;
  confidenceTooLow: number;
  gameStatusNotPreGame: number;
  modelSignalTooWeak: number;
  dataQualityTooLow: number;
  thresholdTooStrict: number;
};

type TopCandidateSummary = {
  totalMoneylineCandidates: number;
  officialPicks: number;
  moneylineLeans: number;
  noBets: number;
  bestCandidate?: {
    game: string;
    selectedSide?: string;
    marketProbability: number | null;
    calibratedProbability: number | null;

    modelProbabilityGapPct?: number | null;
    edge: number | null;
    matchConfidence: "high" | "medium" | "low" | "none";
    riskLevel: BestBetRiskLevel;
    mainReason?: string;
    whyNotOfficialYet: string[];
  };
  top10MoneylineCandidates: MoneylineCandidateResponse[];
  thresholdNotes: string[];
};

type PriceSourceUsed = "polymarket" | "sportsbook" | "model_only";

type ModelAttachFailureCounts = {
  noModelCache: number;
  noGameKeyMatch: number;
  teamAliasMismatch: number;
  dateMismatch: number;
  modelUnavailable: number;
};

type BestBetsDiagnosticsResponse = {
  available: boolean;
  totalRowsEvaluated: number;
  strongBuyCount: number;
  dailyPickCount: number;
  buyCount: number;
  watchCount: number;
  blockedCount: number;
  actionableCount: number;
  visibleBoardCount: number;
  targetDailyPickMin: number;
  targetDailyPickMax: number;
  validCandidateCount: number;
  whyNoDailyPicks: string[];
  whyNoOfficialPicks?: string[];
  priceSourceUsed?: PriceSourceUsed;
  scanGamesFound?: number;
  scanFailed?: boolean;
  sportsbookOddsFound?: number;
  polymarketCleanMoneylineFound?: number;
  rowsWithModelProbability?: number;
  rowsWithRealPrice?: number;
  officialPicks?: number;
  moneylineLeans?: number;
  modelOnlyLeans?: number;
  oddsOnlyWatch?: number;
  noBets?: number;
  usedSportsbookFallbackGames?: boolean;
  rowsWithEdge?: number;
  modelAttachFailures?: ModelAttachFailureCounts;
  moneylinePricesFound?: number;
  leansWithRealPrice?: number;
  rejectionCounts?: RejectionCounts;
  topCandidateSummary?: TopCandidateSummary;
  bankroll: number;
  currentBankroll: number;
  startingBankroll: number;
  stakePercent: number;
  stakeAmount: number;
  totalOpenStakeAmount: number;
  totalOpenExposurePercent: number;
  remainingUnexposedBankroll: number;
  openStrongBuyCount: number;
  exposureLabel: string;
  warnings: string[];
  generatedAt: string;
};

type BestBetsTodayResponse = {
  status: "available" | "partial" | "timeout";
  ok: true;
  realMoneyTrading: "OFF";
  manualOnly: true;
  paperOnly: true;
  bestBetsDiagnostics: BestBetsDiagnosticsResponse;
  bestBetRows: BestBetRowResponse[];
  strongBuyRows: BestBetRowResponse[];
  strongBuyLedgerDiagnostics: Awaited<ReturnType<typeof loadStrongBuyLedgerStatus>> | null;
  gameStatusValidationDiagnostics: Record<string, unknown> | null;
  warnings: string[];
  officialPicks: MoneylineCandidateResponse[];
  moneylineLeans: MoneylineCandidateResponse[];
  modelOnlyLeans: MoneylineCandidateResponse[];
  oddsOnlyWatch: OddsOnlyWatchResponse[];
  noBets: MoneylineCandidateResponse[];
  diagnostics: {
    priceSourceUsed: PriceSourceUsed;
    moneylinePricesFound: number;
    leansWithRealPrice: number;
    modelOnlyLeans: number;
    oddsOnlyWatch: number;
    scanGamesFound: number;
    scanFailed: boolean;
    sportsbookOddsFound: number;
    polymarketCleanMoneylineFound: number;
    rowsWithModelProbability: number;
    rowsWithRealPrice: number;
    rowsWithEdge: number;
    officialPicks: number;
    moneylineLeans: number;
    noBets: number;
    usedSportsbookFallbackGames: boolean;
    modelAttachFailures: ModelAttachFailureCounts;
    whyNoOfficialPicks: string[];
    rejectionCounts: RejectionCounts;
    topCandidateSummary: TopCandidateSummary;
  };
};

const STARTING_BANKROLL = 1000;
const STAKE_PERCENT = 5;
const TIMEOUT_MS = 20_000;

function mapMlbDataQualityToProbabilityQuality(value?: string | null): AstroddsDataQuality {
  const quality = (value ?? "").trim().toUpperCase();
  if (quality === "A" || quality === "B") return "HIGH";
  if (quality === "C") return "MEDIUM";
  if (quality === "D") return "LOW";
  return "VERY_LOW";
}

function mapModelConfidenceToLabel(confidence?: number | null): AstroddsConfidence {
  if (typeof confidence !== "number" || !Number.isFinite(confidence)) return "NO_BET";
  if (confidence >= 85) return "ELITE";
  if (confidence >= 75) return "STRONG";
  if (confidence >= 60) return "MEDIUM";
  if (confidence >= 50) return "LOW";
  return "NO_BET";
}

function modelConfidenceFromProbability(probability?: number | null) {
  if (typeof probability !== "number" || !Number.isFinite(probability)) return undefined;
  return Math.max(0, Math.min(100, probability * 100));
}

function mapPredictionDecision(edge?: number | null): AstroddsDecision {
  if (typeof edge !== "number" || !Number.isFinite(edge)) return "WAIT";
  if (edge >= 0.06) return "STRONG_BUY";
  if (edge >= 0.03) return "BUY";
  if (edge > 0) return "WATCH";
  return "WAIT";
}

function canonicalMlbTeamName(team?: string | null) {
  return findMlbTeamProfile(team ?? undefined)?.canonicalName ?? normalizeText(team ?? "");
}

function canonicalGameDate(value?: string | null) {
  if (!value) return "";
  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) return parsed.toISOString().slice(0, 10);
  return normalizeText(value).slice(0, 10);
}

function canonicalGameKey(date?: string | null, awayTeam?: string | null, homeTeam?: string | null) {
  return [canonicalGameDate(date), canonicalMlbTeamName(awayTeam), canonicalMlbTeamName(homeTeam)]
    .filter((part) => Boolean(part && part.trim()))
    .join("|");
}

function predictionTeamPairKey(awayTeam?: string | null, homeTeam?: string | null) {
  return [canonicalMlbTeamName(awayTeam), canonicalMlbTeamName(homeTeam)]
    .filter((part) => Boolean(part && part.trim()))
    .join("|");
}

function isUsefulProbability(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0 && value < 1;
}

async function loadDailyPredictionCache() {
  const today = canonicalGameDate(new Date().toISOString());
  const candidates = [
    path.join(process.cwd(), ".astrodds", "daily", today, "today_predictions.json"),
    path.join(process.cwd(), "mlb-engine", "outputs", "today_predictions.json"),
  ];

  for (const sourcePath of candidates) {
    try {
      await access(sourcePath);
      return loadPythonMlbPredictions(sourcePath);
    } catch {
      continue;
    }
  }

  return {
    available: false,
    sourcePath: candidates[0],
    predictions: [] as PythonMlbPrediction[],
    warnings: ["No local model prediction cache available for MLB moneyline calibration."],
  };
}

function statusRank(status: BestBetStatus) {
  if (status === "strong_buy") return 4;
  if (status === "daily_pick") return 3;
  if (status === "buy") return 2;
  if (status === "watch") return 1;
  return 0;
}

function riskLevelFromScore(score: number): BestBetRiskLevel {
  if (score >= 78) return "low";
  if (score >= 58) return "medium";
  if (score >= 35) return "high";
  return "unknown";
}

function gameStatusForValidation(validation?: AstroddsGameScan["gameStatusValidation"]): BestBetGameStatus {
  if (!validation) return "unknown";
  if (validation.isPostponed || validation.isSuspended || validation.isCancelled || validation.isFinal || validation.isDateMismatch) return "blocked";
  if (validation.isGameActiveForBetting) return "pre_game";
  if (validation.isLive) return "live";
  return "unknown";
}

function uniqueStrings(values: Array<string | undefined>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value && value.trim()))));
}

function comparableText(value?: string | null) {
  return normalizeText(value ?? "");
}

function teamNameMatches(left?: string | null, right?: string | null) {
  const normalizedLeft = comparableText(left);
  const normalizedRight = comparableText(right);
  if (!normalizedLeft || !normalizedRight) return false;
  return (
    normalizedLeft === normalizedRight ||
    normalizedLeft.includes(normalizedRight) ||
    normalizedRight.includes(normalizedLeft)
  );
}

function hasYesNoOutcomes(market: AstroddsMarketScan) {
  return (market.outcomes ?? []).length > 0 && (market.outcomes ?? []).every((outcome) => /^(yes|no)$/i.test(outcome.trim()));
}

function isCleanMoneylineMarket(market: AstroddsMarketScan) {
  const marketText = normalizeText(`${market.marketTitle} ${market.pick} ${(market.outcomes ?? []).join(" ")}`);
  if (!marketText) return false;
  if (market.betType !== "MONEYLINE" && inferBetType(marketText) !== "MONEYLINE") return false;
  if (hasYesNoOutcomes(market)) return false;
  if (/\b(extra innings|first 5 innings|1st 5 innings|f5 innings|f5|team total|player prop|props?|o\/u|over\/under)\b/.test(marketText)) {
    return false;
  }
  if (/\b(over|under|total|spread|run line|runline|prop|future|futures|championship|division|series|playoff|playoffs|mvp|cy young)\b/.test(marketText)) {
    return false;
  }
  if (/\b(yes|no)\b/.test(marketText) && !/\b(winner|win|moneyline|ml)\b/.test(marketText)) return false;
  return true;
}

type OddsRows = Awaited<ReturnType<typeof fetchConfiguredSportsOdds>>["odds"];

type MoneylinePriceSource = {
  priceSourceUsed: PriceSourceUsed;
  marketProbability: number | null;
  marketConnected: boolean;
  sourceLabel: string;
};

function findOddsMoneylineForGame(game: AstroddsGameScan, oddsRows: OddsRows, selectedSide?: string) {
  if (!selectedSide) return undefined;
  const selected = comparableText(selectedSide);
  return oddsRows.find((row) => {
    if (row.marketType !== "moneyline") return false;
    if (!teamNameMatches(row.homeTeam, game.homeTeam)) return false;
    if (!teamNameMatches(row.awayTeam, game.awayTeam)) return false;
    return comparableText(row.side) === selected;
  });
}

function resolveMoneylinePriceSource(
  game: AstroddsGameScan,
  market: AstroddsMarketScan | undefined,
  oddsRows: OddsRows,
  selectedSide?: string,
): MoneylinePriceSource {
  const cleanPolymarketPrice =
    market && market.category !== "Sportsbook" && isCleanMoneylineMarket(market) && typeof market.currentPrice === "number" && Number.isFinite(market.currentPrice)
      ? market.currentPrice
      : null;

  if (cleanPolymarketPrice !== null) {
    return {
      priceSourceUsed: "polymarket",
      marketProbability: cleanPolymarketPrice,
      marketConnected: true,
      sourceLabel: "Polymarket moneyline",
    };
  }

  const oddsMatch = findOddsMoneylineForGame(game, oddsRows, selectedSide);
  if (oddsMatch && typeof oddsMatch.impliedProbability === "number" && Number.isFinite(oddsMatch.impliedProbability)) {
    return {
      priceSourceUsed: "sportsbook",
      marketProbability: oddsMatch.impliedProbability,
      marketConnected: true,
      sourceLabel: `Sportsbook odds fallback (${oddsMatch.provider})`,
    };
  }

  return {
    priceSourceUsed: "model_only",
    marketProbability: null,
    marketConnected: false,
    sourceLabel: "Model only",
  };
}

function rowSortScore(row: BestBetRowResponse) {
  return (
    statusRank(row.status) * 10000 +
    (row.diagnosticCalibratedEdgePct ?? row.diagnosticRawEdgePct ?? 0) * 100 +
    (row.matchConfidence === "high" ? 100 : row.matchConfidence === "medium" ? 50 : 0) -
    row.riskScore
  );
}

function buildWhyNoOfficialPicks(rows: BestBetRowResponse[], moneylineLeans: MoneylineCandidateResponse[], noBets: MoneylineCandidateResponse[]) {
  const reasons = new Map<string, number>();
  const add = (reason: string, count = 1) => {
    if (count <= 0) return;
    reasons.set(reason, (reasons.get(reason) ?? 0) + count);
  };

  add("No clean moneyline market connected", rows.filter((row) => !row.marketConnected).length || 0);
  add("Missing market prices", rows.filter((row) => row.marketProbability === null || row.marketProbability === undefined).length || 0);
  add("No positive edge", rows.filter((row) => typeof row.diagnosticCalibratedEdgePct !== "number" || row.diagnosticCalibratedEdgePct <= 0).length || 0);
  add("Low match confidence", rows.filter((row) => row.matchConfidence === "low" || row.matchConfidence === "none").length || 0);
  add("All candidates high risk", rows.filter((row) => row.riskLevel === "high" || row.riskLevel === "unknown").length || 0);
  add("No official daily picks qualified yet", rows.filter((row) => row.status === "watch" || row.status === "blocked").length || 0);
  add("Model-only leans still need a market price", moneylineLeans.length || 0);
  add("Model WAIT signals remain no-bets", noBets.length || 0);

  return Array.from(reasons.keys()).slice(0, 6);
}

function buildWhyNoDailyPicks(rows: BestBetRowResponse[]) {
  return buildWhyNoOfficialPicks(rows, [], []);
}

function buildCandidateKeyReasons(row: BestBetRowResponse, game?: AstroddsGameScan) {
  return uniqueStrings([
    row.mainReason,
    row.whyDailyPick,
    row.whyNotStrongBuy,
    ...(row.reasons ?? []),
    ...(row.warnings ?? []),
    ...(game?.modelPick?.missingDataWarnings ?? []),
    game?.modelPick?.modelReason,
  ]).slice(0, 4);
}

function buildMoneylineCandidate(row: BestBetRowResponse, game?: AstroddsGameScan): MoneylineCandidateResponse | null {
  const modelPick = game?.modelPick;
  const gameStatus = gameStatusForValidation(row.gameStatusValidation);
  const selectedSide = row.selectedSide && row.selectedSide !== "MODEL ONLY"
    ? row.selectedSide
    : modelPick?.modelLeanTeam ?? undefined;

  const calibratedProbability = typeof row.calibratedProbability === "number" && Number.isFinite(row.calibratedProbability)
    ? row.calibratedProbability
    : modelPick
      ? modelPick.modelConfidence / 100
      : null;
  const marketProbability = typeof row.marketProbability === "number" && Number.isFinite(row.marketProbability) ? row.marketProbability : null;
  const edge = marketProbability !== null && calibratedProbability !== null ? calibratedProbability - marketProbability : null;
  const modelConfidence = modelPick?.modelConfidence ?? Math.round((calibratedProbability ?? 0) * 100);
  const matchConfidence: MoneylineCandidateResponse["matchConfidence"] =
    gameStatus === "blocked"
      ? "none"
      : marketProbability !== null
        ? row.matchConfidence === "high" || row.matchConfidence === "medium"
          ? row.matchConfidence
          : modelConfidence >= 70
            ? "high"
            : modelConfidence >= 58
              ? "medium"
              : "low"
        : modelConfidence >= 70
          ? "high"
          : modelConfidence >= 58
            ? "medium"
            : "low";
  const status: MoneylineCandidateStatus =
    gameStatus === "blocked"
      ? "no_bet"
      : row.status === "strong_buy" || row.status === "daily_pick"
      ? "official_pick"
      : marketProbability !== null && edge !== null && edge >= 0.03 && matchConfidence !== "low" && matchConfidence !== "none"
        ? "moneyline_lean"
        : modelPick?.modelLeanSide && modelPick.modelLeanSide !== "WAIT"
          ? "moneyline_lean"
          : "no_bet";

  const whyNotOfficialYet = uniqueStrings([
    gameStatus === "blocked" ? "Game status is blocked for pre-game betting." : undefined,
    marketProbability === null ? "No clean moneyline market price connected." : undefined,
    edge === null ? "Moneyline edge cannot be calculated without a market price." : undefined,
    edge !== null && edge < 0.03 ? "Edge is below the 3% official pick gate." : undefined,
    matchConfidence === "low" || matchConfidence === "none" ? "Confidence is not high enough for an official pick." : undefined,
    game?.modelPick?.action === "WAIT_FOR_ODDS" ? "Waiting for a matched market price." : undefined,
    game?.modelPick?.officialBetBlockedReason,
  ]);

  return {
    bestBetId: row.bestBetId,
    gameId: row.gameId,
    date: row.date,
    homeTeam: row.homeTeam,
    awayTeam: row.awayTeam,
    selectedSide,
    marketType: "moneyline" as const,
    status,
    gameStatus: gameStatusForValidation(row.gameStatusValidation),
    marketConnected: Boolean(row.marketConnected),
    marketProbability,
    calibratedProbability,
    edge,
    matchConfidence,
    riskLevel: row.riskLevel,
    modelScore: Math.round(modelPick?.modelScore ?? row.riskScore),
    dataQuality: modelPick?.dataQuality ?? "UNKNOWN",
    keyReasons: buildCandidateKeyReasons(row, game),
    whyNotOfficialYet,
    mainReason: row.mainReason,
    warnings: row.warnings,
    blockReasons: row.blockReasons,
    stakeRecommendation: row.stakeRecommendation,
    paperOnly: true as const,
    realMoneyDisabled: true as const,
  };
}

function candidateSortScore(candidate: MoneylineCandidateResponse) {
  const confidenceScore = candidate.matchConfidence === "high" ? 200 : candidate.matchConfidence === "medium" ? 120 : candidate.matchConfidence === "low" ? 50 : 0;
  const marketScore = candidate.marketProbability !== null ? candidate.marketProbability * 100 : 0;
  const edgeScore = candidate.edge !== null ? candidate.edge * 1000 : 0;
  return candidate.status === "official_pick"
    ? 100000 + confidenceScore + edgeScore
    : 1000 + confidenceScore + candidate.modelScore + marketScore + edgeScore - (candidate.riskLevel === "high" ? 60 : candidate.riskLevel === "unknown" ? 80 : 0);
}

function buildRejectionCounts(rows: BestBetRowResponse[], games: AstroddsGameScan[]): RejectionCounts {
  return {
    noCleanMoneylineMarket: rows.filter((row) => !row.marketConnected).length,
    selectedSideNotTeam: rows.filter((row) => !row.selectedSide || row.selectedSide === "MODEL ONLY").length,
    marketProbabilityMissing: rows.filter((row) => row.marketProbability === null || row.marketProbability === undefined).length,
    calibratedProbabilityMissing: rows.filter((row) => row.calibratedProbability === null || row.calibratedProbability === undefined).length,
    edgeTooLow: rows.filter((row) => typeof row.diagnosticCalibratedEdgePct === "number" && row.diagnosticCalibratedEdgePct <= 0).length,
    confidenceTooLow: games.filter((game) => !game.modelPick || game.modelPick.modelConfidence < 58).length,
    gameStatusNotPreGame: rows.filter((row) => gameStatusForValidation(row.gameStatusValidation) !== "pre_game").length,
    modelSignalTooWeak: games.filter((game) => game.modelPick?.modelLeanSide === "WAIT" || !game.modelPick || game.modelPick.modelConfidence < 58).length,
    dataQualityTooLow: games.filter((game) => game.modelPick?.dataQuality === "C" || game.modelPick?.dataQuality === "D" || game.modelPick?.dataQuality === "F").length,
    thresholdTooStrict: 0,
  };
}

function buildTopCandidateSummary(officialPicks: MoneylineCandidateResponse[], moneylineLeans: MoneylineCandidateResponse[], noBets: MoneylineCandidateResponse[]): TopCandidateSummary {
  const top10MoneylineCandidates = [...moneylineLeans].sort((left, right) => candidateSortScore(right) - candidateSortScore(left)).slice(0, 10);
  const bestCandidate = top10MoneylineCandidates[0];

  return {
    totalMoneylineCandidates: moneylineLeans.length,
    officialPicks: officialPicks.length,
    moneylineLeans: moneylineLeans.length,
    noBets: noBets.length,
    bestCandidate: bestCandidate
      ? {
          game: `${bestCandidate.awayTeam ?? "Away"} @ ${bestCandidate.homeTeam ?? "Home"}`,
          selectedSide: bestCandidate.selectedSide,
          marketProbability: bestCandidate.marketProbability,
          calibratedProbability: bestCandidate.calibratedProbability,
          edge: bestCandidate.edge,
          matchConfidence: bestCandidate.matchConfidence,
          riskLevel: bestCandidate.riskLevel,
          mainReason: bestCandidate.mainReason,
          whyNotOfficialYet: bestCandidate.whyNotOfficialYet,
        }
      : undefined,
    top10MoneylineCandidates,
    thresholdNotes: [
      "Official daily picks stay gated at 3% edge or better once a clean moneyline market price exists.",
      "Strong Buy stays stricter than daily leans.",
      "Thresholds are not the blocker today; clean moneyline market prices are missing.",
    ],
  };
}

function bestMoneylineMarketForGame(game: AstroddsGameScan) {
  const cleanMarkets = game.markets.filter(isCleanMoneylineMarket);
  return [...cleanMarkets].sort((left, right) => {
    const leftRank = statusRank(left.decision === "ELITE" || left.decision === "STRONG_BUY" ? "strong_buy" : left.decision === "BUY" ? "buy" : left.decision === "WATCH" ? "watch" : "blocked");
    const rightRank = statusRank(right.decision === "ELITE" || right.decision === "STRONG_BUY" ? "strong_buy" : right.decision === "BUY" ? "buy" : right.decision === "WATCH" ? "watch" : "blocked");
    return rightRank - leftRank || ((right.score?.total ?? 0) - (left.score?.total ?? 0)) || ((right.edge?.edgeScore ?? 0) - (left.edge?.edgeScore ?? 0));
  })[0];
}

function buildRow(
  game: AstroddsGameScan,
  market: AstroddsMarketScan | undefined,
  oddsRows: OddsRows,
  stakeAmount: number,
  totalOpenExposurePercent: number,
  exposureLabel: string,
): BestBetRowResponse {
  const validation = game.gameStatusValidation;
  const gameStatusBlockReasons = validation?.gameStatusBlockReasons ?? [];
  const gameIsValid = validation
    ? validation.isGameActiveForBetting && !validation.isPostponed && !validation.isSuspended && !validation.isCancelled && !validation.isFinal && !validation.isDateMismatch
    : true;
  const hasMarket = Boolean(market);
  const selectedSide = hasMarket ? market?.pick : game.modelPick?.modelLeanTeam ?? "MODEL ONLY";
  const marketDecision = market?.decision;
  const marketMatchReason = market?.matchReason;
  const marketEdge = market?.edge;
  const marketOrderBook = market?.orderBook;
  const priceSource = resolveMoneylinePriceSource(game, market, oddsRows, selectedSide);
  const marketPrice = priceSource.marketProbability;
  const hasPrice = marketPrice !== null;
  const hasModelProbability =
    typeof market?.probability?.modelProbability === "number" ||
    typeof market?.edge?.modelProbability === "number" ||
    typeof game.modelPick?.modelConfidence === "number";
  const modelProbability = typeof market?.probability?.modelProbability === "number"
    ? market.probability.modelProbability
    : typeof market?.edge?.modelProbability === "number"
      ? market.edge.modelProbability
      : typeof game.modelPick?.modelConfidence === "number"
        ? game.modelPick.modelConfidence / 100
        : null;
  const rawEdge = modelProbability !== null && marketPrice !== null ? modelProbability - marketPrice : null;
  const rawEdgePct = rawEdge !== null ? rawEdge * 100 : null;
  const calibratedEdge = typeof market?.edge?.edge === "number" ? market.edge.edge : rawEdge;
  const calibratedEdgePct = calibratedEdge !== null ? calibratedEdge * 100 : null;
  const score = Math.max(0, Math.min(100, Math.round(game.modelPick?.modelScore ?? market?.score?.total ?? 0)));
  const riskLevel = riskLevelFromScore(score);
  const matchConfidence: BestBetRowResponse["matchConfidence"] =
    priceSource.priceSourceUsed === "sportsbook" && !hasModelProbability
      ? "medium"
      : hasPrice
        ? "high"
        : hasMarket
          ? "medium"
          : "none";
  const reasons = uniqueStrings([
    priceSource.sourceLabel,
    marketEdge?.simpleWhy,
    marketMatchReason,
    game.modelPick?.modelReason,
    game.keyPlayerStatus,
    game.weather?.summary,
    marketOrderBook?.summary,
    market?.unmatchedReason,
    game.unmatchedReason,
  ]);
  const warnings = uniqueStrings([
    ...(game.gameStatusValidation?.warnings ?? []),
    ...(game.modelPick?.missingDataWarnings ?? []),
    !hasMarket && hasPrice ? "Sportsbook odds fallback connected." : undefined,
    market?.unmatchedReason,
    marketMatchReason ? undefined : market?.matchReason,
  ]);
  const blockReasons = uniqueStrings([
    ...(validation?.gameStatusBlockReasons ?? []),
    !hasMarket && !hasPrice ? "No matched market row." : undefined,
    !hasPrice ? "No market price available." : undefined,
  ]);
  const downgradeReasons = uniqueStrings([
    !hasMarket && !hasPrice ? "No clean moneyline market connected." : undefined,
    !hasPrice ? "No market price available." : undefined,
    !hasMarket && hasPrice ? "Odds fallback connected without a matched Polymarket market." : undefined,
    matchConfidence === "medium" ? "Match confidence is only medium." : undefined,
    riskLevel === "high" ? "Risk remains elevated." : undefined,
  ]);

  let status: BestBetStatus = "blocked";
  let mainReason = "";
  let whyNotStrongBuy = "";
  let whyDailyPick = "";
  let telegramEligible = false;
  let saveEligible = false;
  let stakeRecommendation = "Manual only";

  if (!gameIsValid) {
    status = "blocked";
    mainReason = gameStatusBlockReasons[0] ?? "Game status blocked.";
    whyNotStrongBuy = mainReason;
  } else if (!hasPrice) {
    status = "watch";
    mainReason = hasMarket ? "No market price available." : "MODEL ONLY - no market price";
    whyNotStrongBuy = "Only moneyline/team winner markets are eligible for Daily Picks and Strong Buy.";
    whyDailyPick = "MODEL ONLY - no market price";
    stakeRecommendation = "Manual review only";
  } else if ((marketDecision === "ELITE" || marketDecision === "STRONG_BUY") && (rawEdge ?? 0) > 0) {
    status = "strong_buy";
    mainReason = marketEdge?.simpleWhy ?? marketMatchReason ?? (priceSource.priceSourceUsed === "sportsbook" ? "Sportsbook odds fallback connected with a positive edge." : "Strong model edge with matched MLB market.");
    whyNotStrongBuy = "";
    telegramEligible = true;
    saveEligible = true;
    stakeRecommendation = `${STAKE_PERCENT}% paper bankroll / $${stakeAmount.toFixed(2)}`;
  } else if ((rawEdge ?? 0) > 0.05 || marketDecision === "BUY") {
    status = "buy";
    mainReason = marketEdge?.simpleWhy ?? marketMatchReason ?? (priceSource.priceSourceUsed === "sportsbook" ? "Sportsbook odds fallback connected with a positive edge." : "Positive edge, but not strong enough for Strong Buy.");
    whyNotStrongBuy = "Edge is positive, but the gate is still too strict for Strong Buy.";
    stakeRecommendation = `${STAKE_PERCENT}% paper bankroll / $${stakeAmount.toFixed(2)}`;
  } else if ((rawEdge ?? 0) > 0.02 || marketDecision === "WATCH") {
    status = "watch";
    mainReason = marketEdge?.simpleWhy ?? marketMatchReason ?? (priceSource.priceSourceUsed === "sportsbook" ? "Sportsbook odds fallback connected, but the edge is still monitor-only." : "Interesting MLB market, but it stays monitor-only.");
    whyNotStrongBuy = "Edge and/or confidence are not strong enough yet.";
  } else {
    status = "watch";
    mainReason = marketEdge?.simpleWhy ?? marketMatchReason ?? (priceSource.priceSourceUsed === "sportsbook" ? "Sportsbook odds fallback connected, but the edge is not strong enough." : "Market matched, but the edge is not strong enough.");
    whyNotStrongBuy = "The price does not clear the current manual-review threshold.";
  }

  if (status === "watch" && !hasPrice) {
    whyDailyPick = "MODEL ONLY - no market price";
  }

  return {
    bestBetId: `${game.id}:${market?.marketId ?? "model-only"}`,
    gameId: game.id,
    date: game.startTime,
    homeTeam: game.homeTeam,
    awayTeam: game.awayTeam,
    gameStatusValidation: validation,
    mlbStatus: validation?.mlbStatus ?? game.liveStatus,
    gameStatusBlockReasons,
    selectedSide: hasMarket ? market?.pick : game.modelPick?.modelLeanTeam ?? "MODEL ONLY",
    marketType: "moneyline",
    status,
    statusRank: statusRank(status),
    calibratedProbability: modelProbability,
    marketProbability: marketPrice,
    diagnosticRawEdgePct: rawEdgePct,
    diagnosticCalibratedEdge: calibratedEdge,
    diagnosticCalibratedEdgePct: calibratedEdgePct,
    matchConfidence,
    riskLevel,
    riskScore: score,
    bankroll: STARTING_BANKROLL,
    stakePercent: STAKE_PERCENT,
    stakeAmount: status === "strong_buy" ? stakeAmount : 0,
    totalOpenExposurePercent,
    exposureLabel,
    reasons,
    mainReason,
    whyNotStrongBuy,
    whyDailyPick,
    warnings,
    blockReasons,
    downgradeReasons,
    telegramEligible,
    saveEligible,
    stakeRecommendation,
    priceSourceUsed: priceSource.priceSourceUsed,
    manualOnly: true,
    paperOnly: true,
    realMoneyDisabled: true,
    marketConnected: hasPrice,
  };
}

function buildBestBetRows(
  scan: Awaited<ReturnType<typeof scanAstroddsSport>>,
  ledgerDiagnostics: Awaited<ReturnType<typeof loadStrongBuyLedgerStatus>> | null,
  oddsRows: OddsRows,
) {
  const scheduleGames = scan.games.filter((game) => game.sport === "MLB" && !game.source.toLowerCase().includes("market-only"));
  const currentBankroll = ledgerDiagnostics?.currentBankroll ?? STARTING_BANKROLL;
  const totalOpenStakeAmount = ledgerDiagnostics?.totalOpenStakeAmount ?? 0;
  const totalOpenExposurePercent = ledgerDiagnostics?.totalOpenExposurePercent ?? 0;
  const exposureLabel = ledgerDiagnostics?.exposureLabel ?? "Paper only";
  const stakeAmount = Math.max(1, currentBankroll * (STAKE_PERCENT / 100));

  const rows = scheduleGames.map((game) => buildRow(game, bestMoneylineMarketForGame(game), oddsRows, stakeAmount, totalOpenExposurePercent, exposureLabel));
  const promotable = rows
    .filter((row) => row.status !== "blocked" && row.marketProbability !== null && row.marketProbability !== undefined)
    .sort((left, right) => rowSortScore(right) - rowSortScore(left));
  const dailyPickTarget = Math.min(6, promotable.length);

  for (let index = 0; index < dailyPickTarget; index += 1) {
    const row = promotable[index];
    if (row.status === "strong_buy") continue;
    row.status = "daily_pick";
    row.statusRank = statusRank(row.status);
    row.whyDailyPick = row.whyDailyPick ?? "Daily Pick selected as one of the best valid MLB Moneyline candidates.";
    row.stakeRecommendation = `${STAKE_PERCENT}% paper bankroll / $${stakeAmount.toFixed(2)}`;
  }

  for (const row of rows) {
    if (row.status === "daily_pick") {
      row.saveEligible = false;
      row.telegramEligible = false;
      row.mainReason = row.mainReason || row.whyDailyPick || "Daily Pick selected for manual review.";
    }
    if (row.status === "buy") {
      row.telegramEligible = false;
      row.saveEligible = false;
    }
    if (row.status === "watch") {
      row.telegramEligible = false;
      row.saveEligible = false;
    }
  }

  rows.sort((left, right) => rowSortScore(right) - rowSortScore(left));

  const strongBuyRows = rows.filter((row) => row.status === "strong_buy");
  const actionableCount = rows.filter((row) => row.status === "strong_buy" || row.status === "daily_pick" || row.status === "buy").length;
  const validCandidateCount = rows.filter((row) => row.status !== "blocked").length;
  const dailyPickCount = rows.filter((row) => row.status === "daily_pick").length;
  const buyCount = rows.filter((row) => row.status === "buy").length;
  const watchCount = rows.filter((row) => row.status === "watch").length;
  const blockedCount = rows.filter((row) => row.status === "blocked").length;
  const whyNoDailyPicks = dailyPickCount > 0 ? [] : buildWhyNoDailyPicks(rows);
  const priceSourceUsed: PriceSourceUsed = rows.some((row) => row.priceSourceUsed === "polymarket")
    ? "polymarket"
    : rows.some((row) => row.priceSourceUsed === "sportsbook")
      ? "sportsbook"
      : "model_only";

  const bestBetsDiagnostics: BestBetsDiagnosticsResponse = {
    available: true,
    totalRowsEvaluated: rows.length,
    strongBuyCount: strongBuyRows.length,
    dailyPickCount,
    buyCount,
    watchCount,
    blockedCount,
    actionableCount,
    visibleBoardCount: rows.filter((row) => row.status !== "blocked").length,
    targetDailyPickMin: 2,
    targetDailyPickMax: 6,
    validCandidateCount,
    whyNoDailyPicks,
    bankroll: currentBankroll,
    currentBankroll,
    startingBankroll: STARTING_BANKROLL,
    stakePercent: STAKE_PERCENT,
    stakeAmount,
    totalOpenStakeAmount,
    totalOpenExposurePercent,
    remainingUnexposedBankroll: Math.max(0, currentBankroll - totalOpenStakeAmount),
    openStrongBuyCount: ledgerDiagnostics?.openStrongBuyCount ?? strongBuyRows.length,
    exposureLabel,
    priceSourceUsed,
    moneylinePricesFound: rows.filter((row) => typeof row.marketProbability === "number").length,
    leansWithRealPrice: rows.filter((row) => (row.status === "daily_pick" || row.status === "strong_buy" || row.status === "buy") && typeof row.marketProbability === "number").length,
    modelOnlyLeans: rows.filter((row) => (row.status === "daily_pick" || row.status === "strong_buy" || row.status === "buy" || row.status === "watch") && (row.marketProbability === null || row.marketProbability === undefined)).length,
    warnings: uniqueStrings([
      ...(scan.warnings ?? []),
      dailyPickCount > 0 ? undefined : "No Strong Buy today - showing the best available moneyline leans and watch rows for manual review.",
    ]),
    generatedAt: scan.generatedAt,
  };

  return {
    bestBetsDiagnostics,
    bestBetRows: rows.map((row: any, index: number) => withAstroddsEngineV2Fields(row, index)),
    strongBuyRows,
  };
}

function groupMoneylineOddsByGame(oddsRows: OddsRows) {
  const grouped = new Map<string, OddsRows>();
  for (const row of oddsRows) {
    if (row.marketType !== "moneyline") continue;
    if (typeof row.impliedProbability !== "number" || !Number.isFinite(row.impliedProbability)) continue;
    const key = row.gameId ?? `${comparableText(row.awayTeam)}|${comparableText(row.homeTeam)}|${row.commenceTime ?? ""}`;
    const existing = grouped.get(key) ?? [];
    existing.push(row);
    grouped.set(key, existing);
  }
  return grouped;
}

type DailyPredictionAttachResult = {
  prediction?: PythonMlbPrediction;
  selectedSideProbability?: number;
  modelPick?: AstroddsGameScan["modelPick"];
  probability?: AstroddsProbabilityAssessment;
  attachReason?: string;
  failureReason?: keyof ModelAttachFailureCounts;
};


function modelProbabilityGapPct(probability: number | null | undefined) {
  if (typeof probability !== "number" || !Number.isFinite(probability) || probability <= 0 || probability >= 1) {
    return null;
  }

  return Math.abs((probability * 2) - 1) * 100;
}
function buildDailyModelPick(prediction: PythonMlbPrediction, homeTeam: string, awayTeam: string): AstroddsGameScan["modelPick"] | undefined {
  if (!isUsefulProbability(prediction.calibratedProbability)) return undefined;
  const homeProbability = prediction.calibratedProbability;
  const homeLean = homeProbability >= 0.5;
  const confidence = typeof prediction.confidence === "number" && Number.isFinite(prediction.confidence)
    ? prediction.confidence
    : homeProbability * 100;
  return {
    modelLeanSide: homeLean ? "HOME" : "AWAY",
    modelLeanTeam: homeLean ? homeTeam : awayTeam,
    modelConfidence: confidence,
    modelScore: Math.round(confidence),
    pitcherScore: 0,
    lineupScore: 0,
    injuryScore: 0,
    teamFormScore: 0,
    weatherScore: 0,
    dataQuality: "partial" as any,
    dataQualityScore: prediction.dataQuality?.toUpperCase() === "A"
      ? 100
      : prediction.dataQuality?.toUpperCase() === "B"
        ? 80
        : prediction.dataQuality?.toUpperCase() === "C"
          ? 60
          : prediction.dataQuality?.toUpperCase() === "D"
            ? 40
            : 20,
    modelReason: prediction.reasons?.[0] ?? prediction.officialDecision ?? "Local daily model cache attached for moneyline calibration.",
    missingDataWarnings: uniqueStrings([
      ...(prediction.calibrationWarnings ?? []),
      ...(prediction.officialEdgeBlockReasons ?? []),
      ...(prediction.risks ?? []),
    ]),
    officialBetBlockedReason: prediction.officialEdgeBlockReasons?.[0] ?? "Python model remains research-only.",
    action: prediction.officialPickEligible ? "WAIT" : "WAIT_FOR_ODDS",
  };
}

function buildProbabilityAssessment(
  selectedSideProbability: number,
  marketProbability: number,
  prediction: PythonMlbPrediction,
): AstroddsProbabilityAssessment {
  const edge = selectedSideProbability - marketProbability;
  return {
    modelProbability: selectedSideProbability,
    marketImpliedProbability: marketProbability,
    edge,
    expectedValue: edge,
    dataQuality: "partial" as any,
    confidence: mapModelConfidenceToLabel(prediction.confidence ?? selectedSideProbability * 100),
    decision: mapPredictionDecision(edge),
    reasons: uniqueStrings([
      prediction.reasons?.[0],
      prediction.officialDecision,
      "Local daily prediction cache matched to sportsbook moneyline game.",
    ]),
    warnings: uniqueStrings([
      ...(prediction.calibrationWarnings ?? []),
      ...(prediction.officialEdgeBlockReasons ?? []),
      ...(prediction.risks ?? []),
    ]),
  };
}

function attachPredictionToOddsGroup(
  best: OddsRows[number],
  dailyPredictionCache: Awaited<ReturnType<typeof loadDailyPredictionCache>>,
): DailyPredictionAttachResult {
  const source = dailyPredictionCache.available ? dailyPredictionCache.predictions : [];
  if (!dailyPredictionCache.available || !source.length) {
    return { failureReason: "noModelCache" };
  }

  const gameDate = canonicalGameDate(best.commenceTime ?? best.lastUpdated);
  const gameKey = canonicalGameKey(gameDate, best.awayTeam, best.homeTeam);
  const teamPairKey = predictionTeamPairKey(best.awayTeam, best.homeTeam);
  const exactMatches = source.filter((prediction) => canonicalGameKey(prediction.date, prediction.awayTeam, prediction.homeTeam) === gameKey);

  const selectedExact = exactMatches.find((prediction) => isUsefulProbability(prediction.calibratedProbability));
  if (selectedExact) {
    const homeProbability = selectedExact.calibratedProbability as number;
    const selectedSide = canonicalMlbTeamName(best.side);
    const homeTeam = canonicalMlbTeamName(best.homeTeam);
    const awayTeam = canonicalMlbTeamName(best.awayTeam);
    const selectedSideProbability = selectedSide === homeTeam ? homeProbability : selectedSide === awayTeam ? 1 - homeProbability : undefined;
    if (!isUsefulProbability(selectedSideProbability)) {
      return { failureReason: "teamAliasMismatch" };
    }

    return {
      prediction: selectedExact,
      selectedSideProbability,
      modelPick: buildDailyModelPick(selectedExact, best.homeTeam, best.awayTeam),
      probability: buildProbabilityAssessment(
        selectedSideProbability,
        best.impliedProbability ?? selectedSideProbability,
        selectedExact,
      ),
      attachReason: "exact_game_key_match",
    };
  }

  const pairMatches = source.filter((prediction) => predictionTeamPairKey(prediction.awayTeam, prediction.homeTeam) === teamPairKey);
  if (pairMatches.length) {
    const matchedByDate = pairMatches
      .map((prediction) => {
        const predictionDate = canonicalGameDate(prediction.date);
        const currentDate = gameDate;
        const dateDelta = Math.abs(new Date(`${predictionDate}T00:00:00Z`).getTime() - new Date(`${currentDate}T00:00:00Z`).getTime());
        return { prediction, dateDelta };
      })
      .sort((left, right) => left.dateDelta - right.dateDelta)[0];

    if (matchedByDate && isUsefulProbability(matchedByDate.prediction.calibratedProbability) && matchedByDate.dateDelta <= 36_000_000) {
      const homeProbability = matchedByDate.prediction.calibratedProbability as number;
      const selectedSide = canonicalMlbTeamName(best.side);
      const homeTeam = canonicalMlbTeamName(best.homeTeam);
      const awayTeam = canonicalMlbTeamName(best.awayTeam);
      const selectedSideProbability = selectedSide === homeTeam ? homeProbability : selectedSide === awayTeam ? 1 - homeProbability : undefined;
      if (!isUsefulProbability(selectedSideProbability)) {
        return { failureReason: "teamAliasMismatch" };
      }

      return {
        prediction: matchedByDate.prediction,
        selectedSideProbability,
        modelPick: buildDailyModelPick(matchedByDate.prediction, best.homeTeam, best.awayTeam),
        probability: buildProbabilityAssessment(
          selectedSideProbability,
          best.impliedProbability ?? selectedSideProbability,
          matchedByDate.prediction,
        ),
        attachReason: "date_proximity_match",
      };
    }

    return { failureReason: "dateMismatch" };
  }

  return { failureReason: "noGameKeyMatch" };
}

function buildSportsbookFallbackRows(
  oddsRows: OddsRows,
  ledgerDiagnostics: Awaited<ReturnType<typeof loadStrongBuyLedgerStatus>> | null,
  dailyPredictionCache: Awaited<ReturnType<typeof loadDailyPredictionCache>>,
) {
  const grouped = groupMoneylineOddsByGame(oddsRows);
  const currentBankroll = ledgerDiagnostics?.currentBankroll ?? STARTING_BANKROLL;
  const totalOpenStakeAmount = ledgerDiagnostics?.totalOpenStakeAmount ?? 0;
  const totalOpenExposurePercent = ledgerDiagnostics?.totalOpenExposurePercent ?? 0;
  const exposureLabel = ledgerDiagnostics?.exposureLabel ?? "Paper only";
  const stakeAmount = Math.max(1, currentBankroll * (STAKE_PERCENT / 100));
  const modelAttachFailures: ModelAttachFailureCounts = {
    noModelCache: 0,
    noGameKeyMatch: 0,
    teamAliasMismatch: 0,
    dateMismatch: 0,
    modelUnavailable: 0,
  };

  const rows = [...grouped.values()]
    .map((group) => {
      const sorted = [...group].sort((left, right) => (right.impliedProbability ?? 0) - (left.impliedProbability ?? 0));
      const best = sorted[0];
      if (!best) return null;
      const attach = attachPredictionToOddsGroup(best, dailyPredictionCache);
      if (attach.failureReason) {
        modelAttachFailures[attach.failureReason] += 1;
      }
      const fallbackReason = attach.prediction
        ? "Sportsbook moneyline odds connected with a calibrated model cache match."
        : "Sportsbook moneyline odds connected, but calibrated model probability could not be attached.";
      const syntheticMarket: AstroddsMarketScan = {
        marketId: best.gameId ?? compactId(`${best.awayTeam}-${best.homeTeam}-${best.commenceTime ?? best.lastUpdated ?? ""}`),
        marketTitle: `${best.awayTeam} @ ${best.homeTeam} Moneyline`,
        outcomes: sorted.map((row) => row.side).filter((side): side is string => Boolean(side)),
        betType: "MONEYLINE",
        pick: best.side,
        currentPrice: best.impliedProbability ?? 0,
        gameDate: best.commenceTime,
        marketDate: best.commenceTime,
        status: "ACTIVE",
        category: "Sportsbook",
        sourceUrl: best.sourceUrl,
        matchReason: fallbackReason,
        probability: attach.probability,
      };
      const syntheticGame: AstroddsGameScan = {
        id: best.gameId ?? compactId(`${best.awayTeam}-${best.homeTeam}-${best.commenceTime ?? best.lastUpdated ?? ""}`),
        sport: "MLB",
        game: best.game,
        homeTeam: best.homeTeam,
        awayTeam: best.awayTeam,
        startTime: best.commenceTime,
        liveStatus: "UNKNOWN",
        keyContext: [fallbackReason],
        keyPlayerStatus: attach.prediction ? "Model cache attached from local daily snapshot." : "Model unavailable - MLB scan failed.",
        markets: [syntheticMarket],
        dataStatus: "PARTIAL",
        source: "Sportsbook moneyline odds fallback",
        modelPick: attach.modelPick,
      };

      const row = buildRow(syntheticGame, syntheticMarket, oddsRows, stakeAmount, totalOpenExposurePercent, exposureLabel);
      if (attach.selectedSideProbability !== undefined) {
        row.calibratedProbability = attach.selectedSideProbability;
        row.diagnosticCalibratedEdge = attach.selectedSideProbability - (row.marketProbability ?? 0);
        row.diagnosticCalibratedEdgePct = row.diagnosticCalibratedEdge * 100;
      }
      row.mainReason = fallbackReason;
      row.whyDailyPick = attach.prediction
        ? attach.attachReason === "date_proximity_match"
          ? "Calibrated model cache matched by team aliases and date proximity."
          : "Calibrated model cache matched to sportsbook moneyline game."
        : "MODEL ONLY - no calibrated model probability available.";
      row.whyNotStrongBuy = attach.prediction
        ? "Sportsbook odds are connected, but the calibrated edge still needs to clear the Strong Buy gate."
        : "Sportsbook odds are connected, but the MLB scan/model path failed.";
      row.warnings = uniqueStrings([
        ...row.warnings,
        fallbackReason,
        attach.attachReason === "date_proximity_match" ? "Model cache attached by date proximity." : undefined,
      ]);
      row.priceSourceUsed = "sportsbook";
      row.marketConnected = true;
      return row;
    })
    .filter((row): row is BestBetRowResponse => Boolean(row))
    .sort((left, right) => (right.marketProbability ?? 0) - (left.marketProbability ?? 0));
  const dedupedRows = Array.from(new Map(rows.map((row) => [row.bestBetId, row] as const)).values());

  for (const row of dedupedRows) {
    row.modelProbabilityGapPct = modelProbabilityGapPct(row.calibratedProbability);
  }
  const promotable = dedupedRows
    .filter((row) =>
      row.status !== "blocked" &&
      row.marketType === "moneyline" &&
      row.selectedSide !== undefined &&
      row.selectedSide !== "MODEL ONLY" &&
      (row.selectedSide === row.awayTeam || row.selectedSide === row.homeTeam) &&
      typeof row.marketProbability === "number" &&
      row.marketProbability >= 0.30 &&
      row.marketProbability <= 0.75 &&
      typeof row.calibratedProbability === "number" &&
      typeof row.diagnosticCalibratedEdgePct === "number" &&
      row.diagnosticCalibratedEdgePct >= 3 &&
      row.diagnosticCalibratedEdgePct <= 25 &&
      typeof row.modelProbabilityGapPct === "number" &&
      row.modelProbabilityGapPct >= 8 &&
      row.matchConfidence !== "low" &&
      row.matchConfidence !== "none" &&
      row.riskLevel !== "high" &&
      row.riskLevel !== "unknown"
    )
    .sort((left, right) => rowSortScore(right) - rowSortScore(left));
  const dailyPickTarget = Math.min(6, promotable.length);

  for (let index = 0; index < dailyPickTarget; index += 1) {
    const row = promotable[index];
    if (row.status === "strong_buy") continue;
    row.status = "daily_pick";
    row.statusRank = statusRank("daily_pick");
    row.whyDailyPick = row.whyDailyPick ?? "Daily Pick selected as one of the best valid MLB Moneyline candidates.";
    row.stakeRecommendation = `${STAKE_PERCENT}% paper bankroll / $${stakeAmount.toFixed(2)}`;
  }

  const officialPicks = dedupedRows
    .map((row) => buildMoneylineCandidate(row))
    .filter((candidate): candidate is MoneylineCandidateResponse => Boolean(candidate && candidate.status === "official_pick"))
    .sort((left, right) => candidateSortScore(right) - candidateSortScore(left));
  const moneylineLeans = dedupedRows
    .map((row) => buildMoneylineCandidate(row))
    .filter((candidate): candidate is MoneylineCandidateResponse => Boolean(candidate && candidate.status === "moneyline_lean"))
    .sort((left, right) => candidateSortScore(right) - candidateSortScore(left));
  const noBets = dedupedRows
    .map((row) => buildMoneylineCandidate(row))
    .filter((candidate): candidate is MoneylineCandidateResponse => Boolean(candidate && candidate.status === "no_bet"))
    .sort((left, right) => candidateSortScore(right) - candidateSortScore(left));
  const oddsOnlyWatchRows = dedupedRows.filter((row) => row.priceSourceUsed === "sportsbook" && row.status === "watch" && (row.calibratedProbability === null || row.calibratedProbability === undefined));
  const modelOnlyLeanRows = dedupedRows.filter((row) => typeof row.calibratedProbability === "number" && (row.marketProbability === null || row.marketProbability === undefined));
  const rowsWithModelProbability = dedupedRows.filter((row) => typeof row.calibratedProbability === "number").length;
  const rowsWithRealPrice = dedupedRows.filter((row) => typeof row.marketProbability === "number").length;
  const rowsWithEdge = dedupedRows.filter((row) => typeof row.marketProbability === "number" && typeof row.calibratedProbability === "number" && typeof row.diagnosticCalibratedEdgePct === "number").length;
  const leansWithRealPrice = dedupedRows.filter((row) => (row.status === "daily_pick" || row.status === "strong_buy" || row.status === "buy") && typeof row.marketProbability === "number").length;
  const whyNoOfficialPicks = officialPicks.length
    ? []
    : uniqueStrings([
        dedupedRows.length ? "Sportsbook odds are connected, but calibrated model probability could not be attached to enough rows for official picks." : "No sportsbook moneyline odds were available to build fallback rows.",
        modelAttachFailures.noModelCache ? `No model cache was available for ${modelAttachFailures.noModelCache} rows.` : undefined,
        modelAttachFailures.noGameKeyMatch ? `${modelAttachFailures.noGameKeyMatch} rows did not find a canonical game-key match.` : undefined,
        modelAttachFailures.teamAliasMismatch ? `${modelAttachFailures.teamAliasMismatch} rows failed team-alias matching.` : undefined,
        modelAttachFailures.dateMismatch ? `${modelAttachFailures.dateMismatch} rows failed date matching.` : undefined,
        modelAttachFailures.modelUnavailable ? `${modelAttachFailures.modelUnavailable} rows found a prediction row but no calibrated probability.` : undefined,
      ]);

  const bestBetsDiagnostics: BestBetsDiagnosticsResponse = {
    available: true,
    totalRowsEvaluated: dedupedRows.length,
    strongBuyCount: dedupedRows.filter((row) => row.status === "strong_buy").length,
    dailyPickCount: dedupedRows.filter((row) => row.status === "daily_pick").length,
    buyCount: dedupedRows.filter((row) => row.status === "buy").length,
    watchCount: dedupedRows.filter((row) => row.status === "watch").length,
    blockedCount: dedupedRows.filter((row) => row.status === "blocked").length,
    actionableCount: dedupedRows.filter((row) => row.status === "strong_buy" || row.status === "daily_pick" || row.status === "buy").length,
    visibleBoardCount: dedupedRows.length,
    targetDailyPickMin: 2,
    targetDailyPickMax: 6,
    validCandidateCount: dedupedRows.length,
    whyNoDailyPicks: dailyPickTarget > 0
      ? []
      : uniqueStrings([
          dedupedRows.length
            ? "Sportsbook moneyline odds are connected, but calibrated model probability could not be attached to enough rows."
            : "No sportsbook moneyline odds were available to build fallback rows.",
          ...whyNoOfficialPicks,
        ]),
    bankroll: currentBankroll,
    currentBankroll,
    startingBankroll: STARTING_BANKROLL,
    stakePercent: STAKE_PERCENT,
    stakeAmount,
    totalOpenStakeAmount,
    totalOpenExposurePercent,
    remainingUnexposedBankroll: Math.max(0, currentBankroll - totalOpenStakeAmount),
    openStrongBuyCount: ledgerDiagnostics?.openStrongBuyCount ?? 0,
    exposureLabel,
    priceSourceUsed: dedupedRows.some((row) => row.priceSourceUsed === "sportsbook") ? "sportsbook" : "model_only",
    moneylinePricesFound: rowsWithRealPrice,
    leansWithRealPrice,
    modelOnlyLeans: modelOnlyLeanRows.length,
    oddsOnlyWatch: oddsOnlyWatchRows.length,
    scanGamesFound: 0,
    scanFailed: true,
    sportsbookOddsFound: oddsRows.length,
    polymarketCleanMoneylineFound: 0,
    rowsWithModelProbability,
    rowsWithRealPrice,
    rowsWithEdge,
    officialPicks: officialPicks.length,
    moneylineLeans: moneylineLeans.length,
    noBets: noBets.length,
    usedSportsbookFallbackGames: dedupedRows.some((row) => row.priceSourceUsed === "sportsbook"),
    modelAttachFailures,
    whyNoOfficialPicks,
    rejectionCounts: {
      noCleanMoneylineMarket: dedupedRows.filter((row) => !row.marketConnected).length,
      selectedSideNotTeam: dedupedRows.filter((row) => !row.selectedSide || row.selectedSide === "MODEL ONLY").length,
      marketProbabilityMissing: dedupedRows.filter((row) => row.marketProbability === null || row.marketProbability === undefined).length,
      calibratedProbabilityMissing: dedupedRows.filter((row) => row.calibratedProbability === null || row.calibratedProbability === undefined).length,
      edgeTooLow: dedupedRows.filter((row) => typeof row.diagnosticCalibratedEdgePct === "number" && row.diagnosticCalibratedEdgePct <= 0).length,
      confidenceTooLow: dedupedRows.filter((row) => row.matchConfidence === "low" || row.matchConfidence === "none").length,
      gameStatusNotPreGame: dedupedRows.filter((row) => gameStatusForValidation(row.gameStatusValidation) !== "pre_game").length,
      modelSignalTooWeak: dedupedRows.filter((row) => row.calibratedProbability === null || row.calibratedProbability === undefined).length,
      dataQualityTooLow: dedupedRows.filter((row) => row.riskLevel === "high" || row.riskLevel === "unknown").length,
      thresholdTooStrict: 0,
    },
    topCandidateSummary: {
      totalMoneylineCandidates: officialPicks.length + moneylineLeans.length + noBets.length,
      officialPicks: officialPicks.length,
      moneylineLeans: moneylineLeans.length,
      noBets: noBets.length,
      top10MoneylineCandidates: [...moneylineLeans].sort((left, right) => candidateSortScore(right) - candidateSortScore(left)).slice(0, 10),
      thresholdNotes: [
        "Sportsbook odds fallback is active because the MLB scan/model path failed.",
        "Local daily prediction cache is attached when the canonical game key matches.",
        "Official picks require positive edge, pre-game status, and a calibratable model probability.",
      ],
    },
    warnings: uniqueStrings([
      ...(ledgerDiagnostics?.warnings ?? []),
      ...(dailyPredictionCache.warnings ?? []),
      ...(dedupedRows.length ? ["MLB scan failed, but sportsbook odds are connected â€” showing odds-based moneyline board."] : []),
    ]),
    generatedAt: new Date().toISOString(),
  };

  const oddsOnlyWatch: OddsOnlyWatchResponse[] = oddsOnlyWatchRows.map((row) => ({
    bestBetId: row.bestBetId,
    gameId: row.gameId,
    date: row.date,
    homeTeam: row.homeTeam,
    awayTeam: row.awayTeam,
    selectedSide: row.selectedSide,
    marketType: "moneyline",
    status: "odds_only_watch",
    marketProbability: row.marketProbability ?? 0,
    calibratedProbability: null,
    edge: null,
    matchConfidence: row.matchConfidence === "high" ? "medium" : "low",
    riskLevel: row.riskLevel,
    mainReason: row.mainReason,
    warnings: row.warnings,
    blockReasons: row.blockReasons,
    priceSourceUsed: "sportsbook",
  }));

  return {
    bestBetsDiagnostics,
    bestBetRows: dedupedRows.map((row: any, index: number) => withAstroddsEngineV2Fields(row, index)),
    strongBuyRows: dedupedRows.filter((row) => row.status === "strong_buy"),
    officialPicks,
    moneylineLeans,
    modelOnlyLeans: modelOnlyLeanRows.map((row) => buildMoneylineCandidate(row)).filter((candidate): candidate is MoneylineCandidateResponse => Boolean(candidate)),
    oddsOnlyWatch,
    noBets,
    diagnostics: {
      priceSourceUsed: bestBetsDiagnostics.priceSourceUsed ?? "sportsbook",
      moneylinePricesFound: rowsWithRealPrice,
      leansWithRealPrice,
      modelOnlyLeans: modelOnlyLeanRows.length,
      oddsOnlyWatch: oddsOnlyWatchRows.length,
      scanGamesFound: 0,
      scanFailed: true,
      sportsbookOddsFound: oddsRows.length,
      polymarketCleanMoneylineFound: 0,
      rowsWithModelProbability,
      rowsWithRealPrice,
      rowsWithEdge,
      officialPicks: officialPicks.length,
      moneylineLeans: moneylineLeans.length,
      noBets: noBets.length,
      usedSportsbookFallbackGames: dedupedRows.some((row) => row.priceSourceUsed === "sportsbook"),
      modelAttachFailures,
      whyNoOfficialPicks,
      rejectionCounts: bestBetsDiagnostics.rejectionCounts ?? {
        noCleanMoneylineMarket: 0,
        selectedSideNotTeam: 0,
        marketProbabilityMissing: 0,
        calibratedProbabilityMissing: 0,
        edgeTooLow: 0,
        confidenceTooLow: 0,
        gameStatusNotPreGame: 0,
        modelSignalTooWeak: 0,
        dataQualityTooLow: 0,
        thresholdTooStrict: 0,
      },
      topCandidateSummary: bestBetsDiagnostics.topCandidateSummary!,
    },
  };
}async function fetchMlbScan(timeoutMs: number) {
  const controller = new AbortController();
  const timeout = setTimeout(() => {
    controller.abort(new Error(`Best Bets MLB scan timed out after ${Math.round(timeoutMs / 1000)} seconds.`));
  }, timeoutMs);

  try {
    const scan = await scanAstroddsSport("MLB", controller.signal);
    return { status: "available" as const, scan, warnings: [] as string[] };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown MLB scan failure.";
    const timedOut = controller.signal.aborted || /timed out/i.test(message);
    return {
      status: timedOut ? ("timeout" as const) : ("partial" as const),
      scan: undefined,
      warnings: [timedOut ? `Best Bets MLB scan timed out after ${Math.round(timeoutMs / 1000)} seconds.` : `Best Bets MLB scan failed: ${message}`],
    };
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchOddsLayer(timeoutMs: number) {
  const controller = new AbortController();
  const timeout = setTimeout(() => {
    controller.abort(new Error(`Best Bets sportsbook odds timed out after ${Math.round(timeoutMs / 1000)} seconds.`));
  }, timeoutMs);

  try {
    const odds = await fetchConfiguredSportsOdds("baseball_mlb", controller.signal);
    const warnings = odds.error ? [`Sportsbook odds source warning: ${odds.error}`] : [];
    return {
      status: odds.status === "FAILED" ? ("partial" as const) : ("available" as const),
      odds: odds.odds,
      warnings,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown sportsbook odds failure.";
    return {
      status: "partial" as const,
      odds: [] as OddsRows,
      warnings: [`Sportsbook odds fetch failed: ${message}`],
    };
  } finally {
    clearTimeout(timeout);
  }
}

async function buildFallbackResponse(
  status: BestBetsTodayResponse["status"],
  warnings: string[],
  ledgerDiagnostics: Awaited<ReturnType<typeof loadStrongBuyLedgerStatus>> | null,
  oddsRows: OddsRows,
): Promise<BestBetsTodayResponse> {
  const rejectionCounts: RejectionCounts = {
    noCleanMoneylineMarket: 0,
    selectedSideNotTeam: 0,
    marketProbabilityMissing: 0,
    calibratedProbabilityMissing: 0,
    edgeTooLow: 0,
    confidenceTooLow: 0,
    gameStatusNotPreGame: 0,
    modelSignalTooWeak: 0,
    dataQualityTooLow: 0,
    thresholdTooStrict: 0,
  };
  const topCandidateSummary: TopCandidateSummary = {
    totalMoneylineCandidates: 0,
    officialPicks: 0,
    moneylineLeans: 0,
    noBets: 0,
    top10MoneylineCandidates: [],
    thresholdNotes: [
      "Official daily picks stay gated at 3% edge or better once a clean moneyline market price exists.",
      "Strong Buy stays stricter than daily leans.",
      "Thresholds are not the blocker today; clean moneyline market prices are missing.",
    ],
  };
  const whyNoOfficialPicks = [
    "No official moneyline picks cleared the gate today.",
    "No clean moneyline market connected.",
    "No market price is available, so official edge cannot be calculated.",
  ];

  if (oddsRows.length) {
    const dailyPredictionCache = await loadDailyPredictionCache();
    const sportsbookFallback = buildSportsbookFallbackRows(oddsRows, ledgerDiagnostics, dailyPredictionCache);
    const fallbackWarnings = uniqueStrings([
      ...warnings,
      ...(sportsbookFallback.bestBetsDiagnostics.warnings ?? []),
    ]);
    return {
      status,
      ok: true,
      realMoneyTrading: "OFF",
      manualOnly: true,
      paperOnly: true,
      bestBetsDiagnostics: {
        ...sportsbookFallback.bestBetsDiagnostics,
        whyNoOfficialPicks,
        warnings: fallbackWarnings,
      },
      bestBetRows: sportsbookFallback.bestBetRows.map((row: any, index: number) => withAstroddsEngineV2Fields(row, index)),
      strongBuyRows: sportsbookFallback.strongBuyRows,
      strongBuyLedgerDiagnostics: ledgerDiagnostics,
      gameStatusValidationDiagnostics: null,
      warnings: fallbackWarnings,
      officialPicks: sportsbookFallback.officialPicks,
      moneylineLeans: sportsbookFallback.moneylineLeans,
      modelOnlyLeans: sportsbookFallback.modelOnlyLeans,
      oddsOnlyWatch: sportsbookFallback.oddsOnlyWatch,
      noBets: sportsbookFallback.noBets,
      diagnostics: sportsbookFallback.diagnostics,
    };
  }

  return {
    status,
    ok: true,
    realMoneyTrading: "OFF",
    manualOnly: true,
    paperOnly: true,
    bestBetsDiagnostics: {
      available: true,
      totalRowsEvaluated: 0,
      strongBuyCount: 0,
      dailyPickCount: 0,
      buyCount: 0,
      watchCount: 0,
      blockedCount: 0,
      actionableCount: 0,
      visibleBoardCount: 0,
      targetDailyPickMin: 2,
      targetDailyPickMax: 6,
      validCandidateCount: 0,
      whyNoDailyPicks: warnings,
      bankroll: ledgerDiagnostics?.currentBankroll ?? STARTING_BANKROLL,
      currentBankroll: ledgerDiagnostics?.currentBankroll ?? STARTING_BANKROLL,
      startingBankroll: STARTING_BANKROLL,
      stakePercent: STAKE_PERCENT,
      stakeAmount: Math.max(1, (ledgerDiagnostics?.currentBankroll ?? STARTING_BANKROLL) * (STAKE_PERCENT / 100)),
      totalOpenStakeAmount: ledgerDiagnostics?.totalOpenStakeAmount ?? 0,
      totalOpenExposurePercent: ledgerDiagnostics?.totalOpenExposurePercent ?? 0,
      remainingUnexposedBankroll: ledgerDiagnostics?.remainingUnexposedBankroll ?? STARTING_BANKROLL,
      openStrongBuyCount: ledgerDiagnostics?.openStrongBuyCount ?? 0,
      exposureLabel: ledgerDiagnostics?.exposureLabel ?? "Paper only",
      priceSourceUsed: "model_only",
      moneylinePricesFound: 0,
      leansWithRealPrice: 0,
      modelOnlyLeans: 0,
      whyNoOfficialPicks,
      rejectionCounts,
      topCandidateSummary,
      warnings,
      generatedAt: new Date().toISOString(),
    },
    bestBetRows: [],
    strongBuyRows: [],
    strongBuyLedgerDiagnostics: ledgerDiagnostics,
    gameStatusValidationDiagnostics: null,
    warnings,
    officialPicks: [],
    moneylineLeans: [],
    modelOnlyLeans: [],
    oddsOnlyWatch: [],
    noBets: [],
    diagnostics: {
      priceSourceUsed: "model_only",
      moneylinePricesFound: 0,
      leansWithRealPrice: 0,
      modelOnlyLeans: 0,
      oddsOnlyWatch: 0,
      scanGamesFound: 0,
      scanFailed: true,
      sportsbookOddsFound: oddsRows.length,
      polymarketCleanMoneylineFound: 0,
      rowsWithModelProbability: 0,
      rowsWithRealPrice: 0,
      rowsWithEdge: 0,
      modelAttachFailures: { noModelCache: 0, noGameKeyMatch: 0, teamAliasMismatch: 0, dateMismatch: 0, modelUnavailable: 0 },
      officialPicks: 0,
      moneylineLeans: 0,
      noBets: 0,
      usedSportsbookFallbackGames: false,
      whyNoOfficialPicks,
      rejectionCounts,
      topCandidateSummary,
    },
  };
}


function astroddsNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value.replace(",", "."));
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function astroddsRound(value: number, decimals = 2): number {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

function astroddsModelProbabilityGapPct(probability: unknown): number | null {
  const p = astroddsNumber(probability);
  if (p === null) return null;
  return astroddsRound(Math.abs(p - 0.5) * 200, 2);
}

function withAstroddsEngineV2Fields(row: any, index = 0) {
  const marketProbability = astroddsNumber(row.marketProbability);
  const modelProbability = astroddsNumber(row.calibratedProbability ?? row.modelProbability);
  const modelProbabilityGapPct = astroddsModelProbabilityGapPct(modelProbability);

  const calibratedEdgePct =
    marketProbability !== null && modelProbability !== null
      ? astroddsRound((modelProbability - marketProbability) * 100, 2)
      : null;

  const marketOk =
    marketProbability !== null &&
    marketProbability >= 0.3 &&
    marketProbability <= 0.75;

  const edgeOk =
    calibratedEdgePct !== null &&
    calibratedEdgePct >= 3 &&
    calibratedEdgePct <= 25;

  const gapOk =
    modelProbabilityGapPct !== null &&
    modelProbabilityGapPct >= 8;

  const confidenceOk =
    row.matchConfidence === "high" ||
    row.matchConfidence === "medium" ||
    row.confidence === "high" ||
    row.confidence === "medium";

  const riskOk =
    row.riskLevel !== "high" &&
    row.riskLevel !== "unknown" &&
    row.risk !== "high" &&
    row.risk !== "unknown";

  const statusOk =
    row.status !== "blocked" &&
    row.status !== "no_bet" &&
    row.status !== "rejected";

  const moneylineOk = row.marketType === "moneyline";

  const vvsEligible =
    moneylineOk &&
    marketOk &&
    edgeOk &&
    gapOk &&
    confidenceOk &&
    riskOk &&
    statusOk;

  const vvsReason = vvsEligible
    ? `VVS eligible: moneyline, market ${astroddsRound((marketProbability ?? 0) * 100, 1)}%, model gap ${modelProbabilityGapPct}%, edge ${calibratedEdgePct}%.`
    : `Not VVS eligible: ${[
        !moneylineOk ? "not_moneyline" : "",
        !marketOk ? "market_outside_30_75" : "",
        !edgeOk ? "edge_outside_3_25" : "",
        !gapOk ? "model_gap_below_8" : "",
        !confidenceOk ? "confidence_not_high_medium" : "",
        !riskOk ? "risk_blocked" : "",
        !statusOk ? "status_blocked" : "",
      ].filter(Boolean).join("|") || "unknown"}`;

  const vvsRank = vvsEligible
    ? astroddsRound(
        (calibratedEdgePct ?? 0) * 100 +
        (modelProbabilityGapPct ?? 0) +
        (row.matchConfidence === "high" || row.confidence === "high" ? 10 : 0) -
        (row.riskLevel === "medium" || row.risk === "medium" ? 5 : 0),
        2
      )
    : 0;

  return {
    ...row,
    modelProbabilityGapPct,
    vvsEligible,
    vvsReason,
    vvsRank,
  };
}

async function GET_IMPL() {
  const [ledgerDiagnostics, scanResult, oddsResult] = await Promise.all([
    loadStrongBuyLedgerStatus().catch(() => null),
    fetchMlbScan(TIMEOUT_MS),
    fetchOddsLayer(10_000),
  ]);

  if (!scanResult.scan || !scanResult.scan.games.length) {
    const warnings = [...scanResult.warnings, ...(ledgerDiagnostics?.warnings ?? [])];
    return NextResponse.json(buildFallbackResponse(scanResult.status, warnings.length ? warnings : ["Best Bets diagnostics unavailable."], ledgerDiagnostics, oddsResult.odds), {
      status: 200,
      headers: {
        "Cache-Control": "no-store",
        "Content-Type": "application/json; charset=utf-8",
      },
    });
  }

  const built = buildBestBetRows(scanResult.scan, ledgerDiagnostics, oddsResult.odds);
  const gameById = new Map(scanResult.scan.games.map((game) => [game.id, game] as const));
  const officialPicks = built.bestBetRows
    .filter((row: BestBetRowResponse) => row.status === "strong_buy" || row.status === "daily_pick")
    .map((row: BestBetRowResponse) => buildMoneylineCandidate(row, gameById.get(row.gameId ?? "")))
    .filter((candidate: MoneylineCandidateResponse | null): candidate is MoneylineCandidateResponse => Boolean(candidate && candidate.status === "official_pick"));
  const moneylineLeans = built.bestBetRows
    .map((row: BestBetRowResponse) => buildMoneylineCandidate(row, gameById.get(row.gameId ?? "")))
    .filter((candidate: MoneylineCandidateResponse | null): candidate is MoneylineCandidateResponse => Boolean(candidate && candidate.status === "moneyline_lean"))
    .sort((left, right) => candidateSortScore(right) - candidateSortScore(left));
  const noBets = built.bestBetRows
    .map((row: BestBetRowResponse) => buildMoneylineCandidate(row, gameById.get(row.gameId ?? "")))
    .filter((candidate: MoneylineCandidateResponse | null): candidate is MoneylineCandidateResponse => Boolean(candidate && candidate.status === "no_bet"))
    .sort((left, right) => candidateSortScore(right) - candidateSortScore(left));
  const rejectionCounts = buildRejectionCounts(built.bestBetRows, scanResult.scan.games);
  const topCandidateSummary = buildTopCandidateSummary(officialPicks, moneylineLeans, noBets);
  const priceSourceUsed: PriceSourceUsed = built.bestBetsDiagnostics.priceSourceUsed ?? (oddsResult.odds.length ? "sportsbook" : "model_only");
  const whyNoOfficialPicks = uniqueStrings([
    officialPicks.length ? undefined : `No official moneyline picks cleared the gate today.`,
    rejectionCounts.noCleanMoneylineMarket ? `No clean moneyline market connected on ${rejectionCounts.noCleanMoneylineMarket} of ${built.bestBetRows.length} rows.` : undefined,
    rejectionCounts.marketProbabilityMissing ? `Market probability is missing on ${rejectionCounts.marketProbabilityMissing} rows, so official edge cannot be calculated.` : undefined,
    moneylineLeans.length ? `${moneylineLeans.length} model leans exist, but they stay dashboard-only until a clean market price is connected.` : undefined,
    noBets.length ? `${noBets.length} games remain model WAIT / no-bet signals.` : undefined,
    topCandidateSummary.thresholdNotes[2],
  ]);
  const warnings = uniqueStrings([
    ...scanResult.warnings,
    ...(scanResult.scan.warnings ?? []),
    ...(ledgerDiagnostics?.warnings ?? []),
    ...(oddsResult.warnings ?? []),
    built.bestBetsDiagnostics.whyNoDailyPicks.length ? `No Strong Buy today - ${built.bestBetsDiagnostics.whyNoDailyPicks[0]}` : undefined,
  ]);

  const responseBody: BestBetsTodayResponse = {
    status: scanResult.status,
    ok: true,
    realMoneyTrading: "OFF",
    manualOnly: true,
    paperOnly: true,
    bestBetsDiagnostics: {
      ...built.bestBetsDiagnostics,
      whyNoOfficialPicks,
      rejectionCounts,
      topCandidateSummary,
      priceSourceUsed,
      moneylinePricesFound: built.bestBetsDiagnostics.moneylinePricesFound ?? 0,
      leansWithRealPrice: built.bestBetsDiagnostics.leansWithRealPrice ?? 0,
      modelOnlyLeans: built.bestBetsDiagnostics.modelOnlyLeans ?? 0,
      oddsOnlyWatch: built.bestBetsDiagnostics.oddsOnlyWatch ?? built.bestBetRows.filter((row: BestBetRowResponse) => row.priceSourceUsed === "sportsbook" && row.status === "watch").length,
      scanGamesFound: scanResult.scan.games.length,
      scanFailed: scanResult.status !== "available",
      sportsbookOddsFound: oddsResult.odds.length,
      polymarketCleanMoneylineFound: built.bestBetsDiagnostics.polymarketCleanMoneylineFound ?? built.bestBetRows.filter((row: BestBetRowResponse) => row.priceSourceUsed === "polymarket").length,
      rowsWithModelProbability: built.bestBetsDiagnostics.rowsWithModelProbability ?? built.bestBetRows.filter((row: BestBetRowResponse) => typeof row.calibratedProbability === "number").length,
      rowsWithRealPrice: built.bestBetsDiagnostics.rowsWithRealPrice ?? built.bestBetRows.filter((row: BestBetRowResponse) => typeof row.marketProbability === "number").length,
      rowsWithEdge: 0,
      modelAttachFailures: { noModelCache: 0, noGameKeyMatch: 0, teamAliasMismatch: 0, dateMismatch: 0, modelUnavailable: 0 },
      officialPicks: officialPicks.length,
      moneylineLeans: moneylineLeans.length,
      noBets: noBets.length,
      usedSportsbookFallbackGames: built.bestBetRows.some((row: BestBetRowResponse) => row.priceSourceUsed === "sportsbook"),
      warnings: warnings.length ? warnings : ["Best Bets diagnostics loaded successfully."],
    },
    bestBetRows: built.bestBetRows.map((row: any, index: number) => withAstroddsEngineV2Fields(row, index)),
    strongBuyRows: built.strongBuyRows,
    strongBuyLedgerDiagnostics: ledgerDiagnostics,
    gameStatusValidationDiagnostics: scanResult.scan.diagnostics.gameStatusValidationDiagnostics ? { ...scanResult.scan.diagnostics.gameStatusValidationDiagnostics } : null,
    warnings,
    officialPicks,
    moneylineLeans,
    modelOnlyLeans: built.bestBetRows
      .filter((row: BestBetRowResponse) => row.status === "watch" && !row.marketConnected && (row.marketProbability === null || row.marketProbability === undefined))
      .map((row: BestBetRowResponse) => buildMoneylineCandidate(row, gameById.get(row.gameId ?? "")))
      .filter((candidate: MoneylineCandidateResponse | null): candidate is MoneylineCandidateResponse => Boolean(candidate)),
    oddsOnlyWatch: built.bestBetRows
      .filter((row: BestBetRowResponse) => row.priceSourceUsed === "sportsbook" && row.status === "watch")
      .map((row: BestBetRowResponse) => ({
        bestBetId: row.bestBetId,
        gameId: row.gameId,
        date: row.date,
        homeTeam: row.homeTeam,
        awayTeam: row.awayTeam,
        selectedSide: row.selectedSide,
        marketType: "moneyline" as const,
        status: "odds_only_watch" as const,
        marketProbability: row.marketProbability ?? 0,
        calibratedProbability: null,
        edge: null,
        matchConfidence: row.matchConfidence === "high" ? "medium" : "low",
        riskLevel: row.riskLevel,
        mainReason: row.mainReason,
        warnings: row.warnings,
        blockReasons: row.blockReasons,
        priceSourceUsed: "sportsbook" as const,
      })),
    noBets,
    diagnostics: {
      priceSourceUsed,
      moneylinePricesFound: built.bestBetsDiagnostics.moneylinePricesFound ?? 0,
      leansWithRealPrice: built.bestBetsDiagnostics.leansWithRealPrice ?? 0,
      modelOnlyLeans: built.bestBetsDiagnostics.modelOnlyLeans ?? 0,
      oddsOnlyWatch: built.bestBetsDiagnostics.oddsOnlyWatch ?? built.bestBetRows.filter((row: BestBetRowResponse) => row.priceSourceUsed === "sportsbook" && row.status === "watch").length,
      scanGamesFound: scanResult.scan.games.length,
      scanFailed: scanResult.status !== "available",
      sportsbookOddsFound: oddsResult.odds.length,
      polymarketCleanMoneylineFound: built.bestBetsDiagnostics.polymarketCleanMoneylineFound ?? built.bestBetRows.filter((row: BestBetRowResponse) => row.priceSourceUsed === "polymarket").length,
      rowsWithModelProbability: built.bestBetsDiagnostics.rowsWithModelProbability ?? built.bestBetRows.filter((row: BestBetRowResponse) => typeof row.calibratedProbability === "number").length,
      rowsWithRealPrice: built.bestBetsDiagnostics.rowsWithRealPrice ?? built.bestBetRows.filter((row: BestBetRowResponse) => typeof row.marketProbability === "number").length,
      rowsWithEdge: 0,
      modelAttachFailures: { noModelCache: 0, noGameKeyMatch: 0, teamAliasMismatch: 0, dateMismatch: 0, modelUnavailable: 0 },
      officialPicks: officialPicks.length,
      moneylineLeans: moneylineLeans.length,
      noBets: noBets.length,
      usedSportsbookFallbackGames: built.bestBetRows.some((row) => row.priceSourceUsed === "sportsbook"),
      whyNoOfficialPicks,
      rejectionCounts,
      topCandidateSummary,
    },
  };

  return NextResponse.json(responseBody, {
    status: 200,
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "application/json; charset=utf-8",
    },
  });
}

function astroddsFallbackErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    const cause = (error as Error & { cause?: unknown }).cause;
    const causeMessage = cause instanceof Error ? cause.message : cause ? String(cause) : "";
    return [error.message, causeMessage].filter(Boolean).join(" | ");
  }

  return String(error);
}

export async function GET() {
  try {
    return await GET_IMPL();
  } catch (error) {
    const message = astroddsFallbackErrorMessage(error);
    const isTimeout = /ETIMEDOUT|timed out|timeout|abort|fetch failed/i.test(message);
    const status = isTimeout ? "timeout" : "partial";

    return NextResponse.json(
      buildFallbackResponse(
        status,
        [
          isTimeout
            ? `Best Bets route recovered from upstream timeout: ${message}`
            : `Best Bets route recovered from upstream error: ${message}`,
        ],
        null,
        [],
      ),
      {
        status: 200,
        headers: {
          "Cache-Control": "no-store",
          "Content-Type": "application/json; charset=utf-8",
        },
      },
    );
  }
}

