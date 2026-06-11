import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { findMlbTeamProfile } from "../sports-data/mlb-teams";
import { normalizeText, safeNumber } from "../sports-data/normalize";
import type { MlbPaperWatchlistRow } from "./paper-watchlist";

export const PAPER_WATCHLIST_LEDGER_PATH = path.join(/* turbopackIgnore: true */ process.cwd(), ".astrodds", "paper-watchlist-ledger.json");
const MLB_PROCESSED_DIR = path.join(/* turbopackIgnore: true */ process.cwd(), "mlb-engine", "data", "processed");

export type PaperWatchlistLedgerStatus = "open" | "settled" | "void" | "error";
export type PaperWatchlistLedgerResult = "win" | "loss" | "push" | "unknown";

export type PaperWatchlistLedgerRow = MlbPaperWatchlistRow & {
  ledgerId: string;
  createdAt: string;
  updatedAt: string;
  status: PaperWatchlistLedgerStatus;
  result: PaperWatchlistLedgerResult;
  finalHomeScore: number | null;
  finalAwayScore: number | null;
  winner: string;
  settledAt?: string;
  settlementSource?: string;
  paperStakeUnits: number;
  paperPnLUnits: number | null;
  notes: string[];
};

export type PaperWatchlistLedgerDiagnostics = {
  ledgerAvailable: boolean;
  totalRows: number;
  openRows: number;
  settledRows: number;
  wins: number;
  losses: number;
  pushes: number;
  unknown: number;
  paperPnLUnits: number | null;
  warnings: string[];
  generatedAt: string;
  ledgerPath: string;
};

export type PaperWatchlistLedgerStatusResult = PaperWatchlistLedgerDiagnostics & {
  recentRows: PaperWatchlistLedgerRow[];
};

export type PaperWatchlistSaveResult = {
  ok: boolean;
  savedCount: number;
  updatedCount: number;
  skippedCount: number;
  warnings: string[];
  status: PaperWatchlistLedgerDiagnostics;
  recentRows: PaperWatchlistLedgerRow[];
};

export type PaperWatchlistSettleResult = {
  ok: boolean;
  settledCount: number;
  openCount: number;
  errorCount: number;
  warnings: string[];
  status: PaperWatchlistLedgerDiagnostics;
  recentRows: PaperWatchlistLedgerRow[];
};

type CsvGameRow = Record<string, string>;

type MlbProcessedGameRow = {
  gameId: string;
  gameDate?: string;
  season?: string;
  gameType?: string;
  status?: string;
  homeTeam?: string;
  awayTeam?: string;
  homeScore?: number;
  awayScore?: number;
  winner?: string;
  homeWin?: boolean;
  awayWin?: boolean;
  venue?: string;
  doubleheader?: string;
  gameNumber?: string;
};

function uniqueStrings(values: Array<string | undefined>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value && value.trim()))));
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function ledgerKey(row: Pick<PaperWatchlistLedgerRow, "gameId" | "selectedSide" | "researchSide" | "marketType" | "date">) {
  return [row.gameId, row.selectedSide ?? row.researchSide ?? "", row.marketType, row.date ?? ""].map((value) => normalizeText(String(value))).join("|");
}

function safeSlug(value: string) {
  return normalizeText(value).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80) || "paper-watchlist";
}

async function writeJson<T>(filePath: string, value: T) {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, JSON.stringify(value, null, 2), "utf8");
}

function csvLines(text: string) {
  return text.replace(/\r/g, "").split("\n").filter((line, index, lines) => index === 0 || line.trim().length > 0 || index === lines.length - 1);
}

function parseCsvLine(line: string) {
  const cells: string[] = [];
  let current = "";
  let quoted = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === '"') {
      if (quoted && line[index + 1] === '"') {
        current += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
      continue;
    }

    if (char === "," && !quoted) {
      cells.push(current);
      current = "";
      continue;
    }

    current += char;
  }

  cells.push(current);
  return cells;
}

