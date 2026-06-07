import { NextResponse } from "next/server";

import { KNOWN_WHALE_WALLETS, nextWhaleRescanAt } from "@/lib/astrodss/wallets/known-wallets";

export const dynamic = "force-dynamic";

export async function GET() {
  const now = new Date().toISOString();

  return NextResponse.json(
    {
      sourcePolicy: "ASTRODDS uses public Polymarket wallet/profile data only. No private or non-public information is used.",
      scannedAt: now,
      wallets: KNOWN_WHALE_WALLETS.map((wallet) => ({
        ...wallet,
        address: undefined,
        sourceStatus: "NOT_CONNECTED",
        lastScanned: undefined,
        nextRescan: nextWhaleRescanAt(wallet.rank),
        metrics: undefined,
      })),
    },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}
