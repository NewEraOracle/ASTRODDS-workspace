import { NextResponse } from "next/server";
import path from "node:path";

import { loadWeatherBallparkFeatureStatus } from "@/lib/astrodss/mlb/weather-ballpark-feature-status";
import { loadLineupPlayerFeatureStatus } from "@/lib/astrodss/mlb/lineup-player-feature-status";
import { loadHistoricalExpansionStatus, MLB_HISTORICAL_EXPANSION_REPORT_PATH } from "@/lib/astrodss/mlb/historical-expansion-status";
import { loadBullpenFeatureStatus } from "@/lib/astrodss/mlb/bullpen-feature-status";
import { loadPythonMlbEngineStatus, PYTHON_MLB_MODEL_STATUS_PATH } from "@/lib/astrodss/mlb/python-engine-status";
import { loadPitcherFeatureStatus } from "@/lib/astrodss/mlb/pitcher-feature-status";
import { loadPitcherModelComparisonStatus } from "@/lib/astrodss/mlb/pitcher-model-comparison-status";
import { loadPaperWatchlistClvDiagnostics } from "@/lib/astrodss/mlb/paper-watchlist-clv";
import { buildMlbPaperWatchlist } from "@/lib/astrodss/mlb/paper-watchlist";
import { loadPaperWatchlistLedgerStatus } from "@/lib/astrodss/mlb/paper-watchlist-ledger";
import { loadPaperWatchlistPerformanceAnalysis } from "@/lib/astrodss/mlb/paper-performance-analysis";
import { loadPythonMlbPredictions, PYTHON_MLB_PREDICTIONS_PATH, type PythonMlbPrediction } from "@/lib/astrodss/mlb/python-predictions";
import { buildPolymarketMlbMatchDiagnostics } from "@/lib/astrodss/sports-data/polymarket-mlb-match";
import { discoverPolymarketMlbMoneylineMarkets, type PolymarketMlbMoneylineMarket } from "@/lib/astrodss/sports-data/polymarket-mlb-markets";
import { buildUnifiedSignals, serializeUnifiedSignal } from "@/lib/astrodss/signal-engine";
import { scanAstroddsSport } from "@/lib/astrodss/sports-data/scanner";
import { getTelegramConfig } from "@/lib/astrodss/wallets/telegram";
import { scanWhaleWallets } from "@/lib/astrodss/wallets/wallet-scanner";
import type { AstroddsGameScan } from "@/lib/astrodss/sports-data/types";


type SerializedUnifiedSignal = ReturnType<typeof serializeUnifiedSignal>;

type UnifiedNoBetReason = {
  reason: string;
  count: number;
};

function addNoBetReason(reasons: Map<string, number>, reason: string, count = 1) {
  if (count <= 0) return;
  reasons.set(reason, (reasons.get(reason) ?? 0) + count);
}