function parseCsv(text: string): CsvGameRow[] {
  const lines = csvLines(text);
  if (!lines.length) return [];
  const headers = parseCsvLine(lines[0]).map((header) => header.trim());

  return lines.slice(1).map((line) => {
    const cells = parseCsvLine(line);
    return headers.reduce<CsvGameRow>((row, header, index) => {
      row[header] = (cells[index] ?? "").trim();
      return row;
    }, {});
  });
}

function parseBoolean(value: string | undefined) {
  if (!value) return undefined;
  const normalized = normalizeText(value);
  if (["true", "1", "yes", "y"].includes(normalized)) return true;
  if (["false", "0", "no", "n"].includes(normalized)) return false;
  return undefined;
}

function normalizeGameResult(row: CsvGameRow): MlbProcessedGameRow | undefined {
  const gameId = row.game_id ?? row.gameId ?? row.game_pk ?? row.gamePk;
  if (!gameId) return undefined;

  return {
    gameId: String(gameId),
    gameDate: row.game_date ?? row.gameDate,
    season: row.season,
    gameType: row.game_type ?? row.gameType,
    status: row.status,
    homeTeam: row.home_team ?? row.homeTeam,
    awayTeam: row.away_team ?? row.awayTeam,
    homeScore: safeNumber(row.home_score ?? row.homeScore),
    awayScore: safeNumber(row.away_score ?? row.awayScore),
    winner: row.winner,
    homeWin: parseBoolean(row.home_win ?? row.homeWin),
    awayWin: parseBoolean(row.away_win ?? row.awayWin),
    venue: row.venue,
    doubleheader: row.doubleheader,
    gameNumber: row.game_number ?? row.gameNumber,
  };
}

function isFinalGame(game: MlbProcessedGameRow) {
  const status = normalizeText(game.status ?? "");
  return Boolean(game.homeTeam && game.awayTeam && isFiniteNumber(game.homeScore) && isFiniteNumber(game.awayScore) && (status.includes("final") || game.winner));
}

function sameTeam(a?: string, b?: string) {
  const left = findMlbTeamProfile(a);
  const right = findMlbTeamProfile(b);
  if (left && right) return left.canonicalName === right.canonicalName;
  const normalizedLeft = normalizeText(a);
  const normalizedRight = normalizeText(b);
  return Boolean(normalizedLeft && normalizedRight && (normalizedLeft === normalizedRight || normalizedLeft.includes(normalizedRight) || normalizedRight.includes(normalizedLeft)));
}

function ledgerSummary(rows: PaperWatchlistLedgerRow[], ledgerAvailable: boolean, warnings: string[] = []): PaperWatchlistLedgerDiagnostics {
  const wins = rows.filter((row) => row.status === "settled" && row.result === "win").length;
  const losses = rows.filter((row) => row.status === "settled" && row.result === "loss").length;
  const pushes = rows.filter((row) => row.status === "void" || (row.status === "settled" && row.result === "push")).length;
  const unknown = rows.filter((row) => row.status === "error" || row.result === "unknown").length;
  const settledRows = rows.filter((row) => row.status !== "open").length;
  const pnls = rows.map((row) => row.paperPnLUnits).filter((value): value is number => isFiniteNumber(value));
  const hasMissingPnl = rows.some((row) => row.status !== "open" && row.paperPnLUnits === null);

  return {
    ledgerAvailable,
    totalRows: rows.length,
    openRows: rows.filter((row) => row.status === "open").length,
    settledRows,
    wins,
    losses,
    pushes,
    unknown,
    paperPnLUnits: hasMissingPnl ? null : pnls.reduce((total, value) => total + value, 0),
    warnings: uniqueStrings(warnings),
    generatedAt: new Date().toISOString(),
    ledgerPath: ".astrodds/paper-watchlist-ledger.json",
  };
}

