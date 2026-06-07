import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import {
  getPaperTestState,
  loadModelLeanRecords,
  loadOfficialPaperPicks,
  summarizePaperLedger,
  type OfficialPaperPick,
} from "./paper/paper-ledger";

type GenericSignalInput = Record<string, unknown>;

export type AstroddsPerformanceRecord = {
  signalId: string;
  market?: string;
  side?: string;
  entry?: number;
  price15m?: number;
  price1h?: number;
  closingValue?: number;
  clv?: number;
  result?: string;
  pnl: number;
  roi: number;
  sport: string;
  signalType: string;
  whaleGrade: string;
  decision?: string;
  status: "PENDING" | "WIN" | "LOSS" | "VOID" | "UNKNOWN";
  createdAt: string;
  source: string;
};

export type AstroddsPerformanceBucket = {
  signals: number;
  settled: number;
  wins: number;
  losses: number;
  voids: number;
  pnl: number;
  roi: number;
  averageClv: number | null;
  drawdown: number;
  longestLosingStreak: number;
};

const generatedSignalsPath = path.join(process.cwd(), ".astrodds", "generated-signals.json");
const paperSignalsPath = path.join(process.cwd(), ".astrodds", "paper-signals.json");
const overnightPaperSignalsPath = path.join(process.cwd(), ".astrodds", "mlb-paper-signals.json");

function stringValue(value: unknown, fallback = "UNKNOWN") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function numberValue(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function statusValue(value: unknown): AstroddsPerformanceRecord["status"] {
  const status = stringValue(value, "PENDING").toUpperCase();
  if (status === "WON" || status === "WINNER") return "WIN";
  if (status === "LOST" || status === "LOSER") return "LOSS";
  if (status === "WIN" || status === "LOSS" || status === "VOID" || status === "UNKNOWN" || status === "PENDING") return status;
  return "UNKNOWN";
}

async function readJsonArray(filePath: string) {
  try {
    const parsed = JSON.parse(await readFile(filePath, "utf8")) as unknown;
    return Array.isArray(parsed) ? parsed as GenericSignalInput[] : [];
  } catch {
    return [];
  }
}

async function writeJsonArray(filePath: string, rows: AstroddsPerformanceRecord[]) {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, JSON.stringify(rows.slice(-2500), null, 2), "utf8");
}

function normalizeSignal(input: GenericSignalInput, source: string): AstroddsPerformanceRecord {
  const sourceData = input.sourceData && typeof input.sourceData === "object" ? input.sourceData as GenericSignalInput : {};
  const signalId = stringValue(input.signalId ?? input.signalKey ?? input.id ?? sourceData.signalId, `${source}-${stringValue(input.market ?? input.game ?? "signal")}-${stringValue(input.createdAt ?? new Date().toISOString())}`);
  const status = statusValue(input.status ?? input.resultStatus);
  const stake = numberValue(input.stake) ?? 0;
  const pnl = numberValue(input.pnl) ?? 0;
  const roi = numberValue(input.roi) ?? (stake ? pnl / stake : 0);

  return {
    signalId,
    market: stringValue(input.market ?? input.game, undefined),
    side: stringValue(input.side ?? input.pick, undefined),
    entry: numberValue(input.entry ?? input.entryPrice ?? input.currentPrice),
    price15m: numberValue(input.price15m ?? input.price15MinutesLater),
    price1h: numberValue(input.price1h ?? input.price1HourLater),
    closingValue: numberValue(input.closingValue ?? input.closingPrice ?? input.exitPrice),
    clv: numberValue(input.clv),
    result: typeof input.result === "string" ? input.result : undefined,
    pnl,
    roi,
    sport: stringValue(input.sport, "UNKNOWN"),
    signalType: stringValue(input.finalCategory ?? sourceData.finalCategory ?? input.signalType ?? sourceData.signalType, "UNKNOWN"),
    whaleGrade: stringValue(input.whaleGrade ?? sourceData.whaleGrade, "NONE"),
    decision: typeof input.decision === "string" ? input.decision : undefined,
    status,
    createdAt: stringValue(input.createdAt, new Date().toISOString()),
    source,
  };
}
function normalizeOfficialPaperPick(pick: OfficialPaperPick): AstroddsPerformanceRecord {
  const status: AstroddsPerformanceRecord["status"] =
    pick.status === "won"
      ? "WIN"
      : pick.status === "lost"
        ? "LOSS"
        : pick.status === "push" || pick.status === "void"
          ? "VOID"
          : "PENDING";
  const pnl = pick.result?.pnlUnits ?? 0;
  const roi = pick.paperStakeUnits ? pnl / pick.paperStakeUnits : 0;

  return {
    signalId: pick.id,
    market: pick.game,
    side: pick.pickSide,
    entry: pick.entryPricePolymarket ?? pick.impliedProbability ?? pick.entryPriceDecimal,
    closingValue: pick.result?.closingPrice,
    clv: pick.result?.clv,
    result: pick.result?.finalScore,
    pnl,
    roi,
    sport: pick.sport ?? pick.category.toUpperCase(),
    signalType: `OFFICIAL_${pick.category.toUpperCase()}_PAPER_PICK`,
    whaleGrade: pick.whaleSupportLevel ?? "NONE",
    decision: pick.decisionLabel.replace(" ", "_"),
    status,
    createdAt: pick.createdAt,
    source: "OFFICIAL_PAPER_LEDGER",
  };
}

