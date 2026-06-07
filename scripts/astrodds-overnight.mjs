import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const baseUrl = process.env.ASTRODDS_BASE_URL ?? "http://127.0.0.1:3000";
const outDir = path.join(process.cwd(), ".astrodds");
const mlbTelegramStatePath = path.join(outDir, "telegram-mlb-signals.json");

async function getJson(pathname) {
  const response = await fetch(`${baseUrl}${pathname}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`${pathname} returned ${response.status}`);
  return response.json();
}

function countBy(items, key) {
  return items.reduce((counts, item) => {
    const value = item?.[key] ?? "UNKNOWN";
    counts[value] = (counts[value] ?? 0) + 1;
    return counts;
  }, {});
}

function summarizePick(signal) {
  return {
    decision: signal.decision,
    game: signal.game,
    bet: signal.pick,
    entryPrice: signal.entryPrice,
    modelProbability: signal.modelProbability,
    marketProbability: signal.marketProbability,
    edge: signal.edge,
    confidenceScore: signal.confidenceScore,
    confluenceScore: signal.confluenceScore,
    partnerStrategyScore: signal.partnerStrategyScore,
    dataQuality: signal.dataQuality,
    signalType: signal.signalType,
    why: signal.why?.slice?.(0, 4) ?? [],
    warnings: signal.warnings?.slice?.(0, 4) ?? [],
    action: "WATCH / PAPER ONLY",
    realMoneyTrading: "OFF",
  };
}

function mlbAlertsEnabled() {
  return process.env.TELEGRAM_SIGNALS_ENABLED === "true" && process.env.ASTRODDS_TELEGRAM_MLB_ALERTS_ENABLED === "true";
}

function telegramChatId() {
  return process.env.TELEGRAM_SIGNALS_CHAT_ID || process.env.TELEGRAM_CHAT_ID;
}

function signalKey(signal) {
  const day = new Date().toISOString().slice(0, 10);
  const price = typeof signal.entryPrice === "number" ? signal.entryPrice.toFixed(2) : "unknown";
  return ["MLB", signal.game, signal.marketType, signal.pick, price, day].join("|");
}

async function loadSentMlbSignals() {
  try {
    const parsed = JSON.parse(await readFile(mlbTelegramStatePath, "utf8"));
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

async function saveSentMlbSignals(records) {
  await mkdir(outDir, { recursive: true });
  await writeFile(mlbTelegramStatePath, JSON.stringify(records.slice(-500), null, 2), "utf8");
}

function pct(value) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "--";
}

function edgeText(value) {
  if (typeof value !== "number") return "--";
  return `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}

function formatMlbTelegramAlert(signal) {
  return [
    "ASTRODDS MLB STRONG BUY",
    "",
    `Game: ${signal.game}`,
    `Bet: ${signal.marketType}`,
    `Pick: ${signal.pick}`,
    `Entry: ${typeof signal.entryPrice === "number" ? signal.entryPrice.toFixed(3) : "Unknown"}`,
    "",
    `Model: ${pct(signal.modelProbability)}`,
    `Market: ${pct(signal.marketProbability)}`,
    `Edge: ${edgeText(signal.edge)}`,
    `Confidence: ${signal.confidenceScore ?? "--"}/100`,
    `Confluence: ${signal.confluenceScore ?? "--"}/100`,
    "",
    "Why:",
    ...(signal.why ?? []).slice(0, 5).map((line) => `- ${line}`),
    "",
    "Warnings:",
    ...((signal.warnings?.length ? signal.warnings : ["No major warning returned."]).slice(0, 4).map((line) => `- ${line}`)),
    "",
    "Action: WATCH / PAPER ONLY",
    "Risk: Real money trading OFF",
    `Signal Type: ${signal.signalType ?? "MLB_MODEL_SIGNAL"}`,
  ].join("\n");
}

async function sendTelegram(text) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = telegramChatId();
  if (!token || !chatId) return { status: "NOT_CONFIGURED", reason: "Missing token or chat id." };

  const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text,
      disable_web_page_preview: true,
    }),
  });
  const payload = await response.json().catch(() => undefined);
  if (!response.ok || payload?.ok === false) return { status: "FAILED", reason: payload?.description ?? `Telegram returned ${response.status}.` };
  return { status: "SENT", reason: "Sent." };
}

