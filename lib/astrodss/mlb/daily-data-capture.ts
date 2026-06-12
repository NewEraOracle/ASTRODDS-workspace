import { appendFile, mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";

import { buildCombinedRiskGate } from "./combined-risk-gate";
import { loadBullpenFeatureStatus, type BullpenFeatureDiagnostics } from "./bullpen-feature-status";
import { loadHistoricalExpansionStatus, type HistoricalExpansionDiagnostics } from "./historical-expansion-status";
import { loadInjuryAvailabilityStatus, type InjuryAvailabilityDiagnostics } from "./injury-availability-status";
import { loadLineupPlayerFeatureStatus, type LineupPlayerFeatureDiagnostics } from "./lineup-player-feature-status";
import { loadModernModelComparisonStatus, type ModernModelComparisonDiagnostics } from "./modern-model-comparison-status";
import { buildMlbPaperWatchlist } from "./paper-watchlist";
import { loadPaperWatchlistClvDiagnostics, type PaperWatchlistClvDiagnostics } from "./paper-watchlist-clv";
import { loadPaperWatchlistLedgerStatus, type PaperWatchlistLedgerStatusResult } from "./paper-watchlist-ledger";
import { loadPaperWatchlistPerformanceAnalysis, type PaperPerformanceAnalysis } from "./paper-performance-analysis";
import { loadPitcherFeatureStatus, type PitcherFeatureDiagnostics } from "./pitcher-feature-status";
import { loadPitcherModelComparisonStatus, type PitcherModelComparisonDiagnostics } from "./pitcher-model-comparison-status";
import { loadPythonMlbEngineStatus, type PythonMlbEngineStatus } from "./python-engine-status";
import { loadPythonMlbPredictions, type PythonMlbPrediction } from "./python-predictions";
import { discoverPolymarketMlbMoneylineMarkets, type PolymarketMlbMoneylineDiscoveryResult } from "../sports-data/polymarket-mlb-markets";
import { buildPolymarketMlbMatchDiagnostics } from "../sports-data/polymarket-mlb-match";
import { scanAstroddsSport } from "../sports-data/scanner";
import { buildUnifiedSignals, serializeUnifiedSignal } from "../signal-engine";
import { loadWeatherBallparkFeatureStatus, type WeatherBallparkFeatureDiagnostics } from "./weather-ballpark-feature-status";
import { type AstroddsGameScan } from "../sports-data/types";

const ASTRODDS_DIR = path.join(/* turbopackIgnore: true */ process.cwd(), ".astrodds");
const DAILY_ROOT = path.join(/* turbopackIgnore: true */ ASTRODDS_DIR, "daily");
const DAILY_OBSERVATIONS_JSONL = path.join(/* turbopackIgnore: true */ ASTRODDS_DIR, "daily-observations.jsonl");
const DAILY_MARKET_PRICE_JSONL = path.join(/* turbopackIgnore: true */ ASTRODDS_DIR, "market-price-snapshots.jsonl");
const DAILY_PREDICTION_JSONL = path.join(/* turbopackIgnore: true */ ASTRODDS_DIR, "prediction-snapshots.jsonl");
const DAILY_RISK_GATE_JSONL = path.join(/* turbopackIgnore: true */ ASTRODDS_DIR, "risk-gate-snapshots.jsonl");
const REQUIRED_CAPTURE_SNAPSHOT_FILES = [
  "unified_snapshot.json",
  "data_quality_snapshot.json",
  "feature_layers_snapshot.json",
  "combined_risk_gate.json",
] as const;
const DEFAULT_CAPTURE_TASK_TIMEOUT_MS = 12000;
const DEFAULT_CAPTURE_SCAN_TIMEOUT_MS = 25000;
const DEFAULT_CAPTURE_POLYMARKET_TIMEOUT_MS = 3500;

type PromiseResult<T> = PromiseSettledResult<T>;
type DailyMlbResearchCaptureStatus = "active" | "partial" | "missing";

export type DailyMlbResearchCaptureDiagnostics = {
  status: DailyMlbResearchCaptureStatus;
  available: boolean;
  latestCaptureDate?: string;
  dailyFolders: number;
  observationRows: number;
  predictionSnapshotRows: number;
  marketPriceSnapshotRows: number;
  riskGateSnapshotRows: number;
  latestWarnings: string[];
  dataLineageStatus: "active" | "missing";
  officialUseBlocked: true;
  researchOnly: true;
  generatedAt: string;
  sourcePath: string;
};

export type DailyMlbResearchCaptureResult = {
  captureId: string;
  date: string;
  status: Exclude<DailyMlbResearchCaptureStatus, "missing">;
  generatedAt: string;
  filesWritten: string[];
  jsonlRowsAppended: number;
  warnings: string[];
  durationMs: number;
  dailyDataCaptureDiagnostics: DailyMlbResearchCaptureDiagnostics;
};

function uniqueStrings(values: Array<string | undefined>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value && value.trim()))));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function safeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0).map((item) => item.trim());
}

function dateFolderName(date = new Date()) {
  return date.toISOString().slice(0, 10);
}

function captureIdFor(date = new Date()) {
  const iso = date.toISOString().replace(/[:.]/g, "-");
  return `mlb-daily-${dateFolderName(date)}-${iso}-${randomUUID().slice(0, 8)}`;
}

async function ensureDailyRoot() {
  await mkdir(DAILY_ROOT, { recursive: true });
}

async function writeJsonSnapshot(filePath: string, payload: unknown, warnings: string[], filesWritten: string[]) {
  try {
    await ensureDailyRoot();
    await mkdir(path.dirname(filePath), { recursive: true });
    await writeFile(filePath, JSON.stringify(payload, null, 2), "utf8");
    filesWritten.push(filePath);
  } catch (error) {
    warnings.push(`Failed to write ${path.basename(filePath)}: ${error instanceof Error ? error.message : "unknown write failure"}.`);
  }
}