function uniqueRecords(records: AstroddsPerformanceRecord[]) {
  const seen = new Map<string, AstroddsPerformanceRecord>();
  for (const record of records) {
    const key = `${record.source}|${record.signalId}|${record.createdAt.slice(0, 10)}`;
    seen.set(key, record);
  }
  return Array.from(seen.values());
}

function emptyBucket(): AstroddsPerformanceBucket {
  return { signals: 0, settled: 0, wins: 0, losses: 0, voids: 0, pnl: 0, roi: 0, averageClv: null, drawdown: 0, longestLosingStreak: 0 };
}

function addToBucket(bucket: AstroddsPerformanceBucket, record: AstroddsPerformanceRecord) {
  bucket.signals += 1;
  if (record.status === "WIN" || record.status === "LOSS" || record.status === "VOID") {
    bucket.settled += 1;
    bucket.pnl += record.pnl;
    if (record.status === "WIN") bucket.wins += 1;
    if (record.status === "LOSS") bucket.losses += 1;
    if (record.status === "VOID") bucket.voids += 1;
  }
}

function recordClv(record: AstroddsPerformanceRecord) {
  if (typeof record.clv === "number" && Number.isFinite(record.clv)) return record.clv;
  if (typeof record.entry === "number" && typeof record.closingValue === "number") return record.closingValue - record.entry;
  return undefined;
}

function finalizeBucket(bucket: AstroddsPerformanceBucket, records: AstroddsPerformanceRecord[] = []) {
  const risked = bucket.settled ? bucket.settled * 50 : 0;
  const clvValues = records.map(recordClv).filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  let equity = 0;
  let peak = 0;
  let drawdown = 0;
  let currentLosingStreak = 0;
  let longestLosingStreak = 0;
  for (const record of records.sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())) {
    if (record.status === "WIN" || record.status === "LOSS" || record.status === "VOID") {
      equity += record.pnl;
      peak = Math.max(peak, equity);
      drawdown = Math.min(drawdown, equity - peak);
    }
    if (record.status === "LOSS") {
      currentLosingStreak += 1;
      longestLosingStreak = Math.max(longestLosingStreak, currentLosingStreak);
    } else if (record.status === "WIN" || record.status === "VOID") {
      currentLosingStreak = 0;
    }
  }
  return {
    ...bucket,
    pnl: Number(bucket.pnl.toFixed(2)),
    roi: risked ? Number((bucket.pnl / risked).toFixed(4)) : 0,
    averageClv: clvValues.length ? Number((clvValues.reduce((total, value) => total + value, 0) / clvValues.length).toFixed(4)) : null,
    drawdown: Number(drawdown.toFixed(2)),
    longestLosingStreak,
  };
}