async function maybeSendMlbAlerts(signals) {
  const maxAlerts = Math.max(1, Number(process.env.ASTRODDS_MAX_MLB_ALERTS_PER_RUN ?? 6) || 6);
  if (!mlbAlertsEnabled()) {
    return { sent: 0, skipped: signals.length, status: "DISABLED" };
  }

  const state = await loadSentMlbSignals();
  const sentKeys = new Set(state.filter((record) => record.status === "SENT").map((record) => record.signalKey));
  let sent = 0;
  let duplicates = 0;
  const failures = [];

  for (const signal of signals.slice(0, maxAlerts)) {
    const key = signalKey(signal);
    if (sentKeys.has(key)) {
      duplicates += 1;
      continue;
    }
    const result = await sendTelegram(formatMlbTelegramAlert(signal));
    state.push({
      signalKey: key,
      sport: "MLB",
      game: signal.game,
      marketType: signal.marketType,
      pick: signal.pick,
      entryPrice: signal.entryPrice,
      score: signal.confluenceScore,
      confidence: signal.confidence,
      decision: signal.decision,
      sentAt: new Date().toISOString(),
      channel: "signals",
      status: result.status,
      reason: result.reason,
    });
    if (result.status === "SENT") sent += 1;
    else failures.push(result.reason);
  }

  await saveSentMlbSignals(state);
  return { sent, skipped: Math.max(0, signals.length - sent), duplicates, failures, status: "COMPLETE" };
}

