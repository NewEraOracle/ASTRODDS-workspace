import { readFile } from "node:fs/promises";
import path from "node:path";

export const PYTHON_MLB_PREDICTIONS_PATH = path.join(process.cwd(), "mlb-engine", "outputs", "today_predictions.json");

export type PythonMlbMarketType = "moneyline" | "total_runs";
export type PythonMlbCalibrationQuality = "strong" | "medium" | "weak" | "not_enough_history" | "missing";

export type PythonMlbPrediction = {
  gameId?: string;
  date?: string;
  sport?: string;
  league?: string;
  homeTeam?: string;
  awayTeam?: string;
  market?: string;
  pick?: string;
  marketType: PythonMlbMarketType;
  marketAvailability?: string;
  rawModelProbability?: number;
  calibratedProbability?: number;
  marketProbability?: number;
  rawEdge?: number;
  calibratedEdge?: number;
  confidence?: number;
  dataQuality?: string;
  calibrationQuality?: PythonMlbCalibrationQuality;
  calibrationMethod?: string;
  calibrationSampleSize?: number;
  calibrationWarnings?: string[];
  lineupStatus?: string;
  lineupImpactScore?: number;
  pitcherStatus?: string;
  bullpenStatus?: string;
  weatherImpact?: string;
  officialDecision?: string;
  reasons?: string[];
  risks?: string[];
  isPaperOnly: boolean;
};

export type PythonMlbPredictionLoadResult = {
  available: boolean;
  sourcePath: string;
  predictions: PythonMlbPrediction[];
  warnings: string[];
};

const allowedMarketTypes = new Set<PythonMlbMarketType>(["moneyline", "total_runs"]);
const allowedCalibrationQuality = new Set<PythonMlbCalibrationQuality>(["strong", "medium", "weak", "not_enough_history", "missing"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function optionalNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function optionalStringArray(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const strings = value.filter((item): item is string => typeof item === "string" && item.trim().length > 0).map((item) => item.trim());
  return strings.length ? strings : undefined;
}

function normalizeMarketType(value: unknown): PythonMlbMarketType | undefined {
  const marketType = optionalString(value)?.toLowerCase();
  if (!marketType) return undefined;
  if (allowedMarketTypes.has(marketType as PythonMlbMarketType)) return marketType as PythonMlbMarketType;
  return undefined;
}

function normalizeCalibrationQuality(value: unknown): PythonMlbCalibrationQuality | undefined {
  const quality = optionalString(value)?.toLowerCase();
  if (!quality) return undefined;
  if (allowedCalibrationQuality.has(quality as PythonMlbCalibrationQuality)) return quality as PythonMlbCalibrationQuality;
  return undefined;
}

function normalizePrediction(raw: unknown, index: number, warnings: string[]): PythonMlbPrediction | undefined {
  if (!isRecord(raw)) {
    warnings.push(`Prediction ${index + 1} skipped: expected an object.`);
    return undefined;
  }

  const rawMarketType = optionalString(raw.marketType)?.toLowerCase();
  const marketType = normalizeMarketType(raw.marketType);
  if (!marketType) {
    const label = rawMarketType ?? "missing";
    const suffix = label === "runline" ? " Run Line is disabled for now." : "";
    warnings.push(`Prediction ${index + 1} skipped: unsupported marketType '${label}'.${suffix}`);
    return undefined;
  }

  return {
    gameId: optionalString(raw.gameId),
    date: optionalString(raw.date),
    sport: optionalString(raw.sport),
    league: optionalString(raw.league),
    homeTeam: optionalString(raw.homeTeam),
    awayTeam: optionalString(raw.awayTeam),
    market: optionalString(raw.market),
    pick: optionalString(raw.pick),
    marketType,
    marketAvailability: optionalString(raw.marketAvailability),
    rawModelProbability: optionalNumber(raw.rawModelProbability),
    calibratedProbability: optionalNumber(raw.calibratedProbability),
    marketProbability: optionalNumber(raw.marketProbability),
    rawEdge: optionalNumber(raw.rawEdge),
    calibratedEdge: optionalNumber(raw.calibratedEdge),
    confidence: optionalNumber(raw.confidence),
    dataQuality: optionalString(raw.dataQuality),
    calibrationQuality: normalizeCalibrationQuality(raw.calibrationQuality),
    calibrationMethod: optionalString(raw.calibrationMethod),
    calibrationSampleSize: optionalNumber(raw.calibrationSampleSize),
    calibrationWarnings: optionalStringArray(raw.calibrationWarnings),
    lineupStatus: optionalString(raw.lineupStatus),
    lineupImpactScore: optionalNumber(raw.lineupImpactScore),
    pitcherStatus: optionalString(raw.pitcherStatus),
    bullpenStatus: optionalString(raw.bullpenStatus),
    weatherImpact: optionalString(raw.weatherImpact),
    officialDecision: optionalString(raw.officialDecision),
    reasons: optionalStringArray(raw.reasons),
    risks: optionalStringArray(raw.risks),
    isPaperOnly: typeof raw.isPaperOnly === "boolean" ? raw.isPaperOnly : true,
  };
}

function extractPredictionArray(parsed: unknown, warnings: string[]): unknown[] | undefined {
  if (Array.isArray(parsed)) return parsed;
  if (isRecord(parsed) && Array.isArray(parsed.predictions)) return parsed.predictions;
  warnings.push("Python MLB predictions skipped: expected an array or an object with a predictions array.");
  return undefined;
}

export async function loadPythonMlbPredictions(sourcePath = PYTHON_MLB_PREDICTIONS_PATH): Promise<PythonMlbPredictionLoadResult> {
  const warnings: string[] = [];

  try {
    const raw = (await readFile(sourcePath, "utf8")).replace(/^\uFEFF/, "");
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return {
        available: false,
        sourcePath,
        predictions: [],
        warnings: ["Python MLB predictions skipped: invalid JSON in today_predictions.json."],
      };
    }

    const predictionArray = extractPredictionArray(parsed, warnings);
    if (!predictionArray) {
      return { available: false, sourcePath, predictions: [], warnings };
    }

    const predictions = predictionArray
      .map((prediction, index) => normalizePrediction(prediction, index, warnings))
      .filter((prediction): prediction is PythonMlbPrediction => Boolean(prediction));

    return {
      available: true,
      sourcePath,
      predictions,
      warnings,
    };
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") {
      return { available: false, sourcePath, predictions: [], warnings: [] };
    }

    return {
      available: false,
      sourcePath,
      predictions: [],
      warnings: [`Python MLB predictions skipped: ${error instanceof Error ? error.message : "unknown file read error"}.`],
    };
  }
}