async function appendJsonlEntries(filePath: string, entries: unknown[], warnings: string[]) {
  if (!entries.length) return 0;

  try {
    await ensureDailyRoot();
    await mkdir(path.dirname(filePath), { recursive: true });
    const payload = entries.map((entry) => JSON.stringify(entry)).join("\n") + "\n";
    await appendFile(filePath, payload, "utf8");
    return entries.length;
  } catch (error) {
    warnings.push(`Failed to append ${path.basename(filePath)}: ${error instanceof Error ? error.message : "unknown append failure"}.`);
    return 0;
  }
}

async function readJson<T>(filePath: string): Promise<T | undefined> {
  try {
    const raw = await readFile(filePath, "utf8");
    return JSON.parse(raw.replace(/^\uFEFF/, "")) as T;
  } catch {
    return undefined;
  }
}

async function countJsonlRows(filePath: string) {
  try {
    const raw = await readFile(filePath, "utf8");
    return raw
      .replace(/^\uFEFF/, "")
      .split(/\r?\n/)
      .filter((line) => line.trim().length > 0).length;
  } catch {
    return 0;
  }
}

async function listDailyFolders() {
  try {
    const entries = await readdir(DAILY_ROOT, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isDirectory() && /^\d{4}-\d{2}-\d{2}$/.test(entry.name))
      .map((entry) => entry.name)
      .sort((left, right) => right.localeCompare(left));
  } catch {
    return [];
  }
}

function timeoutError(label: string, timeoutMs: number) {
  return new Error(`${label} timed out after ${timeoutMs}ms`);
}

