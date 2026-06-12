import { readFile } from "node:fs/promises";

import { PAPER_WATCHLIST_LEDGER_PATH, type PaperWatchlistLedgerRow } from "./paper-watchlist-ledger";
import { normalizeText, safeNumber } from "../sports-data/normalize";

export type PaperPerformanceStatus = "available" | "empty" | "missing";

export type PaperPerformanceGroup = {
  key: string;
  label: string;
  totalRows: number;
  openRows: number;
  settledRows: number;
  wins: number;
  losses: number;
  pushes: number;
  unknown: number;
  winRate: number | null;
  paperPnLUnits: number | null;
  averageEdge: number | null;
  averageClv: number | null;
  averageClvPct: number | null;
  positiveClvRate: number | null;
  warnings: string[];
};

export type PaperPerformanceSummary = {
  totalRows: number;
  openRows: number;
  settledRows: number;
  wins: number;
  losses: number;
  pushes: number;
  unknown: number;
  winRate: number | null;
  paperPnLUnits: number | null;
  averagePaperPnLUnits: number | null;
  averageMarketProbability: number | null;
  averageRawModelProbability: number | null;
  averageCalibratedProbability: number | null;
  averageDiagnosticCalibratedEdge: number | null;
  averageClv: number | null;
  averageClvPct: number | null;
  positiveClvRate: number | null;
  bestEdgeBucket: string;
  bestWatchlistTier: string;
  warnings: string[];
  generatedAt: string;
  ledgerPath: string;
};

export type PaperPerformanceAnalysis = {
  status: PaperPerformanceStatus;
  summary: PaperPerformanceSummary;
  byWatchlistTier: PaperPerformanceGroup[];
  byEdgeBucket: PaperPerformanceGroup[];
  byMatchConfidence: PaperPerformanceGroup[];
  byCalibrationMappingStatus: PaperPerformanceGroup[];
  recentSettledRows: PaperWatchlistLedgerRow[];
  warnings: string[];
  generatedAt: string;
  ledgerPath: string;
};

const EDGE_BUCKETS = [
  { key: "0_to_3", label: "0% to 3%", min: 0, max: 0.03 },
  { key: "3_to_6", label: "3% to 6%", min: 0.03, max: 0.06 },
  { key: "6_plus", label: "6%+", min: 0.06, max: Number.POSITIVE_INFINITY },
] as const;

const WATCHLIST_TIER_BUCKETS = [
  { key: "monitor", label: "monitor" },
  { key: "paper_watchlist", label: "paper_watchlist" },
  { key: "priority_paper_watchlist", label: "priority_paper_watchlist" },
] as const;

const MATCH_CONFIDENCE_BUCKETS = [
  { key: "high", label: "high" },
  { key: "medium", label: "medium" },
] as const;

const CALIBRATION_MAPPING_BUCKETS = [
  { key: "research_only", label: "research_only" },
  { key: "missing", label: "missing" },
  { key: "other", label: "other" },
] as const;

function uniqueStrings(values: Array<string | undefined>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value && value.trim()))));
}

function isSettled(row: PaperWatchlistLedgerRow) {
  return row.status !== "open";
}

function isUsefulNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function toNumber(value: unknown) {
  const numeric = safeNumber(value);
  return typeof numeric === "number" && Number.isFinite(numeric) ? numeric : undefined;
}

