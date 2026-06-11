import { readFile } from "node:fs/promises";
import path from "node:path";

export const PYTHON_MLB_MODEL_STATUS_PATH = path.join(process.cwd(), "mlb-engine", "outputs", "model_status.json");

export type PythonMlbCalibrationQuality = "strong" | "medium" | "weak" | "not_enough_history" | "missing";

export type PythonMlbEngineStatus = {
  engineAvailable: boolean;
  modelAvailable: boolean;
  modelVersion: string;
  modelType: string;
  trainingRows?: number;
  validationRows?: number;
  holdout2026Rows?: number;
  validationAccuracy?: number;
  baselineHomeTeamAccuracy?: number;
  brierScore?: number;
  logLoss?: number;
  expectedCalibrationError?: number;
  maxCalibrationError?: number;
  calibrationQuality: PythonMlbCalibrationQuality;
  supportedMarkets: string[];
  disabledMarkets: string[];
  officialPickEligible: boolean;
  officialPickBlockReasons: string[];
  warnings: string[];
  generatedAt?: string;
  sourcePath: string;
};

const blockingCalibrationQualities = new Set<PythonMlbCalibrationQuality>(["weak", "missing", "not_enough_history"]);
const allowedCalibrationQualities = new Set<PythonMlbCalibrationQuality>(["strong", "medium", "weak", "not_enough_history", "missing"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function optionalNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0).map((item) => item.trim());
}

function normalizeCalibrationQuality(value: unknown): PythonMlbCalibrationQuality {
  const quality = optionalString(value)?.toLowerCase();
  if (quality && allowedCalibrationQualities.has(quality as PythonMlbCalibrationQuality)) return quality as PythonMlbCalibrationQuality;
  return "missing";
}

function safeDefault(sourcePath = PYTHON_MLB_MODEL_STATUS_PATH, warning?: string): PythonMlbEngineStatus {
  return {
    engineAvailable: false,
    modelAvailable: false,
    modelVersion: "unknown",
    modelType: "unknown",
    calibrationQuality: "missing",
    supportedMarkets: ["moneyline"],
    disabledMarkets: ["runline"],
    officialPickEligible: false,
    officialPickBlockReasons: ["Python MLB model status file missing"],
    warnings: warning ? [warning] : [],
    sourcePath,
  };
}

function enforceSafety(status: PythonMlbEngineStatus) {
  const blockReasons = new Set(status.officialPickBlockReasons);
  if (!status.modelAvailable) blockReasons.add("Python MLB model is not available");
  if (blockingCalibrationQualities.has(status.calibrationQuality)) blockReasons.add(`Calibration quality is ${status.calibrationQuality}`);
  if (!status.supportedMarkets.includes("moneyline")) blockReasons.add("Moneyline market is not supported by Python model status");
  if (!status.disabledMarkets.includes("runline")) blockReasons.add("Runline must remain disabled");
  if (!status.officialPickBlockReasons.length) blockReasons.add("No market prices connected");
  if (!Array.from(blockReasons).some((reason) => reason.toLowerCase().includes("calibrated probability"))) {
    blockReasons.add("No calibrated probability mapping available");
  }
  if (!Array.from(blockReasons).some((reason) => reason.toLowerCase().includes("market price"))) {
    blockReasons.add("No market prices connected");
  }

  const officialPickEligible = Boolean(status.officialPickEligible) && blockReasons.size === 0 && !blockingCalibrationQualities.has(status.calibrationQuality);
  return {
    ...status,
    officialPickEligible,
    officialPickBlockReasons: Array.from(blockReasons),
  };
}

function normalizeStatus(raw: unknown, sourcePath: string): PythonMlbEngineStatus {
  if (!isRecord(raw)) return safeDefault(sourcePath, "Python MLB model status skipped: invalid JSON shape.");

  const status: PythonMlbEngineStatus = {
    engineAvailable: raw.engineAvailable === true,
    modelAvailable: raw.modelAvailable === true,
    modelVersion: optionalString(raw.modelVersion) ?? "unknown",
    modelType: optionalString(raw.modelType) ?? "unknown",
    trainingRows: optionalNumber(raw.trainingRows),
    validationRows: optionalNumber(raw.validationRows),
    holdout2026Rows: optionalNumber(raw.holdout2026Rows),
    validationAccuracy: optionalNumber(raw.validationAccuracy),
    baselineHomeTeamAccuracy: optionalNumber(raw.baselineHomeTeamAccuracy),
    brierScore: optionalNumber(raw.brierScore),
    logLoss: optionalNumber(raw.logLoss),
    expectedCalibrationError: optionalNumber(raw.expectedCalibrationError),
    maxCalibrationError: optionalNumber(raw.maxCalibrationError),
    calibrationQuality: normalizeCalibrationQuality(raw.calibrationQuality),
    supportedMarkets: stringArray(raw.supportedMarkets).length ? stringArray(raw.supportedMarkets) : ["moneyline"],
    disabledMarkets: stringArray(raw.disabledMarkets).length ? stringArray(raw.disabledMarkets) : ["runline"],
    officialPickEligible: raw.officialPickEligible === true,
    officialPickBlockReasons: stringArray(raw.officialPickBlockReasons),
    warnings: stringArray(raw.warnings),
    generatedAt: optionalString(raw.generatedAt),
    sourcePath,
  };

  return enforceSafety(status);
}

export async function loadPythonMlbEngineStatus(sourcePath = PYTHON_MLB_MODEL_STATUS_PATH): Promise<PythonMlbEngineStatus> {
  try {
    const raw = (await readFile(sourcePath, "utf8")).replace(/^\uFEFF/, "");
    try {
      return normalizeStatus(JSON.parse(raw), sourcePath);
    } catch {
      return safeDefault(sourcePath, "Python MLB model status skipped: invalid JSON in model_status.json.");
    }
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") {
      return safeDefault(sourcePath);
    }
    return safeDefault(sourcePath, `Python MLB model status skipped: ${error instanceof Error ? error.message : "unknown file read error"}.`);
  }
}