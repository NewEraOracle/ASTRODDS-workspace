import { NextResponse } from "next/server";

import { settlePaperWatchlistRows } from "@/lib/astrodss/mlb/paper-watchlist-ledger";

export const dynamic = "force-dynamic";

export async function POST() {
  const result = await settlePaperWatchlistRows();

  return NextResponse.json({
    ok: true,
    realMoneyTrading: "OFF",
    settledCount: result.settledCount,
    openCount: result.openCount,
    errorCount: result.errorCount,
    warnings: result.warnings,
    message: `Settled ${result.settledCount} rows, ${result.openCount} open, ${result.errorCount} error.`,
    paperWatchlistLedgerDiagnostics: result.status,
    recentRows: result.recentRows,
  });
}