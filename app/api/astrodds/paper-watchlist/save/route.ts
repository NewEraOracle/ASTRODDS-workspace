import { NextResponse } from "next/server";

import type { MlbPaperWatchlistRow } from "@/lib/astrodss/mlb/paper-watchlist";
import { loadPaperWatchlistLedgerStatus, savePaperWatchlistRows } from "@/lib/astrodss/mlb/paper-watchlist-ledger";

export const dynamic = "force-dynamic";

type SavePaperWatchlistRequest = {
  rows?: MlbPaperWatchlistRow[];
};

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as SavePaperWatchlistRequest;
  const rows = Array.isArray(body.rows) ? body.rows : [];
  const result = await savePaperWatchlistRows(rows);
  const status = await loadPaperWatchlistLedgerStatus();

  return NextResponse.json({
    ok: true,
    realMoneyTrading: "OFF",
    savedCount: result.savedCount,
    updatedCount: result.updatedCount,
    skippedCount: result.skippedCount,
    warnings: result.warnings,
    message: rows.length
      ? `Saved ${result.savedCount} rows, updated ${result.updatedCount}, skipped ${result.skippedCount}.`
      : "No paper watchlist rows were supplied.",
    paperWatchlistLedgerDiagnostics: status,
    recentRows: status.recentRows,
  });
}