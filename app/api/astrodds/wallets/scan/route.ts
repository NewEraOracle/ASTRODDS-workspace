import { NextResponse } from "next/server";

import { scanWhaleWallets } from "@/lib/astrodss/wallets/wallet-scanner";

export const dynamic = "force-dynamic";

type WalletScanRequest = {
  handles?: string[];
  addresses?: string[];
  sport?: string;
  category?: string;
};

function stringArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0) : undefined;
}

export async function POST(request: Request) {
  let body: WalletScanRequest = {};

  try {
    const parsed = (await request.json()) as unknown;
    if (parsed && typeof parsed === "object") {
      const record = parsed as Record<string, unknown>;
      body = {
        handles: stringArray(record.handles),
        addresses: stringArray(record.addresses),
        sport: typeof record.sport === "string" ? record.sport : undefined,
        category: typeof record.category === "string" ? record.category : undefined,
      };
    }
  } catch {
    body = {};
  }

  const payload = await scanWhaleWallets(body);

  return NextResponse.json(
    {
      sourcePolicy: "ASTRODDS uses public Polymarket wallet/profile data only. No private or non-public information is used.",
      ...payload,
    },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}