function buildNoBetReasons(signals: SerializedUnifiedSignal[], scan?: Awaited<ReturnType<typeof scanAstroddsSport>>): UnifiedNoBetReason[] {
  const reasons = new Map<string, number>();
  const noLiveData = !scan || scan.diagnostics.sportApi.status === "FAILED" || (scan.diagnostics.sportApi.gamesFetched === 0 && signals.length === 0);
  if (noLiveData) {
    addNoBetReason(reasons, "No Bet - live MLB data unavailable", 1);
    addNoBetReason(reasons, "No Bet - no verified market price", 1);
    addNoBetReason(reasons, "No Bet - lineup cannot be evaluated without game rows", 1);
  }
  const official = signals.filter((signal) => signal.decision === "ELITE" || signal.decision === "STRONG_BUY" || signal.decision === "BUY");
  const dataOnly = signals.filter((signal) => signal.signalType === "DATA_ONLY");
  const watchOrWait = signals.filter((signal) => signal.decision === "WATCH" || signal.decision === "WAIT");
  const missingPrice = signals.filter((signal) => !signal.entryPrice).length;
  const badBook = signals.filter((signal) => signal.orderBookQuality === "POOR" || signal.orderBookQuality === "NO_LIQUIDITY" || signal.orderBookQuality === "NO_CLOB_TOKEN_ID" || signal.orderBookQuality === "NOT_CONNECTED").length;
  const lowEdge = signals.filter((signal) => typeof signal.edge === "number" && signal.edge < 0.05).length;
  const lowDataQuality = signals.filter((signal) => signal.dataQuality === "LOW" || signal.dataQuality === "VERY_LOW" || signal.dataQuality === "DATA_ONLY").length;
  const missingLineups = signals.filter((signal) => signal.lineupImpact?.lineupStatus === "missing").length;
  const projectedLineups = signals.filter((signal) => signal.lineupImpact?.lineupStatus === "projected").length;

  if (scan?.diagnostics.sportApi.gamesFetched && !scan.diagnostics.matching.matchedGamesCount) {
    addNoBetReason(reasons, "No clean matched Polymarket MLB market", scan.diagnostics.sportApi.gamesFetched);
  }
  addNoBetReason(reasons, "Missing real odds or entry price", missingPrice);
  addNoBetReason(reasons, "Order book missing or blocked", badBook);
  addNoBetReason(reasons, "Edge below official threshold", lowEdge);
  addNoBetReason(reasons, "Low or data-only quality", lowDataQuality);
  addNoBetReason(reasons, "Lineup data unavailable", missingLineups);
  addNoBetReason(reasons, "Watchlist - lineup not confirmed yet", projectedLineups);
  addNoBetReason(reasons, "Watch/WAIT guardrail applied", watchOrWait.length);
  if (!official.length) addNoBetReason(reasons, "No official +EV paper pick passed all guardrails", Math.max(1, signals.length));
  if (dataOnly.length) addNoBetReason(reasons, "Model leans are data-only until odds connect", dataOnly.length);
  for (const warning of scan?.warnings.slice(0, 3) ?? []) addNoBetReason(reasons, warning, 1);

  return Array.from(reasons, ([reason, count]) => ({ reason, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);
}

type TodayPredictionMarketDiagnostics = {
  todayPredictionsEvaluated: number;
  highConfidenceMatches: number;
  mediumConfidenceMatches: number;
  lowConfidenceMatches: number;
  unmatchedPredictions: number;
  diagnosticEdgesCalculated: number;
  diagnosticCalibratedEdgesCalculated: number;
  calibratedProbabilitiesAvailable: number;
  calibrationMappingStatus: string;
  officialEdgesAllowed: 0;
  warnings: string[];
  bestDiagnosticEdge?: {
    gameId?: string;
    game?: string;
    marketQuestion?: string;
    modelProbability?: number;
    marketProbability?: number | null;
    diagnosticRawEdge?: number;
    diagnosticRawEdgePct?: number;
    calibratedProbability?: number;
    diagnosticCalibratedEdge?: number;
    diagnosticCalibratedEdgePct?: number;
    calibrationMappingStatus?: string;
    matchConfidence?: string;
  };
};

type MarketMetadata = {
  marketPricesConnected: boolean;
  cacheUsed?: boolean;
  cacheStatus?: string;
  cacheAgeSeconds?: number;
  cacheGeneratedAt?: string;
  generatedAt?: string;
};

function predictionGameId(prediction: PythonMlbPrediction, index: number) {
  return prediction.gameId ?? `python-mlb-prediction-${index}`;
}

function predictionGameLabel(prediction: PythonMlbPrediction) {
  return `${prediction.awayTeam ?? "Away"} vs ${prediction.homeTeam ?? "Home"}`;
}

function predictionToDiagnosticGame(prediction: PythonMlbPrediction, index: number): AstroddsGameScan | undefined {
  if (prediction.marketType !== "moneyline") return undefined;
  if (!prediction.homeTeam || !prediction.awayTeam) return undefined;

  return {
    id: predictionGameId(prediction, index),
    sport: "MLB",
    league: "MLB",
    game: predictionGameLabel(prediction),
    homeTeam: prediction.homeTeam,
    awayTeam: prediction.awayTeam,
    startTime: prediction.date,
    liveStatus: "PRE_GAME",
    keyContext: ["Python MLB research-only today prediction"],
    keyPlayerStatus: "Lineups, pitchers, bullpen, and weather missing in Python today export",
    markets: [],
    dataStatus: "PARTIAL",
    source: "PYTHON_MLB_RESEARCH_ONLY",
    modelPick: {
      modelLeanSide: "HOME",
      modelLeanTeam: prediction.homeTeam,
      modelConfidence: 0,
      modelScore: 0,
      dataQuality: "F",
      dataQualityScore: 0,
      pitcherScore: 0,
      lineupScore: 0,
      injuryScore: 0,
      teamFormScore: 0,
      weatherScore: 0,
      modelReason: "Raw home-win probability from Python baseline model; research only.",
      missingDataWarnings: prediction.risks ?? ["Market price and calibration mapping unavailable."],
      officialBetBlockedReason: "Research-only Python prediction; official edge gate remains closed.",
      action: "WAIT_FOR_ODDS",
    },
  };
}

function uniqueStrings(values: Array<string | undefined>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value && value.trim()))));
}

