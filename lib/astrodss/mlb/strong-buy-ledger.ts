import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { buildStrongBuyBankrollSnapshot, STRONG_BUY_STARTING_BANKROLL } from "./bankroll-config";
import type { BestBetRow } from "./strong-buy-gate";

export const STRONG_BUY_LEDGER_PATH = path.join(/* turbopackIgnore: true */ process.cwd(), ".astrodds", "strong-buy-ledger.json");

export type StrongBuyLedgerStatus = "open" | "settled" | "void" | "error";
export type StrongBuyLedgerResult = "win" | "loss" | "push" | "unknown";

export type StrongBuyLedgerRow = {
  ledgerId: string;
  bestBetId: string;
  strongBuyId?: string;
  date?: string;
  gameId?: string;
  homeTeam?: string;
  awayTeam?: string;
  marketType: "moneyline";
  selectedSide?: string;
  status: StrongBuyLedgerStatus;
  result: StrongBuyLedgerResult;
  source: "strong_buy_gate";
  manuallyTaken: boolean;
  bankrollAtEntry: number;
  stakePercent: number;
  stakeAmount: number;
  openExposureAtEntry: number;
  marketProbabilityAtEntry?: number | null;
  calibratedProbabilityAtEntry?: number | null;
  diagnosticEdgeAtEntry?: number | null;
  riskLevelAtEntry?: string;
  sentToTelegramAt?: string;
  telegramMessageId?: number;
  paperPnL?: number | null;
  clv?: number | null;
  notes: string[];
  createdAt: string;
  updatedAt: string;
};

export type StrongBuyLedgerSummary = {
  ledgerAvailable: boolean;
  totalTracked: number;
  open: number;
  settled: number;
  wins: number;
  losses: number;
  pushes: number;
  unknown: number;
  winRate: number | null;
  paperPnL: number | null;
  currentBankroll: number;
  averageCLV: number | null;
  averageStake: number | null;
  openStrongBuyCount: number;
  totalOpenStakeAmount: number;
  totalOpenExposurePercent: number;
  remainingUnexposedBankroll: number;
  exposureLabel: string;
  warnings: string[];
  generatedAt: string;
  ledgerPath: string;
  recentBets: StrongBuyLedgerRow[];
};

export type SaveStrongBuyLedgerResult = {
  ok: boolean;
  saved: StrongBuyLedgerRow;
  summary: StrongBuyLedgerSummary;
  warnings: string[];
};

function uniqueStrings(values: Array<string | undefined>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value && value.trim()))));
}

function roundToCents(value: number) {
  return Math.round(value * 100) / 100;
}

function safeSlug(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80) || "strong-buy";
}

function ledgerKey(row: Pick<StrongBuyLedgerRow, "bestBetId" | "date">) {
  return `${row.bestBetId}|${row.date ?? ""}`;
}

function sumSettledPnl(rows: StrongBuyLedgerRow[]) {
  const settled = rows
    .filter((row) => row.status === "settled" && typeof row.paperPnL === "number" && Number.isFinite(row.paperPnL))
    .reduce((total, row) => total + (row.paperPnL ?? 0), 0);
  return roundToCents(settled);
}

async function writeJson<T>(filePath: string, value: T) {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, JSON.stringify(value, null, 2), "utf8");
}

export async function loadStrongBuyLedgerRows(): Promise<{ rows: StrongBuyLedgerRow[]; available: boolean; warnings: string[] }> {
  try {
    const raw = await readFile(STRONG_BUY_LEDGER_PATH, "utf8");
    const parsed = JSON.parse(raw.replace(/^\uFEFF/, "")) as unknown;
    if (!Array.isArray(parsed)) {
      return { rows: [], available: false, warnings: ["Strong Buy ledger skipped: invalid JSON shape."] };
    }

    const rows = parsed
      .filter((value): value is Record<string, unknown> => typeof value === "object" && value !== null)
      .map((value) => value as StrongBuyLedgerRow)
      .filter((row) => Boolean(row.ledgerId && row.bestBetId));

    return { rows, available: true, warnings: [] };
  } catch {
    return { rows: [], available: false, warnings: [] };
  }
}

export async function writeStrongBuyLedgerRows(rows: StrongBuyLedgerRow[]) {
  await writeJson(STRONG_BUY_LEDGER_PATH, rows.slice(-2500));
}

function buildStrongBuyLedgerSummary(rows: StrongBuyLedgerRow[], available: boolean, warnings: string[] = []): StrongBuyLedgerSummary {
  const wins = rows.filter((row) => row.status === "settled" && row.result === "win").length;
  const losses = rows.filter((row) => row.status === "settled" && row.result === "loss").length;
  const pushes = rows.filter((row) => row.status === "void" || (row.status === "settled" && row.result === "push")).length;
  const settled = rows.filter((row) => row.status === "settled" || row.status === "void").length;
  const openRows = rows.filter((row) => row.status === "open");
  const paperPnL = sumSettledPnl(rows);
  const averageClvValues = rows.map((row) => row.clv).filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const averageStakeValues = rows.map((row) => row.stakeAmount).filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const bankroll = buildStrongBuyBankrollSnapshot({
    realizedSettledPaperPnL: paperPnL,
    openRows: openRows.map((row) => ({ status: row.status, stakeAmount: row.stakeAmount })),
  });

  return {
    ledgerAvailable: available,
    totalTracked: rows.length,
    open: openRows.length,
    settled,
    wins,
    losses,
    pushes,
    unknown: rows.filter((row) => row.result === "unknown" || row.status === "error").length,
    winRate: wins + losses > 0 ? wins / (wins + losses) : null,
    paperPnL,
    currentBankroll: bankroll.currentBankroll,
    averageCLV: averageClvValues.length ? roundToCents(averageClvValues.reduce((total, value) => total + value, 0) / averageClvValues.length) : null,
    averageStake: averageStakeValues.length ? roundToCents(averageStakeValues.reduce((total, value) => total + value, 0) / averageStakeValues.length) : null,
    openStrongBuyCount: bankroll.openStrongBuyCount,
    totalOpenStakeAmount: bankroll.totalOpenStakeAmount,
    totalOpenExposurePercent: bankroll.totalOpenExposurePercent,
    remainingUnexposedBankroll: bankroll.remainingUnexposedBankroll,
    exposureLabel: bankroll.exposureLabel,
    warnings: uniqueStrings(warnings),
    generatedAt: new Date().toISOString(),
    ledgerPath: ".astrodds/strong-buy-ledger.json",
    recentBets: [...rows].sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()).slice(0, 10),
  };
}

