import { compactId, normalizeText } from "../sports-data/normalize";
import type { BullpenFeatureDiagnostics } from "./bullpen-feature-status";
import type { InjuryAvailabilityDiagnostics } from "./injury-availability-status";
import type { LineupPlayerFeatureDiagnostics } from "./lineup-player-feature-status";
import type { PaperPerformanceAnalysis } from "./paper-performance-analysis";
import type { PitcherFeatureDiagnostics } from "./pitcher-feature-status";
import type { PythonMlbEngineStatus } from "./python-engine-status";
import type { MlbPaperWatchlistRow } from "./paper-watchlist";
import type { WeatherBallparkFeatureDiagnostics } from "./weather-ballpark-feature-status";
import type { MLBGameStatusValidation } from "./game-status-validation";

export type CombinedRiskGateDecision = "bet_candidate" | "watchlist" | "research_only" | "blocked";

export type CombinedRiskGateRiskLevel = "low" | "medium" | "high" | "unknown";

export type CombinedRiskGateRow = {
  rowId: string;
  gameId?: string;
  date?: string;
  homeTeam?: string;
  awayTeam?: string;
  gameStatusValidation?: MLBGameStatusValidation;
  mlbStatus?: MLBGameStatusValidation["mlbStatus"];
  gameStatusBlockReasons: string[];
  marketType: "moneyline";
  selectedSide?: string;
  researchSide?: string;
  rawModelProbability?: number | null;
  calibratedProbability?: number | null;
  marketProbability?: number | null;
  diagnosticCalibratedEdge?: number | null;
  diagnosticCalibratedEdgePct?: number | null;
  matchConfidence?: "high" | "medium" | "low" | "none" | string;
  riskScore: number;
  riskLevel: CombinedRiskGateRiskLevel;
  decision: CombinedRiskGateDecision;
  blockReasons: string[];
  downgradeReasons: string[];
  positiveReasons: string[];
  dataQuality: string;
  officialPickEligible: false;
  officialEdgeAllowed: false;
  isPaperOnly: true;
  realMoneyDisabled: true;
};

export type CombinedRiskGatePrediction = {
  gameId?: string;
  date?: string;
  homeTeam?: string;
  awayTeam?: string;
  gameStatusValidation?: MLBGameStatusValidation;
  mlbStatus?: MLBGameStatusValidation["mlbStatus"];
  gameStatusBlockReasons?: string[];
  marketType?: string;
  pick?: string;
  rawModelProbability?: number | null;
  calibratedProbability?: number | null;
  marketProbability?: number | null;
  rawEdge?: number | null;
  calibratedEdge?: number | null;
  calibrationQuality?: string;
  calibrationMappingStatus?: string;
  officialPickEligible?: boolean;
  officialEdgeAllowed?: boolean;
  officialDecision?: string;
  officialEdgeBlockReasons?: string[];
  reasons?: string[];
  risks?: string[];
  dataQuality?: string;
  matchConfidence?: string;
  diagnosticRawEdge?: number | null;
  diagnosticRawEdgePct?: number | null;
  diagnosticCalibratedEdge?: number | null;
  diagnosticCalibratedEdgePct?: number | null;
  watchlistTier?: string;
  selectedSide?: string;
  researchSide?: string;
  market?: string;
  modelVersion?: string;
  modelType?: string;
  generatedAt?: string;
  isPaperOnly?: boolean;
};

type CombinedRiskGateMarketPriceDiagnostics = {
  marketPricesConnected: boolean;
  cacheUsed?: boolean;
  cacheStatus?: string;
  cacheAgeSeconds?: number;
  moneylineMarketsFound?: number;
  status?: string;
  warnings?: string[];
  generatedAt?: string;
  sourceDiagnostics?: Array<Record<string, unknown>>;
};

