import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import type { WhaleConsensusSignal } from "./types";

export type TelegramConfigStatus = "CONFIGURED" | "NOT_CONFIGURED" | "DISABLED" | "MISSING_CHAT_ID";

export type TelegramConfig = {
  botToken?: string;
  botTokenMasked?: string;
  defaultChatId?: string;
  signalsChatId?: string;
  devChatId?: string;
  configured: boolean;
  whaleAlertsEnabled: boolean;
  signalsEnabled: boolean;
  mode: string;
  scanIntervalSeconds: number;
  signalsChatConfigured: boolean;
  devChatConfigured: boolean;
  status: TelegramConfigStatus;
};

export type WhaleTelegramStatus = {
  status: "DISABLED" | "NOT_CONFIGURED" | "MISSING_CHAT_ID" | "NOT_QUALIFIED" | "DUPLICATE" | "READY" | "SENT" | "FAILED";
  reason: string;
};

export type TelegramSendResult = {
  status: WhaleTelegramStatus["status"];
  reason: string;
  messageId?: number;
  signalKey?: string;
};

export type SentWhaleSignalRecord = {
  signalKey: string;
  handle: string;
  market: string;
  side: string;
  entryPrice?: number;
  currentPrice?: number;
  sentAt: string;
  channel: string;
  status: string;
};

const TELEGRAM_API_BASE = "https://api.telegram.org";
const SENT_SIGNAL_PATH = path.join(process.cwd(), ".astrodds", "telegram-whale-signals.json");

export function maskTelegramToken(token?: string) {
  if (!token) return undefined;
  if (token.length <= 6) return "***";
  return `${token.slice(0, 3)}***${token.slice(-3)}`;
}

export function getTelegramConfig(): TelegramConfig {
  const botToken = process.env.TELEGRAM_BOT_TOKEN?.trim();
  const defaultChatId = process.env.TELEGRAM_CHAT_ID?.trim();
  const signalsChatId = process.env.TELEGRAM_SIGNALS_CHAT_ID?.trim() || defaultChatId;
  const devChatId = process.env.TELEGRAM_DEV_CHAT_ID?.trim();
  const signalsEnabled = process.env.TELEGRAM_SIGNALS_ENABLED === "true";
  const whaleAlertsEnabled = process.env.TELEGRAM_WHALE_ALERTS_ENABLED === "true";
  const configured = Boolean(botToken);
  const signalsChatConfigured = Boolean(signalsChatId);
  const devChatConfigured = Boolean(devChatId);
  const scanIntervalSeconds = Math.max(15, Number(process.env.ASTRODDS_WHALE_SCAN_INTERVAL_SECONDS ?? 90) || 90);
  const mode = process.env.ASTRODDS_WHALE_ALERT_MODE?.trim() || "conservative";
  const status: TelegramConfigStatus = !configured
    ? "NOT_CONFIGURED"
    : !signalsChatConfigured
      ? "MISSING_CHAT_ID"
      : !signalsEnabled || !whaleAlertsEnabled
        ? "DISABLED"
        : "CONFIGURED";

  return {
    botToken,
    botTokenMasked: maskTelegramToken(botToken),
    defaultChatId,
    signalsChatId,
    devChatId,
    configured,
    whaleAlertsEnabled,
    signalsEnabled,
    mode,
    scanIntervalSeconds,
    signalsChatConfigured,
    devChatConfigured,
    status,
  };
}

export function isTelegramConfigured() {
  const config = getTelegramConfig();
  return config.configured && Boolean(config.defaultChatId || config.signalsChatId || config.devChatId);
}

export function isWhaleAlertsEnabled() {
  const config = getTelegramConfig();
  return config.configured && config.signalsEnabled && config.whaleAlertsEnabled && config.signalsChatConfigured;
}

export function publicTelegramStatus() {
  const config = getTelegramConfig();

  return {
    configured: config.configured,
    whaleAlertsEnabled: config.whaleAlertsEnabled,
    signalsEnabled: config.signalsEnabled,
    mode: config.mode,
    botTokenMasked: config.botTokenMasked,
    signalsChatConfigured: config.signalsChatConfigured,
    devChatConfigured: config.devChatConfigured,
    status: config.status,
  };
}

