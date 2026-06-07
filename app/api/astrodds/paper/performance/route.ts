import { NextResponse } from "next/server";

import { buildPaperLedgerReport } from "@/lib/astrodss/paper/paper-ledger";

export const dynamic = "force-dynamic";

export async function GET() {
  const report = await buildPaperLedgerReport();

  return NextResponse.json({
    ...report.summary,
    generatedAt: report.generatedAt,
    realMoneyTrading: "OFF",
    paperTest: report.paperTest,
    ledgerPath: report.ledgerPath,
    modelLeanLedgerPath: report.modelLeanLedgerPath,
    officialPaperPicks: report.officialPaperPicks,
    modelLeanRecords: report.modelLeans,
    serverPersistence: true,
    note: "Official paper picks require real odds or a real market entry price. Model leans are tracked separately and are not executable bets.",
  });
}