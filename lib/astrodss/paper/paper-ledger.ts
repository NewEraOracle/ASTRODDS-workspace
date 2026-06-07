import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

export type OfficialPaperPickStatus = "open" | "won" | "lost" | "push" | "void";
export type OfficialPaperDecisionLabel = "BUY" | "STRONG BUY" | "ELITE";

export type OfficialPaperPick = {
  id: string;
  createdAt: string;
  status: OfficialPaperPickStatus;
  category: "sports" | "polymarket";
  sport?: string;
  league?: string;
  gameId?: string;
  game: string;
  marketType: string;
  marketLabel: string;
  pickSide: string;
  entryPriceAmerican?: number;
  entryPriceDecimal?: number;
  entryPricePolymarket?: number;
  impliedProbability?: number;
  paperStakePercent: number;
  paperStakeUnits: number;
  modelScore: number;
  confidence: number;
  dataQuality: string;
  decisionLabel: OfficialPaperDecisionLabel;
  whaleSupportLevel?: "NONE" | "LOW" | "MEDIUM" | "HIGH";
  whaleConflict?: boolean;
  reason: string;
  source: string;
  result?: {
    settledAt?: string;
    finalScore?: string;
    closingPrice?: number;
    clv?: number;
    pnlUnits?: number;
  };
};

export type ModelLeanRecord = {
  id: string;
  createdAt: string;
  status: "open" | "correct" | "incorrect" | "push" | "void";
  sport: string;
  league?: string;
  gameId?: string;
  game: string;
  leanSide: string;
  confidence: number;
  modelScore: number;
  dataQuality: string;
  reason: string;
  missingDataWarnings: string[];
  source: string;
  lastSeenAt?: string;
  scanCount?: number;
  result?: {
    settledAt?: string;
    finalScore?: string;
  };
};

export type SevenDayPaperTestState = {
  started: boolean;
  startedAt?: string;
  day: number;
  daysElapsed: number;
  endsAt?: string;
  realMoneyTrading: "OFF";
};

export type LedgerSummary = {
  totalOfficialPaperPicks: number;
  openPicks: number;
  settledPicks: number;
  wins: number;
  losses: number;
  pushes: number;
  voids: number;
  winRate: number;
  roi: number;
  totalStakedUnits: number;
  pnlUnits: number;
  averageConfidence: number;
  averageModelScore: number;
  averageClv: number | null;
  modelLeans: {
    total: number;
    open: number;
    settled: number;
    correct: number;
    incorrect: number;
    accuracy: number;
  };
};

type CreateOfficialPickInput = Omit<OfficialPaperPick, "id" | "createdAt" | "status"> & {
  id?: string;
  createdAt?: string;
  status?: OfficialPaperPickStatus;
};

type CreateModelLeanInput = Omit<ModelLeanRecord, "id" | "createdAt" | "status"> & {
  id?: string;
  createdAt?: string;
  status?: ModelLeanRecord["status"];
};

const astroddsDir = path.join(process.cwd(), ".astrodds");
const paperLedgerPath = path.join(astroddsDir, "paper-ledger.json");
const modelLeanLedgerPath = path.join(astroddsDir, "model-lean-ledger.json");
const paperTestStatePath = path.join(astroddsDir, "paper-test-state.json");

async function readJson<T>(filePath: string, fallback: T): Promise<T> {
  try {
    return JSON.parse(await readFile(filePath, "utf8")) as T;
  } catch {
    return fallback;
  }
}

async function writeJson<T>(filePath: string, value: T) {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, JSON.stringify(value, null, 2), "utf8");
}

function slug(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80) || "paper-pick";
}

function uniqueOfficialPicks(picks: OfficialPaperPick[]) {
  const seen = new Map<string, OfficialPaperPick>();
  for (const pick of picks) {
    const key = pick.id || `${pick.category}|${pick.game}|${pick.marketType}|${pick.pickSide}|${pick.createdAt.slice(0, 10)}`;
    seen.set(key, pick);
  }
  return Array.from(seen.values());
}

function uniqueModelLeanRecords(records: ModelLeanRecord[]) {
  const seen = new Map<string, ModelLeanRecord>();
  for (const record of records) {
    const key = record.id || `${record.sport}|${record.gameId ?? record.game}|${record.leanSide}|${record.createdAt.slice(0, 10)}`;
    const existing = seen.get(key);
    if (existing) {
      seen.set(key, {
        ...existing,
        ...record,
        createdAt: existing.createdAt,
        scanCount: Math.max(existing.scanCount ?? 1, record.scanCount ?? 1),
        lastSeenAt: record.lastSeenAt ?? existing.lastSeenAt ?? record.createdAt,
      });
    } else {
      seen.set(key, record);
    }
  }
  return Array.from(seen.values());
}
export async function loadOfficialPaperPicks() {
  return readJson<OfficialPaperPick[]>(paperLedgerPath, []);
}

export async function saveOfficialPaperPicks(picks: OfficialPaperPick[]) {
  await writeJson(paperLedgerPath, uniqueOfficialPicks(picks).slice(-2500));
}

export async function addOfficialPaperPick(input: CreateOfficialPickInput) {
  const createdAt = input.createdAt ?? new Date().toISOString();
  const pick: OfficialPaperPick = {
    ...input,
    id: input.id ?? `official-${slug(`${input.game}-${input.marketType}-${input.pickSide}`)}-${createdAt.slice(0, 10)}`,
    createdAt,
    status: input.status ?? "open",
  };
  const existing = await loadOfficialPaperPicks();
  await saveOfficialPaperPicks([...existing, pick]);
  return pick;
}