function averageOf(values: number[]) {
  if (!values.length) return null;
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function settledWinRate(wins: number, losses: number) {
  const settledDecisions = wins + losses;
  if (!settledDecisions) return null;
  return wins / settledDecisions;
}

function countStatus(rows: PaperWatchlistLedgerRow[], status: PaperWatchlistLedgerRow["status"]) {
  return rows.filter((row) => row.status === status).length;
}

function countResult(rows: PaperWatchlistLedgerRow[], result: PaperWatchlistLedgerRow["result"]) {
  return rows.filter((row) => row.result === result).length;
}

function settledRows(rows: PaperWatchlistLedgerRow[]) {
  return rows.filter(isSettled);
}

function recentSettledRows(rows: PaperWatchlistLedgerRow[], limit: number) {
  return settledRows(rows)
    .slice()
    .sort((left, right) => {
      const leftTime = new Date(left.settledAt ?? left.updatedAt ?? left.createdAt).getTime();
      const rightTime = new Date(right.settledAt ?? right.updatedAt ?? right.createdAt).getTime();
      return rightTime - leftTime;
    })
    .slice(0, limit);
}

function calibrationBucketForStatus(status?: string) {
  const normalized = normalizeText(status ?? "");
  if (normalized === "research_only") return "research_only";
  if (normalized === "missing" || !normalized) return "missing";
  return "other";
}

function buildGroup(rows: PaperWatchlistLedgerRow[], key: string, label: string, selector: (row: PaperWatchlistLedgerRow) => boolean) {
  const groupRows = rows.filter(selector);
  const settled = settledRows(groupRows);
  const wins = countResult(settled, "win");
  const losses = countResult(settled, "loss");
  const pushes = countResult(settled, "push");
  const unknown = countResult(settled, "unknown");
  const settledCount = settled.length;
  const settledForAverages = settledCount ? settled : groupRows;
  const numericPaperPnLRows = settled.filter((row) => isUsefulNumber(row.paperPnLUnits));
  const numericEdgeRows = settledForAverages.filter((row) => isUsefulNumber(row.diagnosticCalibratedEdge));
  const averageEdge = averageOf(numericEdgeRows.map((row) => Number(row.diagnosticCalibratedEdge)));
  const clvRows = groupRows.filter((row) => isUsefulNumber(row.clv));
  const clvPctRows = groupRows.filter((row) => isUsefulNumber(row.clvPct));
  const averageClv = averageOf(clvRows.map((row) => Number(row.clv)));
  const averageClvPct = averageOf(clvPctRows.map((row) => Number(row.clvPct)));
  const positiveClvRate = clvRows.length ? clvRows.filter((row) => Number(row.clv) > 0).length / clvRows.length : null;
  const paperPnLUnits = settledCount
    ? numericPaperPnLRows.reduce((total, row) => total + Number(row.paperPnLUnits), 0)
    : null;
  const warnings = uniqueStrings([
    settledCount < 3 && groupRows.length ? "Small sample size - research only" : undefined,
    settledCount === 0 && groupRows.length ? "No settled rows yet; averages use available research rows only." : undefined,
    settledCount && numericPaperPnLRows.length !== settledCount ? "Some settled rows are missing paper PnL units; totals use available values only." : undefined,
    settledCount && numericEdgeRows.length !== settledCount ? "Some settled rows are missing diagnostic edge values; averages use available values only." : undefined,
    clvRows.length < 3 && groupRows.length ? "Small CLV sample size - research only" : undefined,
  ]);

  return {
    key,
    label,
    totalRows: groupRows.length,
    openRows: countStatus(groupRows, "open"),
    settledRows: settledCount,
    wins,
    losses,
    pushes,
    unknown,
    winRate: settledWinRate(wins, losses),
    paperPnLUnits,
    averageEdge,
    averageClv,
    averageClvPct,
    positiveClvRate,
    warnings,
  } satisfies PaperPerformanceGroup;
}

async function loadLedgerRows(): Promise<{ rows: PaperWatchlistLedgerRow[]; status: PaperPerformanceStatus; warnings: string[] }> {
  try {
    const raw = await readFile(PAPER_WATCHLIST_LEDGER_PATH, "utf8");
    const parsed = JSON.parse(raw.replace(/^\uFEFF/, "")) as unknown;
    if (!Array.isArray(parsed)) {
      return {
        rows: [],
        status: "missing",
        warnings: ["Paper watchlist ledger file exists but has an invalid JSON shape."],
      };
    }

    const rows = parsed
      .filter((value): value is Record<string, unknown> => typeof value === "object" && value !== null)
      .map((value) => value as PaperWatchlistLedgerRow)
      .filter((row) => Boolean(row.ledgerId && row.createdAt && row.updatedAt));

    return {
      rows,
      status: rows.length ? "available" : "empty",
      warnings: rows.length ? [] : ["Paper watchlist ledger has no rows yet."],
    };
  } catch (error) {
    return {
      rows: [],
      status: "missing",
      warnings: [
        error instanceof Error && error.message ? `Paper watchlist ledger unavailable: ${error.message}` : "Paper watchlist ledger unavailable.",
      ],
    };
  }
}

function bestGroupLabel(groups: PaperPerformanceGroup[]) {
  const settledGroups = groups.filter((group) => group.settledRows > 0);
  if (!settledGroups.length) return "No settled rows yet";
  const ranked = [...settledGroups].sort((left, right) => {
    const leftWinRate = left.winRate ?? -Infinity;
    const rightWinRate = right.winRate ?? -Infinity;
    if (rightWinRate !== leftWinRate) return rightWinRate - leftWinRate;
    const leftPnl = left.paperPnLUnits ?? -Infinity;
    const rightPnl = right.paperPnLUnits ?? -Infinity;
    if (rightPnl !== leftPnl) return rightPnl - leftPnl;
    return right.settledRows - left.settledRows;
  });
  return ranked[0]?.label ?? "No settled rows yet";
}

function averageRows(rows: PaperWatchlistLedgerRow[], selector: (row: PaperWatchlistLedgerRow) => number | undefined) {
  const values = rows
    .map(selector)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  return averageOf(values);
}

export async function loadPaperWatchlistPerformanceAnalysis(limit = 10): Promise<PaperPerformanceAnalysis> {
  const loaded = await loadLedgerRows();
  const rows = loaded.rows;
  const settled = settledRows(rows);
  const settledCount = settled.length;
  const settledWinCount = countResult(settled, "win");
  const settledLossCount = countResult(settled, "loss");
  const settledPushCount = countResult(settled, "push");
  const settledUnknownCount = countResult(settled, "unknown");
  const wins = settledWinCount;
  const losses = settledLossCount;
  const pushes = settledPushCount;
  const unknown = settledUnknownCount;
  const winRate = settledWinRate(wins, losses);
  const paperPnLValues = settled
    .map((row) => toNumber(row.paperPnLUnits))
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const paperPnLUnits = paperPnLValues.length ? paperPnLValues.reduce((total, value) => total + value, 0) : null;
  const averagePaperPnLUnits = settledCount ? averageOf(paperPnLValues) : null;
  const settledEdgeValues = settled
    .map((row) => toNumber(row.diagnosticCalibratedEdge))
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));

  const rowsForAverages = settledCount ? settled : rows;
  const averageMarketProbability = averageRows(rowsForAverages, (row) => toNumber(row.marketProbability));
  const averageRawModelProbability = averageRows(rowsForAverages, (row) => toNumber(row.rawModelProbability));
  const averageCalibratedProbability = averageRows(rowsForAverages, (row) => toNumber(row.calibratedProbability));
  const averageDiagnosticCalibratedEdge = averageRows(rowsForAverages, (row) => toNumber(row.diagnosticCalibratedEdge));
  const averageClv = averageRows(rowsForAverages, (row) => toNumber(row.clv));
  const averageClvPct = averageRows(rowsForAverages, (row) => toNumber(row.clvPct));
  const clvRows = rowsForAverages.filter((row) => isUsefulNumber(row.clv));
  const positiveClvRate = clvRows.length ? clvRows.filter((row) => Number(row.clv) > 0).length / clvRows.length : null;

  const byWatchlistTier = WATCHLIST_TIER_BUCKETS.map((bucket) =>
    buildGroup(rows, bucket.key, bucket.label, (row) => row.watchlistTier === bucket.key),
  );
  const byEdgeBucket = EDGE_BUCKETS.map((bucket) =>
    buildGroup(rows, bucket.key, bucket.label, (row) => {
      const edge = toNumber(row.diagnosticCalibratedEdge);
      if (!isUsefulNumber(edge)) return false;
      return bucket.max === Number.POSITIVE_INFINITY ? edge >= bucket.min : edge >= bucket.min && edge < bucket.max;
    }),
  );
  const byMatchConfidence = MATCH_CONFIDENCE_BUCKETS.map((bucket) =>
    buildGroup(rows, bucket.key, bucket.label, (row) => normalizeText(row.matchConfidence) === bucket.key),
  );
  const byCalibrationMappingStatus = CALIBRATION_MAPPING_BUCKETS.map((bucket) =>
    buildGroup(rows, bucket.key, bucket.label, (row) => calibrationBucketForStatus(row.calibrationMappingStatus) === bucket.key),
  );

  const summaryWarnings = uniqueStrings([
    ...loaded.warnings,
    "Paper performance is research only and does not represent official picks, Strong Buys, Telegram signals, or real-money performance.",
    settledCount < 10 ? "Small sample size - research only" : undefined,
    settledCount === 0 && rows.length ? "No settled rows yet; paper performance is not fully measurable." : undefined,
    settledCount && paperPnLValues.length !== settledCount ? "Some settled rows are missing paper PnL units; totals use available values only." : undefined,
    settledCount && settledEdgeValues.length !== settledCount ? "Some settled rows are missing diagnostic edge values; averages use available values only." : undefined,
    clvRows.length < 5 && rows.length ? "Small CLV sample size - research only." : undefined,
  ]);

  const summary: PaperPerformanceSummary = {
    totalRows: rows.length,
    openRows: countStatus(rows, "open"),
    settledRows: settledCount,
    wins,
    losses,
    pushes,
    unknown,
    winRate,
    paperPnLUnits,
    averagePaperPnLUnits,
    averageMarketProbability,
    averageRawModelProbability,
    averageCalibratedProbability,
    averageDiagnosticCalibratedEdge,
    averageClv,
    averageClvPct,
    positiveClvRate,
    bestEdgeBucket: bestGroupLabel(byEdgeBucket),
    bestWatchlistTier: bestGroupLabel(byWatchlistTier),
    warnings: summaryWarnings,
    generatedAt: new Date().toISOString(),
    ledgerPath: ".astrodds/paper-watchlist-ledger.json",
  };

  const analysisWarnings = uniqueStrings([
    ...summaryWarnings,
    ...byWatchlistTier.flatMap((group) => group.warnings),
    ...byEdgeBucket.flatMap((group) => group.warnings),
    ...byMatchConfidence.flatMap((group) => group.warnings),
    ...byCalibrationMappingStatus.flatMap((group) => group.warnings),
  ]);

  return {
    status: loaded.status,
    summary,
    byWatchlistTier,
    byEdgeBucket,
    byMatchConfidence,
    byCalibrationMappingStatus,
    recentSettledRows: recentSettledRows(rows, limit),
    warnings: analysisWarnings,
    generatedAt: summary.generatedAt,
    ledgerPath: summary.ledgerPath,
  };
}
