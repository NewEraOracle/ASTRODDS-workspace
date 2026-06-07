import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");
const statePath = path.join(projectRoot, ".astrodds", "telegram-whale-signals.json");

function loadWorkerEnv() {
  dotenv.config({ path: path.join(projectRoot, ".env.local"), override: true, quiet: true });
  dotenv.config({ path: path.join(projectRoot, ".env"), override: false, quiet: true });
}

loadWorkerEnv();

function intervalMs() {
  const seconds = Number(process.env.ASTRODDS_WHALE_SCAN_INTERVAL_SECONDS ?? 90);
  return Math.max(15, Number.isFinite(seconds) ? seconds : 90) * 1000;
}

function baseUrl() {
  return process.env.ASTRODDS_BASE_URL ?? "http://127.0.0.1:3000";
}

function alertMode() {
  return process.env.ASTRODDS_WHALE_ALERT_MODE?.trim() || "conservative";
}


function maxAlertsPerRun() {
  const value = Number(process.env.ASTRODDS_WHALE_MAX_ALERTS_PER_RUN ?? 5);
  return Math.max(0, Number.isFinite(value) ? value : 5);
}
function alertCategories() {
  return process.env.ASTRODDS_WHALE_ALERT_CATEGORIES?.trim() || "all";
}

function signalsEnabled() {
  return process.env.TELEGRAM_SIGNALS_ENABLED === "true";
}

function whaleAlertFlagEnabled() {
  return process.env.TELEGRAM_WHALE_ALERTS_ENABLED === "true";
}

function whaleAlertsEnabled() {
  return signalsEnabled() && whaleAlertFlagEnabled();
}

function chatConfigured() {
  return Boolean(process.env.TELEGRAM_SIGNALS_CHAT_ID || process.env.TELEGRAM_CHAT_ID);
}

function telegramConfigured() {
  return Boolean(process.env.TELEGRAM_BOT_TOKEN && chatConfigured());
}


function fetchTimeoutMs() {
  const value = Number(process.env.ASTRODDS_WHALE_FETCH_TIMEOUT_MS ?? 15_000);
  return Math.max(3_000, Number.isFinite(value) ? value : 15_000);
}

function sanitizeUrlForLog(value) {
  if (!value) return "unknown";
  try {
    const url = new URL(value.toString());
    if (url.hostname === "api.telegram.org") return `${url.origin}/bot***/${url.pathname.split("/").pop() ?? "sendMessage"}`;
    for (const sensitiveKey of ["user", "address", "wallet", "walletAddress", "proxyAddress", "token", "key"]) {
      if (url.searchParams.has(sensitiveKey)) url.searchParams.set(sensitiveKey, "<redacted>");
    }
    return url.toString();
  } catch {
    return String(value).slice(0, 160);
  }
}

function safeLogText(value) {
  return String(value ?? "unknown").replace(/\s+/g, " ").slice(0, 240);
}

async function timedFetch(endpointLabel, url, options = {}, timeoutMs = fetchTimeoutMs()) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const target = url.toString();

  try {
    const response = await fetch(target, {
      ...options,
      signal: options.signal ?? controller.signal,
    });
    const text = await response.text().catch(() => "");
    let json;
    try {
      json = text ? JSON.parse(text) : undefined;
    } catch {
      json = undefined;
    }

    return {
      endpointLabel,
      ok: response.ok,
      httpStatus: response.status,
      timeout: false,
      error: response.ok ? undefined : `HTTP ${response.status}`,
      responseTextSnippet: text ? safeLogText(text) : undefined,
      json,
      text,
      url: sanitizeUrlForLog(target),
    };
  } catch (error) {
    const timeoutError = error instanceof Error && error.name === "AbortError";
    return {
      endpointLabel,
      ok: false,
      timeout: timeoutError,
      error: timeoutError ? `Timed out after ${timeoutMs}ms` : error instanceof Error ? error.message : "fetch failed",
      url: sanitizeUrlForLog(target),
    };
  } finally {
    clearTimeout(timeout);
  }
}