async function loadLedgerRows(): Promise<{ rows: PaperWatchlistLedgerRow[]; available: boolean; warnings: string[] }> {
  try {
    const raw = await readFile(PAPER_WATCHLIST_LEDGER_PATH, "utf8");
    const parsed = JSON.parse(raw.replace(/^\uFEFF/, "")) as unknown;
    if (!Array.isArray(parsed)) {
      return { rows: [], available: false, warnings: ["Paper watchlist ledger skipped: invalid JSON shape."] };
    }

    const rows = parsed
      .filter((value): value is Record<string, unknown> => typeof value === "object" && value !== null)
      .map((value) => value as PaperWatchlistLedgerRow)
      .filter((row) => Boolean(row.ledgerId && row.createdAt && row.updatedAt));

    return { rows, available: true, warnings: [] };
  } catch {
    return { rows: [], available: false, warnings: [] };
  }
}

async function writeLedgerRows(rows: PaperWatchlistLedgerRow[]) {
  await writeJson(PAPER_WATCHLIST_LEDGER_PATH, rows.slice(-2500));
}

function mergeNotes(...sources: Array<string[] | undefined>) {
  return uniqueStrings(sources.flatMap((source) => source ?? []));
}

function fromPaperWatchlistRow(row: MlbPaperWatchlistRow, now: string, existing?: PaperWatchlistLedgerRow): PaperWatchlistLedgerRow {
  const baseNotes = mergeNotes(
    existing?.notes,
    row.blockReasons,
    row.reasons,
    row.risks,
    row.matchWarnings,
    row.watchlistDecision === "monitor" ? ["Monitor tier research row."] : undefined,
    row.watchlistDecision === "paper_watchlist" ? ["Paper watchlist research row."] : undefined,
    row.watchlistDecision === "priority_paper_watchlist" ? ["Priority paper watchlist research row."] : undefined,
    ["Research only - not official."],
  );

  if (existing) {
    return {
      ...existing,
      ...row,
      ledgerId: existing.ledgerId,
      createdAt: existing.createdAt,
      updatedAt: now,
      status: existing.status,
      result: existing.result,
      finalHomeScore: existing.finalHomeScore,
      finalAwayScore: existing.finalAwayScore,
      winner: existing.winner,
      settledAt: existing.settledAt,
      settlementSource: existing.settlementSource,
      paperStakeUnits: existing.paperStakeUnits,
      paperPnLUnits: existing.paperPnLUnits,
      notes: baseNotes,
    };
  }

  return {
    ...row,
    ledgerId: `paper-watchlist-${safeSlug(`${row.gameId ?? "game"}-${row.selectedSide ?? row.researchSide ?? "side"}-${row.marketType}-${row.date ?? now.slice(0, 10)}`)}-${now.slice(0, 10)}`,
    createdAt: now,
    updatedAt: now,
    status: "open",
    result: "unknown",
    finalHomeScore: null,
    finalAwayScore: null,
    winner: "",
    settledAt: undefined,
    settlementSource: undefined,
    paperStakeUnits: 1,
    paperPnLUnits: null,
    notes: baseNotes,
  };
}

function rowKey(row: Pick<PaperWatchlistLedgerRow, "gameId" | "selectedSide" | "researchSide" | "marketType" | "date">) {
  return ledgerKey(row);
}

function canSaveRow(row: MlbPaperWatchlistRow) {
  const side = row.selectedSide ?? row.researchSide;
  return Boolean(
    row.gameId &&
    side &&
    row.marketType === "moneyline" &&
    row.isPaperOnly === true &&
    row.officialPickEligible === false &&
    row.officialEdgeAllowed === false,
  );
}