function groupBy(records: AstroddsPerformanceRecord[], key: (record: AstroddsPerformanceRecord) => string) {
  const map: Record<string, AstroddsPerformanceBucket> = {};
  for (const record of records) {
    const bucketKey = key(record);
    map[bucketKey] ??= emptyBucket();
    addToBucket(map[bucketKey], record);
  }

  return Object.fromEntries(Object.entries(map).map(([bucketKey, bucket]) => [bucketKey, finalizeBucket(bucket, records.filter((record) => key(record) === bucketKey))]));
}

function reportWindow(records: AstroddsPerformanceRecord[], days: number) {
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  return summarizeRecords(records.filter((record) => new Date(record.createdAt).getTime() >= cutoff));
}

export async function recordGeneratedSignals(signals: GenericSignalInput[]) {
  if (!signals.length) return;
  const existing = (await readJsonArray(generatedSignalsPath)).map((item) => normalizeSignal(item, "UNIFIED_MODEL_SIGNAL"));
  const next = signals.map((signal) => normalizeSignal(signal, "UNIFIED_MODEL_SIGNAL"));
  await writeJsonArray(generatedSignalsPath, uniqueRecords([...existing, ...next]));
}

export async function loadPerformanceRecords() {
  const [generated, whalePaper, overnightPaper, officialPaper] = await Promise.all([
    readJsonArray(generatedSignalsPath),
    readJsonArray(paperSignalsPath),
    readJsonArray(overnightPaperSignalsPath),
    loadOfficialPaperPicks(),
  ]);

  return uniqueRecords([
    ...generated.map((item) => normalizeSignal(item, "UNIFIED_MODEL_SIGNAL")),
    ...whalePaper.map((item) => normalizeSignal(item, "TELEGRAM_WHALE_ALERT")),
    ...overnightPaper.map((item) => normalizeSignal(item, "MLB_OVERNIGHT_PAPER")),
    ...officialPaper.map(normalizeOfficialPaperPick),
  ]);
}
export function summarizeRecords(records: AstroddsPerformanceRecord[]) {
  const overall = finalizeBucket(records.reduce((bucket, record) => {
    addToBucket(bucket, record);
    return bucket;
  }, emptyBucket()), records);
  const strongBuys = records.filter((record) => record.decision === "STRONG_BUY").length;
  const eliteSignals = records.filter((record) => record.decision === "ELITE" || record.signalType.includes("ELITE")).length;

  return {
    overall,
    overallRoi: overall.roi,
    signalsSent: records.length,
    strongBuys,
    eliteSignals,
    roiBySport: groupBy(records, (record) => record.sport),
    roiByWhaleGrade: groupBy(records, (record) => record.whaleGrade),
    roiBySignalType: groupBy(records, (record) => record.signalType),
    averageClv: overall.averageClv,
    clvBySport: groupBy(records.filter((record) => typeof recordClv(record) === "number"), (record) => record.sport),
    clvBySignalType: groupBy(records.filter((record) => typeof recordClv(record) === "number"), (record) => record.signalType),
    clvByWhaleGrade: groupBy(records.filter((record) => typeof recordClv(record) === "number"), (record) => record.whaleGrade),
  };
}

export async function buildBacktestReport() {
  const records = await loadPerformanceRecords();
  const categories = {
    strongBuy: records.filter((record) => record.decision === "STRONG_BUY"),
    elite: records.filter((record) => record.decision === "ELITE"),
    consensus: records.filter((record) => record.signalType.includes("CONSENSUS") || record.signalType.includes("WHALE_CONFIRMED")),
    whaleBonus: records.filter((record) => record.signalType.includes("WHALE_ONLY") || record.source === "TELEGRAM_WHALE_ALERT"),
  };

  return {
    generatedAt: new Date().toISOString(),
    realMoneyTrading: "OFF",
    backtests: Object.fromEntries(Object.entries(categories).map(([key, value]) => [key, summarizeRecords(value).overall])),
    note: "Backtest uses stored paper/signal records only. Pending and unknown records do not count as wins.",
  };
}