type CombinedRiskGateMarketMatchDiagnostics = {
  matchedMarketsCount?: number;
  matchedGamesCount?: number;
  highConfidenceMatches?: number;
  mediumConfidenceMatches?: number;
  lowConfidenceMatches?: number;
  gamesCount?: number;
  warnings?: string[];
  error?: string;
};

export type CombinedRiskGateInput = {
  predictions?: CombinedRiskGatePrediction[];
  watchlistRows?: MlbPaperWatchlistRow[];
  pythonMlbEngineStatus?: PythonMlbEngineStatus;
  marketPriceDiagnostics?: CombinedRiskGateMarketPriceDiagnostics;
  marketMatchDiagnostics?: CombinedRiskGateMarketMatchDiagnostics;
  lineupPlayerFeatureDiagnostics?: LineupPlayerFeatureDiagnostics;
  injuryAvailabilityDiagnostics?: InjuryAvailabilityDiagnostics;
  weatherBallparkFeatureDiagnostics?: WeatherBallparkFeatureDiagnostics;
  pitcherFeatureDiagnostics?: PitcherFeatureDiagnostics;
  bullpenFeatureDiagnostics?: BullpenFeatureDiagnostics;
  paperPerformanceDiagnostics?: PaperPerformanceAnalysis;
  gameStatusValidationByGameId?: Record<string, MLBGameStatusValidation | undefined>;
};

export type CombinedRiskGateDiagnostics = {
  status: "available" | "partial" | "missing";
  available: boolean;
  totalRows: number;
  betCandidateRows: number;
  watchlistRows: number;
  researchOnlyRows: number;
  blockedRows: number;
  lowRiskRows: number;
  mediumRiskRows: number;
  highRiskRows: number;
  unknownRiskRows: number;
  averageDiagnosticCalibratedEdge: number | null;
  averageCalibratedProbability: number | null;
  averageMarketProbability: number | null;
  officialPickEligible: false;
  officialEdgeAllowed: false;
  isPaperOnly: true;
  realMoneyDisabled: true;
  warnings: string[];
  generatedAt: string;
  sourcePath: string;
  sourceDiagnostics: Array<{
    label: string;
    status: string;
    note: string;
  }>;
};

export type CombinedRiskGateResult = {
  diagnostics: CombinedRiskGateDiagnostics;
  rows: CombinedRiskGateRow[];
  warnings: string[];
  generatedAt: string;
  sourcePath: string;
};

function isUsefulNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function clampRiskScore(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function uniqueStrings(values: Array<string | undefined>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value && value.trim()))));
}

function rowKey(value: {
  gameId?: string;
  date?: string;
  awayTeam?: string;
  homeTeam?: string;
  side?: string;
}) {
  return compactId([value.gameId, value.date, value.awayTeam, value.homeTeam, value.side].filter(Boolean).join(" "));
}

function edgeValue(
  prediction?: Pick<CombinedRiskGatePrediction, "calibratedEdge" | "calibratedProbability" | "marketProbability" | "rawModelProbability">,
  watchlistRow?: Pick<MlbPaperWatchlistRow, "diagnosticCalibratedEdge" | "calibratedProbability" | "marketProbability" | "rawModelProbability">,
) {
  const rowEdge = watchlistRow?.diagnosticCalibratedEdge;
  if (isUsefulNumber(rowEdge)) return rowEdge;
  if (isUsefulNumber(prediction?.calibratedProbability) && isUsefulNumber(prediction?.marketProbability)) {
    return (prediction.calibratedProbability ?? 0) - (prediction.marketProbability ?? 0);
  }
  if (isUsefulNumber(prediction?.calibratedEdge)) return prediction.calibratedEdge;
  return null;
}

function edgePct(edge?: number | null) {
  return isUsefulNumber(edge) ? edge * 100 : null;
}

function confidenceConfidence(matchConfidence?: string) {
  const normalized = normalizeText(matchConfidence ?? "");
  if (normalized === "high") return "high";
  if (normalized === "medium") return "medium";
  if (normalized === "low" || normalized === "none") return normalized;
  return "none";
}