function logWhaleSourceWarning(result, message = "continuing with 0 whale bonus alerts") {
  console.log(
    `WHALE SOURCE WARNING: endpoint=${result.endpointLabel ?? "unknown"} status=${result.httpStatus ?? "NO_STATUS"} timeout=${Boolean(result.timeout)} error=${safeLogText(result.error ?? "source unavailable")} url=${result.url ?? "unknown"}, ${message}`,
  );
}

function fallbackWhalePayload(error) {
  return {
    sourcePolicy: "ASTRODDS uses public Polymarket wallet/profile data only. No private or non-public information is used.",
    sport: "ALL",
    category: alertCategories(),
    signals: [],
    consensus: [],
    sourceStatus: "FAILED",
    errors: [error ?? "WHALE SOURCE WARNING: source unavailable, continuing with 0 whale bonus alerts."],
    diagnostics: [],
    scannedAt: new Date().toISOString(),
    counts: {
      totalSignals: 0,
      activePositions: 0,
      closedPositions: 0,
      COPYABLE_NOW: 0,
      NEAR_WHALE_ENTRY: 0,
      WATCH_ONLY: 0,
      STALE_ENTRY: 0,
      TOO_LATE: 0,
      NO_LIQUIDITY: 0,
      CONFLICT: 0,
      UNKNOWN: 0,
    },
  };
}

function logPayloadDiagnostics(payload) {
  const errors = Array.isArray(payload?.errors) ? payload.errors : [];
  for (const error of errors.slice(0, 6)) {
    console.log(`WHALE SOURCE WARNING: endpoint=wallet-signals-api status=PAYLOAD_ERROR timeout=false error=${safeLogText(error)}`);
  }

  const diagnostics = Array.isArray(payload?.diagnostics) ? payload.diagnostics : [];
  let emitted = 0;
  for (const profile of diagnostics) {
    const checks = Array.isArray(profile?.checks) ? profile.checks : [];
    for (const check of checks) {
      if (check?.status !== "FAILED" && !(check?.status === "PARTIAL" && check?.error)) continue;
      console.log(
        `WHALE SOURCE WARNING: whale=${safeLogText(profile?.handle)} profile=${sanitizeUrlForLog(profile?.profileUrl)} endpoint=${safeLogText(check?.label)} status=${check?.httpStatus ?? check?.status ?? "NO_STATUS"} timeout=false error=${safeLogText(check?.error ?? "source unavailable")} url=${sanitizeUrlForLog(check?.sourceUrl)} snippet=${safeLogText(check?.responseTextSnippet ?? "")}`,
      );
      emitted += 1;
      if (emitted >= 12) return;
    }
  }
}

function maybeLogNoNewCopyable(sent) {
  if (sent === 0) console.log("No new copyable whale trades found.");
}
function startupConfigLog() {
  return [
    "ASTRODDS whale alert worker started.",
    `Signals enabled: ${signalsEnabled()}`,
    `Whale alerts enabled: ${whaleAlertFlagEnabled()}`,
    `Telegram token: ${process.env.TELEGRAM_BOT_TOKEN ? "CONFIGURED" : "MISSING"}`,
    `Signals chat: ${chatConfigured() ? "CONFIGURED" : "MISSING"}`,
    `Dev chat: ${process.env.TELEGRAM_DEV_CHAT_ID ? "CONFIGURED" : "MISSING"}`,
    `Mode: ${alertMode()}`,
    `Categories: ${alertCategories()}`,
    `Interval: ${intervalMs() / 1000}s`,
    "Mode: PAPER ONLY",
    "Real money trading: OFF",
  ].join("\n");
}

function entryBucket(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "unknown";
}

function whaleSignalKey(signal) {
  if (typeof signal.signalKey === "string" && signal.signalKey.trim()) return signal.signalKey;
  const day = new Date().toISOString().slice(0, 10);
  return [
    signal.whale ?? "unknown",
    signal.marketId ?? signal.conditionId ?? signal.assetId ?? signal.market ?? "unknown-market",
    signal.side ?? signal.outcome ?? "unknown-side",
    entryBucket(signal.whaleEntryPrice),
    day,
  ].join("|");
}