function settlePaperWatchlistRow(row: PaperWatchlistLedgerRow, result?: MlbProcessedGameRow): PaperWatchlistLedgerRow {
  const now = new Date().toISOString();
  if (!result) {
    return {
      ...row,
      updatedAt: now,
      notes: mergeNotes(row.notes, ["No matching final MLB result found yet."] ),
    };
  }

  if (!isFinalGame(result)) {
    return {
      ...row,
      updatedAt: now,
      notes: mergeNotes(row.notes, [`Game ${result.gameId} is not final yet.`]),
    };
  }

  const homeScore = isFiniteNumber(result.homeScore) ? result.homeScore : null;
  const awayScore = isFiniteNumber(result.awayScore) ? result.awayScore : null;
  const winner = homeScore !== null && awayScore !== null
    ? homeScore > awayScore
      ? result.homeTeam ?? ""
      : awayScore > homeScore
        ? result.awayTeam ?? ""
        : result.winner ?? ""
    : result.winner ?? "";

  const side = normalizeText(row.selectedSide ?? row.researchSide);
  const homeMatches = sameTeam(row.selectedSide ?? row.researchSide, result.homeTeam);
  const awayMatches = sameTeam(row.selectedSide ?? row.researchSide, result.awayTeam);

  if (!side || (!homeMatches && !awayMatches)) {
    return {
      ...row,
      status: "error",
      result: "unknown",
      finalHomeScore: homeScore,
      finalAwayScore: awayScore,
      winner,
      updatedAt: now,
      settledAt: now,
      settlementSource: "mlb_processed_games",
      paperPnLUnits: null,
      notes: mergeNotes(row.notes, ["Moneyline pick could not be mapped to either MLB team."] ),
    };
  }

  const selectedMatchesWinner = sameTeam(side, winner);
  const resultStatus: PaperWatchlistLedgerResult = selectedMatchesWinner ? "win" : "loss";
  const paperPnLUnits = resultStatus === "win"
    ? (isFiniteNumber(row.marketProbability) && row.marketProbability > 0 ? (1 / row.marketProbability) - 1 : null)
    : resultStatus === "loss"
      ? -1
      : 0;
  const notes = mergeNotes(
    row.notes,
    [
      selectedMatchesWinner
        ? `Selected side won the final MLB game ${result.homeTeam ?? "Home"} vs ${result.awayTeam ?? "Away"}.`
        : `Selected side lost the final MLB game ${result.homeTeam ?? "Home"} vs ${result.awayTeam ?? "Away"}.`,
    ],
    paperPnLUnits === null ? ["Cannot calculate paper PnL without market probability."] : undefined,
  );

  return {
    ...row,
    status: resultStatus === "win" || resultStatus === "loss" ? "settled" : "void",
    result: resultStatus,
    finalHomeScore: homeScore,
    finalAwayScore: awayScore,
    winner,
    updatedAt: now,
    settledAt: now,
    settlementSource: "mlb_processed_games",
    paperPnLUnits,
    notes,
  };
}

async function loadProcessedGameResults(): Promise<{ games: MlbProcessedGameRow[]; warnings: string[] }> {
  const warnings: string[] = [];
  try {
    const entries = await readdir(MLB_PROCESSED_DIR);
    const files = entries
      .filter((file) => /^mlb_games_\d{4}\.csv$/i.test(file))
      .sort((left, right) => Number(right.match(/\d{4}/)?.[0] ?? 0) - Number(left.match(/\d{4}/)?.[0] ?? 0));

    if (!files.length) {
      return { games: [], warnings: ["No processed MLB games CSV files were found."] };
    }

    const byGameId = new Map<string, MlbProcessedGameRow>();
    for (const file of files) {
      const csvText = await readFile(path.join(MLB_PROCESSED_DIR, file), "utf8");
      for (const row of parseCsv(csvText)) {
        const game = normalizeGameResult(row);
        if (!game || !isFinalGame(game)) continue;
        byGameId.set(game.gameId, game);
      }
    }

    return { games: Array.from(byGameId.values()), warnings };
  } catch (error) {
    warnings.push(error instanceof Error ? error.message : "Unknown MLB processed games read failure.");
    return { games: [], warnings };
  }
}

