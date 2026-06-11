import type { PythonMlbCalibrationQuality, PythonMlbPrediction } from "./python-predictions";

export type MlbPaperWatchlistTier = "monitor" | "paper_watchlist" | "priority_paper_watchlist";
export type MlbPaperWatchlistDecision = "monitor" | "paper_watchlist" | "priority_paper_watchlist";
export type MlbPaperOfficialDecision = "research_only" | "watchlist_only";
export type MlbPaperWatchlistMatchConfidence = "high" | "medium" | "low" | "none" | string;

export type MlbPaperWatchlistPrediction = Omit<PythonMlbPrediction, "marketProbability"> & {
  diagnosticRawEdge?: number | null;
  diagnosticRawEdgePct?: number | null;
  diagnosticCalibratedEdge?: number | null;
  diagnosticCalibratedEdgePct?: number | null;
  diagnosticOnly?: boolean;
  marketProbability?: number | null;
  matchConfidence?: MlbPaperWatchlistMatchConfidence;
  matchWarnings?: string[];
  calibrationMappingStatus?: string;
  polymarketMatch?: unknown;
};

export type MlbPaperWatchlistRow = {
  gameId?: string;
  date?: string;
  homeTeam?: string;
  awayTeam?: string;
  marketType: "moneyline";
  selectedSide?: string;
  researchSide?: string;
  rawModelProbability: number;
  calibratedProbability: number;
  marketProbability: number;
  diagnosticRawEdge?: number | null;
  diagnosticCalibratedEdge: number;
  diagnosticCalibratedEdgePct: number;
  matchConfidence: "high" | "medium";
  matchWarnings: string[];
  calibrationQuality: PythonMlbCalibrationQuality | string;
  calibrationMappingStatus: string;
  watchlistTier: MlbPaperWatchlistTier;
  watchlistDecision: MlbPaperWatchlistDecision;
  officialDecision: MlbPaperOfficialDecision;
  officialPickEligible: false;
  officialEdgeAllowed: false;
  blockReasons: string[];
  reasons: string[];
  risks: string[];
  isPaperOnly: true;
};

export type MlbPaperWatchlistDiagnostics = {
  totalCandidatesEvaluated: number;
  monitorCount: number;
  paperWatchlistCount: number;
  priorityPaperWatchlistCount: number;
  skippedCount: number;
  officialPicksAllowed: 0;
  warnings: string[];
};

export type MlbPaperWatchlistResult = {
  watchlistRows: MlbPaperWatchlistRow[];
  watchlistSummary: MlbPaperWatchlistDiagnostics;
  warnings: string[];
};

function uniqueStrings(values: Array<string | undefined>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value && value.trim()))));
}

function isUsefulNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function tierForEdge(edge: number): MlbPaperWatchlistTier | undefined {
  if (edge >= 0.06) return "priority_paper_watchlist";
  if (edge >= 0.03) return "paper_watchlist";
  if (edge > 0) return "monitor";
  return undefined;
}

function watchlistDecisionForTier(tier: MlbPaperWatchlistTier, calibrationQuality: string): MlbPaperWatchlistDecision {
  if (calibrationQuality === "weak") return "paper_watchlist";
  return tier;
}

function officialDecisionFor(calibrationQuality: string, calibrationMappingStatus: string): MlbPaperOfficialDecision {
  if (calibrationQuality === "weak" || calibrationMappingStatus === "research_only") return "research_only";
  return "watchlist_only";
}

function researchSideForPrediction(prediction: MlbPaperWatchlistPrediction) {
  if (prediction.pick && prediction.pick !== "research_only") return prediction.pick;
  if (isUsefulNumber(prediction.rawModelProbability)) {
    return prediction.rawModelProbability >= 0.5 ? prediction.homeTeam : prediction.awayTeam;
  }
  return prediction.homeTeam ?? prediction.awayTeam ?? "Research side unavailable";
}

function watchlistReasons(tier: MlbPaperWatchlistTier, edge: number) {
  const edgePct = `${(edge * 100).toFixed(1)}%`;
  if (tier === "priority_paper_watchlist") {
    return [
      `Diagnostic calibrated edge is ${edgePct}, above the research-only priority threshold.`,
      "Market match confidence is high or medium.",
      "This remains a paper watchlist item, not an official ASTRODDS pick.",
    ];
  }
  if (tier === "paper_watchlist") {
    return [
      `Diagnostic calibrated edge is ${edgePct}, above the research-only watchlist threshold.`,
      "Market match confidence is high or medium.",
      "This remains a paper watchlist item, not an official ASTRODDS pick.",
    ];
  }
  return [
    `Diagnostic calibrated edge is ${edgePct}, positive but below watchlist threshold.`,
    "Monitor only unless market/data quality improves.",
    "This remains a paper watchlist item, not an official ASTRODDS pick.",
  ];
}

