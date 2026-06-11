import { NextResponse } from "next/server";

import { loadPaperWatchlistLedgerStatus } from "@/lib/astrodss/mlb/paper-watchlist-ledger";

export const dynamic = "force-dynamic";

export async function GET() {
  const status = await loadPaperWatchlistLedgerStatus();

  return NextResponse.json({
    ok: true,
    realMoneyTrading: "OFF",
    paperWatchlistLedgerDiagnostics: status,
    recentRows: status.recentRows,
    warnings: status.warnings,
    ledgerPath: status.ledgerPath,
  });
}