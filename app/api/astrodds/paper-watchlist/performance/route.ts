import { NextResponse } from "next/server";

import { loadPaperWatchlistPerformanceAnalysis } from "@/lib/astrodss/mlb/paper-performance-analysis";

export const dynamic = "force-dynamic";

export async function GET() {
  const analysis = await loadPaperWatchlistPerformanceAnalysis();

  return NextResponse.json({
    status: analysis.status,
    summary: analysis.summary,
    byWatchlistTier: analysis.byWatchlistTier,
    byEdgeBucket: analysis.byEdgeBucket,
    byMatchConfidence: analysis.byMatchConfidence,
    byCalibrationMappingStatus: analysis.byCalibrationMappingStatus,
    recentSettledRows: analysis.recentSettledRows,
    warnings: analysis.warnings,
    generatedAt: analysis.generatedAt,
    ledgerPath: analysis.ledgerPath,
    realMoneyTrading: "OFF",
  });
}