async function loadState() {
  try {
    const parsed = JSON.parse(await readFile(statePath, "utf8"));
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

async function saveState(records) {
  await mkdir(path.dirname(statePath), { recursive: true });
  await writeFile(statePath, JSON.stringify(records.slice(-800), null, 2), "utf8");
}

function formatPrice(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "Unknown";
}

function titleCase(value) {
  return String(value ?? "UNKNOWN")
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function orderBookLabel(signal) {
  if (signal.orderBookStatus && signal.orderBookStatus !== "NOT_CONNECTED") return signal.orderBookStatus;
  return signal.orderBook?.status ?? "UNKNOWN";
}

function formatWhaleOnlyAlert(signal) {
  return [
    "ASTRODDS WHALE ALERT",
    "",
    `Whale: ${signal.whale ?? "Public wallet"}`,
    `Category: ${titleCase(signal.category)}`,
    `Market: ${signal.market ?? "Unknown public Polymarket market"}`,
    `Side: ${signal.side ?? signal.outcome ?? "Unknown side"}`,
    `Whale Entry: ${formatPrice(signal.whaleEntryPrice)}`,
    `Current Price: ${formatPrice(signal.currentPrice)}`,
    `Copyability: ${signal.copyability ?? "UNKNOWN"}`,
    `Order Book: ${orderBookLabel(signal)}`,
    "Signal Type: WHALE_ONLY_PUBLIC_SIGNAL",
    "",
    "Why:",
    signal.copyabilityReason ?? "Elite public wallet entered near current price. Entry is still close to whale average and not stale.",
    "",
    "Mode: PAPER ONLY",
    "Real money trading: OFF",
  ].join("\n");
}

function copyabilityAllowed(signal) {
  if (signal.copyability === "COPYABLE_NOW" || signal.copyability === "NEAR_WHALE_ENTRY") return true;
  return alertMode().toLowerCase() === "watch" && signal.copyability === "WATCH_ONLY";
}

function isStaleOrTooLate(signal) {
  return signal.copyability === "STALE_ENTRY" || signal.copyability === "TOO_LATE" || signal.copyability === "NO_LIQUIDITY";
}

function isAlertableWhaleSignal(signal) {
  const statusOpen = signal.status === "OPEN";
  const hasSide = typeof signal.side === "string" && signal.side.trim() && signal.side !== "Unknown side";
  const hasMarket = typeof signal.market === "string" && signal.market.trim();
  const hasPrice = typeof signal.currentPrice === "number" && Number.isFinite(signal.currentPrice);
  const bookOk = !signal.orderBook || ["EXCELLENT", "GOOD", "FAIR", "NOT_CONNECTED"].includes(signal.orderBook.status);

  return statusOpen && hasSide && hasMarket && hasPrice && copyabilityAllowed(signal) && bookOk;
}

async function sendTelegramText(text) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_SIGNALS_CHAT_ID || process.env.TELEGRAM_CHAT_ID;
  if (!token || !chatId) return { status: "NOT_CONFIGURED", reason: "Missing Telegram token or chat id." };

  const result = await timedFetch(
    "telegram-send-message",
    `https://api.telegram.org/bot${token}/sendMessage`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text,
        disable_web_page_preview: true,
      }),
    },
    12_000,
  );

  if (!result.ok || result.json?.ok === false) {
    logWhaleSourceWarning(result, "Telegram send failed; paper-only worker continues");
    return { status: "FAILED", reason: result.json?.description ?? result.error ?? "Telegram request failed." };
  }

  return { status: "SENT", reason: "Sent." };
}

