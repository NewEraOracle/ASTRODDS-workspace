import { NextResponse } from "next/server";

import { saveStrongBuyLedgerRow, wasStrongBuySentToday } from "@/lib/astrodss/mlb/strong-buy-ledger";
import type { BestBetRow } from "@/lib/astrodss/mlb/strong-buy-gate";
import { getTelegramConfig, sendTelegramMessage } from "@/lib/astrodss/wallets/telegram";

export const dynamic = "force-dynamic";

type SendStrongBuyRequest = {
  row?: BestBetRow;
  sendAll?: boolean;
};

type UnifiedBestBetsPayload = {
  bestBetRows?: BestBetRow[];
};

function formatEdge(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

function formatPrice(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value.toFixed(2);
}

function buildStrongBuyMessage(row: BestBetRow) {
  return [
    "ASTRODDS STRONG BUY",
    "",
    `Game: ${row.awayTeam ?? "Away"} @ ${row.homeTeam ?? "Home"}`,
    `Side: ${row.selectedSide ?? "Unavailable"}`,
    "Market: Moneyline",
    `Edge: ${formatEdge(row.diagnosticCalibratedEdgePct)}`,
    `Risk Level: ${row.riskLevel.toUpperCase()} (${row.riskScore})`,
    `Stake: ${row.stakePercent}% of bankroll = $${row.stakeAmount.toFixed(2)}`,
    `Bankroll: $${row.bankroll.toFixed(2)}`,
    `Open Exposure: ${row.totalOpenExposurePercent.toFixed(1)}% (${row.exposureLabel})`,
    "",
    "Why:",
    ...row.reasons.slice(0, 4).map((reason) => `- ${reason}`),
    "",
    `Market Probability: ${formatPrice(row.marketProbability)}`,
    `Calibrated Probability: ${formatPrice(row.calibratedProbability)}`,
    "",
    "Manual action only.",
    "Real-money automation: OFF",
    "Paper-only mode remains ON.",
  ].join("\n");
}

function isTelegramEligibleStrongBuy(row: BestBetRow) {
  return row.status === "strong_buy" && row.telegramEligible && row.marketType === "moneyline";
}

async function loadStrongBuyRowsFromUnified(request: Request) {
  const unifiedUrl = new URL("/api/astrodds/signals/unified?sport=MLB", request.url);
  const response = await fetch(unifiedUrl, {
    cache: "no-store",
    headers: {
      "x-astrodds-strong-buy": "telegram",
    },
  });
  if (!response.ok) {
    return [];
  }

  const payload = (await response.json()) as UnifiedBestBetsPayload;
  return (payload.bestBetRows ?? []).filter(isTelegramEligibleStrongBuy);
}

export async function POST(request: Request) {
  const config = getTelegramConfig();
  if (!config.botToken) {
    return NextResponse.json({ status: "NOT_CONFIGURED", reason: "TELEGRAM_BOT_TOKEN is missing." }, { status: 400, headers: { "Cache-Control": "no-store" } });
  }
  if (!config.signalsChatId) {
    return NextResponse.json({ status: "MISSING_CHAT_ID", reason: "Telegram signals chat id is missing." }, { status: 400, headers: { "Cache-Control": "no-store" } });
  }
  if (!config.signalsEnabled) {
    return NextResponse.json({ status: "DISABLED", reason: "Telegram signals are disabled." }, { status: 200, headers: { "Cache-Control": "no-store" } });
  }

  const body = (await request.json().catch(() => ({}))) as SendStrongBuyRequest;
  const requestedRows = body.row
    ? [body.row]
    : body.sendAll
      ? await loadStrongBuyRowsFromUnified(request)
      : [];
  const rows = requestedRows.filter(isTelegramEligibleStrongBuy);

  if (!rows.length) {
    return NextResponse.json({
      status: "NO_STRONG_BUYS",
      reason: "No Strong Buy rows are eligible for Telegram.",
      sentCount: 0,
      skippedDuplicates: 0,
      rows: [],
    }, { status: 200, headers: { "Cache-Control": "no-store" } });
  }

  let sentCount = 0;
  let skippedDuplicates = 0;
  const sent: Array<{ bestBetId: string; status: string; reason: string; messageId?: number }> = [];

  for (const row of rows) {
    if (await wasStrongBuySentToday(row.bestBetId)) {
      skippedDuplicates += 1;
      sent.push({ bestBetId: row.bestBetId, status: "DUPLICATE", reason: "Strong Buy already sent today." });
      continue;
    }

    const result = await sendTelegramMessage(buildStrongBuyMessage(row), {
      chatId: config.signalsChatId,
    });

    if (result.status === "SENT") {
      sentCount += 1;
      await saveStrongBuyLedgerRow(row, {
        sentToTelegramAt: new Date().toISOString(),
        telegramMessageId: result.messageId,
      });
    }

    sent.push({
      bestBetId: row.bestBetId,
      status: result.status,
      reason: result.reason,
      messageId: result.messageId,
    });
  }

  return NextResponse.json({
    status: sentCount > 0 ? "SENT" : skippedDuplicates > 0 ? "DUPLICATE" : "FAILED",
    reason: sentCount > 0
      ? `Sent ${sentCount} Strong Buy Telegram alert${sentCount === 1 ? "" : "s"}.`
      : skippedDuplicates > 0
        ? "All Strong Buy alerts were duplicates for today."
        : "No Strong Buy alerts were sent.",
    sentCount,
    skippedDuplicates,
    rows: sent,
    realMoneyTrading: "OFF",
    manualOnly: true,
    paperOnly: true,
  }, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