function dataQualityLabel(value?: string) {
  const normalized = (value ?? "").trim().toUpperCase();
  if (normalized) return normalized;
  return "DATA_ONLY";
}

function marketMatchCount(input: CombinedRiskGateInput) {
  return input.marketMatchDiagnostics?.matchedMarketsCount
    ?? input.marketMatchDiagnostics?.matchedGamesCount
    ?? input.marketMatchDiagnostics?.highConfidenceMatches
    ?? 0;
}

function marketSourceAvailable(input: CombinedRiskGateInput) {
  const connected = input.marketPriceDiagnostics?.marketPricesConnected ?? false;
  const cacheUsed = input.marketPriceDiagnostics?.cacheUsed ?? false;
  const cacheStatus = normalizeText(input.marketPriceDiagnostics?.cacheStatus ?? "");
  if (connected) return true;
  if (cacheUsed && cacheStatus === "fresh") return true;
  return false;
}

function calibrationBlockReason(status?: string) {
  const normalized = normalizeText(status ?? "");
  if (normalized === "strong" || normalized === "medium") return undefined;
  if (normalized === "weak") return "Calibration is weak - research only";
  if (normalized === "not_enough_history") return "Calibration lacks enough history";
  return "No calibrated probability mapping";
}

function statusLabel(status?: string) {
  const normalized = normalizeText(status ?? "");
  if (!normalized) return "missing";
  return normalized;
}

