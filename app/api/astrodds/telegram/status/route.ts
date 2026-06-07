import { NextResponse } from "next/server";

import { publicTelegramStatus } from "@/lib/astrodss/wallets/telegram";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(publicTelegramStatus(), {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