export async function sendTelegramMessage(text: string, options?: { chatId?: string; allowWhenDisabled?: boolean }): Promise<TelegramSendResult> {
  const config = getTelegramConfig();
  const chatId = options?.chatId ?? config.signalsChatId ?? config.defaultChatId;

  if (!config.botToken) return { status: "NOT_CONFIGURED", reason: "TELEGRAM_BOT_TOKEN is missing." };
  if (!chatId) return { status: "MISSING_CHAT_ID", reason: "Telegram chat id is missing." };
  if (!options?.allowWhenDisabled && config.status === "DISABLED") return { status: "DISABLED", reason: "Telegram signal alerts are disabled." };

  let response: Response;

  try {
    response = await fetch(`${TELEGRAM_API_BASE}/bot${config.botToken}/sendMessage`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text,
        disable_web_page_preview: true,
      }),
    });
  } catch (error) {
    return {
      status: "FAILED",
      reason: error instanceof Error ? error.message : "Telegram network request failed.",
    };
  }

  const payload = (await response.json().catch(() => undefined)) as { ok?: boolean; result?: { message_id?: number }; description?: string } | undefined;
  if (!response.ok || payload?.ok === false) {
    return {
      status: "FAILED",
      reason: payload?.description ?? `Telegram returned ${response.status}.`,
    };
  }

  return {
    status: "SENT",
    reason: "Telegram message sent.",
    messageId: payload?.result?.message_id,
  };
}

export async function sendTelegramTestMessage() {
  const config = getTelegramConfig();
  const chatId = config.devChatId ?? config.defaultChatId ?? config.signalsChatId;

  return sendTelegramMessage("ASTRODDS Telegram test successful. Paper mode only. Real money trading OFF.", {
    chatId,
    allowWhenDisabled: true,
  });
}

function formatPrice(value?: number, digits = 3) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "Unknown";
}

function formatWhaleAlert(signal: WhaleConsensusSignal) {
  const whale = signal.walletsOnSameSide[0] ?? "Public wallet";
  const orderBook = signal.orderBook?.status ?? "UNKNOWN";
  const fill = signal.orderBook?.fillStatus ?? "Unknown";

  return [
    "ASTRODDS WHALE ALERT",
    "",
    `Whale: ${whale}`,
    `Category: ${signal.sport ? "Sports" : "Public Market"}`,
    `Market: ${signal.marketTitle}`,
    `Side: ${signal.side}`,
    `Whale Entry: ${formatPrice(signal.averageWhaleEntry)}`,
    `Current Price: ${formatPrice(signal.currentPrice)}`,
    `Copyability: ${signal.copyabilityStatus}`,
    `Order Book: ${orderBook}`,
    `Estimated $50 Fill: ${fill}`,
    "Signal Type: WHALE_ONLY_PUBLIC_SIGNAL",
    "",
    "Why:",
    "Elite wallet activity is near the current price and has not been classified as stale.",
    "",
    "Mode: PAPER ONLY",
    "Real money trading: OFF",
  ].join("\n");
}

function entryBucket(value?: number) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "unknown";
}

export function whaleSignalKey(signal: WhaleConsensusSignal, date = new Date()) {
  const day = date.toISOString().slice(0, 10);
  const handle = signal.walletsOnSameSide[0] ?? "unknown";
  return [
    signal.sport ?? "ALL",
    handle,
    signal.marketId ?? signal.conditionId ?? signal.id,
    signal.side,
    entryBucket(signal.averageWhaleEntry),
    day,
  ].join("|");
}

async function loadSentWhaleSignals() {
  try {
    const raw = await readFile(SENT_SIGNAL_PATH, "utf8");
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? parsed.filter((item): item is SentWhaleSignalRecord => Boolean(item && typeof item === "object" && "signalKey" in item)) : [];
  } catch {
    return [];
  }
}

async function saveSentWhaleSignals(records: SentWhaleSignalRecord[]) {
  await mkdir(path.dirname(SENT_SIGNAL_PATH), { recursive: true });
  await writeFile(SENT_SIGNAL_PATH, JSON.stringify(records.slice(-500), null, 2), "utf8");
}