async function fetchWhaleSignals() {
  const url = new URL(`${baseUrl().replace(/\/$/, "")}/api/astrodds/wallets/signals`);
  url.searchParams.set("category", alertCategories());
  const result = await timedFetch("wallet-signals-api", url, { cache: "no-store" }, fetchTimeoutMs());

  if (!result.ok) {
    logWhaleSourceWarning(result);
    return fallbackWhalePayload(result.error);
  }

  const payload = result.json ?? fallbackWhalePayload("Wallet signals API returned non-JSON payload.");
  logPayloadDiagnostics(payload);
  return payload;
}

async function runOnce() {
  const payload = await fetchWhaleSignals();
  const allSignals = Array.isArray(payload.signals) ? payload.signals : [];
  const state = await loadState();
  const known = new Set(state.map((record) => record.signalKey));
  const errors = Array.isArray(payload.errors) ? payload.errors.length : 0;
  let sent = 0;
  let duplicates = 0;
  let staleSkipped = 0;
  let notQualified = 0;
  let failed = 0;
  const maxAlerts = maxAlertsPerRun();
  let alertAttempts = 0;

  if (!whaleAlertsEnabled()) {
    console.log("Whale alerts disabled. Scanning only, no Telegram send.");
    maybeLogNoNewCopyable(0);
    return {
      sent,
      duplicates,
      staleSkipped: allSignals.filter(isStaleOrTooLate).length,
      notQualified: allSignals.filter((signal) => !isAlertableWhaleSignal(signal)).length,
      failed,
      scanned: allSignals.length,
      errors,
    };
  }

  if (!telegramConfigured()) {
    console.log("Telegram not configured. Scanning only, no Telegram send.");
    maybeLogNoNewCopyable(0);
    return {
      sent,
      duplicates,
      staleSkipped: allSignals.filter(isStaleOrTooLate).length,
      notQualified: allSignals.filter((signal) => !isAlertableWhaleSignal(signal)).length,
      failed,
      scanned: allSignals.length,
      errors,
    };
  }

  for (const signal of allSignals) {
    if (isStaleOrTooLate(signal)) {
      staleSkipped += 1;
      continue;
    }

    if (!isAlertableWhaleSignal(signal)) {
      notQualified += 1;
      continue;
    }

    const key = whaleSignalKey(signal);
    if (known.has(key)) {
      duplicates += 1;
      continue;
    }

    if (alertAttempts >= maxAlerts) {
      notQualified += 1;
      continue;
    }

    alertAttempts += 1;
    const result = await sendTelegramText(formatWhaleOnlyAlert(signal));
    state.push({
      signalKey: key,
      handle: signal.whale ?? "unknown",
      market: signal.market ?? "unknown",
      side: signal.side ?? signal.outcome ?? "unknown",
      entryPrice: signal.whaleEntryPrice,
      currentPrice: signal.currentPrice,
      category: signal.category ?? "UNKNOWN",
      copyability: signal.copyability ?? "UNKNOWN",
      sentAt: new Date().toISOString(),
      channel: "signals",
      status: result.status,
    });
    known.add(key);

    if (result.status === "SENT") sent += 1;
    else failed += 1;
  }

  await saveState(state);
  maybeLogNoNewCopyable(sent);
  return { sent, duplicates, staleSkipped, notQualified, failed, scanned: allSignals.length, errors };
}

function summaryLine(prefix, summary) {
  return `${prefix}: sent=${summary.sent} duplicates=${summary.duplicates} staleSkipped=${summary.staleSkipped} notQualified=${summary.notQualified} failed=${summary.failed} scanned=${summary.scanned} errors=${summary.errors}`;
}

async function main() {
  const once = process.argv.includes("--once");
  console.log(startupConfigLog());

  if (once) {
    const summary = await runOnce();
    console.log(summaryLine("Whale alert scan once", summary));
    return;
  }

  for (;;) {
    try {
      const summary = await runOnce();
      console.log(summaryLine("Whale alert scan", summary));
    } catch (error) {
      console.log(`Whale alert scan failed: ${error instanceof Error ? error.message : "unknown error"}`);
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs()));
  }
}

main().catch((error) => {
  console.log(`ASTRODDS whale alert worker stopped: ${error instanceof Error ? error.message : "unknown error"}`);
  process.exitCode = 1;
});
