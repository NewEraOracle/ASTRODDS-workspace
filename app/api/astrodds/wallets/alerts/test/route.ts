import { NextResponse } from "next/server";

import { getTelegramConfig, sampleWhaleSignal, sendTelegramMessage } from "@/lib/astrodss/wallets/telegram";

export const dynamic = "force-dynamic";

function sampleAlertText() {
  return [
    "ASTRODDS WHALE ALERT",
    "",
    "Whale: kch123",
    "Category: Sports",
    "Market: Kansas City Royals vs Cincinnati Reds",
    "Side: Cincinnati Reds",
    "Whale Entry: 0.414",
    "Current Price: 0.421",
    "Copyability: COPYABLE_NOW",
    "Order Book: UNKNOWN",
    "Signal Type: WHALE_ONLY_PUBLIC_SIGNAL",
    "",
    "Why:",
    "Elite wallet entered near current price. Entry is still close to whale average and not stale.",
    "",
    "Mode: PAPER ONLY",
    "Real money trading: OFF",
  ].join("\n");
}

export async function POST() {
  const config = getTelegramConfig();

  if (!config.botToken) {
    return NextResponse.json({ status: "NOT_CONFIGURED", reason: "TELEGRAM_BOT_TOKEN is missing." }, { status: 400 });
  }
  if (!config.signalsChatId) {
    return NextResponse.json({ status: "MISSING_CHAT_ID", reason: "Telegram signals chat id is missing." }, { status: 400 });
  }
  if (!config.signalsEnabled || !config.whaleAlertsEnabled) {
    return NextResponse.json({
      status: "DISABLED",
      reason: "Telegram configured but whale alerts disabled.",
      sample: sampleWhaleSignal(),
    });
  }

  const result = await sendTelegramMessage(sampleAlertText(), {
    chatId: config.signalsChatId,
    allowWhenDisabled: config.whaleAlertsEnabled,
  });

  return NextResponse.json(result, {
    status: result.status === "SENT" ? 200 : 400,
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