function marketPriceSource(metadata: MarketMetadata) {
  if (metadata.cacheUsed) return "polymarket_cache";
  if (metadata.marketPricesConnected) return "polymarket_live";
  return "unavailable";
}

function enrichTodayPredictionsWithMarketDiagnostics(
  predictions: PythonMlbPrediction[],
  markets: PolymarketMlbMoneylineMarket[],
  calibrationQuality: string | undefined,
  metadata: MarketMetadata,
) {
  const diagnosticGames = predictions
    .map((prediction, index) => predictionToDiagnosticGame(prediction, index))
    .filter((game): game is AstroddsGameScan => Boolean(game));
  const modelProbabilitiesByGameId = Object.fromEntries(
    predictions
      .map((prediction, index) => [predictionGameId(prediction, index), prediction.rawModelProbability] as const)
      .filter((entry): entry is [string, number] => typeof entry[1] === "number"),
  );
  const rawDiagnostics = buildPolymarketMlbMatchDiagnostics(diagnosticGames, markets, {
    calibrationQuality,
    modelProbabilitiesByGameId,
  });
  const matchesByGameId = new Map(rawDiagnostics.matches.map((match) => [match.gameId, match]));
  const source = marketPriceSource(metadata);
  const timestamp = metadata.cacheGeneratedAt ?? metadata.generatedAt;

  const enrichedPredictions = predictions.map((prediction, index) => {
    const gameId = predictionGameId(prediction, index);
    const match = matchesByGameId.get(gameId);
    const diagnosticEdgeAvailable = typeof match?.diagnosticRawEdge === "number";
    const calibrationMappingStatus = prediction.calibrationMappingStatus ?? (typeof prediction.calibratedProbability === "number" ? "research_only" : "missing");
    const diagnosticCalibratedEdgeAvailable =
      (match?.matchConfidence === "high" || match?.matchConfidence === "medium") &&
      typeof match.marketProbability === "number" &&
      typeof prediction.calibratedProbability === "number";
    const diagnosticCalibratedEdge = diagnosticCalibratedEdgeAvailable ? (prediction.calibratedProbability ?? 0) - (match?.marketProbability ?? 0) : null;
    const matchWarnings = uniqueStrings([
      ...(match
        ? match.matchWarnings
        : [prediction.marketType === "moneyline" ? "No Polymarket MLB moneyline market match found for this prediction." : "Only moneyline predictions are supported for market diagnostics."]),
      !match || match.matchConfidence === "low" || match.matchConfidence === "none" ? "Market match not reliable enough" : undefined,
      match?.marketProbability === null ? "Market probability unavailable" : undefined,
      typeof prediction.calibratedProbability !== "number" ? "Calibrated probability unavailable" : undefined,
    ]);
    const officialEdgeBlockReasons = uniqueStrings([
      ...(prediction.officialEdgeBlockReasons ?? []),
      ...(match?.officialEdgeBlockReasons ?? []),
      calibrationQuality === "weak" ? "Calibration weak - diagnostic only" : undefined,
      calibrationMappingStatus === "research_only" ? "Calibration mapping research-only" : "No calibrated probability mapping",
      "Official edge gate remains closed",
      "Raw model edge is diagnostics-only",
    ]);

    return {
      ...prediction,
      polymarketMatch: match && match.matchConfidence !== "none"
        ? {
            marketId: match.matchedMarketId,
            question: match.matchedMarketQuestion,
            slug: match.matchedMarketSlug,
            outcome: match.matchedOutcome,
          }
        : null,
      marketProbability: match?.marketProbability ?? null,
      diagnosticRawEdge: diagnosticEdgeAvailable ? match?.diagnosticRawEdge : null,
      diagnosticRawEdgePct: diagnosticEdgeAvailable ? match?.diagnosticRawEdgePct : null,
      diagnosticCalibratedEdge,
      diagnosticCalibratedEdgePct: typeof diagnosticCalibratedEdge === "number" ? diagnosticCalibratedEdge * 100 : null,
      calibrationMappingStatus,
      diagnosticOnly: true,
      diagnosticEdgeAllowed: diagnosticEdgeAvailable,
      officialEdgeAllowed: false,
      officialEdgeBlockReasons,
      matchConfidence: match?.matchConfidence ?? "none",
      matchWarnings,
      marketPriceSource: source,
      marketPriceTimestamp: timestamp,
      marketPriceCacheUsed: Boolean(metadata.cacheUsed),
      marketPriceCacheStatus: metadata.cacheStatus,
      marketPriceCacheAgeSeconds: metadata.cacheAgeSeconds,
    };
  });
  const edgeCandidates = enrichedPredictions
    .filter((prediction) => typeof prediction.diagnosticRawEdge === "number")
    .sort((a, b) => (b.diagnosticRawEdge ?? -Infinity) - (a.diagnosticRawEdge ?? -Infinity));
  const best = edgeCandidates[0];
  const calibratedEdgeCandidates = enrichedPredictions
    .filter((prediction) => typeof prediction.diagnosticCalibratedEdge === "number")
    .sort((a, b) => (b.diagnosticCalibratedEdge ?? -Infinity) - (a.diagnosticCalibratedEdge ?? -Infinity));
  const bestDiagnosticRawEdge = typeof best?.diagnosticRawEdge === "number" ? best.diagnosticRawEdge : undefined;
  const bestDiagnosticRawEdgePct = typeof best?.diagnosticRawEdgePct === "number" ? best.diagnosticRawEdgePct : undefined;
  const bestDiagnosticCalibratedEdge = typeof best?.diagnosticCalibratedEdge === "number" ? best.diagnosticCalibratedEdge : undefined;
  const bestDiagnosticCalibratedEdgePct = typeof best?.diagnosticCalibratedEdgePct === "number" ? best.diagnosticCalibratedEdgePct : undefined;
  const calibratedProbabilitiesAvailable = enrichedPredictions.filter((prediction) => typeof prediction.calibratedProbability === "number").length;
  const calibrationMappingStatuses = uniqueStrings(enrichedPredictions.map((prediction) => prediction.calibrationMappingStatus));
  const calibrationMappingStatus = calibrationMappingStatuses.includes("research_only") ? "research_only" : (calibrationMappingStatuses[0] ?? "missing");
  const warnings = uniqueStrings([
    ...rawDiagnostics.warnings,
    calibrationQuality === "weak" ? "Calibration weak - diagnostic only; official edge remains blocked." : undefined,
    calibratedProbabilitiesAvailable ? "Calibration mapping is research-only; calibrated probabilities cannot create official picks." : "Calibration mapping unavailable for today predictions.",
    !metadata.marketPricesConnected ? "Polymarket market prices are not connected; today prediction market diagnostics may be unmatched." : undefined,
    "Today prediction market comparison is research-only and cannot create official picks.",
  ]).slice(0, 25);

  const diagnostics: TodayPredictionMarketDiagnostics = {
    todayPredictionsEvaluated: predictions.length,
    highConfidenceMatches: rawDiagnostics.highConfidenceMatches,
    mediumConfidenceMatches: rawDiagnostics.mediumConfidenceMatches,
    lowConfidenceMatches: rawDiagnostics.lowConfidenceMatches,
    unmatchedPredictions: predictions.length - rawDiagnostics.highConfidenceMatches - rawDiagnostics.mediumConfidenceMatches - rawDiagnostics.lowConfidenceMatches,
    diagnosticEdgesCalculated: rawDiagnostics.diagnosticEdgesCalculated,
    diagnosticCalibratedEdgesCalculated: calibratedEdgeCandidates.length,
    calibratedProbabilitiesAvailable,
    calibrationMappingStatus,
    officialEdgesAllowed: 0,
    warnings,
    bestDiagnosticEdge: best && typeof bestDiagnosticRawEdge === "number"
      ? {
          gameId: best.gameId,
          game: `${best.awayTeam ?? "Away"} vs ${best.homeTeam ?? "Home"}`,
          marketQuestion: best.polymarketMatch?.question,
          modelProbability: best.rawModelProbability,
          marketProbability: best.marketProbability,
          diagnosticRawEdge: bestDiagnosticRawEdge,
          diagnosticRawEdgePct: bestDiagnosticRawEdgePct,
          calibratedProbability: best.calibratedProbability,
          diagnosticCalibratedEdge: bestDiagnosticCalibratedEdge,
          diagnosticCalibratedEdgePct: bestDiagnosticCalibratedEdgePct,
          calibrationMappingStatus: best.calibrationMappingStatus,
          matchConfidence: best.matchConfidence,
        }
      : undefined,
  };

  return { predictions: enrichedPredictions, diagnostics };
}
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const sport = (searchParams.get("sport") ?? "MLB").toUpperCase();
  const errors: string[] = [];
  const telegram = getTelegramConfig();
  if (sport !== "MLB") errors.push("Unified signal MVP is MLB-only for now.");

  const [scanResult, whaleResult, pythonPredictionResult, pythonStatusResult, polymarketMarketResult, modelComparisonResult, weatherBallparkResult, lineupPlayerResult, historicalExpansionResult] = await Promise.allSettled([
    scanAstroddsSport("MLB"),
    scanWhaleWallets({ sport: "MLB" }),
    loadPythonMlbPredictions(),
    loadPythonMlbEngineStatus(),
    discoverPolymarketMlbMoneylineMarkets(),
    loadPitcherModelComparisonStatus(),
    loadWeatherBallparkFeatureStatus(),
    loadLineupPlayerFeatureStatus(),
    loadHistoricalExpansionStatus(),
  ]);

  if (scanResult.status === "rejected") {
    errors.push(`Scan engine failed: ${scanResult.reason instanceof Error ? scanResult.reason.message : "Unknown scan failure"}`);
  }

  if (whaleResult.status === "rejected") {
    errors.push(`Whale scan failed: ${whaleResult.reason instanceof Error ? whaleResult.reason.message : "Unknown whale scan failure"}`);
  }

  if (pythonPredictionResult.status === "rejected") {
    errors.push(`Python MLB prediction loader failed: ${pythonPredictionResult.reason instanceof Error ? pythonPredictionResult.reason.message : "Unknown loader failure"}`);
  }

  if (pythonStatusResult.status === "rejected") {
    errors.push(`Python MLB model status loader failed: ${pythonStatusResult.reason instanceof Error ? pythonStatusResult.reason.message : "Unknown status loader failure"}`);
  }

  if (polymarketMarketResult.status === "rejected") {
    errors.push(`Polymarket MLB market discovery failed: ${polymarketMarketResult.reason instanceof Error ? polymarketMarketResult.reason.message : "Unknown market discovery failure"}`);
  }

  if (modelComparisonResult.status === "rejected") {
    errors.push(`Pitcher model comparison loader failed: ${modelComparisonResult.reason instanceof Error ? modelComparisonResult.reason.message : "Unknown comparison loader failure"}`);
  }

  if (weatherBallparkResult.status === "rejected") {
    errors.push(`Weather / ballpark feature loader failed: ${weatherBallparkResult.reason instanceof Error ? weatherBallparkResult.reason.message : "Unknown weather / ballpark loader failure"}`);
  }

  if (lineupPlayerResult.status === "rejected") {
    errors.push(`Lineup / player feature loader failed: ${lineupPlayerResult.reason instanceof Error ? lineupPlayerResult.reason.message : "Unknown lineup / player loader failure"}`);
  }

  if (historicalExpansionResult.status === "rejected") {
    errors.push(`Historical expansion loader failed: ${historicalExpansionResult.reason instanceof Error ? historicalExpansionResult.reason.message : "Unknown historical expansion loader failure"}`);
  }

  const scan = scanResult.status === "fulfilled" ? scanResult.value : undefined;
  const whale = whaleResult.status === "fulfilled" ? whaleResult.value : undefined;
  const pythonMlbPredictions = pythonPredictionResult.status === "fulfilled"
    ? pythonPredictionResult.value
    : { available: false, sourcePath: PYTHON_MLB_PREDICTIONS_PATH, predictions: [], warnings: ["Python MLB prediction loader failed."] };
  const pythonMlbEngineStatus = pythonStatusResult.status === "fulfilled"
    ? pythonStatusResult.value
    : {
        engineAvailable: false,
        modelAvailable: false,
        modelVersion: "unknown",
        modelType: "unknown",
        calibrationQuality: "missing",
        supportedMarkets: ["moneyline"],
        disabledMarkets: ["runline"],
        officialPickEligible: false,
        officialPickBlockReasons: ["Python MLB model status loader failed"],
        warnings: ["Python MLB model status loader failed."],
        generatedAt: undefined,
        sourcePath: PYTHON_MLB_MODEL_STATUS_PATH,
      };
  const pythonTodayPredictionStatus = {
    todayPredictionsAvailable: pythonMlbPredictions.available,
    todayPredictionCount: pythonMlbPredictions.predictions.length,
    officialUseBlocked: true,
    officialUseBlockReasons: [
      "Python today predictions are research-only diagnostics",
      "Calibration is not production-ready",
      "No market prices or calibrated probability mapping are attached",
    ],
  };
  const pythonMlbEngineStatusForResponse = {
    ...pythonMlbEngineStatus,
    ...pythonTodayPredictionStatus,
  };
  const polymarketMlbMarkets = polymarketMarketResult.status === "fulfilled"
    ? polymarketMarketResult.value
    : {
        status: "FAILED",
        marketPricesConnected: false,
        supportedMarkets: ["moneyline"],
        disabledMarkets: ["runline"],
        futureMarkets: ["total_runs"],
        markets: [],
        cacheUsed: false,
        cacheStatus: "missing",
        cacheAgeSeconds: undefined,
        cacheGeneratedAt: undefined,
        sourceDiagnostics: [],
        warnings: ["Polymarket MLB market discovery failed."],
        generatedAt: new Date().toISOString(),
      };
  const modelComparisonDiagnostics = modelComparisonResult.status === "fulfilled"
    ? modelComparisonResult.value
    : {
        status: "missing",
        recommendation: "needs_more_data",
        baselineModelVersion: "unknown",
        baselineModelType: "unknown",
        pitcherModelVersion: "unknown",
        pitcherModelType: "unknown",
        reasons: [],
        warnings: ["Pitcher model comparison loader failed."],
        generatedAt: undefined,
        sourcePath: path.join(process.cwd(), "mlb-engine", "models", "moneyline_model_comparison_report.json"),
      };
  const weatherBallparkFeatureDiagnostics = weatherBallparkResult.status === "fulfilled"
    ? weatherBallparkResult.value
    : {
        status: "missing",
        available: false,
        gamesWithVenueData: 0,
        gamesWithWeatherData: 0,
        gamesMissingWeatherData: 0,
        gamesWithBallparkFactorData: 0,
        dataQuality: "missing",
        warnings: ["Weather / ballpark feature loader failed."],
        generatedAt: undefined,
        sourcePath: path.join(process.cwd(), "mlb-engine", "data", "processed", "mlb_weather_ballpark_features_report.json"),
      };
  const lineupPlayerFeatureDiagnostics = lineupPlayerResult.status === "fulfilled"
    ? lineupPlayerResult.value
    : {
        status: "missing",
        available: false,
        gamesWithConfirmedLineupData: 0,
        gamesWithProjectedOrProxyLineupData: 0,
        gamesMissingLineupData: 0,
        dataQuality: "missing",
        proxyUsed: false,
        warnings: ["Lineup / player feature loader failed."],
        generatedAt: undefined,
        sourcePath: path.join(process.cwd(), "mlb-engine", "data", "processed", "mlb_lineup_player_features_report.json"),
      };
  const historicalExpansionDiagnostics = historicalExpansionResult.status === "fulfilled"
    ? historicalExpansionResult.value
    : {
        status: "missing",
        available: false,
        historicalWindow: "2016-2026",
        startYear: 2016,
        endYear: 2026,
        yearsIncluded: [],
        totalGamesRead: 0,
        completedGamesUsed: 0,
        incompleteGamesSkipped: 0,
        malformedGamesSkipped: 0,
        outputRowCount: 0,
        warnings: ["Historical expansion loader failed."],
        generatedAt: undefined,
        sourcePath: MLB_HISTORICAL_EXPANSION_REPORT_PATH,
      };
  const marketPriceDiagnostics = {
    status: polymarketMlbMarkets.status,
    marketPricesConnected: polymarketMlbMarkets.marketPricesConnected,
    moneylineMarketsFound: polymarketMlbMarkets.markets.length,
    cacheUsed: polymarketMlbMarkets.cacheUsed,
    cacheStatus: polymarketMlbMarkets.cacheStatus,
    cacheAgeSeconds: polymarketMlbMarkets.cacheAgeSeconds,
    cacheGeneratedAt: polymarketMlbMarkets.cacheGeneratedAt,
    supportedMarkets: polymarketMlbMarkets.supportedMarkets,
    disabledMarkets: polymarketMlbMarkets.disabledMarkets,
    futureMarkets: polymarketMlbMarkets.futureMarkets,
    warnings: polymarketMlbMarkets.warnings,
    sourceDiagnostics: polymarketMlbMarkets.sourceDiagnostics,
    generatedAt: polymarketMlbMarkets.generatedAt,
  };
  const signals = scan
    ? buildUnifiedSignals(scan.games, {
        whaleConsensus: whale?.consensus ?? [],
        telegramSignalsEnabled: telegram.signalsEnabled,
        telegramWhaleAlertsEnabled: telegram.whaleAlertsEnabled,
      }).map(serializeUnifiedSignal)
    : [];
  const modelProbabilitiesByGameId = Object.fromEntries(
    signals
      .filter((signal) => signal.gameId && typeof signal.modelProbability === "number")
      .map((signal) => [signal.gameId as string, signal.modelProbability]),
  );
  const marketMatchDiagnostics = scan
    ? buildPolymarketMlbMatchDiagnostics(scan.games, polymarketMlbMarkets.markets, {
        calibrationQuality: pythonMlbEngineStatus.calibrationQuality,
        modelProbabilitiesByGameId,
      })
    : {
        gamesEvaluated: 0,
        marketsEvaluated: polymarketMlbMarkets.markets.length,
        highConfidenceMatches: 0,
        mediumConfidenceMatches: 0,
        lowConfidenceMatches: 0,
        unmatchedGames: 0,
        diagnosticEdgesCalculated: 0,
        warnings: ["No MLB scan rows available for Polymarket market matching."],
        matches: [],
      };
  const todayPredictionMarketMatch = enrichTodayPredictionsWithMarketDiagnostics(
    pythonMlbPredictions.predictions,
    polymarketMlbMarkets.markets,
    pythonMlbEngineStatus.calibrationQuality,
    polymarketMlbMarkets,
  );
  const enrichedPythonMlbPredictions = todayPredictionMarketMatch.predictions;
  const todayPredictionMarketDiagnostics = todayPredictionMarketMatch.diagnostics;
  const paperWatchlist = buildMlbPaperWatchlist(enrichedPythonMlbPredictions, {
    calibrationQuality: pythonMlbEngineStatus.calibrationQuality,
  });
  const paperWatchlistLedgerDiagnostics = await loadPaperWatchlistLedgerStatus();
  const paperClvDiagnostics = await loadPaperWatchlistClvDiagnostics();
  const paperPerformanceDiagnostics = await loadPaperWatchlistPerformanceAnalysis();
  const pitcherFeatureDiagnostics = await loadPitcherFeatureStatus();
  const bullpenFeatureDiagnostics = await loadBullpenFeatureStatus();
  const matchesByGameId = new Map(marketMatchDiagnostics.matches.map((match) => [match.gameId, match]));
  const signalsWithMarketDiagnostics = signals.map((signal) => {
    const match = signal.gameId ? matchesByGameId.get(signal.gameId) : undefined;
    if (!match) return signal;
    return {
      ...signal,
      polymarketMatch: match,
      diagnosticRawEdge: match.diagnosticRawEdge,
      diagnosticRawEdgePct: match.diagnosticRawEdgePct,
      diagnosticOnly: true,
      officialEdgeAllowed: false,
      officialEdgeBlockReasons: match.officialEdgeBlockReasons,
    };
  });
  const noBetReasons = buildNoBetReasons(signalsWithMarketDiagnostics, scan);
  const noLiveData = !scan || scan.diagnostics.sportApi.status === "FAILED" || (scan.diagnostics.sportApi.gamesFetched === 0 && signals.length === 0);
  const sourceDiagnostics = scan?.diagnostics.sourceDiagnostics ?? [];

  return NextResponse.json(
    {
      sport: "MLB",
      modelAvailable: Boolean(scan),
      whaleAvailable: Boolean(whale),
      generatedAt: new Date().toISOString(),
      signals: signalsWithMarketDiagnostics,
      noBetReasons,
      summary: {
        status: noLiveData ? "no_live_data" : signals.length ? "signals_ready" : "no_qualified_signals",
        totalSignals: signalsWithMarketDiagnostics.length,
        officialPicks: signalsWithMarketDiagnostics.filter((signal) => signal.decision === "ELITE" || signal.decision === "STRONG_BUY" || signal.decision === "BUY").length,
        strongBuys: signalsWithMarketDiagnostics.filter((signal) => signal.decision === "ELITE" || signal.decision === "STRONG_BUY").length,
        watchlist: signalsWithMarketDiagnostics.filter((signal) => signal.decision === "WATCH").length,
        dataOnly: signalsWithMarketDiagnostics.filter((signal) => signal.signalType === "DATA_ONLY").length,
      },
      sourceDiagnostics,
      polymarketMlbMarkets: {
        ...polymarketMlbMarkets,
        markets: polymarketMlbMarkets.markets.slice(0, 30),
      },
      marketPriceDiagnostics,
      todayPredictionMarketDiagnostics,
      paperWatchlistDiagnostics: paperWatchlist.watchlistSummary,
      paperWatchlistRows: paperWatchlist.watchlistRows,
      paperWatchlistLedgerDiagnostics: {
        ...paperWatchlistLedgerDiagnostics,
        rowsWithEntryPrice: paperClvDiagnostics.summary.rowsWithEntryPrice,
        rowsWithLatestPrice: paperClvDiagnostics.summary.rowsWithLatestPrice,
        rowsWithClosingPrice: paperClvDiagnostics.summary.rowsWithClosingPrice,
        positiveClvRows: paperClvDiagnostics.summary.positiveClvRows,
        negativeClvRows: paperClvDiagnostics.summary.negativeClvRows,
        neutralClvRows: paperClvDiagnostics.summary.neutralClvRows,
        missingClvRows: paperClvDiagnostics.summary.missingClvRows,
        averageClv: paperClvDiagnostics.summary.averageClv,
        averageClvPct: paperClvDiagnostics.summary.averageClvPct,
        clvWarnings: paperClvDiagnostics.summary.warnings,
      },
      paperClvDiagnostics,
      paperPerformanceDiagnostics,
      pitcherFeatureDiagnostics,
      weatherBallparkFeatureDiagnostics,
      lineupPlayerFeatureDiagnostics,
      historicalExpansionDiagnostics,
      bullpenFeatureDiagnostics,
      modelComparisonDiagnostics,
      marketMatchDiagnostics: {
        ...marketMatchDiagnostics,
        matches: marketMatchDiagnostics.matches.slice(0, 50),
      },
      pythonMlbEngine: {
        available: pythonMlbPredictions.available,
        sourcePath: pythonMlbPredictions.sourcePath,
        predictions: enrichedPythonMlbPredictions,
        warnings: pythonMlbPredictions.warnings,
        activeMarkets: ["moneyline", "total_runs"],
        officialPickOverride: false,
        modelAvailable: pythonMlbEngineStatus.modelAvailable,
        todayPredictionsAvailable: pythonTodayPredictionStatus.todayPredictionsAvailable,
        todayPredictionCount: pythonTodayPredictionStatus.todayPredictionCount,
        todayPredictionMarketDiagnostics,
        paperWatchlistDiagnostics: paperWatchlist.watchlistSummary,
        paperWatchlistLedgerDiagnostics: {
          ...paperWatchlistLedgerDiagnostics,
          rowsWithEntryPrice: paperClvDiagnostics.summary.rowsWithEntryPrice,
          rowsWithLatestPrice: paperClvDiagnostics.summary.rowsWithLatestPrice,
          rowsWithClosingPrice: paperClvDiagnostics.summary.rowsWithClosingPrice,
          positiveClvRows: paperClvDiagnostics.summary.positiveClvRows,
          negativeClvRows: paperClvDiagnostics.summary.negativeClvRows,
          neutralClvRows: paperClvDiagnostics.summary.neutralClvRows,
          missingClvRows: paperClvDiagnostics.summary.missingClvRows,
          averageClv: paperClvDiagnostics.summary.averageClv,
          averageClvPct: paperClvDiagnostics.summary.averageClvPct,
          clvWarnings: paperClvDiagnostics.summary.warnings,
        },
        paperClvDiagnostics,
        paperPerformanceDiagnostics,
        pitcherFeatureDiagnostics,
        weatherBallparkFeatureDiagnostics,
        lineupPlayerFeatureDiagnostics,
        historicalExpansionDiagnostics,
        bullpenFeatureDiagnostics,
        officialUseBlocked: pythonTodayPredictionStatus.officialUseBlocked,
        calibrationQuality: pythonMlbEngineStatus.calibrationQuality,
        officialPickEligible: pythonMlbEngineStatus.officialPickEligible,
        officialPickBlockReasons: pythonMlbEngineStatus.officialPickBlockReasons,
        supportedMarkets: pythonMlbEngineStatus.supportedMarkets,
        disabledMarkets: pythonMlbEngineStatus.disabledMarkets,
        modelVersion: pythonMlbEngineStatus.modelVersion,
        generatedAt: pythonMlbEngineStatus.generatedAt,
      },
      pythonMlbEngineStatus: pythonMlbEngineStatusForResponse,
      scanStatus: scan?.sourceStatus,
      whaleStatus: whale?.sourceStatus ?? "NOT_CONNECTED",
      errors: [...errors, ...(scan?.warnings ?? []), ...(whale?.errors ?? []), ...pythonMlbPredictions.warnings, ...pythonMlbEngineStatus.warnings, ...marketPriceDiagnostics.warnings, ...todayPredictionMarketDiagnostics.warnings, ...pitcherFeatureDiagnostics.warnings, ...weatherBallparkFeatureDiagnostics.warnings, ...lineupPlayerFeatureDiagnostics.warnings, ...historicalExpansionDiagnostics.warnings, ...bullpenFeatureDiagnostics.warnings, ...modelComparisonDiagnostics.warnings],
      telegram: {
        configured: telegram.configured,
        signalsEnabled: telegram.signalsEnabled,
        whaleAlertsEnabled: telegram.whaleAlertsEnabled,
        status: telegram.status,
      },
    },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}