function buildRow(
  prediction: CombinedRiskGatePrediction,
  input: CombinedRiskGateInput,
  watchlistRow?: MlbPaperWatchlistRow,
): CombinedRiskGateRow {
  const predictionMatchConfidence = normalizeText(prediction.matchConfidence ?? "");
  const matchConfidence = confidenceConfidence(watchlistRow?.matchConfidence ?? predictionMatchConfidence ?? (marketMatchCount(input) > 0 ? "medium" : "none"));
  const calibratedProbability = watchlistRow?.calibratedProbability ?? prediction.calibratedProbability;
  const marketProbability = watchlistRow?.marketProbability ?? prediction.marketProbability;
  const rawModelProbability = watchlistRow?.rawModelProbability ?? prediction.rawModelProbability;
  const edge = edgeValue(prediction, watchlistRow);
  const edgePctValue = edgePct(edge);
  const selectedSide = watchlistRow?.selectedSide
    ?? watchlistRow?.researchSide
    ?? prediction.pick
    ?? (isUsefulNumber(rawModelProbability) && rawModelProbability >= 0.5 ? prediction.homeTeam : prediction.awayTeam)
    ?? prediction.homeTeam
    ?? prediction.awayTeam;
  const researchSide = watchlistRow?.researchSide ?? selectedSide ?? "Research side unavailable";

  const hasMarketProbability = isUsefulNumber(marketProbability) && marketProbability > 0 && marketProbability < 1;
  const hasCalibratedProbability = isUsefulNumber(calibratedProbability) && calibratedProbability > 0 && calibratedProbability < 1;
  const hasRawModelProbability = isUsefulNumber(rawModelProbability) && rawModelProbability > 0 && rawModelProbability < 1;
  const liveMarketReady = marketSourceAvailable(input) && (marketMatchCount(input) > 0 || Boolean(watchlistRow));
  const gameStatusValidation = prediction.gameStatusValidation ?? (prediction.gameId ? input.gameStatusValidationByGameId?.[prediction.gameId] : undefined);
  const gameStatusBlockReasons = gameStatusValidation?.gameStatusBlockReasons ?? [];
  const gameStatusBlocked = Boolean(gameStatusValidation && !gameStatusValidation.isGameActiveForBetting);

  const lineupStatus = normalizeText(input.lineupPlayerFeatureDiagnostics?.status ?? "");
  const injuryStatus = normalizeText(input.injuryAvailabilityDiagnostics?.status ?? "");
  const weatherStatus = normalizeText(input.weatherBallparkFeatureDiagnostics?.status ?? "");
  const pitcherStatus = normalizeText(input.pitcherFeatureDiagnostics?.status ?? "");
  const bullpenStatus = normalizeText(input.bullpenFeatureDiagnostics?.status ?? "");
  const calibrationQuality = normalizeText(input.pythonMlbEngineStatus?.calibrationQuality ?? prediction.calibrationQuality ?? watchlistRow?.calibrationQuality ?? "");
  const paperSettledRows = input.paperPerformanceDiagnostics?.summary.settledRows ?? 0;

  const positiveReasons = uniqueStrings([
    isUsefulNumber(edgePctValue) ? `Diagnostic calibrated edge is ${edgePctValue.toFixed(1)}%` : undefined,
    liveMarketReady ? "Matched market source is available" : undefined,
    matchConfidence === "high" ? "Match confidence is high" : matchConfidence === "medium" ? "Match confidence is medium" : undefined,
    lineupStatus === "available" ? "Lineup layer is connected" : lineupStatus === "partial" ? "Lineup layer is partial" : undefined,
    injuryStatus === "available" ? "Injury layer is connected" : injuryStatus === "partial" ? "Injury layer is partial" : undefined,
    weatherStatus === "available" ? "Weather layer is connected" : weatherStatus === "partial" ? "Weather layer is partial" : undefined,
    pitcherStatus === "available" ? "Pitcher layer is connected" : pitcherStatus === "partial" ? "Pitcher layer is partial" : undefined,
    bullpenStatus === "available" ? "Bullpen layer is connected" : bullpenStatus === "partial" ? "Bullpen layer is partial" : undefined,
    watchlistRow?.watchlistTier ? `Paper watchlist tier: ${watchlistRow.watchlistTier}` : undefined,
    paperSettledRows >= 10 ? "Paper performance sample is large enough for research context" : undefined,
    gameStatusValidation?.isGameActiveForBetting ? "MLB game status is active for betting" : undefined,
  ]);

  const downgradeReasons = uniqueStrings([
    calibrationBlockReason(input.pythonMlbEngineStatus?.calibrationQuality ?? prediction.calibrationQuality ?? watchlistRow?.calibrationQuality),
    lineupStatus === "projected" ? "Watchlist - lineup not confirmed yet" : lineupStatus === "missing" ? "Lineup data unavailable" : undefined,
    injuryStatus === "partial" ? "Injury / availability data partial" : injuryStatus === "missing" ? "Injury / availability data unavailable" : undefined,
    weatherStatus === "partial" ? "Weather / ballpark data partial" : weatherStatus === "missing" ? "Weather / ballpark data unavailable" : undefined,
    pitcherStatus === "partial" ? "Pitcher data partial" : pitcherStatus === "missing" ? "Pitcher data unavailable" : undefined,
    bullpenStatus === "partial" ? "Bullpen data partial" : bullpenStatus === "missing" ? "Bullpen data unavailable" : undefined,
    input.marketPriceDiagnostics?.cacheUsed && input.marketPriceDiagnostics.cacheStatus === "stale" ? "Polymarket cache is stale" : undefined,
    !marketSourceAvailable(input) ? "No verified live market source available" : undefined,
    marketMatchCount(input) === 0 ? "No clean matched Polymarket MLB market" : undefined,
    ...gameStatusBlockReasons,
    gameStatusBlocked ? "Blocked: MLB game status validation failed" : undefined,
  ]);

  const blockReasons = uniqueStrings([
    !hasRawModelProbability ? "Missing raw model probability" : undefined,
    !hasCalibratedProbability ? "Missing calibrated probability" : undefined,
    !hasMarketProbability ? "Missing real odds or entry price" : undefined,
    matchConfidence === "none" || matchConfidence === "low" ? "Market match confidence too low" : undefined,
    !marketSourceAvailable(input) ? "Polymarket market prices unavailable" : undefined,
    marketMatchCount(input) === 0 ? "No clean matched Polymarket MLB market" : undefined,
    input.pythonMlbEngineStatus?.officialPickEligible ? undefined : "Official pick eligibility remains blocked",
    input.pythonMlbEngineStatus?.calibrationQuality === "weak" ? "Calibration weak - diagnostics only" : undefined,
    input.pythonMlbEngineStatus?.calibrationQuality === "not_enough_history" ? "Calibration lacks enough history" : undefined,
    input.pythonMlbEngineStatus?.calibrationQuality === "missing" ? "No calibrated probability mapping" : undefined,
  ]);

  const riskScoreBase = 24
    + (!marketSourceAvailable(input) ? 34 : 0)
    + (!hasMarketProbability ? 26 : 0)
    + (!hasCalibratedProbability ? 24 : 0)
    + (!hasRawModelProbability ? 20 : 0)
    + (matchConfidence === "high" ? -12 : matchConfidence === "medium" ? -6 : matchConfidence === "low" ? 10 : 18)
    + (lineupStatus === "available" ? -8 : lineupStatus === "partial" ? 4 : 16)
    + (injuryStatus === "available" ? -4 : injuryStatus === "partial" ? 4 : 10)
    + (weatherStatus === "available" ? -3 : weatherStatus === "partial" ? 2 : 6)
    + (pitcherStatus === "available" ? -4 : pitcherStatus === "partial" ? 4 : 10)
    + (bullpenStatus === "available" ? -2 : bullpenStatus === "partial" ? 2 : 6)
    + (calibrationQuality === "strong" ? -4 : calibrationQuality === "medium" ? -1 : calibrationQuality === "weak" ? 8 : 12)
    + (edgePctValue !== null && edgePctValue >= 6 ? -8 : edgePctValue !== null && edgePctValue >= 3 ? -4 : edgePctValue !== null && edgePctValue > 0 ? -1 : 10)
    + (paperSettledRows < 10 ? 3 : 0)
    + (marketMatchCount(input) === 0 ? 20 : 0);
  const riskScore = clampRiskScore(riskScoreBase);
  const riskLevel: CombinedRiskGateRiskLevel = !hasMarketProbability || !hasCalibratedProbability || matchConfidence === "none"
    ? "unknown"
    : riskScore <= 34
      ? "low"
      : riskScore <= 64
        ? "medium"
        : "high";

  let decision: CombinedRiskGateDecision = "blocked";
  if (hasMarketProbability && hasCalibratedProbability && hasRawModelProbability && matchConfidence !== "none" && matchConfidence !== "low") {
    if (!marketSourceAvailable(input) || marketMatchCount(input) === 0) {
      decision = edgePctValue && edgePctValue > 0 ? "research_only" : "blocked";
    } else if (edgePctValue !== null && edgePctValue >= 6 && riskLevel === "low" && lineupStatus === "available" && injuryStatus !== "missing" && pitcherStatus !== "missing" && weatherStatus !== "missing") {
      decision = "bet_candidate";
    } else if (edgePctValue !== null && edgePctValue >= 3 && riskLevel !== "high") {
      decision = "watchlist";
    } else if (edgePctValue !== null && edgePctValue > 0) {
      decision = "research_only";
    } else {
      decision = "blocked";
    }
  }

  if (gameStatusBlocked) decision = "blocked";

  if (lineupStatus === "missing" && decision === "bet_candidate") decision = "watchlist";
  if ((injuryStatus === "missing" || weatherStatus === "missing" || pitcherStatus === "missing" || bullpenStatus === "missing") && decision === "bet_candidate") {
    decision = "watchlist";
  }
  if (riskLevel === "high" && decision === "bet_candidate") decision = "watchlist";
  if (marketMatchCount(input) === 0 && decision === "bet_candidate") decision = "research_only";
  if (!marketSourceAvailable(input) && decision === "bet_candidate") decision = "research_only";

  const rowId = compactId([prediction.gameId, prediction.date, prediction.awayTeam, prediction.homeTeam, selectedSide, prediction.marketType].filter(Boolean).join(" "));

  return {
    rowId,
    gameId: prediction.gameId,
    date: prediction.date,
    homeTeam: prediction.homeTeam,
    awayTeam: prediction.awayTeam,
    gameStatusValidation,
    mlbStatus: gameStatusValidation?.mlbStatus,
    gameStatusBlockReasons,
    marketType: "moneyline",
    selectedSide,
    researchSide,
    rawModelProbability,
    calibratedProbability,
    marketProbability,
    diagnosticCalibratedEdge: edge,
    diagnosticCalibratedEdgePct: edgePctValue,
    matchConfidence,
    riskScore,
    riskLevel,
    decision,
    blockReasons,
    downgradeReasons,
    positiveReasons,
    dataQuality: dataQualityLabel(watchlistRow?.calibrationQuality ?? prediction.dataQuality),
    officialPickEligible: false,
    officialEdgeAllowed: false,
    isPaperOnly: true,
    realMoneyDisabled: true,
  };
}

