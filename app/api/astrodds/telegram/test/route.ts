import { NextResponse } from "next/server";

import { sendTelegramTestMessage } from "@/lib/astrodss/wallets/telegram";

export const dynamic = "force-dynamic";

export async function POST() {
  const result = await sendTelegramTestMessage();

  return NextResponse.json(result, {
    status: result.status === "SENT" ? 200 : 400,
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
