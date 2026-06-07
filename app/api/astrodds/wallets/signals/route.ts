import { NextResponse } from "next/server";

import { getTelegramConfig } from "@/lib/astrodss/wallets/telegram";
import { scanWhaleWallets } from "@/lib/astrodss/wallets/wallet-scanner";
import { buildWhaleOnlySignals } from "@/lib/astrodss/wallets/whale-signals";
import type { CopyabilityStatus, WalletScanResult } from "@/lib/astrodss/wallets/types";

export const dynamic = "force-dynamic";

const copyabilityKeys: CopyabilityStatus[] = [
  "COPYABLE_NOW",
  "NEAR_WHALE_ENTRY",
  "WATCH_ONLY",
  "STALE_ENTRY",
  "TOO_LATE",
  "NO_LIQUIDITY",
  "CONFLICT",
  "UNKNOWN",
];


function emptyScan(scannedAt = new Date().toISOString()): WalletScanResult {
  return {
    profiles: [],
    strategyMetrics: [],
    activePositions: [],
    closedPositions: [],
    copyability: [],
    consensus: [],
    sourceStatus: "FAILED",
    errors: ["WHALE SOURCE WARNING: source unavailable, continuing with 0 whale bonus alerts."],
    diagnostics: [],
    scannedAt,
  };
}
function countByCopyability(signals: Awaited<ReturnType<typeof buildWhaleOnlySignals>>["signals"]) {
  return copyabilityKeys.reduce<Record<CopyabilityStatus, number>>((counts, status) => {
    counts[status] = signals.filter((signal) => signal.copyability === status).length;
    return counts;
  }, {} as Record<CopyabilityStatus, number>);
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const sport = searchParams.get("sport") ?? undefined;
  const category = searchParams.get("category") ?? "all";
  const telegram = getTelegramConfig();
  let scan: WalletScanResult;
  let sourceWarning: string | undefined;

  try {
    scan = await scanWhaleWallets({ sport, category });
  } catch (error) {
    sourceWarning = `WHALE SOURCE WARNING: ${error instanceof Error ? error.message : "unknown whale source failure"}. Continuing with 0 whale bonus alerts.`;
    scan = emptyScan();
  }

  let whaleSignals: Awaited<ReturnType<typeof buildWhaleOnlySignals>>;
  try {
    whaleSignals = await buildWhaleOnlySignals(scan.activePositions, {
      category,
      telegramConfigured: Boolean(telegram.botToken && telegram.signalsChatId),
      telegramAlertsEnabled: telegram.signalsEnabled && telegram.whaleAlertsEnabled,
    });
  } catch (error) {
    sourceWarning = sourceWarning ?? `WHALE SOURCE WARNING: signal build failed: ${error instanceof Error ? error.message : "unknown signal build failure"}. Continuing with 0 whale bonus alerts.`;
    whaleSignals = { signals: [], errors: [sourceWarning] };
  }
  const signals = whaleSignals.signals;

  return NextResponse.json(
    {
      sourcePolicy: "ASTRODDS uses public Polymarket wallet/profile data only. No private or non-public information is used.",
      sport: sport ?? "ALL",
      category,
      signals,
      consensus: scan.consensus,
      sourceStatus: scan.sourceStatus,
      errors: [sourceWarning, ...scan.errors, ...whaleSignals.errors].filter((error): error is string => Boolean(error)),
      scannedAt: scan.scannedAt,
      diagnostics: scan.diagnostics,

      counts: {
        totalSignals: signals.length,
        activePositions: scan.activePositions.length,
        closedPositions: scan.closedPositions.length,
        ...countByCopyability(signals),
      },
      telegram: {
        configured: telegram.configured,
        signalsEnabled: telegram.signalsEnabled,
        whaleAlertsEnabled: telegram.whaleAlertsEnabled,
        status: telegram.status,
      },
    },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}