function aggregateNumbers(rows: CombinedRiskGateRow[], selector: (row: CombinedRiskGateRow) => number | null | undefined) {
  const values = rows
    .map(selector)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!values.length) return null;
  return values.reduce((total, value) => total + value, 0) / values.length;
}

export function buildCombinedRiskGate(input: CombinedRiskGateInput): CombinedRiskGateResult {
  const sourcePath = "in-memory:combined-risk-gate";
  const warnings = uniqueStrings([
    "Combined Risk Gate is research/manual only.",
    "Official picks remain blocked.",
    "Whales remain bonus-only and cannot promote a row to official use.",
    "Runline remains disabled.",
    ...(input.pythonMlbEngineStatus?.warnings ?? []),
    ...(input.marketPriceDiagnostics?.warnings ?? []),
    ...(input.marketMatchDiagnostics?.warnings ?? []),
    ...(input.lineupPlayerFeatureDiagnostics?.warnings ?? []),
    ...(input.injuryAvailabilityDiagnostics?.warnings ?? []),
    ...(input.weatherBallparkFeatureDiagnostics?.warnings ?? []),
    ...(input.pitcherFeatureDiagnostics?.warnings ?? []),
    ...(input.bullpenFeatureDiagnostics?.warnings ?? []),
    ...(input.paperPerformanceDiagnostics?.warnings ?? []),
  ]);

  const predictions = (input.predictions ?? []).filter((prediction) => prediction.marketType === "moneyline");
  const watchlistRows = input.watchlistRows ?? [];
  const watchlistMap = new Map<string, MlbPaperWatchlistRow>();
  for (const row of watchlistRows) {
    watchlistMap.set(rowKey({ gameId: row.gameId, date: row.date, awayTeam: row.awayTeam, homeTeam: row.homeTeam, side: row.selectedSide ?? row.researchSide }), row);
  }
  const gameStatusValidationEntries = Object.values(input.gameStatusValidationByGameId ?? {}).filter(
    (validation): validation is MLBGameStatusValidation => Boolean(validation),
  );
  const gameStatusValidationBlocked = gameStatusValidationEntries.filter((validation) => !validation.isGameActiveForBetting).length;

  const sourceRows: CombinedRiskGateRow[] = [];
  if (predictions.length) {
    for (const prediction of predictions) {
      const watchlistRow = watchlistMap.get(rowKey({
        gameId: prediction.gameId,
        date: prediction.date,
        awayTeam: prediction.awayTeam,
        homeTeam: prediction.homeTeam,
        side: prediction.pick,
      }));
      sourceRows.push(buildRow(prediction, input, watchlistRow));
    }
  } else {
    for (const row of watchlistRows) {
      const prediction: CombinedRiskGatePrediction = {
        gameId: row.gameId,
        date: row.date,
        homeTeam: row.homeTeam,
        awayTeam: row.awayTeam,
        marketType: "moneyline",
        rawModelProbability: row.rawModelProbability,
        calibratedProbability: row.calibratedProbability,
        marketProbability: row.marketProbability,
        rawEdge: row.diagnosticRawEdge ?? undefined,
        calibratedEdge: row.diagnosticCalibratedEdge,
        calibrationQuality: row.calibrationQuality,
        calibrationMappingStatus: row.calibrationMappingStatus,
        reasons: row.reasons,
        risks: row.risks,
        officialPickEligible: false,
        officialEdgeAllowed: false,
        officialDecision: row.officialDecision,
        officialEdgeBlockReasons: row.blockReasons,
        pick: row.researchSide,
        isPaperOnly: true,
      };
      sourceRows.push(buildRow(prediction, input, row));
    }
  }

  sourceRows.sort((left, right) => {
    const decisionRank: Record<CombinedRiskGateDecision, number> = {
      blocked: 0,
      research_only: 1,
      watchlist: 2,
      bet_candidate: 3,
    };
    const leftEdge = left.diagnosticCalibratedEdge ?? -Infinity;
    const rightEdge = right.diagnosticCalibratedEdge ?? -Infinity;
    const leftRisk = left.riskScore;
    const rightRisk = right.riskScore;
    return (
      decisionRank[right.decision] - decisionRank[left.decision] ||
      rightEdge - leftEdge ||
      leftRisk - rightRisk ||
      (left.homeTeam ?? "").localeCompare(right.homeTeam ?? "")
    );
  });

  const totalRows = sourceRows.length;
  const betCandidateRows = sourceRows.filter((row) => row.decision === "bet_candidate").length;
  const watchlistCount = sourceRows.filter((row) => row.decision === "watchlist").length;
  const researchOnlyRows = sourceRows.filter((row) => row.decision === "research_only").length;
  const blockedRows = sourceRows.filter((row) => row.decision === "blocked").length;
  const lowRiskRows = sourceRows.filter((row) => row.riskLevel === "low").length;
  const mediumRiskRows = sourceRows.filter((row) => row.riskLevel === "medium").length;
  const highRiskRows = sourceRows.filter((row) => row.riskLevel === "high").length;
  const unknownRiskRows = sourceRows.filter((row) => row.riskLevel === "unknown").length;
  const averageDiagnosticCalibratedEdge = aggregateNumbers(sourceRows, (row) => row.diagnosticCalibratedEdge);
  const averageCalibratedProbability = aggregateNumbers(sourceRows, (row) => row.calibratedProbability);
  const averageMarketProbability = aggregateNumbers(sourceRows, (row) => row.marketProbability);

  const sourceDiagnostics = [
    {
      label: "Python MLB Engine",
      status: input.pythonMlbEngineStatus?.modelAvailable ? "available" : "blocked",
      note: `Calibration ${input.pythonMlbEngineStatus?.calibrationQuality ?? "missing"}; official use ${input.pythonMlbEngineStatus?.officialPickEligible ? "eligible" : "blocked"}.`,
    },
    {
      label: "Polymarket prices",
      status: input.marketPriceDiagnostics?.marketPricesConnected ? "connected" : input.marketPriceDiagnostics?.cacheUsed ? "cache" : "blocked",
      note: input.marketPriceDiagnostics?.cacheUsed
        ? `Cache ${input.marketPriceDiagnostics.cacheStatus ?? "missing"}; ${input.marketPriceDiagnostics.moneylineMarketsFound ?? 0} moneyline markets found.`
        : `${input.marketPriceDiagnostics?.moneylineMarketsFound ?? 0} moneyline markets found.`,
    },
    {
      label: "Market matching",
      status: marketMatchCount(input) > 0 ? "matched" : "blocked",
      note: `${marketMatchCount(input)} matched MLB markets.`,
    },
    {
      label: "Game status validation",
      status: gameStatusValidationEntries.length ? (gameStatusValidationBlocked > 0 ? "partial" : "available") : "missing",
      note: gameStatusValidationEntries.length
        ? `${gameStatusValidationEntries.length} MLB rows validated; ${gameStatusValidationBlocked} blocked by status.`
        : "MLB game status validation not attached yet.",
    },
    {
      label: "Lineup layer",
      status: input.lineupPlayerFeatureDiagnostics?.status ?? "missing",
      note: input.lineupPlayerFeatureDiagnostics?.warnings?.[0] ?? `Lineup status ${statusLabel(input.lineupPlayerFeatureDiagnostics?.status)}.`,
    },
    {
      label: "Injury layer",
      status: input.injuryAvailabilityDiagnostics?.status ?? "missing",
      note: input.injuryAvailabilityDiagnostics?.warnings?.[0] ?? `Injury status ${statusLabel(input.injuryAvailabilityDiagnostics?.status)}.`,
    },
    {
      label: "Weather / ballpark",
      status: input.weatherBallparkFeatureDiagnostics?.status ?? "missing",
      note: input.weatherBallparkFeatureDiagnostics?.warnings?.[0] ?? `Weather status ${statusLabel(input.weatherBallparkFeatureDiagnostics?.status)}.`,
    },
    {
      label: "Pitchers / bullpen",
      status: input.pitcherFeatureDiagnostics?.status ?? input.bullpenFeatureDiagnostics?.status ?? "missing",
      note: input.pitcherFeatureDiagnostics?.warnings?.[0] ?? input.bullpenFeatureDiagnostics?.warnings?.[0] ?? "Pitcher / bullpen diagnostics unavailable.",
    },
    {
      label: "Paper performance",
      status: input.paperPerformanceDiagnostics?.status ?? "missing",
      note: input.paperPerformanceDiagnostics?.summary?.settledRows
        ? `Settled rows: ${input.paperPerformanceDiagnostics.summary.settledRows}`
        : "Research-only sample still small.",
    },
  ];

  const diagnostics: CombinedRiskGateDiagnostics = {
    status: totalRows ? (betCandidateRows > 0 ? "available" : "partial") : "missing",
    available: totalRows > 0,
    totalRows,
    betCandidateRows,
    watchlistRows: watchlistCount,
    researchOnlyRows,
    blockedRows,
    lowRiskRows,
    mediumRiskRows,
    highRiskRows,
    unknownRiskRows,
    averageDiagnosticCalibratedEdge,
    averageCalibratedProbability,
    averageMarketProbability,
    officialPickEligible: false,
    officialEdgeAllowed: false,
    isPaperOnly: true,
    realMoneyDisabled: true,
      warnings: uniqueStrings([
      ...warnings,
      totalRows === 0 ? "No combined risk rows available yet." : undefined,
      marketMatchCount(input) === 0 ? "No clean matched Polymarket MLB market." : undefined,
      gameStatusValidationBlocked > 0 ? `${gameStatusValidationBlocked} MLB rows blocked by status validation.` : undefined,
      !input.marketPriceDiagnostics?.marketPricesConnected && !input.marketPriceDiagnostics?.cacheUsed
        ? "Polymarket prices are not connected."
        : undefined,
      input.pythonMlbEngineStatus?.officialPickEligible ? undefined : "Official pick eligibility remains blocked.",
      input.paperPerformanceDiagnostics?.summary && input.paperPerformanceDiagnostics.summary.settledRows < 10 ? "Small sample size - research only" : undefined,
    ]),
    generatedAt: new Date().toISOString(),
    sourcePath,
    sourceDiagnostics,
  };

  return {
    diagnostics,
    rows: sourceRows,
    warnings: diagnostics.warnings,
    generatedAt: diagnostics.generatedAt,
    sourcePath,
  };
}