function createLedgerRow(row: BestBetRow, now: string, options?: { manuallyTaken?: boolean; sentToTelegramAt?: string; telegramMessageId?: number }, existing?: StrongBuyLedgerRow): StrongBuyLedgerRow {
  if (existing) {
    return {
      ...existing,
      strongBuyId: row.strongBuyId ?? existing.strongBuyId,
      homeTeam: row.homeTeam ?? existing.homeTeam,
      awayTeam: row.awayTeam ?? existing.awayTeam,
      selectedSide: row.selectedSide ?? existing.selectedSide,
      bankrollAtEntry: existing.bankrollAtEntry || row.bankroll || STRONG_BUY_STARTING_BANKROLL,
      stakePercent: existing.stakePercent || row.stakePercent,
      stakeAmount: existing.stakeAmount || row.stakeAmount,
      openExposureAtEntry: existing.openExposureAtEntry || row.totalOpenExposurePercent,
      marketProbabilityAtEntry: existing.marketProbabilityAtEntry ?? row.marketProbability,
      calibratedProbabilityAtEntry: existing.calibratedProbabilityAtEntry ?? row.calibratedProbability,
      diagnosticEdgeAtEntry: existing.diagnosticEdgeAtEntry ?? row.diagnosticCalibratedEdge,
      riskLevelAtEntry: existing.riskLevelAtEntry ?? row.riskLevel,
      manuallyTaken: existing.manuallyTaken || Boolean(options?.manuallyTaken),
      sentToTelegramAt: options?.sentToTelegramAt ?? existing.sentToTelegramAt,
      telegramMessageId: options?.telegramMessageId ?? existing.telegramMessageId,
      updatedAt: now,
      notes: uniqueStrings([
        ...existing.notes,
        ...row.reasons,
        ...row.warnings,
      ]),
    };
  }

  return {
    ledgerId: `strong-buy-${safeSlug(`${row.bestBetId}-${row.date ?? now.slice(0, 10)}`)}`,
    bestBetId: row.bestBetId,
    strongBuyId: row.strongBuyId,
    date: row.date,
    gameId: row.gameId,
    homeTeam: row.homeTeam,
    awayTeam: row.awayTeam,
    marketType: "moneyline",
    selectedSide: row.selectedSide,
    status: "open",
    result: "unknown",
    source: "strong_buy_gate",
    manuallyTaken: Boolean(options?.manuallyTaken),
    bankrollAtEntry: row.bankroll,
    stakePercent: row.stakePercent,
    stakeAmount: row.stakeAmount,
    openExposureAtEntry: row.totalOpenExposurePercent,
    marketProbabilityAtEntry: row.marketProbability,
    calibratedProbabilityAtEntry: row.calibratedProbability,
    diagnosticEdgeAtEntry: row.diagnosticCalibratedEdge,
    riskLevelAtEntry: row.riskLevel,
    sentToTelegramAt: options?.sentToTelegramAt,
    telegramMessageId: options?.telegramMessageId,
    paperPnL: null,
    clv: null,
    notes: uniqueStrings([
      ...row.reasons,
      ...row.warnings,
      options?.manuallyTaken ? "Saved as manually tracked Strong Buy." : undefined,
      options?.sentToTelegramAt ? "Sent to Telegram as Strong Buy alert." : undefined,
      "Manual action only. Real-money automation remains OFF.",
    ]),
    createdAt: now,
    updatedAt: now,
  };
}

export async function loadStrongBuyLedgerStatus() {
  const { rows, available, warnings } = await loadStrongBuyLedgerRows();
  return buildStrongBuyLedgerSummary(rows, available, warnings);
}

export async function saveStrongBuyLedgerRow(row: BestBetRow, options?: { manuallyTaken?: boolean; sentToTelegramAt?: string; telegramMessageId?: number }): Promise<SaveStrongBuyLedgerResult> {
  const now = new Date().toISOString();
  const { rows, warnings } = await loadStrongBuyLedgerRows();
  const rowMap = new Map(rows.map((entry) => [ledgerKey(entry), entry]));
  const key = ledgerKey({ bestBetId: row.bestBetId, date: row.date });
  const nextRow = createLedgerRow(row, now, options, rowMap.get(key));
  rowMap.set(key, nextRow);
  const nextRows = Array.from(rowMap.values()).sort((left, right) => new Date(left.updatedAt).getTime() - new Date(right.updatedAt).getTime());
  await writeStrongBuyLedgerRows(nextRows);
  const summary = buildStrongBuyLedgerSummary(nextRows, true, warnings);

  return {
    ok: true,
    saved: nextRow,
    summary,
    warnings: summary.warnings,
  };
}

export async function wasStrongBuySentToday(bestBetId: string, date = new Date().toISOString().slice(0, 10)) {
  const { rows } = await loadStrongBuyLedgerRows();
  return rows.some((row) => row.bestBetId === bestBetId && row.sentToTelegramAt?.slice(0, 10) === date);
}