async function settleWithTimeout<T>(label: string, task: Promise<T>, timeoutMs: number): Promise<PromiseResult<T>> {
  let timeoutId: ReturnType<typeof setTimeout> | undefined;

  try {
    const value = await Promise.race([
      task,
      new Promise<T>((_, reject) => {
        timeoutId = setTimeout(() => reject(timeoutError(label, timeoutMs)), timeoutMs);
      }),
    ]);
    return { status: "fulfilled", value };
  } catch (error) {
    return { status: "rejected", reason: error };
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

async function settleTaskWithTimeout<T>(
  label: string,
  taskFactory: (signal: AbortSignal) => Promise<T>,
  timeoutMs: number,
): Promise<PromiseResult<T>> {
  const controller = new AbortController();
  let timeoutId: ReturnType<typeof setTimeout> | undefined;

  try {
    const task = taskFactory(controller.signal);
    const value = await Promise.race([
      task,
      new Promise<T>((_, reject) => {
        timeoutId = setTimeout(() => {
          controller.abort(timeoutError(label, timeoutMs));
          reject(timeoutError(label, timeoutMs));
        }, timeoutMs);
      }),
    ]);
    return { status: "fulfilled", value };
  } catch (error) {
    return { status: "rejected", reason: error };
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
    if (!controller.signal.aborted) controller.abort();
  }
}

async function folderSnapshotStatus(date: string) {
  const folder = path.join(DAILY_ROOT, date);

  try {
    const entries = await readdir(folder, { withFileTypes: true });
    const fileNames = new Set(
      entries
        .filter((entry) => entry.isFile())
        .map((entry) => entry.name),
    );
    const missingRequiredFiles = REQUIRED_CAPTURE_SNAPSHOT_FILES.filter((fileName) => !fileNames.has(fileName));
    return {
      fileNames,
      missingRequiredFiles,
      status: missingRequiredFiles.length === 0 ? "active" : "partial",
    } as const;
  } catch {
    return {
      fileNames: new Set<string>(),
      missingRequiredFiles: [...REQUIRED_CAPTURE_SNAPSHOT_FILES],
      status: "partial",
    } as const;
  }
}

function extractWarnings(snapshot: unknown) {
  if (!isRecord(snapshot)) return [];
  const warnings = [
    ...safeStringArray(snapshot.warnings),
    ...safeStringArray(snapshot.latestWarnings),
  ];
  const summary = isRecord(snapshot.summary) ? safeStringArray(snapshot.summary.warnings) : [];
  const diagnostics = isRecord(snapshot.diagnostics) ? safeStringArray(snapshot.diagnostics.warnings) : [];
  const combinedRisk = isRecord(snapshot.combinedRiskGateDiagnostics) ? safeStringArray(snapshot.combinedRiskGateDiagnostics.warnings) : [];
  return uniqueStrings([...warnings, ...summary, ...diagnostics, ...combinedRisk]).slice(0, 12);
}

async function latestWarningsForDate(date: string) {
  const folder = path.join(DAILY_ROOT, date);
  const candidates = [
    path.join(folder, "data_quality_snapshot.json"),
    path.join(folder, "unified_snapshot.json"),
    path.join(folder, "combined_risk_gate.json"),
    path.join(folder, "paper_performance_snapshot.json"),
  ];

  for (const candidate of candidates) {
    const parsed = await readJson<unknown>(candidate);
    const warnings = extractWarnings(parsed);
    if (warnings.length) return warnings;
  }

  return [];
}

function baseSnapshot(captureId: string, date: string, generatedAt: string) {
  return { captureId, date, generatedAt };
}

function observationRowsForGames(captureId: string, date: string, generatedAt: string, games: AstroddsGameScan[]) {
  return games.map((game) => ({
    ...baseSnapshot(captureId, date, generatedAt),
    kind: "today_game",
    gameId: game.id,
    sport: game.sport,
    game: game.game,
    homeTeam: game.homeTeam,
    awayTeam: game.awayTeam,
    liveStatus: game.liveStatus,
    dataStatus: game.dataStatus,
    marketCount: game.markets.length,
    modelLeanSide: game.modelPick?.modelLeanSide,
    modelLeanTeam: game.modelPick?.modelLeanTeam,
    modelConfidence: game.modelPick?.modelConfidence,
    modelScore: game.modelPick?.modelScore,
    dataQuality: game.modelPick?.dataQuality,
    unmatchedReason: game.unmatchedReason,
    missingDataWarnings: game.modelPick?.missingDataWarnings ?? [],
  }));
}

function predictionRowsForJsonl(captureId: string, date: string, generatedAt: string, predictions: PythonMlbPrediction[]) {
  return predictions.map((prediction, index) => ({
    ...baseSnapshot(captureId, date, generatedAt),
    kind: "prediction",
    predictionId: prediction.gameId ?? `prediction-${index + 1}`,
    gameId: prediction.gameId,
    homeTeam: prediction.homeTeam,
    awayTeam: prediction.awayTeam,
    marketType: prediction.marketType,
    rawModelProbability: prediction.rawModelProbability,
    calibratedProbability: prediction.calibratedProbability,
    marketProbability: prediction.marketProbability,
    rawEdge: prediction.rawEdge,
    calibratedEdge: prediction.calibratedEdge,
    confidence: prediction.confidence,
    dataQuality: prediction.dataQuality,
    calibrationQuality: prediction.calibrationQuality,
    calibrationMappingStatus: prediction.calibrationMappingStatus,
    lineupStatus: prediction.lineupStatus,
    lineupImpactScore: prediction.lineupImpactScore,
    pitcherStatus: prediction.pitcherStatus,
    bullpenStatus: prediction.bullpenStatus,
    weatherImpact: prediction.weatherImpact,
    officialDecision: prediction.officialDecision,
    officialPickEligible: prediction.officialPickEligible,
    officialEdgeAllowed: prediction.officialEdgeAllowed,
    officialEdgeBlockReasons: prediction.officialEdgeBlockReasons ?? [],
    reasons: prediction.reasons ?? [],
    risks: prediction.risks ?? [],
    modelVersion: prediction.modelVersion,
    modelType: prediction.modelType,
    warnings: prediction.calibrationWarnings ?? [],
  }));
}

function marketRowsForJsonl(captureId: string, date: string, generatedAt: string, markets: PolymarketMlbMoneylineDiscoveryResult["markets"], sourceDiagnostics: PolymarketMlbMoneylineDiscoveryResult["sourceDiagnostics"]) {
  const sourceMode = markets.length ? "market_prices_connected" : "not_connected";
  const sourceUrl = sourceDiagnostics.find((item) => Boolean(item.sanitizedUrl))?.sanitizedUrl;
  return markets.map((market) => ({
    ...baseSnapshot(captureId, date, generatedAt),
    kind: "market_price",
    marketId: market.marketId,
    conditionId: market.conditionId,
    question: market.question,
    title: market.title,
    slug: market.slug,
    category: market.category,
    detectedTeams: market.detectedTeams,
    detectedHomeTeam: market.detectedHomeTeam,
    detectedAwayTeam: market.detectedAwayTeam,
    marketProbability: market.marketProbability,
    liquidity: market.liquidity,
    volume: market.volume,
    active: market.active,
    closed: market.closed,
    endDate: market.endDate,
    gameDate: market.gameDate,
    sourceMode,
    sourceUrl: market.sourceUrl ?? sourceUrl,
    warnings: market.warnings,
  }));
}

function riskGateRowsForJsonl(captureId: string, date: string, generatedAt: string, rows: ReturnType<typeof buildCombinedRiskGate>["rows"]) {
  return rows.map((row) => ({
    ...baseSnapshot(captureId, date, generatedAt),
    kind: "risk_gate",
    rowId: row.rowId,
    gameId: row.gameId,
    homeTeam: row.homeTeam,
    awayTeam: row.awayTeam,
    marketType: row.marketType,
    selectedSide: row.selectedSide,
    researchSide: row.researchSide,
    rawModelProbability: row.rawModelProbability,
    calibratedProbability: row.calibratedProbability,
    marketProbability: row.marketProbability,
    diagnosticCalibratedEdge: row.diagnosticCalibratedEdge,
    diagnosticCalibratedEdgePct: row.diagnosticCalibratedEdgePct,
    matchConfidence: row.matchConfidence,
    riskScore: row.riskScore,
    riskLevel: row.riskLevel,
    decision: row.decision,
    blockReasons: row.blockReasons,
    downgradeReasons: row.downgradeReasons,
    positiveReasons: row.positiveReasons,
    dataQuality: row.dataQuality,
  }));
}

function marketPriceDiagnosticsFor(result: PolymarketMlbMoneylineDiscoveryResult) {
  return {
    status: result.status,
    marketPricesConnected: result.marketPricesConnected,
    moneylineMarketsFound: result.markets.length,
    cacheUsed: result.cacheUsed,
    cacheStatus: result.cacheStatus,
    cacheAgeSeconds: result.cacheAgeSeconds,
    cacheGeneratedAt: result.cacheGeneratedAt,
    supportedMarkets: result.supportedMarkets,
    disabledMarkets: result.disabledMarkets,
    futureMarkets: result.futureMarkets,
    sourceDiagnostics: result.sourceDiagnostics,
    warnings: result.warnings,
    generatedAt: result.generatedAt,
  };
}

function safeDiagnostics<T>(result: PromiseResult<T>, fallback: T) {
  return result.status === "fulfilled" ? result.value : fallback;
}

export async function loadDailyMlbResearchCaptureStatus(): Promise<DailyMlbResearchCaptureDiagnostics> {
  const generatedAt = new Date().toISOString();
  const folders = await listDailyFolders();
  const latestDate = folders[0];
  const [observationRows, predictionSnapshotRows, marketPriceSnapshotRows, riskGateSnapshotRows] = await Promise.all([
    countJsonlRows(DAILY_OBSERVATIONS_JSONL),
    countJsonlRows(DAILY_PREDICTION_JSONL),
    countJsonlRows(DAILY_MARKET_PRICE_JSONL),
    countJsonlRows(DAILY_RISK_GATE_JSONL),
  ]);
  if (!latestDate) {
    return {
      status: "missing",
      available: false,
      latestCaptureDate: latestDate,
      dailyFolders: folders.length,
      observationRows,
      predictionSnapshotRows,
      marketPriceSnapshotRows,
      riskGateSnapshotRows,
      latestWarnings: ["No daily capture snapshots have been recorded yet."],
      dataLineageStatus: "missing",
      officialUseBlocked: true,
      researchOnly: true,
      generatedAt,
      sourcePath: DAILY_ROOT,
    };
  }

  const snapshotStatus = await folderSnapshotStatus(latestDate);
  const warnings = uniqueStrings([
    ...(await latestWarningsForDate(latestDate)),
    snapshotStatus.missingRequiredFiles.length
      ? `Required daily capture snapshots missing: ${snapshotStatus.missingRequiredFiles.join(", ")}`
      : undefined,
  ]);

  return {
    status: snapshotStatus.status,
    available: true,
    latestCaptureDate: latestDate,
    dailyFolders: folders.length,
    observationRows,
    predictionSnapshotRows,
    marketPriceSnapshotRows,
    riskGateSnapshotRows,
    latestWarnings: warnings,
    dataLineageStatus: snapshotStatus.status === "active" ? "active" : "missing",
    officialUseBlocked: true,
    researchOnly: true,
    generatedAt,
    sourcePath: DAILY_ROOT,
  };
}

export async function captureDailyMlbResearchSnapshot(): Promise<DailyMlbResearchCaptureResult> {
  const startedAt = Date.now();
  const now = new Date();
  const date = dateFolderName(now);
  const generatedAt = now.toISOString();
  const captureId = captureIdFor(now);
  const captureDir = path.join(DAILY_ROOT, date);
  const filesWritten: string[] = [];
  const warnings: string[] = [];

  await mkdir(captureDir, { recursive: true });
  await ensureDailyRoot();
  const dailyFolders = (await listDailyFolders()).length;

  const [
    scanResult,
    pythonPredictionsResult,
    pythonEngineStatusResult,
    marketDiscoveryResult,
    pitcherFeatureResult,
    bullpenFeatureResult,
    weatherBallparkResult,
    lineupPlayerResult,
    injuryAvailabilityResult,
    historicalExpansionResult,
    pitcherModelComparisonResult,
    modernModelComparisonResult,
    paperWatchlistLedgerResult,
    paperClvResult,
    paperPerformanceResult,
  ] = await Promise.all([
    settleTaskWithTimeout("ASTRODDS MLB scan", (signal) => scanAstroddsSport("MLB", signal), DEFAULT_CAPTURE_SCAN_TIMEOUT_MS),
    settleWithTimeout("Python MLB predictions", loadPythonMlbPredictions(), DEFAULT_CAPTURE_TASK_TIMEOUT_MS),
    settleWithTimeout("Python MLB engine status", loadPythonMlbEngineStatus(), DEFAULT_CAPTURE_TASK_TIMEOUT_MS),
    settleTaskWithTimeout(
      "Polymarket MLB market discovery",
      (signal) => discoverPolymarketMlbMoneylineMarkets({ timeoutMs: DEFAULT_CAPTURE_POLYMARKET_TIMEOUT_MS, signal }),
      DEFAULT_CAPTURE_TASK_TIMEOUT_MS,
    ),
    settleWithTimeout("Pitcher feature diagnostics", loadPitcherFeatureStatus(), DEFAULT_CAPTURE_TASK_TIMEOUT_MS),
    settleWithTimeout("Bullpen feature diagnostics", loadBullpenFeatureStatus(), DEFAULT_CAPTURE_TASK_TIMEOUT_MS),
    settleWithTimeout("Weather / ballpark diagnostics", loadWeatherBallparkFeatureStatus(), DEFAULT_CAPTURE_TASK_TIMEOUT_MS),
    settleWithTimeout("Lineup / player diagnostics", loadLineupPlayerFeatureStatus(), DEFAULT_CAPTURE_TASK_TIMEOUT_MS),
    settleWithTimeout("Injury / availability diagnostics", loadInjuryAvailabilityStatus(), DEFAULT_CAPTURE_TASK_TIMEOUT_MS),
    settleWithTimeout("Historical expansion diagnostics", loadHistoricalExpansionStatus(), DEFAULT_CAPTURE_TASK_TIMEOUT_MS),
    settleWithTimeout("Pitcher model comparison", loadPitcherModelComparisonStatus(), DEFAULT_CAPTURE_TASK_TIMEOUT_MS),
    settleWithTimeout("Modern model comparison", loadModernModelComparisonStatus(), DEFAULT_CAPTURE_TASK_TIMEOUT_MS),
    settleWithTimeout("Paper watchlist ledger status", loadPaperWatchlistLedgerStatus(), DEFAULT_CAPTURE_TASK_TIMEOUT_MS),
    settleWithTimeout("Paper watchlist CLV diagnostics", loadPaperWatchlistClvDiagnostics(), DEFAULT_CAPTURE_TASK_TIMEOUT_MS),
    settleWithTimeout("Paper performance diagnostics", loadPaperWatchlistPerformanceAnalysis(), DEFAULT_CAPTURE_TASK_TIMEOUT_MS),
  ]);

  const taskFailures: Array<[string, PromiseResult<unknown>]> = [
    ["ASTRODDS MLB scan", scanResult],
    ["Python MLB predictions", pythonPredictionsResult],
    ["Python MLB engine status", pythonEngineStatusResult],
    ["Polymarket MLB market discovery", marketDiscoveryResult],
    ["Pitcher feature diagnostics", pitcherFeatureResult],
    ["Bullpen feature diagnostics", bullpenFeatureResult],
    ["Weather / ballpark diagnostics", weatherBallparkResult],
    ["Lineup / player diagnostics", lineupPlayerResult],
    ["Injury / availability diagnostics", injuryAvailabilityResult],
    ["Historical expansion diagnostics", historicalExpansionResult],
    ["Pitcher model comparison", pitcherModelComparisonResult],
    ["Modern model comparison", modernModelComparisonResult],
    ["Paper watchlist ledger status", paperWatchlistLedgerResult],
    ["Paper watchlist CLV diagnostics", paperClvResult],
    ["Paper performance diagnostics", paperPerformanceResult],
  ];

  for (const [label, result] of taskFailures) {
    if (result.status === "rejected") {
      warnings.push(`${label} unavailable: ${result.reason instanceof Error ? result.reason.message : "unknown failure"}.`);
    }
  }

  const scan = scanResult.status === "fulfilled" ? scanResult.value : undefined;
  const pythonPredictions = safeDiagnostics(pythonPredictionsResult, { available: false, sourcePath: "", predictions: [], warnings: ["Python predictions unavailable."] });
  const pythonStatus = safeDiagnostics(pythonEngineStatusResult, {
    engineAvailable: false,
    modelAvailable: false,
    modelVersion: "unknown",
    modelType: "unknown",
    calibrationQuality: "missing",
    supportedMarkets: ["moneyline"],
    disabledMarkets: ["runline"],
    officialPickEligible: false,
    officialPickBlockReasons: ["Python model status unavailable."],
    warnings: ["Python model status unavailable."],
    sourcePath: "",
  } satisfies PythonMlbEngineStatus);
  const polymarketMarkets = safeDiagnostics(marketDiscoveryResult, {
    status: "FAILED",
    marketPricesConnected: false,
    supportedMarkets: ["moneyline"],
    disabledMarkets: ["runline"],
    futureMarkets: ["total_runs"],
    markets: [],
    sourceDiagnostics: [],
    warnings: ["Polymarket market data unavailable or timed out."],
    generatedAt,
    cacheUsed: false,
    cacheStatus: "missing",
  } satisfies PolymarketMlbMoneylineDiscoveryResult);
  const pitcherDiagnostics = safeDiagnostics(pitcherFeatureResult, {
    status: "missing",
    available: false,
    totalGamesRead: 0,
    completedGamesUsed: 0,
    gamesWithPitcherData: 0,
    gamesWithFullPitcherData: 0,
    gamesWithPartialPitcherData: 0,
    gamesMissingPitcherData: 0,
    dataQualitySummary: { high: 0, medium: 0, low: 0, missing: 0 },
    warnings: ["Pitcher feature diagnostics unavailable."],
    sourcePath: "",
  } satisfies PitcherFeatureDiagnostics);
  const bullpenDiagnostics = safeDiagnostics(bullpenFeatureResult, {
    status: "missing",
    available: false,
    totalGamesRead: 0,
    completedGamesUsed: 0,
    gamesWithBullpenData: 0,
    gamesMissingBullpenData: 0,
    gamesApproximatedBullpenData: 0,
    approximationMethod: "unavailable",
    approximationUsed: false,
    dataQuality: "missing",
    dataQualitySummary: { high: 0, medium: 0, low: 0, missing: 0 },
    warnings: ["Bullpen feature diagnostics unavailable."],
    sourcePath: "",
  } satisfies BullpenFeatureDiagnostics);
  const weatherDiagnostics = safeDiagnostics(weatherBallparkResult, {
    status: "missing",
    available: false,
    gamesWithVenueData: 0,
    gamesWithWeatherData: 0,
    gamesMissingWeatherData: 0,
    gamesWithBallparkFactorData: 0,
    dataQuality: "missing",
    warnings: ["Weather / ballpark diagnostics unavailable."],
    sourcePath: "",
  } satisfies WeatherBallparkFeatureDiagnostics);
  const lineupDiagnostics = safeDiagnostics(lineupPlayerResult, {
    status: "missing",
    available: false,
    gamesWithConfirmedLineupData: 0,
    gamesWithProjectedOrProxyLineupData: 0,
    gamesMissingLineupData: 0,
    dataQuality: "missing",
    proxyUsed: false,
    warnings: ["Lineup / player diagnostics unavailable."],
    sourcePath: "",
  } satisfies LineupPlayerFeatureDiagnostics);
  const injuryDiagnostics = safeDiagnostics(injuryAvailabilityResult, {
    status: "missing",
    available: false,
    gamesWithInjuryData: 0,
    gamesMissingInjuryData: 0,
    injurySource: "unavailable",
    dataQuality: "missing",
    warnings: ["Injury / availability diagnostics unavailable."],
    sourcePath: "",
  } satisfies InjuryAvailabilityDiagnostics);
  const historicalDiagnostics = safeDiagnostics(historicalExpansionResult, {
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
    warnings: ["Historical expansion diagnostics unavailable."],
    sourcePath: "",
  } satisfies HistoricalExpansionDiagnostics);
  const pitcherModelComparisonDiagnostics = safeDiagnostics(pitcherModelComparisonResult, {
    status: "missing",
    recommendation: "needs_more_data",
    baselineModelVersion: "unknown",
    baselineModelType: "unknown",
    pitcherModelVersion: "unknown",
    pitcherModelType: "unknown",
    reasons: [],
    warnings: ["Pitcher model comparison diagnostics unavailable."],
    sourcePath: "",
  } satisfies PitcherModelComparisonDiagnostics);
  const modernModelComparisonDiagnostics = safeDiagnostics(modernModelComparisonResult, {
    status: "missing",
    recommendation: "needs_more_data",
    baselineModelVersion: "unknown",
    baselineModelType: "unknown",
    modernModelVersion: "unknown",
    modernModelType: "unknown",
    activeModelChanged: false,
    reasons: [],
    warnings: ["Modern model comparison diagnostics unavailable."],
    sourcePath: "",
  } satisfies ModernModelComparisonDiagnostics);
  const paperWatchlistLedgerStatus = safeDiagnostics(paperWatchlistLedgerResult, {
    ledgerAvailable: false,
    totalRows: 0,
    openRows: 0,
    settledRows: 0,
    wins: 0,
    losses: 0,
    pushes: 0,
    unknown: 0,
    paperPnLUnits: null,
    recentRows: [],
    warnings: ["Paper watchlist ledger diagnostics unavailable."],
    generatedAt,
    ledgerPath: ".astrodds/paper-watchlist-ledger.json",
  } satisfies PaperWatchlistLedgerStatusResult);
  const paperClvDiagnostics = safeDiagnostics(paperClvResult, {
    status: "missing",
    summary: {
      totalRows: 0,
      openRows: 0,
      settledRows: 0,
      rowsWithEntryPrice: 0,
      rowsWithLatestPrice: 0,
      rowsWithClosingPrice: 0,
      positiveClvRows: 0,
      negativeClvRows: 0,
      neutralClvRows: 0,
      missingClvRows: 0,
      averageClv: null,
      averageClvPct: null,
      warnings: ["Paper watchlist CLV diagnostics unavailable."],
    },
    recentRows: [],
    warnings: ["Paper watchlist CLV diagnostics unavailable."],
    generatedAt,
    ledgerPath: ".astrodds/paper-watchlist-ledger.json",
  } satisfies PaperWatchlistClvDiagnostics);
  const paperPerformanceDiagnostics = safeDiagnostics(paperPerformanceResult, {
    status: "missing",
    summary: {
      totalRows: 0,
      openRows: 0,
      settledRows: 0,
      wins: 0,
      losses: 0,
      pushes: 0,
      unknown: 0,
      winRate: null,
      paperPnLUnits: null,
      averagePaperPnLUnits: null,
      averageMarketProbability: null,
      averageRawModelProbability: null,
      averageCalibratedProbability: null,
      averageDiagnosticCalibratedEdge: null,
      averageClv: null,
      averageClvPct: null,
      positiveClvRate: null,
      bestEdgeBucket: "No settled rows yet",
      bestWatchlistTier: "No settled rows yet",
      warnings: ["Paper performance diagnostics unavailable."],
      generatedAt,
      ledgerPath: ".astrodds/paper-watchlist-ledger.json",
    },
    byWatchlistTier: [],
    byEdgeBucket: [],
    byMatchConfidence: [],
    byCalibrationMappingStatus: [],
    recentSettledRows: [],
    warnings: ["Paper performance diagnostics unavailable."],
    generatedAt,
    ledgerPath: ".astrodds/paper-watchlist-ledger.json",
  } satisfies PaperPerformanceAnalysis);

  const modelProbabilitiesByGameId = Object.fromEntries(
    (pythonPredictions.predictions ?? [])
      .map((prediction, index) => [prediction.gameId ?? `python-mlb-prediction-${index}`, prediction.rawModelProbability] as const)
      .filter((entry): entry is [string, number] => typeof entry[1] === "number"),
  );
  const marketMatchDiagnostics = scan
    ? buildPolymarketMlbMatchDiagnostics(scan.games, polymarketMarkets.markets, {
        calibrationQuality: pythonStatus.calibrationQuality,
        modelProbabilitiesByGameId,
      })
    : {
        gamesEvaluated: 0,
        marketsEvaluated: polymarketMarkets.markets.length,
        highConfidenceMatches: 0,
        mediumConfidenceMatches: 0,
        lowConfidenceMatches: 0,
        unmatchedGames: 0,
        diagnosticEdgesCalculated: 0,
        warnings: ["No MLB scan rows were available for Polymarket market matching."],
        matches: [],
      };
  const signals = scan ? buildUnifiedSignals(scan.games).map(serializeUnifiedSignal) : [];
  const paperWatchlist = buildMlbPaperWatchlist(pythonPredictions.predictions, {
    calibrationQuality: pythonStatus.calibrationQuality,
  });
  const combinedRiskGate = buildCombinedRiskGate({
    predictions: pythonPredictions.predictions,
    watchlistRows: paperWatchlist.watchlistRows,
    pythonMlbEngineStatus: pythonStatus,
    marketPriceDiagnostics: marketPriceDiagnosticsFor(polymarketMarkets),
    marketMatchDiagnostics,
    lineupPlayerFeatureDiagnostics: lineupDiagnostics,
    injuryAvailabilityDiagnostics: injuryDiagnostics,
    weatherBallparkFeatureDiagnostics: weatherDiagnostics,
    pitcherFeatureDiagnostics: pitcherDiagnostics,
    bullpenFeatureDiagnostics: bullpenDiagnostics,
    paperPerformanceDiagnostics,
  });

  const filesToWrite = [
    {
      name: "today_games.json",
      payload: {
        ...baseSnapshot(captureId, date, generatedAt),
        captureId,
        date,
        status: scan?.diagnostics,
        sourceStatus: scan?.sourceStatus,
        games: scan?.games ?? [],
        warnings: scan?.warnings ?? ["MLB scan unavailable."],
      },
    },
    {
      name: "today_predictions.json",
      payload: {
        ...baseSnapshot(captureId, date, generatedAt),
        captureId,
        date,
        predictions: pythonPredictions.predictions ?? [],
        modelVersion: pythonStatus.modelVersion,
        modelType: pythonStatus.modelType,
        calibrationQuality: pythonStatus.calibrationQuality,
        calibrationMappingStatus: uniqueStrings((pythonPredictions.predictions ?? []).map((prediction) => prediction.calibrationMappingStatus)).join(", ") || "missing",
        warnings: uniqueStrings([...(pythonPredictions.warnings ?? []), ...(pythonStatus.warnings ?? [])]),
      },
    },
    {
      name: "polymarket_markets.json",
      payload: {
        ...baseSnapshot(captureId, date, generatedAt),
        captureId,
        date,
        ...marketPriceDiagnosticsFor(polymarketMarkets),
        markets: polymarketMarkets.markets,
      },
    },
    {
      name: "market_matches.json",
      payload: {
        ...baseSnapshot(captureId, date, generatedAt),
        captureId,
        date,
        marketMatchDiagnostics,
        matches: marketMatchDiagnostics.matches ?? [],
        warnings: marketMatchDiagnostics.warnings ?? [],
      },
    },
    {
      name: "paper_watchlist.json",
      payload: {
        ...baseSnapshot(captureId, date, generatedAt),
        captureId,
        date,
        watchlistSummary: paperWatchlist.watchlistSummary,
        watchlistRows: paperWatchlist.watchlistRows,
        warnings: paperWatchlist.warnings,
      },
    },
    {
      name: "combined_risk_gate.json",
      payload: {
        ...baseSnapshot(captureId, date, generatedAt),
        captureId,
        date,
        diagnostics: combinedRiskGate.diagnostics,
        rows: combinedRiskGate.rows,
        warnings: combinedRiskGate.warnings,
      },
    },
    {
      name: "taken_bets.json",
      payload: {
        ...baseSnapshot(captureId, date, generatedAt),
        captureId,
        date,
        rows: paperWatchlistLedgerStatus.totalRows ? paperWatchlistLedgerStatus.recentRows.filter((row) => row.status === "open") : [],
        summary: paperWatchlistLedgerStatus,
        researchOnly: true,
        officialUseBlocked: true,
        warnings: uniqueStrings([...paperWatchlistLedgerStatus.warnings]),
      },
    },
    {
      name: "settlement_snapshot.json",
      payload: {
        ...baseSnapshot(captureId, date, generatedAt),
        captureId,
        date,
        ledgerDiagnostics: paperWatchlistLedgerStatus,
        clvDiagnostics: paperClvDiagnostics,
        warnings: uniqueStrings([
          ...(paperWatchlistLedgerStatus.warnings ?? []),
          ...(paperClvDiagnostics.warnings ?? []),
        ]),
      },
    },
    {
      name: "clv_snapshot.json",
      payload: {
        ...baseSnapshot(captureId, date, generatedAt),
        captureId,
        date,
        clvDiagnostics: paperClvDiagnostics,
        warnings: paperClvDiagnostics.warnings,
      },
    },
    {
      name: "paper_performance_snapshot.json",
      payload: {
        ...baseSnapshot(captureId, date, generatedAt),
        captureId,
        date,
        paperPerformanceDiagnostics,
        warnings: paperPerformanceDiagnostics.warnings,
      },
    },
    {
      name: "feature_layers_snapshot.json",
      payload: {
        ...baseSnapshot(captureId, date, generatedAt),
        captureId,
        date,
        pitcher: pitcherDiagnostics,
        bullpen: bullpenDiagnostics,
        weather: weatherDiagnostics,
        lineup: lineupDiagnostics,
        injury: injuryDiagnostics,
        historicalExpansion: historicalDiagnostics,
        pitcherModelComparison: pitcherModelComparisonDiagnostics,
        modernModelComparison: modernModelComparisonDiagnostics,
        modelVersion: pythonStatus.modelVersion,
        modelType: pythonStatus.modelType,
        activeModel: pythonStatus.modelAvailable ? pythonStatus.modelVersion : "unknown",
        calibrationQuality: pythonStatus.calibrationQuality,
        calibrationMappingStatus: uniqueStrings((pythonPredictions.predictions ?? []).map((prediction) => prediction.calibrationMappingStatus)).join(", ") || "missing",
        paperOnly: true,
        realMoneyTrading: "OFF",
        runlineDisabled: true,
        warnings: uniqueStrings([
          ...(pitcherDiagnostics.warnings ?? []),
          ...(bullpenDiagnostics.warnings ?? []),
          ...(weatherDiagnostics.warnings ?? []),
          ...(lineupDiagnostics.warnings ?? []),
          ...(injuryDiagnostics.warnings ?? []),
          ...(historicalDiagnostics.warnings ?? []),
          ...(pitcherModelComparisonDiagnostics.warnings ?? []),
          ...(modernModelComparisonDiagnostics.warnings ?? []),
        ]),
      },
    },
    {
      name: "unified_snapshot.json",
      payload: {
        ...baseSnapshot(captureId, date, generatedAt),
        captureId,
        date,
        modelVersion: pythonStatus.modelVersion,
        modelType: pythonStatus.modelType,
        activeModel: pythonStatus.modelAvailable ? pythonStatus.modelVersion : "unknown",
        calibrationQuality: pythonStatus.calibrationQuality,
        calibrationMappingStatus: uniqueStrings((pythonPredictions.predictions ?? []).map((prediction) => prediction.calibrationMappingStatus)).join(", ") || "missing",
        paperOnly: true,
        realMoneyTrading: "OFF",
        runlineDisabled: true,
        sourceStatus: scan?.sourceStatus,
        scanDiagnostics: scan?.diagnostics,
        todayGames: scan?.games ?? [],
        todayPredictions: pythonPredictions.predictions ?? [],
        marketPriceDiagnostics: marketPriceDiagnosticsFor(polymarketMarkets),
        marketMatchDiagnostics,
        paperWatchlistDiagnostics: paperWatchlist.watchlistSummary,
        paperWatchlistRows: paperWatchlist.watchlistRows,
        paperWatchlistLedgerDiagnostics: paperWatchlistLedgerStatus,
        paperClvDiagnostics,
        paperPerformanceDiagnostics,
        combinedRiskGateDiagnostics: combinedRiskGate.diagnostics,
        combinedRiskRows: combinedRiskGate.rows.slice(0, 20),
        featureLayerDiagnostics: {
          pitcher: pitcherDiagnostics,
          bullpen: bullpenDiagnostics,
          weather: weatherDiagnostics,
          lineup: lineupDiagnostics,
          injury: injuryDiagnostics,
        },
        modelComparisonDiagnostics: pitcherModelComparisonDiagnostics,
        modernModelComparisonDiagnostics,
        historicalExpansionDiagnostics: historicalDiagnostics,
        signals: signals.slice(0, 20),
        warnings: uniqueStrings([
          ...(scan?.warnings ?? []),
          ...(pythonPredictions.warnings ?? []),
          ...(pythonStatus.warnings ?? []),
          ...(polymarketMarkets.warnings ?? []),
          ...(marketMatchDiagnostics.warnings ?? []),
          ...(paperWatchlist.warnings ?? []),
          ...(combinedRiskGate.warnings ?? []),
        ]),
      },
    },
    {
      name: "data_quality_snapshot.json",
      payload: {
        ...baseSnapshot(captureId, date, generatedAt),
        captureId,
        date,
        available: Boolean(scan),
        dataLineageStatus: "active",
        officialUseBlocked: true,
        researchOnly: true,
        paperOnly: true,
        realMoneyTrading: "OFF",
        runlineDisabled: true,
        summary: {
          modelAvailable: pythonStatus.modelAvailable,
          calibrationQuality: pythonStatus.calibrationQuality,
          marketPricesConnected: polymarketMarkets.marketPricesConnected,
          marketCacheStatus: polymarketMarkets.cacheStatus,
          matchedGames: marketMatchDiagnostics.matches.length,
          dailyFolders,
          observationRows: scan?.games.length ?? 0,
          predictionRows: pythonPredictions.predictions.length,
          marketRows: polymarketMarkets.markets.length,
          riskGateRows: combinedRiskGate.rows.length,
        },
        sourceDiagnostics: {
          scan: scan?.diagnostics,
          marketPrices: marketPriceDiagnosticsFor(polymarketMarkets),
          marketMatches: marketMatchDiagnostics,
          paperPerformance: paperPerformanceDiagnostics.summary,
          combinedRiskGate: combinedRiskGate.diagnostics,
        },
        warnings: uniqueStrings([
          ...(scan?.warnings ?? []),
          ...(pythonPredictions.warnings ?? []),
          ...(pythonStatus.warnings ?? []),
          ...(polymarketMarkets.warnings ?? []),
          ...(paperWatchlist.warnings ?? []),
          ...(combinedRiskGate.warnings ?? []),
          "Daily capture is research-only and does not create official picks, Strong Buys, Telegram alerts, or real-money behavior.",
        ]),
      },
    },
  ] as const;

  let jsonlRowsAppended = 0;

  await Promise.all(
    filesToWrite.map(async ({ name, payload }) => {
      const filePath = path.join(captureDir, name);
      await writeJsonSnapshot(filePath, payload, warnings, filesWritten);
    }),
  );

  jsonlRowsAppended += await appendJsonlEntries(DAILY_OBSERVATIONS_JSONL, observationRowsForGames(captureId, date, generatedAt, scan?.games ?? []), warnings);
  jsonlRowsAppended += await appendJsonlEntries(DAILY_PREDICTION_JSONL, predictionRowsForJsonl(captureId, date, generatedAt, pythonPredictions.predictions ?? []), warnings);
  jsonlRowsAppended += await appendJsonlEntries(DAILY_MARKET_PRICE_JSONL, marketRowsForJsonl(captureId, date, generatedAt, polymarketMarkets.markets, polymarketMarkets.sourceDiagnostics), warnings);
  jsonlRowsAppended += await appendJsonlEntries(DAILY_RISK_GATE_JSONL, riskGateRowsForJsonl(captureId, date, generatedAt, combinedRiskGate.rows), warnings);

  const diagnostics = await loadDailyMlbResearchCaptureStatus();
  const durationMs = Date.now() - startedAt;
  const status = diagnostics.status === "active" ? "active" : "partial";

  if (!polymarketMarkets.marketPricesConnected) {
    warnings.push("Polymarket market data unavailable or timed out.");
  }
  if (!filesWritten.length) {
    warnings.push("No daily snapshot files were written.");
  }

  return {
    captureId,
    date,
    status,
    generatedAt,
    filesWritten,
    jsonlRowsAppended,
    warnings: uniqueStrings([
      ...warnings,
      ...(scan?.warnings ?? []),
      ...(pythonPredictions.warnings ?? []),
      ...(pythonStatus.warnings ?? []),
      ...(polymarketMarkets.warnings ?? []),
      ...(paperWatchlist.warnings ?? []),
      ...(combinedRiskGate.warnings ?? []),
      ...(paperPerformanceDiagnostics.warnings ?? []),
      diagnostics.status === "partial" ? "Daily capture completed partially; one or more required snapshot files are missing." : undefined,
    ]),
    durationMs,
    dailyDataCaptureDiagnostics: diagnostics,
  };
}