function noBetReasons(records: AstroddsPerformanceRecord[]) {
  const reasons = new Map<string, number>();
  for (const record of records) {
    if (record.status !== "PENDING") continue;
    if (!record.entry) reasons.set("No price", (reasons.get("No price") ?? 0) + 1);
    if (record.whaleGrade === "WATCHLIST") reasons.set("Whale grade watchlist", (reasons.get("Whale grade watchlist") ?? 0) + 1);
    if (!record.decision || record.decision === "WAIT" || record.decision === "WATCH") reasons.set("No edge or watch-only", (reasons.get("No edge or watch-only") ?? 0) + 1);
  }
  return Array.from(reasons.entries()).sort((a, b) => b[1] - a[1]).map(([reason, count]) => ({ reason, count }));
}

export async function buildDailyReport() {
  const records = await loadPerformanceRecords();
  const [officialPaper, modelLeans, paperTest] = await Promise.all([
    loadOfficialPaperPicks(),
    loadModelLeanRecords(),
    getPaperTestState(),
  ]);
  const paperLedger = summarizePaperLedger(officialPaper, modelLeans);
  const today = new Date().toISOString().slice(0, 10);
  const todaysRecords = records.filter((record) => record.createdAt.slice(0, 10) === today);
  const todayOfficialPaperPicks = officialPaper.filter((pick) => pick.createdAt.slice(0, 10) === today);
  const todayModelLeans = modelLeans.filter((lean) => lean.createdAt.slice(0, 10) === today);
  const summary = summarizeRecords(todaysRecords);
  const topByPnl = [...todaysRecords].sort((a, b) => b.pnl - a.pnl);
  const consensus = todaysRecords.filter((record) => record.signalType.includes("CONSENSUS") || record.signalType.includes("WHALE_CONFIRMED"));
  const whale = todaysRecords.filter((record) => record.source === "TELEGRAM_WHALE_ALERT" || record.signalType.includes("WHALE"));

  return {
    title: "ASTRODDS Daily Report",
    generatedAt: new Date().toISOString(),
    date: today,
    realMoneyTrading: "OFF",
    signalsSent: summary.signalsSent,
    eliteSignals: summary.eliteSignals,
    strongBuys: summary.strongBuys,
    winRate: summary.overall.settled ? summary.overall.wins / summary.overall.settled : 0,
    roi: summary.overall.roi,
    pnl: summary.overall.pnl,
    averageClv: summary.averageClv,
    topPerformer: topByPnl[0] ?? null,
    worstPerformer: topByPnl.at(-1) ?? null,
    topWhale: whale.sort((a, b) => b.pnl - a.pnl)[0] ?? null,
    topConsensus: consensus.sort((a, b) => b.pnl - a.pnl)[0] ?? null,
    noBetReasons: noBetReasons(todaysRecords),
    paperLedger,
    paperTest,
    todayOfficialPaperPicks,
    todayModelLeans,
    summary,
  };
}
export async function buildPerformanceReport() {
  const records = await loadPerformanceRecords();
  const [officialPaper, modelLeans, paperTest] = await Promise.all([
    loadOfficialPaperPicks(),
    loadModelLeanRecords(),
    getPaperTestState(),
  ]);
  const paperLedger = summarizePaperLedger(officialPaper, modelLeans);

  return {
    generatedAt: new Date().toISOString(),
    realMoneyTrading: "OFF",
    ...summarizeRecords(records),
    reports: {
      sevenDay: reportWindow(records, 7),
      thirtyDay: reportWindow(records, 30),
      ninetyDay: reportWindow(records, 90),
    },
    recordsTracked: records.length,
    paperLedger,
    paperTest,
  };
}