export async function hasSentWhaleSignal(signalKey: string) {
  const records = await loadSentWhaleSignals();
  return records.some((record) => record.signalKey === signalKey);
}

export async function recordSentWhaleSignal(signal: WhaleConsensusSignal, result: TelegramSendResult, channel = "signals") {
  const signalKey = result.signalKey ?? whaleSignalKey(signal);
  const records = await loadSentWhaleSignals();
  const nextRecord: SentWhaleSignalRecord = {
    signalKey,
    handle: signal.walletsOnSameSide[0] ?? "unknown",
    market: signal.marketTitle,
    side: signal.side,
    entryPrice: signal.averageWhaleEntry,
    currentPrice: signal.currentPrice,
    sentAt: new Date().toISOString(),
    channel,
    status: result.status,
  };
  await saveSentWhaleSignals([...records.filter((record) => record.signalKey !== signalKey), nextRecord]);
}

function isWhaleSignalQualified(signal: WhaleConsensusSignal) {
  const copyable = signal.copyabilityStatus === "COPYABLE_NOW" || signal.copyabilityStatus === "NEAR_WHALE_ENTRY";
  const notStale = signal.copyabilityStatus !== "STALE_ENTRY" && signal.copyabilityStatus !== "TOO_LATE";
  const orderBookOk = !signal.orderBook || signal.orderBook.status === "EXCELLENT" || signal.orderBook.status === "GOOD" || signal.orderBook.status === "FAIR";
  return copyable && notStale && orderBookOk && signal.consensusStrength !== "CONFLICTED_WHALES";
}

export function telegramStatusForWhaleSignal(signal: WhaleConsensusSignal): WhaleTelegramStatus {
  const config = getTelegramConfig();

  if (!isWhaleSignalQualified(signal)) {
    return {
      status: "NOT_QUALIFIED",
      reason: "Whale signal is stale, conflicted, illiquid, or not copyable enough for Telegram.",
    };
  }

  if (!config.botToken) return { status: "NOT_CONFIGURED", reason: "TELEGRAM_BOT_TOKEN is missing." };
  if (!config.signalsChatId) return { status: "MISSING_CHAT_ID", reason: "Telegram signals chat id is missing." };
  if (!config.signalsEnabled || !config.whaleAlertsEnabled) {
    return {
      status: "DISABLED",
      reason: "Telegram whale alerts are disabled by default.",
    };
  }

  return {
    status: "READY",
    reason: "Qualified whale signal is ready for paper-only Telegram alert workflow.",
  };
}

export async function sendWhaleTradeAlert(signal: WhaleConsensusSignal): Promise<TelegramSendResult> {
  const status = telegramStatusForWhaleSignal(signal);
  const signalKey = whaleSignalKey(signal);

  if (status.status !== "READY") return { status: status.status, reason: status.reason, signalKey };
  if (await hasSentWhaleSignal(signalKey)) {
    return {
      status: "DUPLICATE",
      reason: "Whale signal already sent today.",
      signalKey,
    };
  }

  const result = await sendTelegramMessage(formatWhaleAlert(signal), {
    chatId: getTelegramConfig().signalsChatId,
  });
  const withKey = { ...result, signalKey };

  if (result.status === "SENT") await recordSentWhaleSignal(signal, withKey);
  return withKey;
}

export function sampleWhaleSignal(): WhaleConsensusSignal {
  return {
    id: "sample-whale-alert",
    sport: "MLB",
    marketTitle: "Kansas City Royals vs Cincinnati Reds",
    marketId: "sample-market",
    side: "Cincinnati Reds",
    walletsOnSameSide: ["kch123"],
    walletsOnOppositeSide: [],
    totalWhalePositionValue: 5000,
    averageWhaleEntry: 0.414,
    currentPrice: 0.421,
    priceDeltaFromWhaleAverage: 0.007,
    consensusStrength: "SINGLE_WHALE_ACTIVITY",
    conflictingWhales: [],
    copyabilityStatus: "COPYABLE_NOW",
    signalType: "WHALE_CONFIRMED",
  };
}
