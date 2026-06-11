import { readFile } from "node:fs/promises";
import path from "node:path";

export const MLB_HISTORICAL_EXPANSION_REPORT_PATH = path.join(
  process.cwd(),
  "mlb-engine",
  "data",
  "processed",
  "mlb_historical_expansion_2016_2026_report.json",
);

export type HistoricalExpansionStatus = "available" | "partial" | "missing";

export type HistoricalExpansionDiagnostics = {
  status: HistoricalExpansionStatus;
  available: boolean;
  historicalWindow: string;
  startYear: number;
  endYear: number;
  yearsIncluded: number[];
  totalGamesRead: number;
  completedGamesUsed: number;
  incompleteGamesSkipped: number;
  malformedGamesSkipped: number;
  outputRowCount: number;
  outputCsv?: string;
  featureReportPath?: string;
  expansionReportPath?: string;
  warnings: string[];
  generatedAt?: string;
  sourcePath: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function optionalNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function optionalNumberArray(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is number => typeof item === "number" && Number.isFinite(item));
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    .map((item) => item.trim());
}

function safeDefault(sourcePath = MLB_HISTORICAL_EXPANSION_REPORT_PATH, warning?: string): HistoricalExpansionDiagnostics {
  return {
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
    warnings: warning ? [warning] : [],
    sourcePath,
  };
}

function normalizeStatus(summary: HistoricalExpansionDiagnostics): HistoricalExpansionDiagnostics {
  if (summary.completedGamesUsed <= 0) {
    return {
      ...summary,
      status: "missing",
      available: false,
    };
  }

  const incomplete = summary.incompleteGamesSkipped > 0 || summary.malformedGamesSkipped > 0;
  return {
    ...summary,
    status: incomplete ? "partial" : "available",
    available: true,
  };
}

function normalizeDiagnostics(raw: unknown, sourcePath: string): HistoricalExpansionDiagnostics {
  if (!isRecord(raw)) {
    return safeDefault(sourcePath, "Historical expansion report skipped: invalid JSON shape.");
  }

  const startYear = optionalNumber(raw.start_year) ?? optionalNumber(raw.startYear) ?? 2016;
  const endYear = optionalNumber(raw.end_year) ?? optionalNumber(raw.endYear) ?? 2026;
  const yearsIncluded = optionalNumberArray(raw.years_included).length
    ? optionalNumberArray(raw.years_included)
    : optionalNumberArray(raw.seasons_included).length
      ? optionalNumberArray(raw.seasons_included)
      : optionalNumberArray(raw.yearsIncluded);
  const historicalWindow = optionalString(raw.historical_window) ?? optionalString(raw.historicalWindow) ?? `${startYear}-${endYear}`;

  const summary: HistoricalExpansionDiagnostics = {
    status: "missing",
    available: false,
    historicalWindow,
    startYear,
    endYear,
    yearsIncluded,
    totalGamesRead: optionalNumber(raw.total_games_read) ?? optionalNumber(raw.totalGamesRead) ?? 0,
    completedGamesUsed: optionalNumber(raw.completed_games_used) ?? optionalNumber(raw.completedGamesUsed) ?? 0,
    incompleteGamesSkipped: optionalNumber(raw.incomplete_games_skipped) ?? optionalNumber(raw.incompleteGamesSkipped) ?? 0,
    malformedGamesSkipped: optionalNumber(raw.malformed_games_skipped) ?? optionalNumber(raw.malformedGamesSkipped) ?? 0,
    outputRowCount: optionalNumber(raw.output_row_count) ?? optionalNumber(raw.outputRowCount) ?? 0,
    outputCsv: optionalString(raw.output_csv) ?? optionalString(raw.outputCsv),
    featureReportPath: optionalString(raw.report_json) ?? optionalString(raw.featureReportPath),
    expansionReportPath: optionalString(raw.expansion_report_json) ?? optionalString(raw.expansionReportPath),
    warnings: stringArray(raw.warnings),
    generatedAt: optionalString(raw.generated_at) ?? optionalString(raw.generatedAt),
    sourcePath,
  };

  return normalizeStatus(summary);
}

export async function loadHistoricalExpansionStatus(sourcePath = MLB_HISTORICAL_EXPANSION_REPORT_PATH): Promise<HistoricalExpansionDiagnostics> {
  try {
    const raw = (await readFile(sourcePath, "utf8")).replace(/^\uFEFF/, "");
    try {
      return normalizeDiagnostics(JSON.parse(raw), sourcePath);
    } catch {
      return safeDefault(sourcePath, "Historical expansion report skipped: invalid JSON in mlb_historical_expansion_2016_2026_report.json.");
    }
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") {
      return safeDefault(sourcePath);
    }
    return safeDefault(sourcePath, `Historical expansion report skipped: ${error instanceof Error ? error.message : "unknown file read error"}.`);
  }
}