function matchGameResult(row: PaperWatchlistLedgerRow, games: MlbProcessedGameRow[]) {
  const rowGamePk = safeNumber(row.gameId);
  if (isFiniteNumber(rowGamePk)) {
    const exact = games.find((game) => safeNumber(game.gameId) === rowGamePk);
    if (exact) return exact;
  }

  const rowDate = row.date ? row.date.slice(0, 10) : undefined;
  return games.find((game) => {
    if (rowDate && game.gameDate?.slice(0, 10) !== rowDate) return false;
    return sameTeam(row.homeTeam, game.homeTeam) && sameTeam(row.awayTeam, game.awayTeam);
  });
}

export async function loadPaperWatchlistLedgerStatus(limit = 10): Promise<PaperWatchlistLedgerStatusResult> {
  const { rows, available, warnings } = await loadLedgerRows();
  const summary = ledgerSummary(rows, available, warnings);
  return {
    ...summary,
    recentRows: [...rows].sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()).slice(0, limit),
  };
}

export async function savePaperWatchlistRows(rows: MlbPaperWatchlistRow[]) {
  const now = new Date().toISOString();
  const { rows: existingRows, warnings } = await loadLedgerRows();
  const ledgerMap = new Map(existingRows.map((row) => [rowKey(row), row]));
  let savedCount = 0;
  let updatedCount = 0;
  let skippedCount = 0;

  for (const row of rows) {
    if (!canSaveRow(row)) {
      skippedCount += 1;
      continue;
    }

    const key = rowKey(row);
    const existing = ledgerMap.get(key);
    const nextRow = fromPaperWatchlistRow(row, now, existing);
    ledgerMap.set(key, nextRow);
    if (existing) updatedCount += 1;
    else savedCount += 1;
  }

  const nextRows = Array.from(ledgerMap.values()).sort((left, right) => new Date(left.updatedAt).getTime() - new Date(right.updatedAt).getTime());
  await writeLedgerRows(nextRows);
  const status = ledgerSummary(nextRows, true, warnings);

  return {
    ok: true,
    savedCount,
    updatedCount,
    skippedCount,
    warnings: uniqueStrings([
      ...warnings,
      !rows.length ? "No paper watchlist rows were supplied to save." : undefined,
      !savedCount && !updatedCount ? "No research-only paper watchlist rows were eligible to save." : undefined,
    ]),
    status,
    recentRows: nextRows.slice(-10).reverse(),
  } satisfies PaperWatchlistSaveResult;
}

export async function settlePaperWatchlistRows() {
  const { rows: existingRows, available, warnings } = await loadLedgerRows();
  const openRows = existingRows.filter((row) => row.status === "open");
  if (!openRows.length) {
    const status = ledgerSummary(existingRows, available, warnings);
    return {
      ok: true,
      settledCount: 0,
      openCount: 0,
      errorCount: 0,
      warnings: uniqueStrings([...warnings, "No open paper watchlist rows to settle."]),
      status,
      recentRows: existingRows.slice(-10).reverse(),
    } satisfies PaperWatchlistSettleResult;
  }

  const { games, warnings: resultWarnings } = await loadProcessedGameResults();
  const gameMap = new Map(games.map((game) => [game.gameId, game]));
  const nextRows = existingRows.map((row) => {
    if (row.status !== "open") return row;
    const matched = matchGameResult(row, games) ?? (isFiniteNumber(safeNumber(row.gameId)) ? gameMap.get(String(safeNumber(row.gameId))) : undefined);
    return settlePaperWatchlistRow(row, matched);
  });

  await writeLedgerRows(nextRows);
  const status = ledgerSummary(nextRows, true, uniqueStrings([...warnings, ...resultWarnings]));

  return {
    ok: true,
    settledCount: nextRows.filter((row) => row.status === "settled" || row.status === "void").length - existingRows.filter((row) => row.status === "settled" || row.status === "void").length,
    openCount: nextRows.filter((row) => row.status === "open").length,
    errorCount: nextRows.filter((row) => row.status === "error").length,
    warnings: uniqueStrings([
      ...warnings,
      ...resultWarnings,
      !games.length ? "No final MLB results were available for settlement." : undefined,
    ]),
    status,
    recentRows: nextRows.slice(-10).reverse(),
  } satisfies PaperWatchlistSettleResult;
}