export async function loadModelLeanRecords() {
  return readJson<ModelLeanRecord[]>(modelLeanLedgerPath, []);
}

export async function saveModelLeanRecords(records: ModelLeanRecord[]) {
  await writeJson(modelLeanLedgerPath, uniqueModelLeanRecords(records).slice(-5000));
}

export async function addModelLeanRecord(input: CreateModelLeanInput) {
  const seenAt = new Date().toISOString();
  const createdAt = input.createdAt ?? seenAt;
  const stableId = input.id ?? `modelLean:${slug(input.gameId ?? input.game)}:${slug(input.leanSide)}:${createdAt.slice(0, 10)}`;
  const existing = await loadModelLeanRecords();
  const existingRecord = existing.find((record) => record.id === stableId);
  const record: ModelLeanRecord = {
    ...existingRecord,
    ...input,
    id: stableId,
    createdAt: existingRecord?.createdAt ?? createdAt,
    status: input.status ?? existingRecord?.status ?? "open",
    scanCount: (existingRecord?.scanCount ?? 0) + 1,
    lastSeenAt: seenAt,
  };
  await saveModelLeanRecords([...existing.filter((item) => item.id !== stableId), record]);
  return record;
}

export async function getPaperTestState(): Promise<SevenDayPaperTestState> {
  const state = await readJson<SevenDayPaperTestState>(paperTestStatePath, { started: false, day: 0, daysElapsed: 0, realMoneyTrading: "OFF" });
  if (!state.startedAt) return state;
  const startedMs = new Date(state.startedAt).getTime();
  const daysElapsed = Number.isFinite(startedMs) ? Math.min(7, Math.max(0, Math.floor((Date.now() - startedMs) / 86_400_000))) : 0;
  return {
    ...state,
    daysElapsed,
    day: state.started ? Math.min(7, daysElapsed + 1) : 0,
  };
}

export async function startPaperTest() {
  const startedAt = new Date().toISOString();
  const ends = new Date(startedAt);
  ends.setDate(ends.getDate() + 7);
  const state: SevenDayPaperTestState = {
    started: true,
    startedAt,
    day: 1,
    daysElapsed: 0,
    endsAt: ends.toISOString(),
    realMoneyTrading: "OFF",
  };
  await writeJson(paperTestStatePath, state);
  return state;
}

function statusBuckets(picks: OfficialPaperPick[]) {
  return {
    openPicks: picks.filter((pick) => pick.status === "open").length,
    wins: picks.filter((pick) => pick.status === "won").length,
    losses: picks.filter((pick) => pick.status === "lost").length,
    pushes: picks.filter((pick) => pick.status === "push").length,
    voids: picks.filter((pick) => pick.status === "void").length,
  };
}

export function summarizePaperLedger(picks: OfficialPaperPick[], modelLeans: ModelLeanRecord[] = []): LedgerSummary {
  const buckets = statusBuckets(picks);
  const settledPicks = buckets.wins + buckets.losses + buckets.pushes + buckets.voids;
  const totalStakedUnits = picks.reduce((total, pick) => total + pick.paperStakeUnits, 0);
  const pnlUnits = picks.reduce((total, pick) => total + (pick.result?.pnlUnits ?? 0), 0);
  const clvValues = picks.map((pick) => pick.result?.clv).filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const settledLeans = modelLeans.filter((lean) => lean.status === "correct" || lean.status === "incorrect" || lean.status === "push" || lean.status === "void");
  const correctLeans = modelLeans.filter((lean) => lean.status === "correct").length;
  const incorrectLeans = modelLeans.filter((lean) => lean.status === "incorrect").length;

  return {
    totalOfficialPaperPicks: picks.length,
    openPicks: buckets.openPicks,
    settledPicks,
    wins: buckets.wins,
    losses: buckets.losses,
    pushes: buckets.pushes,
    voids: buckets.voids,
    winRate: buckets.wins + buckets.losses ? buckets.wins / (buckets.wins + buckets.losses) : 0,
    roi: totalStakedUnits ? pnlUnits / totalStakedUnits : 0,
    totalStakedUnits,
    pnlUnits,
    averageConfidence: picks.length ? picks.reduce((total, pick) => total + pick.confidence, 0) / picks.length : 0,
    averageModelScore: picks.length ? picks.reduce((total, pick) => total + pick.modelScore, 0) / picks.length : 0,
    averageClv: clvValues.length ? clvValues.reduce((total, value) => total + value, 0) / clvValues.length : null,
    modelLeans: {
      total: modelLeans.length,
      open: modelLeans.filter((lean) => lean.status === "open").length,
      settled: settledLeans.length,
      correct: correctLeans,
      incorrect: incorrectLeans,
      accuracy: correctLeans + incorrectLeans ? correctLeans / (correctLeans + incorrectLeans) : 0,
    },
  };
}

export async function buildPaperLedgerReport() {
  const [picks, modelLeans, testState] = await Promise.all([
    loadOfficialPaperPicks(),
    loadModelLeanRecords(),
    getPaperTestState(),
  ]);

  return {
    generatedAt: new Date().toISOString(),
    realMoneyTrading: "OFF",
    ledgerPath: ".astrodds/paper-ledger.json",
    modelLeanLedgerPath: ".astrodds/model-lean-ledger.json",
    paperTest: testState,
    summary: summarizePaperLedger(picks, modelLeans),
    officialPaperPicks: picks,
    modelLeans,
  };
}