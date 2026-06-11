import { NextResponse } from "next/server";

import { loadPythonMlbEngineStatus, PYTHON_MLB_MODEL_STATUS_PATH } from "@/lib/astrodss/mlb/python-engine-status";
import { loadPythonMlbPredictions, PYTHON_MLB_PREDICTIONS_PATH } from "@/lib/astrodss/mlb/python-predictions";
import { buildPolymarketMlbMatchDiagnostics } from "@/lib/astrodss/sports-data/polymarket-mlb-match";
import { discoverPolymarketMlbMoneylineMarkets } from "@/lib/astrodss/sports-data/polymarket-mlb-markets";
import { buildUnifiedSignals, serializeUnifiedSignal } from "@/lib/astrodss/signal-engine";
import { scanAstroddsSport } from "@/lib/astrodss/sports-data/scanner";
import { getTelegramConfig } from "@/lib/astrodss/wallets/telegram";
import { scanWhaleWallets } from "@/lib/astrodss/wallets/wallet-scanner";


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
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const sport = (searchParams.get("sport") ?? "MLB").toUpperCase();
  const errors: string[] = [];
  const telegram = getTelegramConfig();
  if (sport !== "MLB") errors.push("Unified signal MVP is MLB-only for now.");

  const [scanResult, whaleResult, pythonPredictionResult, pythonStatusResult, polymarketMarketResult] = await Promise.allSettled([
    scanAstroddsSport("MLB"),
    scanWhaleWallets({ sport: "MLB" }),
    loadPythonMlbPredictions(),
    loadPythonMlbEngineStatus(),
    discoverPolymarketMlbMoneylineMarkets(),
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
      marketMatchDiagnostics: {
        ...marketMatchDiagnostics,
        matches: marketMatchDiagnostics.matches.slice(0, 50),
      },
      pythonMlbEngine: {
        available: pythonMlbPredictions.available,
        sourcePath: pythonMlbPredictions.sourcePath,
        predictions: pythonMlbPredictions.predictions,
        warnings: pythonMlbPredictions.warnings,
        activeMarkets: ["moneyline", "total_runs"],
        officialPickOverride: false,
        modelAvailable: pythonMlbEngineStatus.modelAvailable,
        todayPredictionsAvailable: pythonTodayPredictionStatus.todayPredictionsAvailable,
        todayPredictionCount: pythonTodayPredictionStatus.todayPredictionCount,
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
      errors: [...errors, ...(scan?.warnings ?? []), ...(whale?.errors ?? []), ...pythonMlbPredictions.warnings, ...pythonMlbEngineStatus.warnings, ...marketPriceDiagnostics.warnings],
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