async function main() {
  await mkdir(outDir, { recursive: true });

  const [scan, unified, whaleSignals] = await Promise.all([
    getJson("/api/astrodds/scan?sport=MLB"),
    getJson("/api/astrodds/signals/unified?sport=MLB"),
    getJson("/api/astrodds/wallets/signals?category=all"),
  ]);

  const summary = {
    generatedAt: new Date().toISOString(),
    mode: "PAPER_ONLY",
    realMoneyTrading: "OFF",
    mlb: {
      gamesScanned: unified.summary?.mlbGamesScanned ?? scan.games?.length ?? 0,
      marketsMatched: unified.summary?.marketsMatched ?? scan.diagnostics?.matching?.matchedMarketsCount ?? 0,
      strongBuys: unified.topMlbStrongBuys?.length ?? 0,
      buyCount: unified.summary?.buysFound ?? 0,
      watchCount: unified.summary?.watchFound ?? 0,
      rejectedOrAvoided: unified.summary?.rejectedOrAvoided ?? 0,
      noStrongBuyReasons: unified.noStrongBuyReasons ?? [],
      topPicks: (unified.topMlbStrongBuys?.length ? unified.topMlbStrongBuys : unified.topQualifiedSportsSignals ?? []).slice(0, 6).map(summarizePick),
      decisionCounts: countBy(unified.signals ?? [], "decision"),
    },
    whales: {
      whalesScanned: whaleSignals.counts?.whalesScanned ?? 0,
      qualifiedSignals: whaleSignals.counts?.qualifiedSignals ?? 0,
      rejectedLowQuality: whaleSignals.counts?.rejectedLowScore ?? 0,
      copyableNow: whaleSignals.counts?.COPYABLE_NOW ?? 0,
      nearWhaleEntry: whaleSignals.counts?.NEAR_WHALE_ENTRY ?? 0,
      totalSignals: whaleSignals.counts?.totalSignals ?? 0,
      topSignals: (whaleSignals.signals ?? []).slice(0, 8).map((signal) => ({
        whale: signal.whale,
        category: signal.category,
        sport: signal.sport,
        market: signal.market,
        side: signal.side,
        score: signal.signalQualityScore,
        copyability: signal.copyability,
        rejectionReason: signal.rejectionReason,
      })),
    },
    system: {
      scanStatus: scan.sourceStatus,
      diagnostics: {
        polymarket: scan.diagnostics?.polymarket,
        sportApi: scan.diagnostics?.sportApi,
        weather: scan.diagnostics?.weather,
        matching: scan.diagnostics?.matching,
        orderBook: scan.diagnostics?.orderBook,
      },
      errors: [...(scan.warnings ?? []), ...(unified.errors ?? []), ...(whaleSignals.errors ?? [])].slice(0, 20),
    },
  };

  const outPath = path.join(outDir, "overnight-summary.json");
  const paperSignalsPath = path.join(outDir, "mlb-paper-signals.json");
  const paperSignals = (unified.topMlbStrongBuys ?? []).slice(0, 6).map((signal) => ({
    id: signal.signalId,
    source: "ASTRODDS_OVERNIGHT",
    signalType: signal.signalType ?? "MLB_MODEL_SIGNAL",
    sport: "MLB",
    game: signal.game,
    marketType: signal.marketType,
    pick: signal.pick,
    entryPrice: signal.entryPrice,
    modelProbability: signal.modelProbability,
    marketProbability: signal.marketProbability,
    edge: signal.edge,
    confidence: signal.confidence,
    confluenceScore: signal.confluenceScore,
    partnerStrategyScore: signal.partnerStrategyScore,
    status: "PENDING",
    action: "WATCH / PAPER ONLY",
    realMoneyTrading: "OFF",
    createdAt: summary.generatedAt,
  }));
  await writeFile(outPath, JSON.stringify(summary, null, 2), "utf8");
  await writeFile(paperSignalsPath, JSON.stringify(paperSignals, null, 2), "utf8");
  const telegramMlb = await maybeSendMlbAlerts(unified.topMlbStrongBuys ?? []);

  console.log("ASTRODDS Overnight Summary");
  console.log("");
  console.log("MLB:");
  console.log(`- Games scanned: ${summary.mlb.gamesScanned}`);
  console.log(`- Markets matched: ${summary.mlb.marketsMatched}`);
  console.log(`- Strong buys: ${summary.mlb.strongBuys}`);
  console.log(`- BUY: ${summary.mlb.buyCount}`);
  console.log(`- WATCH: ${summary.mlb.watchCount}`);
  console.log(`- Rejected/Avoided: ${summary.mlb.rejectedOrAvoided}`);
  if (!summary.mlb.strongBuys) console.log(`- Why no Strong Buy: ${summary.mlb.noStrongBuyReasons.join(" | ") || "No reason returned."}`);
  console.log("");
  console.log("Whales:");
  console.log(`- Whales scanned: ${summary.whales.whalesScanned}`);
  console.log(`- Qualified signals: ${summary.whales.qualifiedSignals}`);
  console.log(`- Rejected low quality: ${summary.whales.rejectedLowQuality}`);
  console.log("");
  console.log("System:");
  console.log(`- Polymarket: ${summary.system.diagnostics.polymarket?.status ?? "UNKNOWN"}`);
  console.log(`- MLB API: ${summary.system.diagnostics.sportApi?.status ?? "UNKNOWN"}`);
  console.log(`- Weather: ${summary.system.diagnostics.weather?.status ?? "UNKNOWN"}`);
  console.log(`- Matching: ${summary.system.diagnostics.matching?.status ?? "UNKNOWN"}`);
  console.log(`- Summary saved: ${outPath}`);
  console.log(`- Paper signals saved: ${paperSignalsPath}`);
  console.log(`- MLB Telegram alerts: ${telegramMlb.status} sent=${telegramMlb.sent} duplicates=${telegramMlb.duplicates ?? 0}`);
  console.log("- Real money trading: OFF");
}

main().catch((error) => {
  console.error(`ASTRODDS overnight run failed: ${error instanceof Error ? error.message : "unknown error"}`);
  process.exitCode = 1;
});