export function buildMlbPaperWatchlist(
  predictions: MlbPaperWatchlistPrediction[],
  options: { calibrationQuality?: PythonMlbCalibrationQuality | string } = {},
): MlbPaperWatchlistResult {
  const warnings: string[] = [
    "Paper Watchlist is research-only and cannot create official picks, Strong Buys, Telegram alerts, or real-money actions.",
    "Thresholds are diagnostic watchlist thresholds, not official betting thresholds.",
  ];
  const candidatePredictions = predictions.filter((prediction) => prediction.marketType === "moneyline");
  const rows: MlbPaperWatchlistRow[] = [];
  let skippedCount = 0;

  for (const prediction of candidatePredictions) {
    const matchConfidence = prediction.matchConfidence;
    const validMatch = matchConfidence === "high" || matchConfidence === "medium";
    const edge = prediction.diagnosticCalibratedEdge;
    const tier = isUsefulNumber(edge) ? tierForEdge(edge) : undefined;

    if (
      !isUsefulNumber(prediction.rawModelProbability) ||
      !isUsefulNumber(prediction.calibratedProbability) ||
      !isUsefulNumber(prediction.marketProbability) ||
      !validMatch ||
      !isUsefulNumber(edge) ||
      !tier
    ) {
      skippedCount += 1;
      continue;
    }

    const calibrationQuality = prediction.calibrationQuality ?? options.calibrationQuality ?? "missing";
    const calibrationMappingStatus = prediction.calibrationMappingStatus ?? "missing";
    const researchSide = researchSideForPrediction(prediction);
    const matchWarnings = prediction.matchWarnings ?? [];
    const blockReasons = uniqueStrings([
      ...(prediction.officialEdgeBlockReasons ?? []),
      calibrationQuality === "weak" ? "Calibration weak - paper watchlist only" : undefined,
      calibrationMappingStatus === "research_only" ? "Calibration mapping research-only" : "No calibrated probability mapping",
      "Official picks remain blocked",
      "Strong Buys remain blocked",
      "Paper mode only - real-money trading OFF",
    ]);

    rows.push({
      gameId: prediction.gameId,
      date: prediction.date,
      homeTeam: prediction.homeTeam,
      awayTeam: prediction.awayTeam,
      marketType: "moneyline",
      selectedSide: researchSide,
      researchSide,
      rawModelProbability: prediction.rawModelProbability,
      calibratedProbability: prediction.calibratedProbability,
      marketProbability: prediction.marketProbability,
      diagnosticRawEdge: prediction.diagnosticRawEdge ?? null,
      diagnosticCalibratedEdge: edge,
      diagnosticCalibratedEdgePct: edge * 100,
      matchConfidence,
      matchWarnings,
      calibrationQuality,
      calibrationMappingStatus,
      watchlistTier: tier,
      watchlistDecision: watchlistDecisionForTier(tier, calibrationQuality),
      officialDecision: officialDecisionFor(calibrationQuality, calibrationMappingStatus),
      officialPickEligible: false,
      officialEdgeAllowed: false,
      blockReasons,
      reasons: watchlistReasons(tier, edge),
      risks: uniqueStrings([
        ...(prediction.risks ?? []),
        ...matchWarnings,
        calibrationQuality === "weak" ? "Calibration is weak, so this is not an official pick." : undefined,
        calibrationMappingStatus === "research_only" ? "Calibration mapping is research-only." : undefined,
        "Market diagnostics can change if Polymarket price/cache changes.",
      ]),
      isPaperOnly: true,
    });
  }

  rows.sort((a, b) => b.diagnosticCalibratedEdge - a.diagnosticCalibratedEdge);

  const watchlistSummary: MlbPaperWatchlistDiagnostics = {
    totalCandidatesEvaluated: candidatePredictions.length,
    monitorCount: rows.filter((row) => row.watchlistTier === "monitor").length,
    paperWatchlistCount: rows.filter((row) => row.watchlistTier === "paper_watchlist").length,
    priorityPaperWatchlistCount: rows.filter((row) => row.watchlistTier === "priority_paper_watchlist").length,
    skippedCount,
    officialPicksAllowed: 0,
    warnings: rows.length
      ? warnings
      : [...warnings, "No research-only paper watchlist rows passed calibrated edge and match-confidence requirements."],
  };

  return {
    watchlistRows: rows,
    watchlistSummary,
    warnings: watchlistSummary.warnings,
  };
}