"use client";

import Image from "next/image";
import { useEffect, useMemo, useRef, useState } from "react";
import type { SyntheticEvent } from "react";
import {
  Activity,
  BadgeDollarSign,
  BellRing,
  Bot,
  CheckCircle2,
  CircleDollarSign,
  DatabaseZap,
  Diamond,
  Gauge,
  LineChart,
  Loader2,
  RadioTower,
  ShieldAlert,
  Trophy,
  WalletCards,
} from "lucide-react";

import { isBrowserFallbackResult, scanMlbWithBrowserFallback, shouldUseBrowserFallback } from "@/lib/astrodss/sports-data/browser-fallback";
import { buildUnifiedSignals, type UnifiedAstroddsSignal } from "@/lib/astrodss/signal-engine";
import { displayDecision, SCAN_STEPS, SPORTS } from "@/lib/astrodss/sports-data/normalize";
import type {
  AstroddsApiTestResult,
  AstroddsApiTestSource,
  AstroddsDataStatus,
  AstroddsDiagnosticStatus,
  AstroddsDecision,
  AstroddsGameScan,
  AstroddsMarketScan,
  AstroddsScanResult,
  AstroddsSourceStatus,
  AstroddsSportFilter,
} from "@/lib/astrodss/sports-data/types";
import type { AstroddsPaperTrade, AstroddsPaperTradeStatus } from "@/lib/astrodss/sports-data/mlb-results";
import type {
  KnownWhaleWallet,
  WalletPosition,
  WalletProfile,
  WalletScanResult,
  WalletSourceStatus,
  WhaleConsensusSignal,
  WhalePositionCopyability,
  WhaleStrategyMetrics,
} from "@/lib/astrodss/wallets/types";

type ScanStatus = "Idle" | "Scanning" | "Completed" | "Failed" | "Button test OK";

type ScannerRow = {
  game: AstroddsGameScan;
  market?: AstroddsMarketScan;
};

type PaperTrade = AstroddsPaperTrade & {
  bankroll: number;
  dataConfidence: AstroddsDataStatus;
  dataStatuses: {
    pitchers: AstroddsSourceStatus;
    weather: AstroddsSourceStatus;
    lineups: AstroddsSourceStatus;
    injuries: AstroddsSourceStatus;
    polymarket: AstroddsSourceStatus;
  };
  walletSupport: string;
};

const pageLinks = [
  { id: "scanner", label: "Scanner", icon: RadioTower },
  { id: "best-picks", label: "Best Picks", icon: LineChart },
  { id: "sports-data", label: "Sports Data", icon: DatabaseZap },
  { id: "paper", label: "Paper Trading", icon: CircleDollarSign },
  { id: "cashout", label: "Live Cashout", icon: ShieldAlert },
  { id: "record", label: "Official Record", icon: Trophy },
  { id: "wallets", label: "Wallet Intelligence", icon: WalletCards },
  { id: "telegram", label: "Telegram", icon: Bot },
  { id: "vault", label: "Card Vault", icon: Diamond },
];

const decisionClass: Record<AstroddsDecision | "NONE", string> = {
  ELITE: "border-[#f8d66a]/85 bg-[#f8d66a]/18 text-[#fff3b8] shadow-[0_0_18px_rgba(248,214,106,0.18)]",
  STRONG_BUY: "border-emerald-300/70 bg-emerald-400/15 text-emerald-50",
  BUY: "border-green-300/55 bg-green-400/12 text-green-100",
  WATCH: "border-yellow-300/60 bg-yellow-400/[0.14] text-yellow-50",
  WAIT: "border-amber-300/50 bg-amber-400/12 text-amber-100",
  AVOID: "border-red-300/55 bg-red-400/[0.14] text-red-100",
  PROFIT_LOCK: "border-yellow-200/75 bg-yellow-300/[0.18] text-yellow-50",
  CASH_OUT: "border-red-200/70 bg-red-500/[0.18] text-red-50",
  HEDGE: "border-blue-300/55 bg-blue-400/[0.14] text-blue-100",
  NONE: "border-slate-300/35 bg-slate-400/10 text-slate-200",
};

const statusClass: Record<AstroddsSourceStatus, string> = {
  CONNECTED: "border-emerald-300/55 bg-emerald-400/12 text-emerald-100",
  PARTIAL: "border-yellow-300/55 bg-yellow-400/12 text-yellow-100",
  NOT_CONNECTED: "border-red-300/55 bg-red-400/12 text-red-100",
  DEMO_FALLBACK: "border-fuchsia-300/55 bg-fuchsia-400/12 text-fuchsia-100",
  WALLET_LED: "border-cyan-300/55 bg-cyan-400/12 text-cyan-100",
};

const diagnosticStatusClass: Record<AstroddsDiagnosticStatus, string> = {
  CONNECTED_SERVER: "border-emerald-300/55 bg-emerald-400/12 text-emerald-100",
  CONNECTED_BROWSER: "border-cyan-300/60 bg-cyan-400/15 text-cyan-50",
  CONNECTED: "border-emerald-300/55 bg-emerald-400/12 text-emerald-100",
  PARTIAL: "border-yellow-300/55 bg-yellow-400/12 text-yellow-100",
  FAILED: "border-red-300/65 bg-red-500/15 text-red-100",
  NOT_CONNECTED: "border-slate-300/35 bg-slate-400/10 text-slate-200",
};

const scanLabel: Record<AstroddsSportFilter, string> = {
  ALL: "All Sports",
  MLB: "MLB",
  NFL: "NFL",
  NBA: "NBA",
  NHL: "NHL",
  SOCCER: "Soccer",
  TENNIS: "Tennis",
  MMA: "MMA/UFC",
  OTHER: "Other",
};

const CARD_REFERENCE_SRC = "/astrodds/card-reference.png";
const PAPER_TRADES_STORAGE_KEY = "astrodds.paperTrades.v1";
const STARTING_BANKROLL = 1000;
const DEFAULT_PAPER_STAKE = 50;
const MAX_ACTIVE_EXPOSURE = 300;

type ResolveSummary = {
  resolved: number;
  pending: number;
  wins: number;
  losses: number;
  voids: number;
  unknown: number;
  errors: string[];
  resultsFetched?: number;
};

type WhaleWatchlistItem = KnownWhaleWallet & {
  address?: string;
  sourceStatus: WalletSourceStatus;
  lastScanned?: string;
  nextRescan?: string;
  metrics?: WhaleStrategyMetrics;
};

type WhaleWatchlistResponse = {
  sourcePolicy: string;
  scannedAt: string;
  wallets: WhaleWatchlistItem[];
};

type WhaleScanResponse = WalletScanResult & {
  sourcePolicy: string;
};

type TelegramStatusResponse = {
  configured: boolean;
  whaleAlertsEnabled: boolean;
  signalsEnabled: boolean;
  mode: string;
  botTokenMasked?: string;
  signalsChatConfigured: boolean;
  devChatConfigured: boolean;
  status: "CONFIGURED" | "NOT_CONFIGURED" | "DISABLED" | "MISSING_CHAT_ID";
};

type TelegramActionResult = {
  status: string;
  reason: string;
  messageId?: number;
};
type OddsLayerResponse = {
  status: "CONNECTED" | "PARTIAL" | "NOT_CONNECTED" | "FAILED";
  provider: string;
  sourceUrl?: string;
  keyConfigured: boolean;
  supportedMarkets: string[];
  priceAvailable: boolean;
  officialBetEligibility: boolean;
  reason: string;
  odds?: unknown[];
  error?: string;
};

type PaperTestState = {
  started: boolean;
  startedAt?: string;
  day: number;
  daysElapsed: number;
  endsAt?: string;
  realMoneyTrading: "OFF";
};

type PaperLedgerSummary = {
  totalOfficialPaperPicks: number;
  openPicks: number;
  settledPicks: number;
  wins: number;
  losses: number;
  pushes: number;
  voids: number;
  winRate: number;
  roi: number;
  totalStakedUnits: number;
  pnlUnits: number;
  averageConfidence: number;
  averageModelScore: number;
  averageClv: number | null;
  modelLeans: {
    total: number;
    open: number;
    settled: number;
    correct: number;
    incorrect: number;
    accuracy: number;
  };
};

type PaperPerformanceResponse = PaperLedgerSummary & {
  generatedAt: string;
  realMoneyTrading: "OFF";
  paperTest: PaperTestState;
  ledgerPath: string;
  modelLeanLedgerPath: string;
  serverPersistence: boolean;
  note: string;
};

type DailyReportResponse = {
  generatedAt: string;
  date: string;
  signalsSent: number;
  eliteSignals: number;
  strongBuys: number;
  winRate: number;
  roi: number;
  pnl: number;
  averageClv: number | null;
  paperLedger?: PaperLedgerSummary;
  paperTest?: PaperTestState;
  noBetReasons?: { reason: string; count: number }[];
};

function Badge({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center justify-center border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.15em] ${className}`}>
      {children}
    </span>
  );
}

function StatusBadge({ status }: { status?: AstroddsSourceStatus }) {
  return <Badge className={statusClass[status ?? "NOT_CONNECTED"]}>{(status ?? "NOT_CONNECTED").replace(/_/g, " ")}</Badge>;
}

function WhaleSourceBadge({ status }: { status?: WalletSourceStatus }) {
  const className =
    status === "CONNECTED"
      ? "border-emerald-300/55 bg-emerald-400/12 text-emerald-100"
      : status === "PARTIAL"
        ? "border-yellow-300/55 bg-yellow-400/12 text-yellow-100"
        : status === "FAILED"
          ? "border-red-300/65 bg-red-500/15 text-red-100"
          : "border-slate-300/35 bg-slate-400/10 text-slate-200";

  return <Badge className={className}>{(status ?? "NOT_CONNECTED").replace(/_/g, " ")}</Badge>;
}

function TelegramStatusBadge({ status }: { status?: TelegramStatusResponse["status"] | string }) {
  const className =
    status === "CONFIGURED" || status === "SENT"
      ? "border-emerald-300/55 bg-emerald-400/12 text-emerald-100"
      : status === "DISABLED"
        ? "border-yellow-300/55 bg-yellow-400/12 text-yellow-100"
        : status === "MISSING_CHAT_ID" || status === "NOT_CONFIGURED" || status === "FAILED"
          ? "border-red-300/65 bg-red-500/15 text-red-100"
          : "border-slate-300/35 bg-slate-400/10 text-slate-200";

  return <Badge className={className}>{(status ?? "UNKNOWN").replace(/_/g, " ")}</Badge>;
}

function DiagnosticBadge({ status }: { status?: AstroddsDiagnosticStatus }) {
  const label = status === "CONNECTED_BROWSER" ? "CONNECTED VIA BROWSER FALLBACK" : (status ?? "NOT_CONNECTED").replace(/_/g, " ");
  return <Badge className={diagnosticStatusClass[status ?? "NOT_CONNECTED"]}>{label}</Badge>;
}

function DecisionBadge({ decision }: { decision?: AstroddsDecision }) {
  return <Badge className={decisionClass[decision ?? "NONE"]}>{displayDecision(decision)}</Badge>;
}

function DataQualityBadge({ quality }: { quality?: string }) {
  const className =
    quality === "HIGH"
      ? "border-emerald-300/55 bg-emerald-400/12 text-emerald-100"
      : quality === "MEDIUM"
        ? "border-cyan-300/45 bg-cyan-400/10 text-cyan-100"
        : quality === "LOW"
          ? "border-yellow-300/55 bg-yellow-400/12 text-yellow-100"
          : "border-red-300/55 bg-red-400/12 text-red-100";

  return <Badge className={className}>{quality ?? "VERY LOW"}</Badge>;
}

function PaperStatusBadge({ status }: { status: AstroddsPaperTradeStatus }) {
  const className =
    status === "WIN"
      ? "border-emerald-300/55 bg-emerald-400/12 text-emerald-100"
      : status === "LOSS"
        ? "border-red-300/55 bg-red-400/12 text-red-100"
        : status === "VOID"
          ? "border-slate-300/35 bg-slate-400/10 text-slate-200"
          : status === "UNKNOWN"
            ? "border-yellow-300/55 bg-yellow-400/12 text-yellow-100"
            : "border-cyan-300/45 bg-cyan-400/10 text-cyan-100";

  return <Badge className={className}>{status}</Badge>;
}

function teamInitials(name?: string) {
  return (name ?? "MLB")
    .split(/\s+/)
    .filter(Boolean)
    .slice(-2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function shortContext(value?: string, fallback = "--") {
  if (!value) return fallback;
  return value.length > 96 ? `${value.slice(0, 93)}...` : value;
}

function sampleSummary(sample: unknown) {
  if (!sample || typeof sample !== "object") return "No sample returned.";
  const record = sample as Record<string, unknown>;
  const title =
    record.sampleMarketTitle ??
    record.sampleGame ??
    record.testLocation ??
    record.sampleGameTitle ??
    (Array.isArray(record.tests) ? `${record.tests.length} matching samples` : undefined);

  if (typeof title === "string") return title;
  if (typeof title === "number") return title.toString();
  return "Sample returned. Open raw JSON for details.";
}

function sourceModeLabel(mode?: string, status?: AstroddsDiagnosticStatus) {
  if (mode === "BROWSER_FALLBACK" || status === "CONNECTED_BROWSER") return "Browser Fallback";
  if (mode === "SERVER" || status === "CONNECTED_SERVER" || status === "CONNECTED") return "Server";
  if (mode === "FAILED" || status === "FAILED") return "Failed";
  return "Not Connected";
}

function Panel({
  id,
  title,
  kicker,
  children,
  action,
}: {
  id: string;
  title: string;
  kicker?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section id={id} className="astro-panel scroll-mt-28 p-4 md:p-5">
      <div className="mb-4 flex flex-col gap-3 border-b border-white/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          {kicker ? <p className="text-[10px] font-black uppercase tracking-[0.28em] text-[#d6af55]">{kicker}</p> : null}
          <h2 className="mt-1 text-xl font-black uppercase tracking-[0.08em] text-white md:text-2xl">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function modelLeanForGame(game: AstroddsGameScan) {
  const pick = game.modelPick;
  if (pick) {
    const team = pick.modelLeanTeam ?? "WAIT";
    return {
      label: "MODEL PICK / DATA ONLY",
      action: pick.action === "WAIT_FOR_ODDS" ? "WAIT FOR ODDS" : "WAIT",
      team,
      confidence: pick.modelConfidence,
      score: pick.modelScore,
      quality: pick.dataQuality,
      reason: pick.modelReason,
      blocked: pick.officialBetBlockedReason,
    };
  }

  const pitcher = pitcherStatus(game);
  const weather = game.weather?.status ?? "NOT_CONNECTED";
  const parts = [
    pitcher === "CONNECTED" ? "probable pitcher context available" : pitcher === "PARTIAL" ? "pitcher context partial" : "pitcher context missing",
    weather === "CONNECTED" ? "weather connected" : weather === "PARTIAL" ? "weather partial" : "weather missing",
    game.venue ? `venue: ${game.venue}` : "venue TBD",
  ];

  return {
    label: "MODEL LEAN / DATA ONLY",
    action: "WAIT",
    team: "WAIT",
    confidence: 0,
    score: 0,
    quality: "F",
    reason: `No official bet - no matched Polymarket entry price. Public MLB data loaded: ${parts.join(", ")}.`,
    blocked: "No official bet - no matched Polymarket entry price.",
  };
}

function modelPickText(game: AstroddsGameScan) {
  const lean = modelLeanForGame(game);
  return lean.team && lean.team !== "WAIT" ? `Lean ${lean.team}` : "WAIT";
}

function modelActionClass(action: string) {
  return action === "WAIT FOR ODDS"
    ? "border-cyan-300/45 bg-cyan-400/10 text-cyan-100"
    : "border-yellow-300/45 bg-yellow-400/10 text-yellow-100";
}

function statsApiHealthItems(result?: AstroddsScanResult | null) {
  const games = result?.games.filter((game) => game.sport === "MLB" && !game.source.toLowerCase().includes("market-only")) ?? [];
  const count = (status: AstroddsSourceStatus, selector: (game: AstroddsGameScan) => AstroddsSourceStatus | undefined) =>
    games.filter((game) => selector(game) === status).length;

  return [
    ["Schedule", games.length, games.length],
    ["Standings", count("CONNECTED", (game) => game.mlbContext?.statsApiHealth.standings), games.length],
    ["Recent Form", count("CONNECTED", (game) => game.mlbContext?.statsApiHealth.recentForm), games.length],
    ["Pitcher Details", count("CONNECTED", (game) => game.mlbContext?.statsApiHealth.pitcherDetails), games.length],
    ["Linescore", count("CONNECTED", (game) => game.mlbContext?.statsApiHealth.linescore), games.length],
  ] as const;
}
function metric(label: string, value: string, detail: string, icon: typeof Gauge) {
  const Icon = icon;

  return (
    <div className="astro-metric p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">{label}</p>
        <Icon className="size-4 text-[#f1d27a]" aria-hidden="true" />
      </div>
      <p className="mt-3 text-2xl font-black text-white">{value}</p>
      <p className="mt-1 text-xs font-bold text-slate-400">{detail}</p>
    </div>
  );
}

function formatDate(value?: string) {
  if (!value) return "TBD";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function formatPrice(price?: number) {
  return typeof price === "number" ? price.toFixed(2) : "--";
}

function currency(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}$${value.toFixed(0)}`;
}

function compactCurrency(value?: number) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const sign = value > 0 ? "+" : "";
  const abs = Math.abs(value);
  const suffix = abs >= 1_000_000 ? `${(abs / 1_000_000).toFixed(1)}M` : abs >= 1_000 ? `${(abs / 1_000).toFixed(1)}K` : abs.toFixed(0);
  return `${sign}$${suffix}`;
}

function numberText(value?: number) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function formatPercent(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

function formatRoi(value: number) {
  return formatPercent(value * 100);
}

function formatProbability(value?: number) {
  return typeof value === "number" && Number.isFinite(value) ? `${Math.round(value * 100)}%` : "--";
}

function formatEdge(value?: number) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}%`;
}

function formatExpectedValue(value?: number) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}% EV`;
}

function paperTradeId(market: AstroddsMarketScan) {
  return `${market.marketId}-${market.assetId ?? market.conditionId ?? market.pick}-${market.pick}`;
}

function gamePkFromId(game: AstroddsGameScan) {
  const parsed = game.id.match(/(\d{4,})/)?.[1];
  return parsed ? Number(parsed) : undefined;
}

function paperMarketType(market: AstroddsMarketScan) {
  if (market.betType === "MONEYLINE") return "MONEYLINE";
  if (market.betType === "SPREAD") return "RUN_LINE";
  if (market.betType === "TOTAL") return "TOTAL";
  if (market.betType === "PROP") return "PROP";
  return "OTHER";
}

function tradeLineFromMarket(market: AstroddsMarketScan) {
  const text = `${market.pick} ${market.marketTitle}`;
  const total = text.match(/(?:o\/u|over\/under|total|over|under)\s*([0-9]+(?:\.[0-9]+)?)/i)?.[1];
  const spread = text.match(/([+-]\s*\d+(?:\.\d+)?)/)?.[1]?.replace(/\s+/g, "");
  const parsed = Number(total ?? spread);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function normalizePaperStatus(status?: string, result?: string): AstroddsPaperTradeStatus {
  const text = `${status ?? ""} ${result ?? ""}`.toUpperCase();
  if (/\b(WIN|WON|WINNER)\b/.test(text)) return "WIN";
  if (/\b(LOSS|LOST|LOSER)\b/.test(text)) return "LOSS";
  if (/\bVOID|PUSH\b/.test(text)) return "VOID";
  if (/\bUNKNOWN\b/.test(text)) return "UNKNOWN";
  return "PENDING";
}

function isPaperTrade(value: unknown): value is PaperTrade {
  if (!value || typeof value !== "object") return false;
  const trade = value as Partial<PaperTrade> & { result?: string };
  return Boolean(trade.id && trade.market && trade.pick && trade.createdAt);
}

function normalizeStoredPaperTrade(trade: Partial<PaperTrade> & { result?: string }): PaperTrade {
  const legacyStatus = normalizePaperStatus(trade.status, trade.result);

  return {
    id: trade.id ?? `paper-${Date.now()}`,
    sport: trade.sport ?? "MLB",
    gameId: trade.gameId,
    gamePk: trade.gamePk,
    homeTeam: trade.homeTeam,
    awayTeam: trade.awayTeam,
    game: trade.game ?? "Unknown game",
    market: trade.market ?? "Unknown market",
    marketType: trade.marketType ?? "Other",
    pick: trade.pick ?? "Unknown pick",
    line: typeof trade.line === "number" ? trade.line : undefined,
    decision: trade.decision ?? "WAIT",
    status: legacyStatus,
    confidence: trade.confidence ?? "NO BET",
    score: typeof trade.score === "number" ? trade.score : 0,
    entryPrice: typeof trade.entryPrice === "number" ? trade.entryPrice : 0,
    stake: typeof trade.stake === "number" ? trade.stake : DEFAULT_PAPER_STAKE,
    bankroll: typeof trade.bankroll === "number" ? trade.bankroll : STARTING_BANKROLL,
    why: trade.why ?? "Saved before rationale persistence was added.",
    pnl: typeof trade.pnl === "number" && Number.isFinite(trade.pnl) ? trade.pnl : 0,
    roi: typeof trade.roi === "number" && Number.isFinite(trade.roi) ? trade.roi : 0,
    dataConfidence: trade.dataConfidence ?? "PARTIAL",
    dataStatuses: trade.dataStatuses ?? {
      pitchers: "NOT_CONNECTED",
      weather: "NOT_CONNECTED",
      lineups: "NOT_CONNECTED",
      injuries: "NOT_CONNECTED",
      polymarket: "CONNECTED",
    },
    walletSupport: trade.walletSupport ?? "No wallet support attached.",
    createdAt: trade.createdAt ?? new Date().toISOString(),
    resolvedAt: trade.resolvedAt,
    result: trade.result,
    sourceData: trade.sourceData,
  };
}

function loadStoredPaperTrades() {
  try {
    const stored = window.localStorage.getItem(PAPER_TRADES_STORAGE_KEY);
    const parsed = stored ? (JSON.parse(stored) as unknown) : [];
    return Array.isArray(parsed) ? parsed.filter(isPaperTrade).map((trade) => normalizeStoredPaperTrade(trade)) : [];
  } catch {
    return [];
  }
}

function bestMarketForGame(game: AstroddsGameScan) {
  if (!game.markets.length) return undefined;

  return [...game.markets].sort((a, b) => {
    const decisionRank: Record<string, number> = {
      ELITE: 6,
      STRONG_BUY: 5,
      BUY: 4,
      WATCH: 3,
      WAIT: 2,
      AVOID: 1,
    };

    return (
      (decisionRank[b.decision ?? "WAIT"] ?? 0) - (decisionRank[a.decision ?? "WAIT"] ?? 0) ||
      (b.score?.total ?? 0) - (a.score?.total ?? 0) ||
      (b.orderBook?.orderBookScore ?? 0) - (a.orderBook?.orderBookScore ?? 0) ||
      (b.volume ?? 0) - (a.volume ?? 0)
    );
  })[0];
}

function rowsFromResult(result?: AstroddsScanResult | null): ScannerRow[] {
  if (!result) return [];
  return result.games
    .filter((game) => game.sport === "MLB" && !game.source.toLowerCase().includes("market-only"))
    .map((game) => ({ game, market: bestMarketForGame(game) }));
}


function normalizedModelKeyPart(value?: string) {
  return (value ?? "unknown").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "unknown";
}

function modelStartKey(value?: string) {
  if (!value) return "tbd";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return normalizedModelKeyPart(value);
  return date.toISOString();
}

function modelStartDate(value?: string) {
  const key = modelStartKey(value);
  return key === "tbd" ? key : key.slice(0, 10);
}

function dataQualityRankValue(quality?: string) {
  const normalized = (quality ?? "").toUpperCase();
  if (normalized === "A" || normalized === "HIGH") return 5;
  if (normalized === "B" || normalized === "MEDIUM") return 4;
  if (normalized === "C") return 3;
  if (normalized === "D" || normalized === "LOW") return 2;
  return 1;
}

function isOfficialModelRow(row: ScannerRow) {
  return Boolean(row.market && typeof row.market.currentPrice === "number" && row.market.currentPrice > 0);
}

function modelPickDedupeKey(row: ScannerRow) {
  const gamePk = gamePkFromId(row.game);
  const marketType = row.market ? marketTypeLabel(row.market) : "DATA_ONLY";
  if (gamePk) return `gamePk:${gamePk}:${marketType}`;
  return [
    "fallback",
    normalizedModelKeyPart(row.game.awayTeam),
    normalizedModelKeyPart(row.game.homeTeam),
    modelStartKey(row.game.startTime),
    marketType,
  ].join(":");
}

function compareModelPickRows(a: ScannerRow, b: ScannerRow) {
  const aPick = a.game.modelPick;
  const bPick = b.game.modelPick;
  const aStart = new Date(a.game.startTime ?? "").getTime();
  const bStart = new Date(b.game.startTime ?? "").getTime();
  return (
    Number(isOfficialModelRow(b)) - Number(isOfficialModelRow(a)) ||
    (bPick?.modelScore ?? 0) - (aPick?.modelScore ?? 0) ||
    (bPick?.modelConfidence ?? 0) - (aPick?.modelConfidence ?? 0) ||
    dataQualityRankValue(bPick?.dataQuality) - dataQualityRankValue(aPick?.dataQuality) ||
    (Number.isFinite(aStart) ? aStart : Number.MAX_SAFE_INTEGER) - (Number.isFinite(bStart) ? bStart : Number.MAX_SAFE_INTEGER)
  );
}

function dedupeModelPickRows(rawRows: ScannerRow[]) {
  const sorted = [...rawRows].sort(compareModelPickRows);
  const seen = new Map<string, ScannerRow>();
  const duplicateExamples: string[] = [];

  for (const row of sorted) {
    const key = modelPickDedupeKey(row);
    if (seen.has(key)) {
      if (duplicateExamples.length < 5) {
        duplicateExamples.push(`${row.game.game} (${modelStartDate(row.game.startTime)}) duplicate key ${key}`);
      }
      continue;
    }
    seen.set(key, row);
  }

  return {
    rows: Array.from(seen.values()),
    rawCount: rawRows.length,
    dedupedCount: seen.size,
    removedCount: Math.max(0, rawRows.length - seen.size),
    duplicateExamples,
  };
}


function modelSeriesKey(row: ScannerRow) {
  return `${normalizedModelKeyPart(row.game.awayTeam)}@${normalizedModelKeyPart(row.game.homeTeam)}`;
}

function rowStartMs(row: ScannerRow) {
  const value = new Date(row.game.startTime ?? "").getTime();
  return Number.isFinite(value) ? value : Number.MAX_SAFE_INTEGER;
}

function filterModelSeriesRows(rows: ScannerRow[], showSeriesGames: boolean) {
  if (showSeriesGames) return { rows, hiddenSeriesGames: 0 };
  const groups = new Map<string, ScannerRow[]>();
  for (const row of rows) {
    const key = modelSeriesKey(row);
    groups.set(key, [...(groups.get(key) ?? []), row]);
  }

  const kept: ScannerRow[] = [];
  let hiddenSeriesGames = 0;
  for (const groupRows of groups.values()) {
    const sorted = [...groupRows].sort((a, b) => rowStartMs(a) - rowStartMs(b));
    const firstDate = modelStartDate(sorted[0]?.game.startTime);
    const sameDateRows = sorted.filter((row) => modelStartDate(row.game.startTime) === firstDate);
    kept.push(...sameDateRows);
    hiddenSeriesGames += Math.max(0, sorted.length - sameDateRows.length);
  }

  return { rows: kept.sort(compareModelPickRows), hiddenSeriesGames };
}

function confidenceClass(value?: number) {
  if ((value ?? 0) >= 85) return "border-emerald-300/60 bg-emerald-400/15 text-emerald-50";
  if ((value ?? 0) >= 74) return "border-green-300/55 bg-green-400/12 text-green-100";
  if ((value ?? 0) >= 60) return "border-yellow-300/55 bg-yellow-400/12 text-yellow-100";
  return "border-slate-300/35 bg-slate-400/10 text-slate-200";
}

function modelDisplayStatus(row: ScannerRow) {
  const pick = row.game.modelPick;
  const score = pick?.modelScore ?? 0;
  const official = isOfficialModelRow(row);
  if (official && score >= 82 && canPaperTradePick(row.market as AstroddsMarketScan)) return "STRONG BUY";
  if (official && score >= 74 && canPaperTradePick(row.market as AstroddsMarketScan)) return "BUY";
  if (official && score >= 60) return "WATCH";
  if (!official && score >= 60) return "DATA ONLY - WAIT FOR ODDS";
  if (!official) return "OFFICIAL BET BLOCKED";
  return "WAIT";
}

function modelDisplayStatusClass(status: string) {
  if (status === "STRONG BUY") return decisionClass.STRONG_BUY;
  if (status === "BUY") return decisionClass.BUY;
  if (status === "WATCH") return decisionClass.WATCH;
  if (status.startsWith("DATA ONLY")) return "border-cyan-300/45 bg-cyan-400/10 text-cyan-100";
  if (status === "OFFICIAL BET BLOCKED") return "border-yellow-300/45 bg-yellow-400/10 text-yellow-100";
  return decisionClass.WAIT;
}

function compactPitcherMatchup(game: AstroddsGameScan) {
  const text = game.keyPlayerStatus || "Pitchers not posted";
  return text
    .replace(/Probable pitchers?:?/i, "")
    .replace(/Starting pitchers?:?/i, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80) || "Pitchers not posted";
}

function compactWeatherFactor(game: AstroddsGameScan) {
  if (!game.weather?.summary) return "Weather source needed";
  return game.weather.summary.replace(/\s+/g, " ").slice(0, 48);
}

function compactModelFactors(row: ScannerRow) {
  const statuses = dataStatuses(row.game, row.market);
  const factors = [
    compactWeatherFactor(row.game),
    `Pitchers: ${compactPitcherMatchup(row.game)}`,
  ];
  if (statuses.lineups !== "CONNECTED") factors.push("Lineups missing");
  if (statuses.injuries !== "CONNECTED") factors.push("No injury feed");
  if (!row.market) factors.push("Odds missing");
  return factors.slice(0, 5).join(" | ");
}

function compactMarketLabel(row: ScannerRow) {
  if (row.market) return marketTypeLabel(row.market);
  return "Data Only";
}

function compactEntryLabel(row: ScannerRow) {
  if (row.market) return `${formatPrice(row.market.currentPrice)} Polymarket`;
  return "Waiting for odds";
}
function doubleheaderLabel(row: ScannerRow, rows: ScannerRow[]) {
  const date = modelStartDate(row.game.startTime);
  const away = normalizedModelKeyPart(row.game.awayTeam);
  const home = normalizedModelKeyPart(row.game.homeTeam);
  const sameGameSet = rows
    .filter((candidate) => modelStartDate(candidate.game.startTime) === date)
    .filter((candidate) => normalizedModelKeyPart(candidate.game.awayTeam) === away && normalizedModelKeyPart(candidate.game.homeTeam) === home)
    .sort((a, b) => new Date(a.game.startTime ?? "").getTime() - new Date(b.game.startTime ?? "").getTime());
  if (sameGameSet.length <= 1) return undefined;
  const index = sameGameSet.findIndex((candidate) => candidate.game.id === row.game.id);
  return `Game ${index + 1}`;
}

type DecisionCenterReason = { reason: string; count: number };
type DecisionQualityItem = { label: string; value: string; tone: "green" | "yellow" | "red" };


function lineupStatusLabel(status?: string) {
  if (status === "confirmed") return "Confirmed";
  if (status === "projected") return "Projected";
  return "Missing";
}

function lineupImpactTone(status?: string): "green" | "yellow" | "red" {
  if (status === "confirmed") return "green";
  if (status === "projected") return "yellow";
  return "red";
}

function lineupImpactDisplay(signal?: UnifiedAstroddsSignal) {
  if (!signal?.lineupImpact) return "Missing";
  return `${Math.round(signal.lineupImpact.lineupImpactScore * 100)}%`;
}

function lineupKeyReasons(signal?: UnifiedAstroddsSignal) {
  if (!signal?.lineupImpact) return ["Lineup data unavailable"];
  return [...signal.lineupImpact.lineupReasons, ...signal.lineupImpact.downgradeReasons].slice(0, 3);
}
function decisionToneClass(tone: "green" | "yellow" | "red") {
  if (tone === "green") return "border-emerald-300/45 bg-emerald-400/10 text-emerald-100";
  if (tone === "yellow") return "border-yellow-300/45 bg-yellow-400/10 text-yellow-100";
  return "border-red-300/55 bg-red-500/12 text-red-100";
}

function normalizeDecisionStatus(status?: string) {
  return (status ?? "NOT_CONNECTED").replace(/_/g, " ");
}

function qualityTone(status?: string): "green" | "yellow" | "red" {
  const normalized = (status ?? "").toUpperCase();
  if (normalized.includes("CONNECTED") && !normalized.includes("NOT")) return "green";
  if (normalized.includes("PARTIAL") || normalized.includes("BROWSER") || normalized.includes("WALLET") || normalized.includes("BONUS")) return "yellow";
  return "red";
}

function appendReason(reasons: Map<string, number>, reason: string, count = 1) {
  if (count <= 0) return;
  reasons.set(reason, (reasons.get(reason) ?? 0) + count);
}

function deriveNoBetReasons(input: {
  result: AstroddsScanResult | null;
  rows: ScannerRow[];
  topQualifiedSignals: UnifiedAstroddsSignal[];
  missingDataWarnings: string[];
  hiddenSeriesGames: number;
}): DecisionCenterReason[] {
  const reasons = new Map<string, number>();
  const { result, rows, topQualifiedSignals, missingDataWarnings, hiddenSeriesGames } = input;

  if (!result) {
    appendReason(reasons, "Run an MLB scan to calculate current no-bet reasons", 1);
    return Array.from(reasons, ([reason, count]) => ({ reason, count }));
  }

  const gamesFetched = result.diagnostics.sportApi.gamesFetched;
  const matchedGames = result.diagnostics.matching.matchedGamesCount;
  const dataOnlyRows = rows.filter((row) => !row.market).length;
  const staleOrMissingOdds = rows.filter((row) => !row.market || !row.market.currentPrice).length;
  const orderBookBlocked = rows.filter((row) => row.market && (!row.market.orderBook || row.market.orderBook.status === "POOR" || row.market.orderBook.status === "NO_LIQUIDITY")).length;
  const lineupMissing = rows.filter((row) => dataStatuses(row.game, row.market).lineups !== "CONNECTED").length;
  const injuryMissing = rows.filter((row) => dataStatuses(row.game, row.market).injuries !== "CONNECTED").length;
  const pitcherMissing = rows.filter((row) => dataStatuses(row.game, row.market).pitchers !== "CONNECTED").length;
  const lowEdgeSignals = rows.filter((row) => row.market && ((row.market.probability?.edge ?? row.market.edge?.edge ?? 0) < 0.05)).length;

  if (gamesFetched > 0 && matchedGames === 0) appendReason(reasons, "No clean matched Polymarket MLB market", gamesFetched);
  appendReason(reasons, "Games missing real odds or entry price", staleOrMissingOdds);
  appendReason(reasons, "Model leans are data-only until odds connect", dataOnlyRows);
  appendReason(reasons, "Order book missing or blocked", orderBookBlocked);
  appendReason(reasons, "Edge below official threshold", lowEdgeSignals);
  appendReason(reasons, "Lineup not confirmed yet", lineupMissing);
  appendReason(reasons, "Injury/news source missing or partial", injuryMissing);
  appendReason(reasons, "Pitcher data missing or partial", pitcherMissing);
  appendReason(reasons, "Series games hidden by display filter", hiddenSeriesGames);

  for (const warning of missingDataWarnings.slice(0, 3)) appendReason(reasons, warning, 1);
  if (!topQualifiedSignals.length) appendReason(reasons, "No official +EV paper pick passed all guardrails", Math.max(1, rows.length));

  return Array.from(reasons, ([reason, count]) => ({ reason, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6);
}

function watchlistNeeds(row: ScannerRow) {
  const statuses = dataStatuses(row.game, row.market);
  const needs: string[] = [];
  if (!row.market) needs.push("clean matched odds");
  if (statuses.pitchers !== "CONNECTED") needs.push("pitcher confirmation");
  if (statuses.lineups !== "CONNECTED") needs.push("lineup not confirmed yet");
  if (statuses.injuries !== "CONNECTED") needs.push("injury/news feed");
  if (!row.market?.orderBook) needs.push("order book liquidity");
  if (row.market && ((row.market.probability?.edge ?? row.market.edge?.edge ?? 0) < 0.05)) needs.push("better edge or price");
  return needs.slice(0, 4);
}

function whaleBonusStatus(signal: UnifiedAstroddsSignal) {
  if (signal.whaleSupport === "CONFLICT" || signal.copyability === "CONFLICT") return "CONFLICT";
  if (signal.whaleSupport === "STALE_ENTRY" || signal.copyability === "STALE_ENTRY" || signal.copyability === "TOO_LATE") return "STALE";
  if (signal.copyability === "COPYABLE_NOW" || signal.copyability === "NEAR_WHALE_ENTRY") return "COPYABLE BONUS";
  return "WATCH ONLY";
}

function whaleBonusStatusClass(status: string) {
  if (status === "COPYABLE BONUS") return "border-emerald-300/45 bg-emerald-400/10 text-emerald-100";
  if (status === "CONFLICT" || status === "STALE") return "border-red-300/55 bg-red-500/12 text-red-100";
  return "border-yellow-300/45 bg-yellow-400/10 text-yellow-100";
}
function sourceStatusRows(result?: AstroddsScanResult | null) {
  const status = result?.sourceStatus;

  return [
    ["Polymarket markets", status?.polymarket ?? "NOT_CONNECTED", "Gamma API market discovery; CLOB orderbook prepared for later pricing depth."],
    ["Sport data", status?.sportData ?? "NOT_CONNECTED", "MLB StatsAPI where available; TheSportsDB free schedule for selected sports."],
    ["Weather", status?.weather ?? "NOT_CONNECTED", "Open-Meteo for outdoor sports when venue coordinates are available."],
    ["Lineups", status?.lineups ?? "NOT_CONNECTED", "Confirmed lineups are honest partial/not-connected until a source is attached."],
    ["Injuries", status?.injuries ?? "NOT_CONNECTED", "Free injury feeds are not treated as connected unless a provider returns data."],
    ["Key players", status?.keyPlayers ?? "NOT_CONNECTED", "Pitchers, goalies, QB/star status, starting XI, fighter news."],
    ["Wallet layer", status?.wallets ?? "WALLET_LED", "Bonus confirmation only; never the main buy trigger."],
  ] as const;
}

function diagnosticCards(result?: AstroddsScanResult | null) {
  const diagnostics = result?.diagnostics;

  return [
    {
      label: "Polymarket",
      icon: RadioTower,
      status: diagnostics?.polymarket.status ?? "NOT_CONNECTED",
      primary: `Markets fetched: ${diagnostics?.polymarket.marketsFetched ?? 0}`,
      secondary: `MLB candidates: ${diagnostics?.polymarket.mlbMarketsDetected ?? diagnostics?.polymarket.sportsMarketsDetected ?? 0} | Single-game: ${diagnostics?.polymarket.singleGameMlbMarketsDetected ?? 0} | Matched: ${diagnostics?.polymarket.marketsMatchedToGames ?? 0}`,
      issue: diagnostics?.polymarket.error,
      sourceUrl: diagnostics?.polymarket.sourceUrl,
      sourceMode: diagnostics?.polymarket.sourceMode,
      rawDetail: `Raw events: ${diagnostics?.polymarket.rawEventsFetched ?? 0} | Raw markets: ${diagnostics?.polymarket.rawMarketsFetched ?? 0} | Rejected non-MLB: ${diagnostics?.polymarket.rejectedNonMlbMarkets ?? 0} | Futures rejected: ${diagnostics?.polymarket.futuresRejected ?? 0} | Wrong sport rejected: ${diagnostics?.polymarket.wrongSportsRejected ?? 0} | No MLB team match: ${diagnostics?.polymarket.noMlbTeamMatchRejected ?? 0} | Queries: ${diagnostics?.polymarket.teamSearchQueriesAttempted?.length ?? 0}`,
    },
    {
      label: "MLB API",
      icon: DatabaseZap,
      status: diagnostics?.sportApi.status ?? "NOT_CONNECTED",
      primary: `Games fetched: ${diagnostics?.sportApi.gamesFetched ?? 0}`,
      secondary: `Pitchers found: ${diagnostics?.sportApi.probablePitchersFound ?? 0} | Venues found: ${diagnostics?.sportApi.venuesFound ?? 0}`,
      issue: diagnostics?.sportApi.error,
      sourceUrl: diagnostics?.sportApi.sourceUrl,
      sourceMode: diagnostics?.sportApi.sourceMode,
      rawDetail: undefined,
    },
    {
      label: "Weather",
      icon: Activity,
      status: diagnostics?.weather.status ?? "NOT_CONNECTED",
      primary: `Weather fetched: ${diagnostics?.weather.weatherResultsFetched ?? 0}`,
      secondary: `Mapped venues: ${diagnostics?.weather.gamesWithMappedCityOrStadium ?? 0}`,
      issue: diagnostics?.weather.error,
      sourceUrl: diagnostics?.weather.sourceUrl,
      sourceMode: diagnostics?.weather.sourceMode,
      rawDetail: undefined,
    },
    {
      label: "Matching",
      icon: Gauge,
      status: diagnostics?.matching.status ?? "NOT_CONNECTED",
      primary: `Matched games: ${diagnostics?.matching.matchedGamesCount ?? 0} / ${diagnostics?.matching.gamesCount ?? 0}`,
      secondary: `Markets checked: ${diagnostics?.matching.polymarketMarketsCount ?? 0} | Market matches: ${diagnostics?.matching.matchedMarketsCount ?? 0}`,
      issue: diagnostics?.matching.error,
      sourceUrl: undefined,
      sourceMode: diagnostics?.matching.sourceMode,
      rawDetail: undefined,
    },
    {
      label: "Order Book",
      icon: LineChart,
      status: diagnostics?.orderBook.status ?? "NOT_CONNECTED",
      primary: `Books fetched: ${diagnostics?.orderBook.orderBooksFetched ?? 0} / ${diagnostics?.orderBook.orderBooksRequested ?? 0}`,
      secondary: `Failed: ${diagnostics?.orderBook.orderBooksFailed ?? 0} | $50 fill simulated`,
      issue: diagnostics?.orderBook.error,
      sourceUrl: diagnostics?.orderBook.sourceUrl,
      sourceMode: diagnostics?.orderBook.sourceMode,
      rawDetail: undefined,
    },
  ] as const;
}

function marketTypeLabel(market?: AstroddsMarketScan) {
  if (!market) return "Other";
  if (market.betType === "MONEYLINE") return "Moneyline";
  if (market.betType === "SPREAD") return "Run Line";
  if (market.betType === "TOTAL") return "Over Under";
  if (market.betType === "PROP") return "Prop";
  return "Other";
}

function extractTotalLine(market: AstroddsMarketScan) {
  const text = `${market.marketTitle} ${market.pick}`;
  const match = text.match(/(?:o\/u|over\/under|total|over|under)\s*([0-9]+(?:\.[0-9]+)?)/i);
  return match?.[1];
}

function clearBetText(market: AstroddsMarketScan) {
  if (market.edge?.exactPick) return market.edge.exactPick;
  const price = formatPrice(market.currentPrice);
  if (market.betType === "MONEYLINE") return `Bet ${market.pick} Moneyline at ${price}`;
  if (market.betType === "SPREAD") return `Bet ${market.pick} Run Line at ${price}`;
  if (market.betType === "TOTAL") {
    const line = extractTotalLine(market);
    const side = line && !market.pick.includes(line) ? `${market.pick} ${line}` : market.pick;
    return `Bet ${side} at ${price}`;
  }
  return `Bet ${market.pick} at ${price}`;
}

function orderBookSummary(market?: AstroddsMarketScan) {
  if (!market) return "Waiting for matched Polymarket token.";
  if (!market.assetId) return "Not available - no CLOB token ID.";
  if (!market.orderBook) return "NOT CONNECTED - order book unavailable.";
  const ask = typeof market.orderBook.bestAsk === "number" ? market.orderBook.bestAsk.toFixed(2) : "--";
  const spread = typeof market.orderBook.spread === "number" ? market.orderBook.spread.toFixed(3) : "--";
  const slippage =
    typeof market.orderBook.estimatedSlippage === "number"
      ? market.orderBook.estimatedSlippage <= 0.01
        ? "Low"
        : market.orderBook.estimatedSlippage <= 0.04
          ? "Medium"
          : "High"
      : "Unknown";
  const fill = market.orderBook.fillStatus === "OK" ? "$50 fill OK" : market.orderBook.fillStatus === "PARTIAL" ? "$50 partial" : "Not enough liquidity";

  return `${market.orderBook.status.replace(/_/g, " ")} - Best Ask ${ask}, Spread ${spread}, ${fill}, Slippage ${slippage}`;
}

function telegramStatusForSignal(signal: UnifiedAstroddsSignal, status: TelegramStatusResponse | null) {
  if (!status?.configured) return "Telegram: NOT CONFIGURED";
  if (!status.signalsEnabled || !status.whaleAlertsEnabled) return signal.telegramEligible ? "Telegram: READY BUT DISABLED" : "Telegram: DISABLED";
  return signal.telegramEligible ? "Telegram: READY" : "Telegram: NOT ELIGIBLE";
}

function canPaperTradeSignal(signal: UnifiedAstroddsSignal) {
  return signal.paperTradeEligible && Boolean(signal.gameRef && signal.marketRef);
}

function signalOrderBookSummary(signal: UnifiedAstroddsSignal) {
  if (signal.marketRef) return orderBookSummary(signal.marketRef);
  return signal.orderBookQuality.replace(/_/g, " ");
}

function signalBetText(signal: UnifiedAstroddsSignal) {
  if (signal.entryPrice && signal.pick.includes(" at ")) return signal.pick;
  if (signal.entryPrice) return `${signal.pick} at ${formatPrice(signal.entryPrice)}`;
  return signal.pick;
}

function pitcherStatus(game: AstroddsGameScan): AstroddsSourceStatus {
  const text = game.keyPlayerStatus.toLowerCase();
  if (!game.keyPlayerStatus || text.includes("not connected") || text.includes("not posted")) return "NOT_CONNECTED";
  if (text.includes("tbd")) return "PARTIAL";
  return "CONNECTED";
}

function dataStatuses(game: AstroddsGameScan, market?: AstroddsMarketScan) {
  return {
    pitchers: pitcherStatus(game),
    weather: game.weather?.status ?? "NOT_CONNECTED",
    lineups: game.lineups?.status ?? "NOT_CONNECTED",
    injuries: game.injuries?.status ?? "NOT_CONNECTED",
    polymarket: market ? "CONNECTED" as const : "NOT_CONNECTED" as const,
  };
}

function simpleReasons(game: AstroddsGameScan, market: AstroddsMarketScan) {
  if (market.edge?.simpleWhy) return [market.edge.simpleWhy];
  const reasons: string[] = [];
  const statuses = dataStatuses(game, market);

  if (market.matchReason) reasons.push("Market is matched to a real MLB game.");
  if (market.score?.entryQuality === "EXCELLENT" || market.score?.entryQuality === "GOOD") reasons.push("Entry price is still reasonable.");
  if (statuses.pitchers === "CONNECTED") reasons.push("Pitcher matchup data is available.");
  if (statuses.pitchers !== "CONNECTED" && market.betType === "MONEYLINE") reasons.push("Pitcher data is not fully posted, confidence reduced.");
  if (statuses.weather === "CONNECTED") reasons.push("Weather is included in the model.");
  if (market.orderBook?.status === "EXCELLENT" || market.orderBook?.status === "GOOD") reasons.push("Order book supports a $50 paper entry.");
  if (!market.orderBook) reasons.push("Order book is missing, so Elite is disabled.");
  if (market.orderBook?.status === "POOR" || market.orderBook?.status === "NO_LIQUIDITY") reasons.push("Order book is weak, so this is not a buy.");
  if (market.betType === "TOTAL" && statuses.weather !== "CONNECTED") reasons.push("Weather is missing for this total, so no Strong Buy.");
  if (statuses.lineups === "NOT_CONNECTED" || statuses.injuries === "NOT_CONNECTED") reasons.push("No injury/lineup source connected yet, confidence reduced.");
  if ((market.walletSupport?.supportingWallets ?? 0) > 0) reasons.push("Wallet support is present, but only as a bonus signal.");
  if (!reasons.length) reasons.push("Data is partial, so this stays conservative.");

  return reasons.slice(0, 5);
}

function shortReason(game: AstroddsGameScan, market: AstroddsMarketScan) {
  if (market.edge) {
    const firstReason = market.edge.simpleWhy.split(". ").find(Boolean);
    return [
      `Model ${formatProbability(market.edge.modelProbability)} vs market ${formatProbability(market.edge.marketImpliedProbability)}; edge ${formatEdge(market.edge.edge)}.`,
      firstReason ? `${firstReason}.` : "",
      market.edge.dataQuality === "LOW" || market.edge.dataQuality === "VERY_LOW" ? "Data quality caps this signal." : "",
    ]
      .filter(Boolean)
      .join(" ");
  }

  const reasons = simpleReasons(game, market);
  return reasons.slice(0, 3).join(" ");
}


function officialPaperDecisionLabel(decision?: AstroddsDecision | UnifiedAstroddsSignal["decision"]) {
  if (decision === "ELITE") return "ELITE";
  if (decision === "STRONG_BUY") return "STRONG BUY";
  if (decision === "BUY") return "BUY";
  return undefined;
}

function oddsStatusBadgeClass(status?: OddsLayerResponse["status"]) {
  if (status === "CONNECTED") return "border-emerald-300/55 bg-emerald-400/12 text-emerald-100";
  if (status === "PARTIAL") return "border-yellow-300/55 bg-yellow-400/12 text-yellow-100";
  if (status === "FAILED") return "border-red-300/65 bg-red-500/15 text-red-100";
  return "border-slate-300/35 bg-slate-400/10 text-slate-200";
}
function canPaperTradePick(market: AstroddsMarketScan) {
  return (
    (market.decision === "BUY" || market.decision === "STRONG_BUY" || market.decision === "ELITE" || market.confidence === "ELITE") &&
    (market.probability?.edge ?? 0) >= 0.05 &&
    market.probability?.dataQuality !== "LOW" &&
    market.probability?.dataQuality !== "VERY_LOW" &&
    market.orderBook?.fillStatus === "OK" &&
    market.orderBook.status !== "POOR" &&
    market.orderBook.status !== "NO_LIQUIDITY"
  );
}

export default function AstrodssTerminal() {
  const [selectedSport, setSelectedSport] = useState<AstroddsSportFilter>("MLB");
  const [result, setResult] = useState<AstroddsScanResult | null>(null);
  const [scanStatus, setScanStatus] = useState<ScanStatus>("Idle");
  const [scanAttemptCount, setScanAttemptCount] = useState(0);
  const [lastScanRoute, setLastScanRoute] = useState("");
  const [scanDebugMessage, setScanDebugMessage] = useState("Run the scanner to populate live diagnostics.");
  const [hydrated, setHydrated] = useState(false);
  const [lastClickDebug, setLastClickDebug] = useState("No click captured yet.");
  const [isScanning, setIsScanning] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [error, setError] = useState("");
  const [paperTrades, setPaperTrades] = useState<PaperTrade[]>([]);
  const [paperTradesLoaded, setPaperTradesLoaded] = useState(false);
  const [cardImageMissing, setCardImageMissing] = useState(false);
  const [apiTests, setApiTests] = useState<Partial<Record<AstroddsApiTestSource, AstroddsApiTestResult>>>({});
  const [testingSource, setTestingSource] = useState<AstroddsApiTestSource | null>(null);
  const [isResolvingPaper, setIsResolvingPaper] = useState(false);
  const [paperResolveSummary, setPaperResolveSummary] = useState<ResolveSummary | null>(null);
  const [lastResolvedAt, setLastResolvedAt] = useState<string | null>(null);
  const [whaleWatchlist, setWhaleWatchlist] = useState<WhaleWatchlistItem[]>([]);
  const [whaleSourcePolicy, setWhaleSourcePolicy] = useState("ASTRODDS uses public Polymarket wallet/profile data only. No private or non-public information is used.");
  const [whaleProfiles, setWhaleProfiles] = useState<WalletProfile[]>([]);
  const [whaleMetrics, setWhaleMetrics] = useState<WhaleStrategyMetrics[]>([]);
  const [whalePositions, setWhalePositions] = useState<WalletPosition[]>([]);
  const [whaleCopyability, setWhaleCopyability] = useState<WhalePositionCopyability[]>([]);
  const [whaleConsensus, setWhaleConsensus] = useState<WhaleConsensusSignal[]>([]);
  const [whaleErrors, setWhaleErrors] = useState<string[]>([]);
  const [isScanningWhales, setIsScanningWhales] = useState(false);
  const [lastWhaleScanAt, setLastWhaleScanAt] = useState<string | null>(null);
  const [telegramStatus, setTelegramStatus] = useState<TelegramStatusResponse | null>(null);
  const [telegramTestResult, setTelegramTestResult] = useState<TelegramActionResult | null>(null);
  const [whaleAlertTestResult, setWhaleAlertTestResult] = useState<TelegramActionResult | null>(null);
  const [lastTelegramTestAt, setLastTelegramTestAt] = useState<string | null>(null);
  const [lastWhaleAlertTestAt, setLastWhaleAlertTestAt] = useState<string | null>(null);
  const [isTestingTelegram, setIsTestingTelegram] = useState(false);
  const [isTestingWhaleAlert, setIsTestingWhaleAlert] = useState(false);
  const [oddsStatus, setOddsStatus] = useState<OddsLayerResponse | null>(null);
  const [paperLedgerReport, setPaperLedgerReport] = useState<PaperPerformanceResponse | null>(null);
  const [dailyReport, setDailyReport] = useState<DailyReportResponse | null>(null);
  const [isStartingPaperTest, setIsStartingPaperTest] = useState(false);
  const [modelLeansSavedAt, setModelLeansSavedAt] = useState<string | null>(null);
  const [showAllModelPicks, setShowAllModelPicks] = useState(false);
  const [showSeriesGames, setShowSeriesGames] = useState(false);
  const lastScanClickAtRef = useRef(0);
  const lastTestClickAtRef = useRef(0);

  const rows = useMemo(() => rowsFromResult(result), [result]);
  const unifiedSignals = useMemo(
    () =>
      buildUnifiedSignals(result?.games ?? [], {
        whaleConsensus,
        telegramSignalsEnabled: Boolean(telegramStatus?.signalsEnabled),
        telegramWhaleAlertsEnabled: Boolean(telegramStatus?.whaleAlertsEnabled),
      }),
    [result?.games, telegramStatus?.signalsEnabled, telegramStatus?.whaleAlertsEnabled, whaleConsensus],
  );
  const topQualifiedSignals = unifiedSignals
    .filter((signal) => signal.decision === "ELITE" || signal.decision === "STRONG_BUY" || signal.decision === "BUY")
    .slice(0, 10);
  const bestFinalSignal = topQualifiedSignals.find((signal) => signal.decision === "ELITE" || signal.decision === "STRONG_BUY") ?? topQualifiedSignals[0];
  const strongBuySignals = topQualifiedSignals.filter((signal) => signal.decision === "ELITE" || signal.decision === "STRONG_BUY");
  const whaleWatchSignals = unifiedSignals
    .filter((signal) => signal.whaleSupport !== "NONE" && signal.signalType !== "DATA_ONLY")
    .slice(0, 8);
  const whaleBonusSignals = whaleWatchSignals.slice(0, 6);
  const dataOnlySignals = unifiedSignals.filter((signal) => signal.signalType === "DATA_ONLY").slice(0, 8);
  const decisionLineupSignal = bestFinalSignal ?? unifiedSignals.find((signal) => signal.lineupImpact.lineupStatus !== "missing") ?? unifiedSignals[0];
  const decisionLineupImpact = decisionLineupSignal?.lineupImpact;
  const decisionLineupReasons = lineupKeyReasons(decisionLineupSignal);
  const decisionNoLiveMlbData = Boolean(result && (result.diagnostics.sportApi.status === "FAILED" || (result.diagnostics.sportApi.gamesFetched === 0 && rows.length === 0)));
  const decisionSourceWarning = result?.diagnostics.sourceDiagnostics?.find((item) => item.status === "FAILED")?.errorMessage ?? result?.diagnostics.sportApi.error ?? result?.diagnostics.lastErrors[0];
  const rawModelPickRows = useMemo(
    () => rows.filter((row) => row.game.sport === "MLB" && row.game.modelPick),
    [rows],
  );
  const modelPickDedupe = useMemo(() => dedupeModelPickRows(rawModelPickRows), [rawModelPickRows]);
  const modelPickRows = modelPickDedupe.rows;
  const topModelPickSeries = useMemo(
    () => filterModelSeriesRows(modelPickRows.filter((row) => row.game.modelPick?.modelLeanSide !== "WAIT"), showSeriesGames),
    [modelPickRows, showSeriesGames],
  );
  const topModelPicks = topModelPickSeries.rows;
  const officialModelPicks = topModelPicks.filter((row) => row.market && canPaperTradePick(row.market));
  const visibleTopModelPicks = showAllModelPicks ? topModelPicks : topModelPicks.slice(0, 8);
  const bestModelPick = officialModelPicks[0] ?? topModelPicks[0];
  const bestModelPickOfficial = Boolean(bestModelPick?.market && canPaperTradePick(bestModelPick.market));
  const missingDataWarnings = Array.from(new Set(modelPickRows.flatMap((row) => row.game.modelPick?.missingDataWarnings ?? []))).slice(0, 8);
  const decisionWatchlistRows = topModelPicks
    .filter((row) => !officialModelPicks.includes(row) && (row.game.modelPick?.modelScore ?? 0) >= 60)
    .slice(0, 5);
  const decisionNoBetReasons = deriveNoBetReasons({
    result,
    rows,
    topQualifiedSignals,
    missingDataWarnings,
    hiddenSeriesGames: topModelPickSeries.hiddenSeriesGames,
  });
  const decisionQualityItems: DecisionQualityItem[] = [
    { label: "MLB Schedule", value: normalizeDecisionStatus(result?.diagnostics.sportApi.status), tone: qualityTone(result?.diagnostics.sportApi.status) },
    { label: "Polymarket", value: normalizeDecisionStatus(result?.diagnostics.polymarket.status), tone: qualityTone(result?.diagnostics.polymarket.status) },
    { label: "Odds", value: oddsStatus?.status === "CONNECTED" ? "CONNECTED" : oddsStatus?.status === "PARTIAL" ? "PARTIAL" : "MISSING", tone: oddsStatus?.status === "CONNECTED" ? "green" : oddsStatus?.status === "PARTIAL" ? "yellow" : "red" },
    { label: "Pitchers", value: result ? `${result.diagnostics.sportApi.probablePitchersFound} found` : "MISSING", tone: result?.diagnostics.sportApi.probablePitchersFound ? "green" : "red" },
    { label: "Lineups", value: decisionLineupImpact ? lineupStatusLabel(decisionLineupImpact.lineupStatus) : normalizeDecisionStatus(result?.sourceStatus.lineups), tone: decisionLineupImpact ? lineupImpactTone(decisionLineupImpact.lineupStatus) : qualityTone(result?.sourceStatus.lineups) },
    { label: "Lineup Impact", value: decisionLineupImpact ? `${Math.round(decisionLineupImpact.lineupImpactScore * 100)}%` : "MISSING", tone: decisionLineupImpact ? lineupImpactTone(decisionLineupImpact.lineupStatus) : "red" },
    { label: "Injuries", value: normalizeDecisionStatus(result?.sourceStatus.injuries), tone: qualityTone(result?.sourceStatus.injuries) },
    { label: "Weather", value: normalizeDecisionStatus(result?.diagnostics.weather.status), tone: qualityTone(result?.diagnostics.weather.status) },
    { label: "Whales", value: whaleConsensus.length || whaleProfiles.length ? "BONUS ONLY" : "BONUS ONLY", tone: whaleErrors.length ? "yellow" : "yellow" },
  ];
  const openPaperTrades = paperTrades.filter((trade) => trade.status === "PENDING");
  const resolvedPaperTrades = paperTrades.filter((trade) => trade.status !== "PENDING");
  const paperPnl = paperTrades.reduce((total, trade) => total + trade.pnl, 0);
  const bankroll = STARTING_BANKROLL + paperPnl;
  const exposure = openPaperTrades.reduce((total, trade) => total + trade.stake, 0);
  const wins = paperTrades.filter((trade) => trade.status === "WIN").length;
  const losses = paperTrades.filter((trade) => trade.status === "LOSS").length;
  const voids = paperTrades.filter((trade) => trade.status === "VOID").length;
  const unknowns = paperTrades.filter((trade) => trade.status === "UNKNOWN").length;
  const settledStake = paperTrades.filter((trade) => trade.status === "WIN" || trade.status === "LOSS").reduce((total, trade) => total + trade.stake, 0);
  const paperRoi = settledStake ? (paperPnl / settledStake) * 100 : 0;
  const settledTrades = wins + losses;
  const winRate = settledTrades ? (wins / settledTrades) * 100 : 0;
  const maxScore = topQualifiedSignals.reduce((highest, signal) => Math.max(highest, Math.round((signal.modelProbability ?? 0) * 100)), 0);
  const sportsCovered = new Set(result?.games.map((game) => game.sport) ?? []).size;
  const bestPick = topQualifiedSignals[0];
  const browserFallbackActive = isBrowserFallbackResult(result);
  const dataOnlyMode = Boolean(result && rows.length && rows.every((row) => !row.market));
  const serverPaperSummary = paperLedgerReport;
  const sevenDayPaperTest = paperLedgerReport?.paperTest ?? dailyReport?.paperTest;
  const dailyNoBetReasons = dailyReport?.noBetReasons?.slice(0, 4) ?? [];
  const displayedPaperTrades = useMemo(
    () =>
      [...paperTrades].sort((a, b) => {
        if (a.status === "PENDING" && b.status !== "PENDING") return -1;
        if (a.status !== "PENDING" && b.status === "PENDING") return 1;
        return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
      }),
    [paperTrades],
  );

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setPaperTrades(loadStoredPaperTrades());
      setPaperTradesLoaded(true);
    }, 0);

    return () => window.clearTimeout(handle);
  }, []);

  useEffect(() => {
    let active = true;

    fetch("/api/astrodds/wallets/watchlist", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() as Promise<WhaleWatchlistResponse> : Promise.reject(new Error(`Watchlist failed with ${response.status}`))))
      .then((payload) => {
        if (!active) return;
        setWhaleWatchlist(payload.wallets);
        setWhaleSourcePolicy(payload.sourcePolicy);
      })
      .catch((watchlistError: unknown) => {
        if (!active) return;
        setWhaleErrors((errors) => [...errors, watchlistError instanceof Error ? watchlistError.message : "Unknown whale watchlist failure"]);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    fetch("/api/astrodds/telegram/status", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() as Promise<TelegramStatusResponse> : Promise.reject(new Error(`Telegram status failed with ${response.status}`))))
      .then((payload) => {
        if (active) setTelegramStatus(payload);
      })
      .catch((statusError: unknown) => {
        if (!active) return;
        setTelegramTestResult({
          status: "FAILED",
          reason: statusError instanceof Error ? statusError.message : "Unknown Telegram status failure",
        });
      });

    return () => {
      active = false;
    };
  }, []);


  async function refreshOddsStatus(fetchLiveOdds = false) {
    const route = fetchLiveOdds ? "/api/astrodds/odds/status?fetch=true&sportKey=baseball_mlb" : "/api/astrodds/odds/status";
    try {
      const response = await fetch(route, { cache: "no-store" });
      if (!response.ok) throw new Error(`Odds status failed with ${response.status}`);
      setOddsStatus((await response.json()) as OddsLayerResponse);
    } catch (oddsError) {
      setOddsStatus({
        status: "FAILED",
        provider: "UNKNOWN",
        keyConfigured: false,
        supportedMarkets: ["Moneyline / Winner", "Spread / Handicap", "Totals / Over-Under"],
        priceAvailable: false,
        officialBetEligibility: false,
        reason: oddsError instanceof Error ? oddsError.message : "Unknown odds status failure.",
      });
    }
  }

  async function refreshPaperLedger() {
    try {
      const response = await fetch("/api/astrodds/paper/performance", { cache: "no-store" });
      if (!response.ok) throw new Error(`Paper performance failed with ${response.status}`);
      setPaperLedgerReport((await response.json()) as PaperPerformanceResponse);
    } catch (paperError) {
      setError((previous) => previous || (paperError instanceof Error ? paperError.message : "Unknown paper performance failure."));
    }
  }

  async function refreshDailyReport() {
    try {
      const response = await fetch("/api/astrodds/daily-report", { cache: "no-store" });
      if (!response.ok) throw new Error(`Daily report failed with ${response.status}`);
      setDailyReport((await response.json()) as DailyReportResponse);
    } catch (dailyError) {
      setError((previous) => previous || (dailyError instanceof Error ? dailyError.message : "Unknown daily report failure."));
    }
  }

  async function startSevenDayPaperTest() {
    setIsStartingPaperTest(true);
    try {
      const response = await fetch("/api/astrodds/paper/test", { method: "POST" });
      if (!response.ok) throw new Error(`Paper test failed with ${response.status}`);
      await refreshPaperLedger();
      await refreshDailyReport();
    } catch (paperTestError) {
      setError(paperTestError instanceof Error ? paperTestError.message : "Unknown paper-test failure.");
    } finally {
      setIsStartingPaperTest(false);
    }
  }

  async function persistModelLeansFromResult(scanResult: AstroddsScanResult) {
    const modelLeanPayloads = scanResult.games
      .filter((game) => game.sport === "MLB" && game.modelPick)
      .map((game) => ({
        kind: "model_lean" as const,
        payload: {
          sport: game.sport,
          league: game.league ?? "MLB",
          gameId: game.id,
          game: game.game,
          leanSide: game.modelPick?.modelLeanTeam ?? game.modelPick?.modelLeanSide ?? "WAIT",
          confidence: game.modelPick?.modelConfidence ?? 0,
          modelScore: game.modelPick?.modelScore ?? 0,
          dataQuality: game.modelPick?.dataQuality ?? "UNKNOWN",
          reason: game.modelPick?.modelReason ?? "StatsAPI model lean saved for validation.",
          missingDataWarnings: game.modelPick?.missingDataWarnings ?? [],
          source: "ASTRODDS_STATSAPI_MODEL_LEAN",
        },
      }));

    if (!modelLeanPayloads.length) return;
    await Promise.allSettled(modelLeanPayloads.map((body) => fetch("/api/astrodds/paper/create", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    })));
    setModelLeansSavedAt(new Date().toISOString());
    void refreshPaperLedger();
    void refreshDailyReport();
  }


  useEffect(() => {
    void refreshOddsStatus(false);
    void refreshPaperLedger();
    void refreshDailyReport();
  }, []);
  useEffect(() => {
    if (!paperTradesLoaded) return;
    window.localStorage.setItem(PAPER_TRADES_STORAGE_KEY, JSON.stringify(paperTrades));
  }, [paperTrades, paperTradesLoaded]);

  function handleTestClick(event?: SyntheticEvent<HTMLElement>) {
    event?.preventDefault();
    const now = Date.now();
    if (now - lastTestClickAtRef.current < 350) return;
    lastTestClickAtRef.current = now;
    console.log("TEST CLICK FIRED");
    setScanAttemptCount((count) => count + 1);
    setScanStatus("Button test OK");
    setScanDebugMessage("React click works");
    setLastClickDebug(`TEST CLICK FIRED via ${event?.type ?? "manual"}`);
  }

  async function handleScan(event?: SyntheticEvent<HTMLElement>) {
    event?.preventDefault();
    const now = Date.now();
    if (now - lastScanClickAtRef.current < 500 || isScanning) return;
    lastScanClickAtRef.current = now;
    const apiRoute = `/api/astrodds/scan?sport=${selectedSport}`;
    console.log("ASTRODDS SCAN BUTTON CLICKED");
    setLastClickDebug(`SCAN BUTTON CLICKED via ${event?.type ?? "manual"}`);
    setIsScanning(true);
    setScanStatus("Scanning");
    setScanDebugMessage("SCAN BUTTON CLICKED");
    setScanAttemptCount((count) => count + 1);
    setLastScanRoute(apiRoute);
    setError("");
    setActiveStep(0);

    const interval = window.setInterval(() => {
      setActiveStep((step) => Math.min(step + 1, SCAN_STEPS.length - 1));
    }, 420);

    try {
      const response = await fetch(apiRoute, { cache: "no-store" });
      if (!response.ok) throw new Error(`Scan failed with ${response.status}`);
      const nextResult = (await response.json()) as AstroddsScanResult;
      console.log("ASTRODDS scan response received", {
        responseKeys: Object.keys(nextResult),
        diagnosticsCounts: {
          marketsFetched: nextResult.diagnostics?.polymarket?.marketsFetched ?? 0,
          gamesFetched: nextResult.diagnostics?.sportApi?.gamesFetched ?? 0,
          weatherFetched: nextResult.diagnostics?.weather?.weatherResultsFetched ?? 0,
          matchedGames: nextResult.diagnostics?.matching?.matchedGamesCount ?? 0,
          gamesCount: nextResult.diagnostics?.matching?.gamesCount ?? 0,
          mlbMarketsDetected: nextResult.diagnostics?.polymarket?.mlbMarketsDetected ?? 0,
          singleGameMlbMarketsDetected: nextResult.diagnostics?.polymarket?.singleGameMlbMarketsDetected ?? 0,
        },
        games: nextResult.games?.length ?? 0,
      });
      const finalResult = selectedSport === "MLB" && shouldUseBrowserFallback(nextResult)
        ? await scanMlbWithBrowserFallback(nextResult)
        : nextResult;
      setResult(finalResult);
      void persistModelLeansFromResult(finalResult);
      void refreshOddsStatus(false);
      setScanStatus("Completed");
      setScanDebugMessage("Scan completed. Backend response mapped into dashboard.");
      setActiveStep(SCAN_STEPS.length - 1);
    } catch (scanError) {
      if (selectedSport === "MLB") {
        try {
          const fallbackResult = await scanMlbWithBrowserFallback(null);
          console.log("ASTRODDS scan response received", {
            responseKeys: Object.keys(fallbackResult),
            diagnosticsCounts: {
              marketsFetched: fallbackResult.diagnostics?.polymarket?.marketsFetched ?? 0,
              gamesFetched: fallbackResult.diagnostics?.sportApi?.gamesFetched ?? 0,
              weatherFetched: fallbackResult.diagnostics?.weather?.weatherResultsFetched ?? 0,
              matchedGames: fallbackResult.diagnostics?.matching?.matchedGamesCount ?? 0,
              gamesCount: fallbackResult.diagnostics?.matching?.gamesCount ?? 0,
              mlbMarketsDetected: fallbackResult.diagnostics?.polymarket?.mlbMarketsDetected ?? 0,
              singleGameMlbMarketsDetected: fallbackResult.diagnostics?.polymarket?.singleGameMlbMarketsDetected ?? 0,
            },
            games: fallbackResult.games?.length ?? 0,
          });
          setResult(fallbackResult);
          void persistModelLeansFromResult(fallbackResult);
          void refreshOddsStatus(false);
          setScanStatus("Completed");
          setScanDebugMessage("Scan completed through browser fallback. Backend response mapped into dashboard.");
          setActiveStep(SCAN_STEPS.length - 1);
          return;
        } catch (fallbackError) {
          setScanStatus("Failed");
          setScanDebugMessage("Scan failed after click. Check error details.");
          setError(
            `Server scan failed: ${scanError instanceof Error ? scanError.message : "Unknown scanner error"}. Browser fallback failed: ${
              fallbackError instanceof Error ? fallbackError.message : "Unknown browser fallback error"
            }`,
          );
        }
      } else {
        setScanStatus("Failed");
        setScanDebugMessage("Scan failed after click. Check error details.");
        setError(scanError instanceof Error ? scanError.message : "Unknown scanner error");
      }
    } finally {
      window.clearInterval(interval);
      setIsScanning(false);
    }
  }

  async function persistOfficialPaperPick(game: AstroddsGameScan, market: AstroddsMarketScan, signal?: UnifiedAstroddsSignal) {
    const decisionLabel = officialPaperDecisionLabel((signal?.decision as AstroddsDecision | undefined) ?? market.decision);
    if (!decisionLabel || typeof market.currentPrice !== "number" || market.currentPrice <= 0) return;

    await fetch("/api/astrodds/paper/create", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        kind: "official",
        payload: {
          id: `official-${paperTradeId(market)}`,
          category: "polymarket",
          sport: game.sport,
          league: game.league ?? "MLB",
          gameId: game.id,
          game: game.game,
          marketType: paperMarketType(market),
          marketLabel: market.marketTitle,
          pickSide: signal?.pick ?? market.pick,
          entryPricePolymarket: market.currentPrice,
          impliedProbability: signal?.marketProbability ?? market.probability?.marketImpliedProbability ?? market.currentPrice,
          paperStakePercent: 5,
          paperStakeUnits: DEFAULT_PAPER_STAKE,
          modelScore: market.score?.total ?? Math.round((signal?.modelProbability ?? 0) * 100),
          confidence: Math.round((signal?.modelProbability ?? market.probability?.modelProbability ?? 0) * 100) || (market.score?.total ?? 0),
          dataQuality: signal?.dataQuality ?? market.probability?.dataQuality ?? game.dataStatus,
          decisionLabel,
          whaleSupportLevel: signal?.whaleSupport && signal.whaleSupport !== "NONE" ? "MEDIUM" : "NONE",
          whaleConflict: signal?.whaleSupport === "CONFLICT",
          reason: signal?.why.join(" ") ?? market.why ?? shortReason(game, market),
          source: "ASTRODDS_OFFICIAL_PAPER_BUTTON",
        },
      }),
    }).then((response) => {
      if (!response.ok) throw new Error(`Official paper pick failed with ${response.status}`);
    });
    void refreshPaperLedger();
    void refreshDailyReport();
  }

  function addPaperTrade(game: AstroddsGameScan, market: AstroddsMarketScan, signal?: UnifiedAstroddsSignal) {
    const id = paperTradeId(market);
    const activeExposure = paperTrades.filter((trade) => trade.status === "PENDING").reduce((total, trade) => total + trade.stake, 0);
    if (paperTrades.some((trade) => trade.id === id)) return;
    if (activeExposure + DEFAULT_PAPER_STAKE > MAX_ACTIVE_EXPOSURE) return;

    const trade: PaperTrade = {
      id,
      sport: game.sport,
      gameId: game.id,
      gamePk: game.sport === "MLB" ? gamePkFromId(game) : undefined,
      homeTeam: game.homeTeam,
      awayTeam: game.awayTeam,
      game: game.game,
      market: market.marketTitle,
      marketType: paperMarketType(market),
      pick: signal?.pick ?? market.pick,
      line: tradeLineFromMarket(market),
      decision: signal ? displayDecision(signal.decision as AstroddsDecision) : displayDecision(market.decision),
      confidence: signal?.confidence ?? market.confidence?.replace(/_/g, " ") ?? "NO BET",
      score: market.score?.total ?? 0,
      entryPrice: market.currentPrice,
      stake: DEFAULT_PAPER_STAKE,
      bankroll: STARTING_BANKROLL,
      status: "PENDING",
      pnl: 0,
      roi: 0,
      result: "Pending final result.",
      dataConfidence: game.dataStatus,
      dataStatuses: dataStatuses(game, market),
      walletSupport: market.walletSupport?.summary ?? "No wallet support attached.",
      why: signal?.why.join(" ") ?? market.why ?? shortReason(game, market),
      createdAt: new Date().toISOString(),
      sourceData: {
        signalId: signal?.signalId,
        signalType: signal?.signalType,
        marketId: market.marketId,
        conditionId: market.conditionId,
        assetId: market.assetId,
        sourceUrl: market.sourceUrl,
        modelProbability: signal?.modelProbability ?? market.probability?.modelProbability,
        marketProbability: signal?.marketProbability ?? market.probability?.marketImpliedProbability,
        edge: signal?.edge ?? market.probability?.edge,
        expectedValue: signal?.expectedValue ?? market.probability?.expectedValue,
        dataQuality: signal?.dataQuality ?? market.probability?.dataQuality,
        whaleSupport: signal?.whaleSupport,
        copyability: signal?.copyability,
        orderBookQuality: signal?.orderBookQuality,
      },
    };

    setPaperTrades((trades) => [...trades, trade]);
    void persistOfficialPaperPick(game, market, signal).catch((paperError) => {
      setError((previous) => previous || (paperError instanceof Error ? paperError.message : "Unknown official paper ledger failure."));
    });
  }

  async function testApiConnection(source: AstroddsApiTestSource) {
    setTestingSource(source);

    try {
      const response = await fetch(`/api/astrodds/test?source=${source}`, { cache: "no-store" });
      const payload = (await response.json()) as AstroddsApiTestResult;
      setApiTests((tests) => ({
        ...tests,
        [source]: payload,
      }));
    } catch (testError) {
      setApiTests((tests) => ({
        ...tests,
        [source]: {
          source,
          status: "FAILED",
          count: 0,
          error: testError instanceof Error ? testError.message : "Unknown API connection test failure",
          testedAt: new Date().toISOString(),
        },
      }));
    } finally {
      setTestingSource(null);
    }
  }

  async function resolveMlbPaperTrades() {
    setIsResolvingPaper(true);
    setError("");

    try {
      const response = await fetch("/api/astrodds/paper/resolve", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          trades: paperTrades,
        }),
      });

      if (!response.ok) throw new Error(`Resolver failed with ${response.status}`);
      const payload = (await response.json()) as ResolveSummary & { trades?: PaperTrade[] };
      const resolvedTrades = Array.isArray(payload.trades) ? payload.trades.map((trade) => normalizeStoredPaperTrade(trade)) : [];
      const byId = new Map(resolvedTrades.map((trade) => [trade.id, trade]));

      setPaperTrades((trades) => trades.map((trade) => byId.get(trade.id) ?? trade));
      setPaperResolveSummary({
        resolved: payload.resolved,
        pending: payload.pending,
        wins: payload.wins,
        losses: payload.losses,
        voids: payload.voids,
        unknown: payload.unknown,
        errors: payload.errors ?? [],
        resultsFetched: payload.resultsFetched,
      });
      setLastResolvedAt(new Date().toISOString());
    } catch (resolveError) {
      setError(resolveError instanceof Error ? resolveError.message : "Unknown MLB paper resolver failure");
    } finally {
      setIsResolvingPaper(false);
    }
  }

  async function scanPublicWhales() {
    setIsScanningWhales(true);
    setWhaleErrors([]);

    try {
      const response = await fetch("/api/astrodds/wallets/scan", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          handles: whaleWatchlist.length ? whaleWatchlist.map((wallet) => wallet.handle) : undefined,
          category: "all",
        }),
      });
      if (!response.ok) throw new Error(`Whale scan failed with ${response.status}`);
      const payload = (await response.json()) as WhaleScanResponse;
      setWhaleSourcePolicy(payload.sourcePolicy);
      setWhaleProfiles(payload.profiles);
      setWhaleMetrics(payload.strategyMetrics);
      setWhalePositions(payload.activePositions);
      setWhaleCopyability(payload.copyability);
      setWhaleConsensus(payload.consensus);
      setWhaleErrors(payload.errors);
      setLastWhaleScanAt(payload.scannedAt);
      setWhaleWatchlist((wallets) =>
        wallets.map((wallet) => {
          const profile = payload.profiles.find((item) => item.handle.toLowerCase() === wallet.handle.toLowerCase());
          const metrics = payload.strategyMetrics.find((item) => item.handle.toLowerCase() === wallet.handle.toLowerCase());

          return profile
            ? {
                ...wallet,
                address: profile.address,
                sourceStatus: profile.sourceStatus,
                lastScanned: payload.scannedAt,
                nextRescan: metrics?.nextRescan ?? wallet.nextRescan,
                metrics,
              }
            : wallet;
        }),
      );
    } catch (scanError) {
      setWhaleErrors([scanError instanceof Error ? scanError.message : "Unknown public whale scan failure"]);
    } finally {
      setIsScanningWhales(false);
    }
  }

  async function refreshTelegramStatus() {
    const response = await fetch("/api/astrodds/telegram/status", { cache: "no-store" });
    if (!response.ok) throw new Error(`Telegram status failed with ${response.status}`);
    setTelegramStatus((await response.json()) as TelegramStatusResponse);
  }

  async function testTelegram() {
    setIsTestingTelegram(true);

    try {
      const response = await fetch("/api/astrodds/telegram/test", { method: "POST" });
      const payload = (await response.json()) as TelegramActionResult;
      setTelegramTestResult(payload);
      setLastTelegramTestAt(new Date().toISOString());
      await refreshTelegramStatus();
    } catch (testError) {
      setTelegramTestResult({
        status: "FAILED",
        reason: testError instanceof Error ? testError.message : "Unknown Telegram test failure",
      });
    } finally {
      setIsTestingTelegram(false);
    }
  }

  async function testWhaleAlert() {
    setIsTestingWhaleAlert(true);

    try {
      const response = await fetch("/api/astrodds/wallets/alerts/test", { method: "POST" });
      const payload = (await response.json()) as TelegramActionResult;
      setWhaleAlertTestResult(payload);
      setLastWhaleAlertTestAt(new Date().toISOString());
      await refreshTelegramStatus();
    } catch (testError) {
      setWhaleAlertTestResult({
        status: "FAILED",
        reason: testError instanceof Error ? testError.message : "Unknown whale alert test failure",
      });
    } finally {
      setIsTestingWhaleAlert(false);
    }
  }

  function jumpTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <main className="astro-terminal min-h-screen bg-[#05060a] text-white">
      <div className="astro-grid-bg fixed inset-0" aria-hidden="true" />
      <div className="relative z-10 mx-auto max-w-[1820px] px-3 py-3 md:px-5 md:py-5">
        <div className="astro-shell">
          <header className="sticky top-0 z-30 border-b border-[#d6af55]/30 bg-black/[0.92] backdrop-blur-xl">
            <div className="grid gap-3 px-3 py-2 xl:grid-cols-[350px_minmax(0,1fr)_170px] xl:items-stretch">
              <div className="flex min-w-0 items-center gap-3">
                <div className="grid size-14 shrink-0 place-items-center overflow-hidden border border-[#d6af55]/75 bg-black shadow-[0_0_20px_rgba(214,175,85,0.28)]">
                  {!cardImageMissing ? (
                    <Image
                      src={CARD_REFERENCE_SRC}
                      alt="ASTRODDS card avatar"
                      width={56}
                      height={56}
                      className="h-full w-full object-cover"
                      onError={() => setCardImageMissing(true)}
                    />
                  ) : (
                    <RadioTower className="size-7 text-[#f1d27a]" aria-hidden="true" />
                  )}
                </div>
                <div className="min-w-0">
                  <h1 className="truncate text-3xl font-black uppercase tracking-[0.15em] text-[#f4d274]">ASTRODDS</h1>
                  <p className="mt-0.5 truncate text-[10px] font-black uppercase tracking-[0.22em] text-slate-300">
                    Real Sports Data + Polymarket Scanner
                  </p>
                </div>
              </div>

              <nav className="astro-nav-scroll flex min-w-0 gap-0 overflow-x-auto xl:justify-center">
                {pageLinks.map((item) => {
                  const Icon = item.icon;
                  const isActive = item.id === "scanner";
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => jumpTo(item.id)}
                      className={`relative inline-flex min-h-14 min-w-[102px] shrink-0 flex-col items-center justify-center gap-1 border-r border-white/10 px-2 text-[8.5px] font-black uppercase tracking-[0.1em] transition hover:bg-[#d6af55]/10 hover:text-white ${
                        isActive ? "bg-[#d6af55]/10 text-white shadow-[inset_0_-2px_0_#f4d274,0_8px_26px_rgba(214,175,85,0.22)]" : "text-slate-300"
                      }`}
                    >
                      <Icon className="size-4 text-[#f1d27a]" aria-hidden="true" />
                      {item.label}
                    </button>
                  );
                })}
              </nav>

              <div className="flex min-w-0 items-center justify-end">
                <button
                  type="button"
                  onClick={() => jumpTo("wallets")}
                  className="inline-flex min-h-14 w-full items-center justify-center gap-2 border border-[#d6af55]/70 bg-[#d6af55]/10 px-3 text-[10px] font-black uppercase tracking-[0.12em] text-[#f4d274] shadow-[0_0_24px_rgba(214,175,85,0.22)]"
                >
                  Wallet Tracker
                  <Badge className="border-yellow-200/70 bg-yellow-300/15 text-yellow-50">Soon</Badge>
                </button>
              </div>
            </div>
          </header>

          <div className="grid gap-3 p-3">
            <section
              id="scanner"
              className="scroll-mt-24"
              onClickCapture={(event) => {
                const target = event.target as HTMLElement;
                const button = target.closest("button");
                const label = (button?.textContent ?? target.textContent ?? target.tagName).trim().slice(0, 80) || "unknown";
                console.log("ASTRODDS PANEL CLICK CAPTURED", label);
                setLastClickDebug(`Panel captured ${target.tagName}: ${label}`);
              }}
            >
              <div className="grid gap-3 2xl:grid-cols-[minmax(260px,17fr)_minmax(0,55fr)_minmax(360px,28fr)]">
                <aside className="astro-panel-soft relative z-50 p-4 pointer-events-auto" style={{ pointerEvents: "auto" }}>
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="text-xs font-black uppercase tracking-[0.2em] text-[#f4d274]">Scan Controls</h3>
                    <Badge className="border-emerald-300/45 bg-emerald-400/12 text-emerald-100">Paper Only</Badge>
                  </div>

                  <label htmlFor="sport-select" className="mt-5 block text-[10px] font-black uppercase tracking-[0.22em] text-slate-500">
                    Sport
                  </label>
                  <select
                    id="sport-select"
                    value={selectedSport}
                    onChange={(event) => setSelectedSport(event.target.value as AstroddsSportFilter)}
                    className="mt-2 h-11 w-full border border-[#d6af55]/35 bg-black px-3 text-sm font-black uppercase tracking-[0.12em] text-white outline-none shadow-[inset_0_0_18px_rgba(214,175,85,0.08)]"
                  >
                    {SPORTS.map((sport) => (
                      <option key={sport.value} value={sport.value}>
                        {sport.label}
                      </option>
                    ))}
                  </select>

                  <button
                    type="button"
                    onPointerDown={handleScan}
                    onMouseDown={handleScan}
                    onClick={handleScan}
                    disabled={isScanning}
                    aria-disabled={false}
                    style={{ pointerEvents: "auto" }}
                    className="mt-4 inline-flex h-16 w-full items-center justify-center gap-3 border border-[#f4d274]/80 bg-[#d6af55]/15 px-4 text-lg font-black uppercase tracking-[0.14em] text-[#ffe59b] shadow-[inset_0_0_22px_rgba(214,175,85,0.16),0_0_28px_rgba(214,175,85,0.26)] transition hover:bg-[#d6af55]/20 disabled:cursor-wait disabled:opacity-60 pointer-events-auto"
                  >
                    {isScanning ? <Loader2 className="size-6 animate-spin" aria-hidden="true" /> : <RadioTower className="size-6" aria-hidden="true" />}
                    Scan {scanLabel[selectedSport]}
                  </button>
                  <button
                    type="button"
                    onPointerDown={handleTestClick}
                    onMouseDown={handleTestClick}
                    onClick={handleTestClick}
                    aria-disabled={false}
                    style={{ pointerEvents: "auto" }}
                    className="mt-2 inline-flex h-10 w-full items-center justify-center border border-cyan-300/50 bg-cyan-400/10 px-3 text-xs font-black uppercase tracking-[0.16em] text-cyan-100 pointer-events-auto"
                  >
                    TEST CLICK
                  </button>
                  <p className="mt-2 text-center text-xs font-bold text-[#f4d274]">Fetch and analyze markets</p>
                  <p className="mt-1 text-center text-xs font-black text-cyan-100">{scanDebugMessage}</p>

                  <div className="mt-5 border-y border-white/10 py-4">
                    <div className="flex items-center justify-between gap-3 text-sm">
                      <span className="font-black uppercase tracking-[0.14em] text-[#f4d274]">Scan Status</span>
                      <span className={(scanStatus === "Completed" || scanStatus === "Button test OK") ? "font-black text-emerald-300" : scanStatus === "Scanning" ? "font-black text-[#f4d274]" : scanStatus === "Failed" ? "font-black text-red-300" : "font-black text-slate-500"}>{scanStatus}</span>
                    </div>
                    <p className="mt-2 text-xs text-slate-400">{result ? formatDate(result.lastScanTime) : "Run the scanner to populate live diagnostics."}</p>
                    <p className="mt-1 text-xs text-slate-500">Scan attempts: {scanAttemptCount}</p>
                    <p className="mt-1 text-xs text-slate-500">React hydrated: <span className={hydrated ? "font-black text-emerald-300" : "font-black text-red-300"}>{hydrated ? "YES" : "NO"}</span></p>
                    <p className="mt-1 text-xs font-bold text-cyan-100">{lastClickDebug}</p>
                    {browserFallbackActive ? (
                      <Badge className="mt-3 border-cyan-300/55 bg-cyan-400/15 text-cyan-50">Browser fallback active</Badge>
                    ) : null}
                  </div>

                  <div className="mt-4 grid gap-2">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-[#f4d274]">Data Sources</p>
                    {diagnosticCards(result).map((card) => (
                      <div key={card.label} className="flex items-center justify-between gap-3 border border-white/10 bg-black/30 px-3 py-2">
                        <span className="text-xs font-bold text-slate-300">{card.label}</span>
                        <DiagnosticBadge status={card.status} />
                      </div>
                    ))}
                  </div>

                  <div className="mt-4 border-t border-white/10 pt-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-[#f4d274]">System Health</p>
                    <div className="mt-3 flex items-center gap-4">
                      <div className="astro-health-ring">
                        <span>98%</span>
                      </div>
                      <div>
                        <p className="text-sm font-black uppercase tracking-[0.14em] text-emerald-300">Excellent</p>
                        <p className="mt-1 text-xs text-slate-400">Scanner shell operational</p>
                      </div>
                    </div>
                    <div className="astro-sparkline mt-4" aria-hidden="true" />
                  </div>

                  <div className="mt-4 grid gap-1.5">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-[#f4d274]">Live Pipeline</p>
                    {SCAN_STEPS.slice(0, 5).map((step, index) => (
                      <div key={step} className="flex items-center gap-2 text-[11px] text-slate-400">
                        {index <= activeStep && result && !isScanning ? (
                          <CheckCircle2 className="size-3.5 text-emerald-300" aria-hidden="true" />
                        ) : index === activeStep && isScanning ? (
                          <Loader2 className="size-3.5 animate-spin text-[#f4d274]" aria-hidden="true" />
                        ) : (
                          <span className="size-3.5 border border-current" />
                        )}
                        {step}
                      </div>
                    ))}
                  </div>

                  <div className="mt-4 border border-[#d6af55]/30 bg-[#d6af55]/10 p-4">
                    <div className="flex items-center gap-3">
                      <Diamond className="size-7 text-[#f4d274]" aria-hidden="true" />
                      <div>
                        <p className="text-sm font-black text-white">Wallet Tracker</p>
                        <p className="text-xs text-slate-400">Wallet intelligence remains a bonus layer.</p>
                      </div>
                    </div>
                    <Badge className="mt-3 border-yellow-200/70 bg-yellow-300/15 text-yellow-50">Soon</Badge>
                  </div>
                </aside>

                <section className="grid gap-4">
                  <div className="astro-panel-soft p-4">
                    <div className="mb-4 flex flex-col gap-2 border-b border-[#d6af55]/25 pb-3 md:flex-row md:items-center md:justify-between">
                      <div>
                        <p className="text-[10px] font-black uppercase tracking-[0.22em] text-[#f4d274]">ASTRODDS Decision Center</p>
                        <h3 className="mt-1 text-lg font-black uppercase tracking-[0.08em] text-white">Bet Decision Snapshot</h3>
                      </div>
                      <Badge className="border-cyan-300/40 bg-cyan-400/10 text-cyan-100">Model first | Whales bonus only</Badge>
                    </div>

                    <div className="grid gap-3 xl:grid-cols-5">
                      <div className="border border-white/10 bg-black/35 p-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#f4d274]">Best Official Pick</p>
                        {bestFinalSignal ? (
                          <div className="mt-3 grid gap-2 text-xs">
                            <DecisionBadge decision={bestFinalSignal.decision as AstroddsDecision} />
                            <p className="font-black text-white">{signalBetText(bestFinalSignal)}</p>
                            <p className="text-slate-400">{bestFinalSignal.game}</p>
                            <div className="grid gap-1 border-t border-white/10 pt-2">
                              <div className="flex justify-between gap-3"><span className="text-slate-500">Market</span><span className="font-bold text-white">{bestFinalSignal.marketType}</span></div>
                              <div className="flex justify-between gap-3"><span className="text-slate-500">Entry</span><span className="font-mono font-bold text-cyan-100">{formatPrice(bestFinalSignal.entryPrice)}</span></div>
                              <div className="flex justify-between gap-3"><span className="text-slate-500">Confidence</span><span className="font-bold text-white">{bestFinalSignal.confidence}</span></div>
                              <div className="flex justify-between gap-3"><span className="text-slate-500">Edge</span><span className="font-bold text-emerald-100">{formatEdge(bestFinalSignal.edge)}</span></div>
                              <div className="flex justify-between gap-3"><span className="text-slate-500">Lineup</span><span className="font-bold text-white">{lineupStatusLabel(bestFinalSignal.lineupImpact.lineupStatus)}</span></div>
                              <div className="flex justify-between gap-3"><span className="text-slate-500">Lineup Impact</span><span className="font-bold text-cyan-100">{lineupImpactDisplay(bestFinalSignal)}</span></div>
                              <div className="flex justify-between gap-3"><span className="text-slate-500">Risk</span><span className="font-bold text-white">5% paper</span></div>
                            </div>
                          </div>
                        ) : (
                          <div className="mt-3 grid gap-2 text-xs">
                            <Badge className={decisionNoLiveMlbData ? "border-red-300/55 bg-red-500/12 text-red-100" : "border-cyan-300/45 bg-cyan-400/10 text-cyan-100"}>{decisionNoLiveMlbData ? "NO BET / NO LIVE MLB DATA" : "DATA ONLY / WAIT FOR ODDS"}</Badge>
                            {decisionNoLiveMlbData ? <p className="font-black text-red-100">No Bet - live MLB data unavailable.</p> : null}
                            {decisionSourceWarning ? <p className="leading-5 text-yellow-100">Source warning: {decisionSourceWarning}</p> : null}
                            <p className="font-bold text-slate-300">Lineup: {lineupStatusLabel(decisionLineupImpact?.lineupStatus)}</p>
                            <p className="font-bold text-cyan-100">Lineup Impact: {decisionLineupImpact ? `${Math.round(decisionLineupImpact.lineupImpactScore * 100)}%` : "Missing"}</p>
                            {decisionLineupImpact?.lineupStatus === "missing" ? <p className="text-yellow-100">Watchlist - lineup not confirmed yet.</p> : null}
                            {decisionNoBetReasons.slice(0, 4).map((item) => (
                              <p key={item.reason} className="leading-5 text-slate-300">{item.reason}</p>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="border border-white/10 bg-black/35 p-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#f4d274]">Strong Buys</p>
                        <p className="mt-3 text-3xl font-black text-white">{strongBuySignals.length}</p>
                        {strongBuySignals.length ? (
                          <div className="mt-2 grid gap-2 text-xs">
                            {strongBuySignals.slice(0, 3).map((signal) => (
                              <div key={`${signal.signalId}-decision-strong`} className="border-t border-white/10 pt-2">
                                <p className="font-black text-white">{signal.game}</p>
                                <p className="text-[#f4d274]">{signalBetText(signal)}</p>
                                <p className="text-slate-400">{formatPrice(signal.entryPrice)} | {signal.confidence} | {formatEdge(signal.edge)}</p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="mt-2 grid gap-1 text-xs text-slate-300">
                            <p>No official Strong Buy right now.</p>
                            <p>Common blocks: missing odds, stale price, low edge, low confluence, or data quality too low.</p>
                          </div>
                        )}
                      </div>

                      <div className="border border-white/10 bg-black/35 p-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#f4d274]">Watchlist</p>
                        <div className="mt-3 grid gap-2 text-xs">
                          {decisionWatchlistRows.length ? decisionWatchlistRows.slice(0, 4).map((row) => (
                            <div key={`${modelPickDedupeKey(row)}-decision-watch`} className="border-t border-white/10 pt-2 first:border-t-0 first:pt-0">
                              <p className="font-black text-white">{row.game.game}</p>
                              <p className="text-slate-300">{modelPickText(row.game)}</p>
                              <p className="text-yellow-100">Needs: {watchlistNeeds(row).join(", ") || "better price confirmation"}</p>
                            </div>
                          )) : <p className="text-slate-400">Run Scan MLB to populate model watchlist rows.</p>}
                        </div>
                      </div>

                      <div className="border border-white/10 bg-black/35 p-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#f4d274]">Why No Bet</p>
                        <div className="mt-3 grid gap-2 text-xs">
                          {decisionNoBetReasons.map((item) => (
                            <div key={item.reason} className="flex items-start justify-between gap-3 border-b border-white/10 pb-2 last:border-b-0">
                              <span className="leading-5 text-slate-300">{item.reason}</span>
                              <span className="font-mono font-black text-yellow-100">{item.count}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="border border-white/10 bg-black/35 p-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#f4d274]">Data Quality</p>
                        <div className="mt-3 grid gap-1.5 text-[11px]">
                          {decisionNoLiveMlbData ? (
                            <div className="border border-red-300/25 bg-red-500/10 p-2 text-[11px] leading-5 text-red-100">No live MLB rows returned. Official picks remain blocked until verified schedule, odds, and lineup inputs are available.</div>
                          ) : null}
                          {decisionQualityItems.map((item) => (
                            <div key={item.label} className="flex items-center justify-between gap-2 border-b border-white/10 pb-1.5 last:border-b-0">
                              <span className="text-slate-400">{item.label}</span>
                              <Badge className={decisionToneClass(item.tone)}>{item.value}</Badge>
                            </div>
                          ))}
                        </div>
                        <div className="mt-3 border-t border-white/10 pt-2 text-[11px] leading-5 text-slate-300">
                          <p className="font-black uppercase tracking-[0.14em] text-[#f4d274]">Key lineup reasons</p>
                          {decisionLineupReasons.map((reason) => <p key={reason}>{reason}</p>)}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="astro-panel-soft p-4"> 
                    <div className="mb-4 flex flex-col gap-2 border-b border-white/10 pb-3 md:flex-row md:items-center md:justify-between">
                      <div>
                        <h3 className="text-sm font-black uppercase tracking-[0.18em] text-[#f4d274]">Data Engine Diagnostics</h3>
                        <p className="mt-1 text-xs text-slate-500">Live source health, raw counts, and failure reasons.</p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {browserFallbackActive ? <Badge className="border-cyan-300/55 bg-cyan-400/15 text-cyan-50">Browser fallback active</Badge> : null}
                        <Badge className="border-[#d6af55]/45 bg-[#d6af55]/10 text-[#ffe7a1]">MLB Reliability Pass</Badge>
                      </div>
                    </div>

                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                      {diagnosticCards(result).map((card) => {
                        const Icon = card.icon;

                        return (
                        <div key={card.label} className="astro-diag-card p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-center gap-3">
                              <Icon className="size-6 text-slate-200" aria-hidden="true" />
                              <p className="text-xs font-black uppercase tracking-[0.12em] text-white">{card.label}</p>
                            </div>
                            <DiagnosticBadge status={card.status} />
                          </div>
                          <p className="mt-4 text-3xl font-black text-white">{card.primary.replace(/^[^:]+:\s*/, "")}</p>
                          <p className="mt-1 text-xs leading-5 text-slate-400">{card.primary}</p>
                          <p className="text-xs leading-5 text-slate-400">{card.secondary}</p>
                          <p className="mt-2 text-xs font-black uppercase tracking-[0.12em] text-[#f4d274]">
                            Source Mode: {sourceModeLabel(card.sourceMode, card.status)}
                          </p>
                          {card.rawDetail ? <p className="mt-1 text-xs leading-5 text-slate-500">{card.rawDetail}</p> : null}
                          {card.sourceUrl ? <p className="mt-2 truncate text-[10px] font-mono text-slate-500" title={card.sourceUrl}>{card.sourceUrl}</p> : null}
                          {card.issue ? <p className="mt-2 text-xs font-black leading-5 text-red-300">{card.issue}</p> : <p className="mt-2 text-xs font-black text-emerald-300">No conflicts detected</p>}
                        </div>
                        );
                      })}
                    </div>

                    <div className="mt-4 border border-[#d6af55]/25 bg-black/35 p-3">
                      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                        <div>
                          <h4 className="text-xs font-black uppercase tracking-[0.18em] text-[#f4d274]">API Connection Tests</h4>
                          <p className="mt-1 text-xs text-slate-500">Direct source checks for MLB reliability. Matching runs locally.</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {(["polymarket", "mlb", "weather", "matching"] as AstroddsApiTestSource[]).map((source) => (
                            <button
                              key={source}
                              type="button"
                              onClick={() => testApiConnection(source)}
                              disabled={testingSource === source}
                              className="inline-flex min-h-9 items-center justify-center gap-2 border border-[#d6af55]/45 bg-[#d6af55]/10 px-3 text-[10px] font-black uppercase tracking-[0.12em] text-[#ffe59b] disabled:cursor-wait disabled:opacity-60"
                            >
                              {testingSource === source ? <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> : null}
                              Test {source === "mlb" ? "MLB API" : source === "polymarket" ? "Polymarket" : source === "matching" ? "Matching Engine" : "Weather"}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="mt-3 grid gap-2 xl:grid-cols-4">
                        {(["polymarket", "mlb", "weather", "matching"] as AstroddsApiTestSource[]).map((source) => {
                          const test = apiTests[source];

                          return (
                            <div key={source} className="border border-white/10 bg-black/35 p-3">
                              <div className="flex items-center justify-between gap-2">
                                <p className="text-[10px] font-black uppercase tracking-[0.16em] text-white">
                                  {source === "mlb" ? "MLB API" : source === "polymarket" ? "Polymarket" : source === "matching" ? "Matching" : "Weather"}
                                </p>
                                <DiagnosticBadge status={test?.status} />
                              </div>
                              <dl className="mt-3 grid gap-1 text-xs text-slate-400">
                                <div className="flex justify-between gap-3">
                                  <dt>HTTP</dt>
                                  <dd className="font-mono text-white">{test?.httpStatus ?? "--"}</dd>
                                </div>
                                <div className="flex justify-between gap-3">
                                  <dt>Count</dt>
                                  <dd className="font-mono text-white">{test?.count ?? "--"}</dd>
                                </div>
                                <div className="flex justify-between gap-3">
                                  <dt>Last Tested</dt>
                                  <dd className="font-mono text-white">{test ? formatDate(test.testedAt) : "--"}</dd>
                                </div>
                              </dl>
                              <p className="mt-2 min-h-9 text-xs leading-5 text-slate-300">{test ? sampleSummary(test.sample) : "Not tested yet."}</p>
                              {test?.sourceUrl ? <p className="mt-2 truncate font-mono text-[10px] text-slate-500" title={test.sourceUrl}>{test.sourceUrl}</p> : null}
                              {test?.error ? <p className="mt-2 text-xs font-black leading-5 text-red-300">{test.error}</p> : null}
                              {test ? (
                                <details className="mt-2">
                                  <summary className="cursor-pointer text-[10px] font-black uppercase tracking-[0.16em] text-[#f4d274]">Raw JSON</summary>
                                  <pre className="mt-2 max-h-44 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-slate-300">
                                    {JSON.stringify(test, null, 2)}
                                  </pre>
                                </details>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {error ? <p className="mt-4 border border-red-300/35 bg-red-400/12 p-3 text-sm font-bold text-red-100">{error}</p> : null}
                    {result?.warnings.length ? (
                      <div className="mt-4 grid gap-2">
                        {result.warnings.slice(0, 3).map((warning) => (
                          <p key={warning} className="border border-yellow-300/25 bg-yellow-400/10 p-3 text-xs font-bold text-yellow-100">
                            {warning}
                          </p>
                        ))}
                      </div>
                    ) : null}

                    {result ? (
                      <div className="mt-4 border border-cyan-300/20 bg-cyan-400/10 p-3">
                        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                          <div>
                            <p className="text-xs font-black uppercase tracking-[0.18em] text-cyan-100">Backend Response Summary</p>
                            <p className="mt-1 font-mono text-[11px] text-slate-400">API route used: {lastScanRoute || `/api/astrodds/scan?sport=${result.sport}`}</p>
                          </div>
                          <Badge className="border-cyan-300/45 bg-cyan-400/10 text-cyan-100">Generated {formatDate(result.generatedAt)}</Badge>
                        </div>
                        <div className="mt-3 grid gap-2 text-xs md:grid-cols-3 xl:grid-cols-10">
                          <div className="border border-white/10 bg-black/30 p-2"><p className="text-slate-500">Markets Fetched</p><p className="mt-1 font-mono text-lg font-black text-white">{result.diagnostics.polymarket.marketsFetched}</p></div>
                          <div className="border border-white/10 bg-black/30 p-2"><p className="text-slate-500">Games Fetched</p><p className="mt-1 font-mono text-lg font-black text-white">{result.diagnostics.sportApi.gamesFetched}</p></div>
                          <div className="border border-white/10 bg-black/30 p-2"><p className="text-slate-500">Weather Fetched</p><p className="mt-1 font-mono text-lg font-black text-white">{result.diagnostics.weather.weatherResultsFetched}</p></div>
                          <div className="border border-white/10 bg-black/30 p-2"><p className="text-slate-500">MLB Markets</p><p className="mt-1 font-mono text-lg font-black text-white">{result.diagnostics.polymarket.mlbMarketsDetected ?? 0}</p></div>
                          <div className="border border-white/10 bg-black/30 p-2"><p className="text-slate-500">Matched Games</p><p className="mt-1 font-mono text-lg font-black text-white">{result.diagnostics.matching.matchedGamesCount} / {result.diagnostics.matching.gamesCount}</p></div>
                          <div className="border border-white/10 bg-black/30 p-2"><p className="text-slate-500">Rows</p><p className="mt-1 font-mono text-lg font-black text-white">{result.games.length}</p></div>
                          <div className="border border-white/10 bg-black/30 p-2"><p className="text-slate-500">Raw Model Picks</p><p className="mt-1 font-mono text-lg font-black text-white">{modelPickDedupe.rawCount}</p></div>
                          <div className="border border-white/10 bg-black/30 p-2"><p className="text-slate-500">Displayed Picks</p><p className="mt-1 font-mono text-lg font-black text-white">{topModelPicks.length}</p></div>
                          <div className="border border-white/10 bg-black/30 p-2"><p className="text-slate-500">Hidden Series</p><p className="mt-1 font-mono text-lg font-black text-white">{topModelPickSeries.hiddenSeriesGames}</p></div>
                          <div className="border border-white/10 bg-black/30 p-2"><p className="text-slate-500">Duplicates Removed</p><p className="mt-1 font-mono text-lg font-black text-white">{modelPickDedupe.removedCount}</p></div>
                        </div>
                        {modelPickDedupe.duplicateExamples.length ? (
                          <div className="mt-3 grid gap-1">
                            {modelPickDedupe.duplicateExamples.map((duplicate) => (
                              <p key={duplicate} className="text-xs font-bold leading-5 text-cyan-100">Duplicate model pick removed: {duplicate}</p>
                            ))}
                          </div>
                        ) : null}
                        {result.diagnostics.lastErrors.length ? (
                          <div className="mt-3 grid gap-1">
                            {result.diagnostics.lastErrors.slice(0, 3).map((lastError) => (
                              <p key={lastError} className="text-xs font-bold leading-5 text-yellow-100">{lastError}</p>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                    <div className="mt-4 grid gap-4 xl:grid-cols-3">
                      <div className="border border-cyan-300/20 bg-cyan-400/10 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-xs font-black uppercase tracking-[0.18em] text-cyan-100">Market / Odds Layer</p>
                          <Badge className={oddsStatusBadgeClass(oddsStatus?.status)}>{oddsStatus?.status?.replace(/_/g, " ") ?? "NOT CONNECTED"}</Badge>
                        </div>
                        <div className="mt-3 grid gap-2 text-xs text-slate-300">
                          <div className="flex justify-between gap-3 border-b border-white/10 pb-2"><span>Provider</span><span className="font-bold text-white">{oddsStatus?.provider ?? "NOT_CONFIGURED"}</span></div>
                          <div className="flex justify-between gap-3 border-b border-white/10 pb-2"><span>Key Configured</span><span className="font-bold text-white">{oddsStatus?.keyConfigured ? "YES" : "NO"}</span></div>
                          <div className="flex justify-between gap-3 border-b border-white/10 pb-2"><span>Official Eligibility</span><span className={oddsStatus?.officialBetEligibility ? "font-bold text-emerald-100" : "font-bold text-yellow-100"}>{oddsStatus?.officialBetEligibility ? "ENABLED" : "BLOCKED"}</span></div>
                          <div className="flex justify-between gap-3 border-b border-white/10 pb-2"><span>Odds Returned</span><span className="font-mono font-bold text-white">{Array.isArray(oddsStatus?.odds) ? oddsStatus?.odds.length : 0}</span></div>
                        </div>
                        <p className="mt-3 text-xs font-bold leading-5 text-slate-300">{oddsStatus?.reason ?? "No odds source connected. Official sports paper picks require real odds or Polymarket price."}</p>
                        {oddsStatus?.sourceUrl ? <p className="mt-2 truncate font-mono text-[10px] text-slate-500" title={oddsStatus.sourceUrl}>{oddsStatus.sourceUrl}</p> : null}
                        <button
                          type="button"
                          onClick={() => refreshOddsStatus(true)}
                          className="mt-3 inline-flex min-h-9 w-full items-center justify-center border border-cyan-300/35 bg-cyan-400/10 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-cyan-100"
                        >
                          Test Real Odds Source
                        </button>
                      </div>

                      <div className="border border-[#d6af55]/25 bg-[#d6af55]/10 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-xs font-black uppercase tracking-[0.18em] text-[#f4d274]">7-Day Paper Test</p>
                          <Badge className={sevenDayPaperTest?.started ? "border-emerald-300/55 bg-emerald-400/12 text-emerald-100" : "border-yellow-300/55 bg-yellow-400/12 text-yellow-100"}>{sevenDayPaperTest?.started ? `DAY ${sevenDayPaperTest.day}` : "NOT STARTED"}</Badge>
                        </div>
                        <div className="mt-3 grid gap-2 text-xs text-slate-300">
                          <div className="flex justify-between gap-3 border-b border-white/10 pb-2"><span>Official Picks</span><span className="font-mono font-bold text-white">{serverPaperSummary?.totalOfficialPaperPicks ?? 0}</span></div>
                          <div className="flex justify-between gap-3 border-b border-white/10 pb-2"><span>Model Leans</span><span className="font-mono font-bold text-white">{serverPaperSummary?.modelLeans.total ?? 0}</span></div>
                          <div className="flex justify-between gap-3 border-b border-white/10 pb-2"><span>Ledger ROI</span><span className={(serverPaperSummary?.roi ?? 0) >= 0 ? "font-bold text-emerald-100" : "font-bold text-red-100"}>{formatRoi(serverPaperSummary?.roi ?? 0)}</span></div>
                          <div className="flex justify-between gap-3 border-b border-white/10 pb-2"><span>Model Accuracy</span><span className="font-bold text-white">{formatPercent((serverPaperSummary?.modelLeans.accuracy ?? 0) * 100)}</span></div>
                        </div>
                        <p className="mt-3 text-xs font-bold leading-5 text-slate-300">Model-only leans are validation records, not bets. Official picks require real entry price and paper mode only.</p>
                        <button
                          type="button"
                          onClick={startSevenDayPaperTest}
                          disabled={Boolean(sevenDayPaperTest?.started) || isStartingPaperTest}
                          className="mt-3 inline-flex min-h-9 w-full items-center justify-center border border-[#f4d274]/60 bg-[#d6af55]/12 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-[#ffe59b] disabled:cursor-not-allowed disabled:opacity-45"
                        >
                          {isStartingPaperTest ? "Starting..." : sevenDayPaperTest?.started ? "Paper Test Running" : "Start 7-Day Paper Test"}
                        </button>
                      </div>

                      <div className="border border-emerald-300/20 bg-emerald-400/10 p-3">
                        <p className="text-xs font-black uppercase tracking-[0.18em] text-emerald-100">Daily Validation Report</p>
                        <div className="mt-3 grid gap-2 text-xs text-slate-300">
                          <div className="flex justify-between gap-3 border-b border-white/10 pb-2"><span>Date</span><span className="font-bold text-white">{dailyReport?.date ?? "--"}</span></div>
                          <div className="flex justify-between gap-3 border-b border-white/10 pb-2"><span>Signals Sent</span><span className="font-mono font-bold text-white">{dailyReport?.signalsSent ?? 0}</span></div>
                          <div className="flex justify-between gap-3 border-b border-white/10 pb-2"><span>Strong / Elite</span><span className="font-mono font-bold text-white">{dailyReport?.strongBuys ?? 0} / {dailyReport?.eliteSignals ?? 0}</span></div>
                          <div className="flex justify-between gap-3 border-b border-white/10 pb-2"><span>Daily ROI</span><span className={(dailyReport?.roi ?? 0) >= 0 ? "font-bold text-emerald-100" : "font-bold text-red-100"}>{formatRoi(dailyReport?.roi ?? 0)}</span></div>
                          <div className="flex justify-between gap-3 border-b border-white/10 pb-2"><span>CLV</span><span className="font-bold text-white">{dailyReport?.averageClv === null || dailyReport?.averageClv === undefined ? "--" : formatEdge(dailyReport.averageClv)}</span></div>
                        </div>
                        {dailyNoBetReasons.length ? (
                          <div className="mt-3 grid gap-1 text-xs font-bold text-yellow-100">
                            {dailyNoBetReasons.map((item) => <p key={item.reason}>{item.reason}: {item.count}</p>)}
                          </div>
                        ) : <p className="mt-3 text-xs font-bold text-slate-400">No no-bet reasons logged today.</p>}
                        {modelLeansSavedAt ? <p className="mt-2 text-[10px] font-bold text-slate-500">Model leans saved: {formatDate(modelLeansSavedAt)}</p> : null}
                      </div>
                    </div>



                    {result ? (
                      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1fr]">
                        <div className="border border-emerald-300/20 bg-emerald-400/10 p-3">
                          <p className="text-xs font-black uppercase tracking-[0.18em] text-emerald-100">MLB StatsAPI Health</p>
                          <div className="mt-3 grid gap-2 text-xs md:grid-cols-5 xl:grid-cols-1 2xl:grid-cols-5">
                            {statsApiHealthItems(result).map(([label, connected, total]) => (
                              <div key={label} className="border border-white/10 bg-black/30 p-2">
                                <p className="text-slate-500">{label}</p>
                                <p className="mt-1 font-mono text-lg font-black text-white">{connected} / {total}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="border border-yellow-300/20 bg-yellow-400/10 p-3">
                          <p className="text-xs font-black uppercase tracking-[0.18em] text-yellow-100">Missing Data Warnings</p>
                          {missingDataWarnings.length ? (
                            <div className="mt-3 grid gap-1">
                              {missingDataWarnings.map((warning) => (
                                <p key={warning} className="text-xs font-bold leading-5 text-yellow-100">{warning}</p>
                              ))}
                            </div>
                          ) : (
                            <p className="mt-3 text-xs font-bold text-slate-400">Run a scan to populate model warning details.</p>
                          )}
                        </div>
                      </div>
                    ) : null}
                    <details className="mt-4 border border-white/10 bg-black/35 p-3">
                      <summary className="cursor-pointer text-xs font-black uppercase tracking-[0.18em] text-[#f1d27a]">Show Debug Details</summary>
                      {result?.diagnostics ? (
                        <div className="mt-4 grid gap-4 lg:grid-cols-2">
                          {[
                            ["Polymarket", result.diagnostics.polymarket],
                            ["MLB API", result.diagnostics.sportApi],
                            ["Weather", result.diagnostics.weather],
                            ["Matching", result.diagnostics.matching],
                            ["Order Book", result.diagnostics.orderBook],
                          ].map(([label, diagnostic]) => (
                            <div key={label as string} className="border border-white/10 bg-black/30 p-3">
                              <div className="mb-2 flex items-center justify-between gap-3">
                                <p className="text-xs font-black uppercase tracking-[0.14em] text-white">{label as string}</p>
                                <DiagnosticBadge status={(diagnostic as { status: AstroddsDiagnosticStatus }).status} />
                              </div>
                              <pre className="max-h-72 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-300">
                                {JSON.stringify(diagnostic, null, 2)}
                              </pre>
                            </div>
                          ))}
                          <div className="border border-white/10 bg-black/30 p-3 lg:col-span-2">
                            <p className="text-xs font-black uppercase tracking-[0.14em] text-white">Last Errors</p>
                            <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-300">
                              {JSON.stringify(result.diagnostics.lastErrors, null, 2)}
                            </pre>
                          </div>
                          {Object.keys(apiTests).length ? (
                            <div className="border border-white/10 bg-black/30 p-3 lg:col-span-2">
                              <p className="text-xs font-black uppercase tracking-[0.14em] text-white">API Connection Test Results</p>
                              <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-300">
                                {JSON.stringify(apiTests, null, 2)}
                              </pre>
                            </div>
                          ) : null}
                          {unifiedSignals.length ? (
                            <div className="border border-white/10 bg-black/30 p-3 lg:col-span-2">
                              <p className="text-xs font-black uppercase tracking-[0.14em] text-white">Unified Signal Engine</p>
                              <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-300">
                                {JSON.stringify(
                                  unifiedSignals.slice(0, 20).map((signal) => ({
                                    signalId: signal.signalId,
                                    game: signal.game,
                                    pick: signal.pick,
                                    decision: signal.decision,
                                    edge: signal.edge,
                                    dataQuality: signal.dataQuality,
                                    orderBookQuality: signal.orderBookQuality,
                                    whaleSupport: signal.whaleSupport,
                                    copyability: signal.copyability,
                                    signalType: signal.signalType,
                                    warnings: signal.warnings,
                                    why: signal.why,
                                  })),
                                  null,
                                  2,
                                )}
                              </pre>
                            </div>
                          ) : null}
                        </div>
                      ) : (
                        <p className="mt-3 text-sm text-slate-400">Run a scan to populate raw diagnostics, source URLs, unmatched games, and unmatched markets.</p>
                      )}
                    </details>
                  </div>

                  <section className="grid gap-4 xl:grid-cols-[minmax(260px,0.78fr)_1.9fr]">
                    <article className="astro-chrome-card p-4">
                      <div className="mb-4 flex items-center justify-between gap-3 border-b border-white/10 pb-3">
                        <div>
                          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-[#f4d274]">Best Pick</p>
                          <h3 className="mt-1 text-lg font-black uppercase tracking-[0.08em] text-white">Scan Summary</h3>
                        </div>
                        <Badge className={bestModelPickOfficial ? decisionClass.BUY : "border-cyan-300/35 bg-cyan-300/10 text-cyan-100"}>{bestModelPickOfficial ? "Official" : "Data Only"}</Badge>
                      </div>
                      {bestModelPick?.game.modelPick ? (
                        <div className="grid gap-3">
                          <Badge className={modelDisplayStatusClass(modelDisplayStatus(bestModelPick))}>{modelDisplayStatus(bestModelPick)}</Badge>
                          <h4 className="break-words text-xl font-black uppercase tracking-[0.06em] text-white">{bestModelPick.game.game}</h4>
                          <p className="text-sm font-black text-[#f4d274]">{bestModelPickOfficial && bestModelPick.market ? clearBetText(bestModelPick.market) : modelPickText(bestModelPick.game)}</p>
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <div className="border border-white/10 bg-black/35 p-3"><p className="text-slate-500">Confidence</p><p className="mt-1 text-lg font-black text-white">{bestModelPick.game.modelPick.modelConfidence}%</p></div>
                            <div className="border border-white/10 bg-black/35 p-3"><p className="text-slate-500">Score</p><p className="mt-1 text-lg font-black text-white">{bestModelPick.game.modelPick.modelScore}/100</p></div>
                            <div className="border border-white/10 bg-black/35 p-3"><p className="text-slate-500">Entry</p><p className="mt-1 text-lg font-black text-white">{bestModelPickOfficial && bestModelPick.market ? formatPrice(bestModelPick.market.currentPrice) : "--"}</p></div>
                            <div className="border border-white/10 bg-black/35 p-3"><p className="text-slate-500">Stake</p><p className="mt-1 text-lg font-black text-white">{bestModelPickOfficial ? "5%" : "0%"}</p></div>
                          </div>
                          <p className="text-sm leading-6 text-slate-300">{shortContext(bestModelPick.game.modelPick.modelReason, bestModelPick.game.modelPick.modelReason.slice(0, 180))}</p>
                          <p className="border border-yellow-300/25 bg-yellow-400/10 p-3 text-xs font-bold text-yellow-100">
                            {bestModelPickOfficial ? "Official paper mode only. Real money trading OFF." : "Official bet: NO. Action: WAIT FOR ODDS."}
                          </p>
                        </div>
                      ) : (
                        <div className="grid min-h-[220px] place-items-center border border-white/10 bg-black/35 p-5 text-center">
                          <div>
                            <p className="text-lg font-black uppercase tracking-[0.1em] text-white">No model lean above threshold.</p>
                            <p className="mt-3 text-sm leading-6 text-slate-400">ASTRODDS will show WAIT when context is too thin or confidence is genuinely low.</p>
                          </div>
                        </div>
                      )}
                    </article>

                    <article className="astro-chrome-card min-w-0 p-4">
                      <div className="mb-4 flex flex-col gap-3 border-b border-[#d6af55]/25 pb-4 md:flex-row md:items-start md:justify-between">
                        <div className="min-w-0">
                          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-[#f4d274]">MLB Matched Opportunities</p>
                          <h3 className="mt-1 text-lg font-black uppercase tracking-[0.08em] text-white">Top MLB Picks</h3>
                          <p className="mt-2 text-xs font-bold leading-5 text-slate-400">Data-only picks are not official bets until real odds/market price is connected.</p>
                        </div>
                        <div className="flex shrink-0 flex-wrap gap-2">
                          <Badge className="border-cyan-300/35 bg-cyan-300/10 text-cyan-100">{topModelPicks.length} displayed pool</Badge>
                          <Badge className="border-yellow-300/45 bg-yellow-400/10 text-yellow-100">{topModelPickSeries.hiddenSeriesGames} hidden series</Badge>
                          <Badge className={modelPickDedupe.removedCount ? "border-yellow-300/45 bg-yellow-400/10 text-yellow-100" : "border-emerald-300/45 bg-emerald-400/10 text-emerald-100"}>{modelPickDedupe.removedCount} duplicates</Badge>
                        </div>
                      </div>
                      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap gap-2">
                          <Badge className="border-slate-300/35 bg-slate-400/10 text-slate-200">Raw {modelPickDedupe.rawCount}</Badge>
                          <Badge className="border-slate-300/35 bg-slate-400/10 text-slate-200">Displayed {visibleTopModelPicks.length}</Badge>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => setShowSeriesGames((value) => !value)}
                            className="inline-flex min-h-8 items-center justify-center border border-cyan-300/35 bg-cyan-400/10 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-cyan-100"
                          >
                            {showSeriesGames ? "Hide Series Games" : "Show Series Games"}
                          </button>
                          {topModelPicks.length > 8 ? (
                            <button
                              type="button"
                              onClick={() => setShowAllModelPicks((value) => !value)}
                              className="inline-flex min-h-8 items-center justify-center border border-[#d6af55]/45 bg-[#d6af55]/10 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-[#ffe7a1]"
                            >
                              {showAllModelPicks ? "Show Top 8" : `Show All ${topModelPicks.length}`}
                            </button>
                          ) : null}
                        </div>
                      </div>

                      <div className="overflow-hidden border border-white/10 bg-black/25">
                        <div className="hidden grid-cols-[1.15fr_0.7fr_0.8fr_0.55fr_1.55fr_0.8fr] border-b border-[#d6af55]/25 bg-white/[0.03] text-[10px] font-black uppercase tracking-[0.14em] text-slate-400 lg:grid">
                          <div className="p-3">Game</div>
                          <div className="p-3">Market</div>
                          <div className="p-3">Odds / Entry</div>
                          <div className="p-3">Confidence</div>
                          <div className="p-3">Factors / Reason</div>
                          <div className="p-3">Status</div>
                        </div>
                        {visibleTopModelPicks.length ? (
                          <div className="divide-y divide-white/[0.08]">
                            {visibleTopModelPicks.map((row) => {
                              const pick = row.game.modelPick;
                              if (!pick) return null;
                              const status = modelDisplayStatus(row);
                              const doubleheader = doubleheaderLabel(row, modelPickRows);
                              const warnings = pick.missingDataWarnings.slice(0, 3);
                              return (
                                <details key={`${modelPickDedupeKey(row)}-compact`} className="group">
                                  <summary className="grid cursor-pointer gap-3 p-3 hover:bg-white/[0.025] lg:grid-cols-[1.15fr_0.7fr_0.8fr_0.55fr_1.55fr_0.8fr] lg:items-center">
                                    <div className="min-w-0">
                                      <div className="flex items-center gap-3">
                                        <div className="grid size-9 shrink-0 place-items-center rounded-full border border-[#d6af55]/35 bg-black text-[10px] font-black text-[#f4d274]">{teamInitials(row.game.awayTeam)}</div>
                                        <div className="min-w-0">
                                          <p className="break-words text-sm font-black uppercase tracking-[0.05em] text-white">{row.game.game}</p>
                                          <p className="mt-1 text-xs font-bold text-slate-500">{formatDate(row.game.startTime)} | {row.game.venue ?? "Venue TBD"}</p>
                                        </div>
                                      </div>
                                      {doubleheader ? <Badge className="mt-2 border-cyan-300/35 bg-cyan-300/10 text-cyan-100">DH {doubleheader}</Badge> : null}
                                    </div>
                                    <div><p className="text-sm font-bold text-white">{compactMarketLabel(row)}</p><p className="mt-1 text-xs text-slate-500">{row.market ? row.market.marketTitle : "No market matched"}</p></div>
                                    <div><p className="text-sm font-black text-cyan-100">{compactEntryLabel(row)}</p><p className="mt-1 text-xs text-slate-500">{row.market ? "Paper mode only" : "No fake odds"}</p></div>
                                    <div><Badge className={confidenceClass(pick.modelConfidence)}>{pick.modelConfidence}%</Badge><p className="mt-1 text-xs text-slate-500">Score {pick.modelScore}</p></div>
                                    <div className="min-w-0"><p className="line-clamp-2 text-xs font-bold leading-5 text-slate-300">{compactModelFactors(row)}</p>{warnings.length ? <div className="mt-1 flex flex-wrap gap-1">{warnings.slice(0, 2).map((warning) => <Badge key={warning} className="border-yellow-300/35 bg-yellow-400/10 text-yellow-100">{shortContext(warning, warning.length > 32 ? `${warning.slice(0, 29)}...` : warning)}</Badge>)}</div> : null}</div>
                                    <div><Badge className={modelDisplayStatusClass(status)}>{status}</Badge><p className="mt-1 text-[10px] font-bold text-slate-500">Details</p></div>
                                  </summary>
                                  <div className="border-t border-white/10 bg-black/35 p-3 text-xs leading-5 text-slate-300">
                                    <p><span className="font-black text-white">Full reason:</span> {pick.modelReason}</p>
                                    <p className="mt-2"><span className="font-black text-white">Blocked reason:</span> {pick.officialBetBlockedReason ?? "No official block."}</p>
                                    {warnings.length ? <p className="mt-2"><span className="font-black text-white">Missing:</span> {warnings.join(" | ")}</p> : null}
                                  </div>
                                </details>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="grid min-h-[220px] place-items-center p-6 text-center">
                            <div>
                              <p className="text-lg font-black uppercase tracking-[0.1em] text-white">No model lean above threshold.</p>
                              <p className="mt-3 text-sm leading-6 text-slate-400">No StatsAPI model pick cleared the data-only threshold. Best action: WAIT.</p>
                            </div>
                          </div>
                        )}
                      </div>
                    </article>
                  </section>

                  <section className="grid gap-4 xl:grid-cols-[minmax(280px,0.9fr)_1.6fr]">
                    <article className="astro-chrome-card p-4">
                      <div className="mb-4 flex items-center justify-between gap-3 border-b border-white/10 pb-3">
                        <div>
                          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-[#f4d274]">Best Final Signal</p>
                          <h3 className="mt-1 text-lg font-black uppercase tracking-[0.08em] text-white">Unified Edge</h3>
                        </div>
                        <Badge className="border-[#d6af55]/45 bg-[#d6af55]/10 text-[#ffe7a1]">$50 Paper</Badge>
                      </div>

                      {bestFinalSignal ? (
                        <div>
                          <DecisionBadge decision={bestFinalSignal.decision as AstroddsDecision} />
                          <h4 className="mt-3 text-xl font-black uppercase tracking-[0.06em] text-white">{bestFinalSignal.game}</h4>
                          <p className="mt-2 text-sm font-black text-[#f4d274]">{signalBetText(bestFinalSignal)}</p>
                          <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                            <div className="border border-white/10 bg-black/35 p-3">
                              <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">Entry</p>
                              <p className="mt-1 text-xl font-black text-white">{formatPrice(bestFinalSignal.entryPrice)}</p>
                            </div>
                            <div className="border border-white/10 bg-black/35 p-3">
                              <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">Edge</p>
                              <p className="mt-1 text-xl font-black text-emerald-200">{formatEdge(bestFinalSignal.edge)}</p>
                            </div>
                            <div className="border border-white/10 bg-black/35 p-3">
                              <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">Model Prob.</p>
                              <p className="mt-1 text-xl font-black text-white">{formatProbability(bestFinalSignal.modelProbability)}</p>
                            </div>
                            <div className="border border-white/10 bg-black/35 p-3">
                              <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">Market Prob.</p>
                              <p className="mt-1 text-xl font-black text-white">{formatProbability(bestFinalSignal.marketProbability)}</p>
                            </div>
                          </div>
                          <p className="mt-4 text-sm leading-6 text-slate-300">{bestFinalSignal.why.slice(0, 3).join(" ")}</p>
                          <div className="mt-4 grid gap-2 text-xs">
                            <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-2">
                              <span className="text-slate-400">Expected Value</span>
                              <span className="font-bold text-emerald-100">{formatExpectedValue(bestFinalSignal.expectedValue)}</span>
                            </div>
                            <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-2">
                              <span className="text-slate-400">Data Quality</span>
                              <DataQualityBadge quality={bestFinalSignal.dataQuality} />
                            </div>
                            {bestFinalSignal.gameRef && bestFinalSignal.marketRef
                              ? Object.entries(dataStatuses(bestFinalSignal.gameRef, bestFinalSignal.marketRef)).map(([label, status]) => (
                                  <div key={label} className="flex items-center justify-between gap-3 border-b border-white/10 pb-2">
                                    <span className="capitalize text-slate-400">{label}</span>
                                    <StatusBadge status={status} />
                                  </div>
                                ))
                              : null}
                            <div className="border-b border-white/10 pb-2">
                              <p className="text-slate-400">Order Book</p>
                              <p className="mt-1 font-bold text-white">{signalOrderBookSummary(bestFinalSignal)}</p>
                            </div>
                            <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-2">
                              <span className="text-slate-400">Whale Intelligence</span>
                              <span className="font-bold text-white">{bestFinalSignal.whaleSupport.replace(/_/g, " ")} / {bestFinalSignal.copyability.replace(/_/g, " ")}</span>
                            </div>
                            <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-2">
                              <span className="text-slate-400">Telegram</span>
                              <span className="font-bold text-yellow-100">{telegramStatusForSignal(bestFinalSignal, telegramStatus)}</span>
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={() => bestFinalSignal.gameRef && bestFinalSignal.marketRef ? addPaperTrade(bestFinalSignal.gameRef, bestFinalSignal.marketRef, bestFinalSignal) : undefined}
                            disabled={!canPaperTradeSignal(bestFinalSignal) || exposure >= MAX_ACTIVE_EXPOSURE || Boolean(bestFinalSignal.marketRef && paperTrades.some((trade) => trade.id === paperTradeId(bestFinalSignal.marketRef as AstroddsMarketScan)))}
                            className="mt-4 inline-flex h-11 w-full items-center justify-center border border-emerald-300/40 bg-emerald-400/12 px-4 text-xs font-black uppercase tracking-[0.16em] text-emerald-50 disabled:opacity-45"
                          >
                            Paper Trade 5%
                          </button>
                        </div>
                      ) : (
                        <div className="grid min-h-[280px] place-items-center border border-white/10 bg-black/35 p-5 text-center">
                          <div>
                            <p className="text-lg font-black uppercase tracking-[0.1em] text-white">No Strong Buy detected. Best action: WAIT.</p>
                            <p className="mt-3 text-sm leading-6 text-slate-400">
                              ASTRODDS will only label Strong Buy when the market is matched to a real MLB game and data quality supports the price.
                            </p>
                          </div>
                        </div>
                      )}
                    </article>

                    <article className="astro-table-wrap overflow-x-auto">
                      <div className="flex flex-col gap-2 border-b border-[#d6af55]/25 p-4 md:flex-row md:items-center md:justify-between">
                        <div>
                          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-[#f4d274]">Official Qualified Picks</p>
                          <h3 className="mt-1 text-lg font-black uppercase tracking-[0.08em] text-white">Odds-Backed MLB Decisions</h3>
                        </div>
                        <Badge className="border-cyan-300/35 bg-cyan-300/10 text-cyan-100">{topQualifiedSignals.length} official qualified picks</Badge>
                      </div>
                      <table className="min-w-[1780px] w-full text-left text-sm">
                        <thead>
                          <tr className="border-b border-[#d6af55]/25 text-[10px] uppercase tracking-[0.14em] text-slate-400">
                            <th className="p-3">Rank</th>
                            <th className="p-3">Decision</th>
                            <th className="p-3">Game</th>
                            <th className="p-3">Bet</th>
                            <th className="p-3">Entry</th>
                            <th className="p-3">Model Prob.</th>
                            <th className="p-3">Market Prob.</th>
                            <th className="p-3">Edge</th>
                            <th className="p-3">EV</th>
                            <th className="p-3">Confidence</th>
                            <th className="p-3">Data Quality</th>
                            <th className="p-3">Why</th>
                            <th className="p-3">Data Status</th>
                            <th className="p-3">Order Book</th>
                            <th className="p-3">Whale Intelligence</th>
                            <th className="p-3">Paper Trade</th>
                            <th className="p-3">Telegram</th>
                          </tr>
                        </thead>
                        <tbody>
                          {topQualifiedSignals.length ? (
                            topQualifiedSignals.map((signal, index) => {
                              const gameRef = signal.gameRef;
                              const marketRef = signal.marketRef;
                              const statuses = gameRef && marketRef ? dataStatuses(gameRef, marketRef) : undefined;
                              const alreadyTraded = marketRef ? paperTrades.some((trade) => trade.id === paperTradeId(marketRef)) : false;

                              return (
                                <tr key={`${signal.signalId}-ranked`} className="border-b border-white/[0.08] align-top hover:bg-white/[0.025]">
                                  <td className="p-3 text-xl font-black text-[#f4d274]">#{index + 1}</td>
                                  <td className="p-3"><DecisionBadge decision={signal.decision as AstroddsDecision} /></td>
                                  <td className="p-3">
                                    <p className="font-black text-white">{signal.game}</p>
                                    <p className="mt-1 text-xs text-slate-500">{formatDate(gameRef?.startTime)} | {gameRef?.venue ?? "Venue TBD"}</p>
                                  </td>
                                  <td className="p-3">
                                    <p className="font-black text-white">{signal.marketType}</p>
                                    <p className="mt-1 text-xs text-[#f4d274]">{signalBetText(signal)}</p>
                                  </td>
                                  <td className="p-3 text-cyan-100">{formatPrice(signal.entryPrice)}</td>
                                  <td className="p-3 font-black text-white">{formatProbability(signal.modelProbability)}</td>
                                  <td className="p-3 text-slate-300">{formatProbability(signal.marketProbability)}</td>
                                  <td className={`p-3 font-black ${(signal.edge ?? 0) > 0 ? "text-emerald-200" : "text-red-200"}`}>
                                    {formatEdge(signal.edge)}
                                  </td>
                                  <td className={`p-3 font-black ${(signal.expectedValue ?? 0) > 0 ? "text-emerald-200" : "text-red-200"}`}>
                                    {formatExpectedValue(signal.expectedValue)}
                                  </td>
                                  <td className="p-3 text-slate-300">{signal.confidence}</td>
                                  <td className="p-3"><DataQualityBadge quality={signal.dataQuality} /></td>
                                  <td className="max-w-[300px] p-3">
                                    <p className="text-xs leading-5 text-slate-300">{signal.why.slice(0, 3).join(" ")}</p>
                                    {signal.warnings.length ? <p className="mt-2 text-xs font-bold leading-5 text-yellow-100">Warnings: {signal.warnings.slice(0, 2).join(" ")}</p> : null}
                                  </td>
                                  <td className="p-3">
                                    <div className="grid gap-1.5">
                                      {statuses
                                        ? ([
                                            ["Pitchers", statuses.pitchers],
                                            ["Weather", statuses.weather],
                                            ["Lineup", statuses.lineups],
                                            ["Injuries", statuses.injuries],
                                            ["Price", statuses.polymarket],
                                          ] as const).map(([label, status]) => (
                                            <div key={label} className="flex items-center justify-between gap-2 text-[10px]">
                                              <span className="text-slate-500">{label}</span>
                                              <StatusBadge status={status} />
                                            </div>
                                          ))
                                        : <span className="text-xs text-slate-500">Data only</span>}
                                    </div>
                                  </td>
                                  <td className="max-w-[230px] p-3 text-xs leading-5 text-slate-300">{signalOrderBookSummary(signal)}</td>
                                  <td className="p-3 text-xs font-bold text-slate-300">
                                    <p>{signal.whaleSupport.replace(/_/g, " ")}</p>
                                    <p className="mt-1 text-slate-500">{signal.copyability.replace(/_/g, " ")} | {signal.signalType.replace(/_/g, " ")}</p>
                                  </td>
                                  <td className="p-3">
                                    {canPaperTradeSignal(signal) && gameRef && marketRef ? (
                                      <button
                                        type="button"
                                        onClick={() => addPaperTrade(gameRef, marketRef, signal)}
                                        disabled={exposure >= MAX_ACTIVE_EXPOSURE || alreadyTraded}
                                        className="inline-flex min-h-10 items-center justify-center border border-emerald-300/35 bg-emerald-400/12 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-emerald-50 disabled:opacity-45"
                                      >
                                        Paper Trade 5%
                                      </button>
                                    ) : (
                                      <Badge className="border-yellow-300/45 bg-yellow-400/10 text-yellow-100">Watch Only</Badge>
                                    )}
                                  </td>
                                  <td className="p-3 text-xs font-bold text-yellow-100">{telegramStatusForSignal(signal, telegramStatus)}</td>
                                </tr>
                              );
                            })
                          ) : (
                            <tr>
                              <td colSpan={17} className="p-8 text-center text-sm font-bold text-slate-400">
                                Official Qualified Picks: 0. No matched betting market with real entry price passed the threshold. Data-only model picks are shown above.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </article>
                  </section>

                  <article className="astro-table-wrap overflow-x-auto">
                    <div className="flex flex-col gap-2 border-b border-[#d6af55]/25 p-4 md:flex-row md:items-center md:justify-between">
                      <div>
                        <p className="text-[10px] font-black uppercase tracking-[0.22em] text-[#f4d274]">Whale Bonus Signals</p>
                        <h3 className="mt-1 text-lg font-black uppercase tracking-[0.08em] text-white">Public Wallet Bonus Layer</h3>
                        <p className="mt-1 text-xs text-slate-500">Bonus only. Whale activity does not create official MLB picks without ASTRODDS model agreement.</p>
                      </div>
                      <Badge className="border-yellow-300/45 bg-yellow-400/10 text-yellow-100">{whaleBonusSignals.length} bonus signals</Badge>
                    </div>
                    <table className="min-w-[980px] w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-[#d6af55]/25 text-[10px] uppercase tracking-[0.14em] text-slate-400">
                          <th className="p-3">Market</th>
                          <th className="p-3">Side</th>
                          <th className="p-3">Whale Grade</th>
                          <th className="p-3">Entry</th>
                          <th className="p-3">Now</th>
                          <th className="p-3">Copyability</th>
                          <th className="p-3">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {whaleBonusSignals.length ? (
                          whaleBonusSignals.map((signal) => {
                            const bonusStatus = whaleBonusStatus(signal);
                            return (
                              <tr key={`${signal.signalId}-whale-bonus`} className="border-b border-white/[0.08] align-top hover:bg-white/[0.025]">
                                <td className="p-3">
                                  <p className="font-black text-white">{signal.game}</p>
                                  <p className="mt-1 text-xs text-slate-500">{signal.marketType}</p>
                                </td>
                                <td className="p-3">
                                  <p className="font-bold text-[#f4d274]">{signal.pick.replace(/ at .*/, "")}</p>
                                  <p className="mt-1 text-xs text-slate-500">{signal.signalType.replace(/_/g, " ")}</p>
                                </td>
                                <td className="p-3 text-xs font-bold text-slate-300">{signal.whaleSupport.replace(/_/g, " ")}</td>
                                <td className="p-3 font-mono text-cyan-100">{formatPrice(signal.whaleConsensus?.averageWhaleEntry)}</td>
                                <td className="p-3 font-mono text-white">{formatPrice(signal.entryPrice)}</td>
                                <td className="p-3 text-xs font-bold text-slate-300">{signal.copyability.replace(/_/g, " ")}</td>
                                <td className="p-3"><Badge className={whaleBonusStatusClass(bonusStatus)}>{bonusStatus}</Badge></td>
                              </tr>
                            );
                          })
                        ) : (
                          <tr>
                            <td colSpan={7} className="p-6 text-center text-sm font-bold text-slate-400">
                              No whale bonus signals loaded yet. Run Whale Scan Once from Wallet Intelligence to attach public wallet context.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </article>
                  <div className="astro-table-wrap overflow-x-auto">
                    <div className="flex flex-col gap-3 border-b border-[#d6af55]/25 p-4 md:flex-row md:items-center md:justify-between">
                      <div>
                        <h3 className="text-sm font-black uppercase tracking-[0.18em] text-white">MLB Matched Opportunities</h3>
                        <p className="mt-1 text-xs text-slate-500">{rows.length} MLB game groups from real scan rows | {dataOnlySignals.length} data-only WAIT rows</p>
                      </div>
                      <div className="flex gap-2">
                        {dataOnlyMode ? <Badge className="border-yellow-300/55 bg-yellow-400/12 text-yellow-100">Mode: MLB Data Only</Badge> : null}
                        <Badge className="border-[#d6af55]/45 bg-[#d6af55]/10 text-[#ffe7a1]">All Markets</Badge>
                        <Badge className="border-slate-300/35 bg-slate-400/10 text-slate-200">Filters</Badge>
                      </div>
                    </div>
                    <table className="astro-opportunity-table min-w-[1480px] w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-[#d6af55]/25 text-[10px] uppercase tracking-[0.16em] text-slate-400">
                          <th className="p-3">Game</th>
                          <th className="p-3">Market</th>
                          <th className="p-3">Pick</th>
                          <th className="p-3">Entry Price</th>
                          <th className="p-3">Model Probability</th>
                          <th className="p-3">Market Probability</th>
                          <th className="p-3">Edge</th>
                          <th className="p-3">Weather</th>
                          <th className="p-3">Pitchers</th>
                          <th className="p-3">Confidence</th>
                          <th className="p-3">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {!result ? (
                          <tr>
                            <td colSpan={11} className="p-8 text-center text-sm font-bold text-slate-400">
                              Select MLB and scan. ASTRODDS will fetch sports data, Polymarket markets, weather, then match and score entries.
                            </td>
                          </tr>
                        ) : rows.length ? (
                          rows.map((row) => (
                            <tr key={`${row.game.id}-${row.market?.marketId ?? "no-market"}-${row.market?.pick ?? ""}`} className="border-b border-white/[0.08] align-top hover:bg-white/[0.025]">
                              <td className="p-3">
                                <div className="flex items-center gap-3">
                                  <div className="grid size-10 shrink-0 place-items-center rounded-full border border-[#d6af55]/35 bg-black text-xs font-black text-[#f4d274]">
                                    {teamInitials(row.game.awayTeam)}
                                  </div>
                                  <div>
                                    <p className="font-black text-white">{row.game.game}</p>
                                    <p className="mt-1 text-xs text-slate-500">{formatDate(row.game.startTime)} | {row.game.period ?? row.game.liveStatus}</p>
                                  </div>
                                </div>
                              </td>
                              <td className="max-w-[180px] p-3 text-slate-300">
                                <p className="font-bold text-white">{row.market ? marketTypeLabel(row.market) : modelLeanForGame(row.game).label}</p>
                                <p className="mt-1 text-xs text-slate-500">{row.market ? shortContext(row.market.marketTitle, "No matching market found.") : modelLeanForGame(row.game).reason}</p>
                              </td>
                              <td className="p-3">
                                <p className="font-black text-white">{row.market ? clearBetText(row.market) : modelPickText(row.game)}</p>
                                <p className="mt-1 text-xs text-slate-500">{row.market?.score?.entryQuality?.replace(/_/g, " ") ?? "No official bet - no matched Polymarket entry price."}</p>
                              </td>
                              <td className="p-3">
                                <p className="mt-1 text-xs text-cyan-100">{row.market ? `${formatPrice(row.market.currentPrice)} Polymarket` : "--"}</p>
                                <p className="text-xs text-slate-500">{orderBookSummary(row.market)}</p>
                              </td>
                              <td className="p-3">
                                <p className="font-black text-white">{row.market ? formatProbability(row.market.probability?.modelProbability) : `${modelLeanForGame(row.game).confidence}% confidence`}</p>
                                <p className="mt-1 text-xs text-slate-500">{row.market?.probability?.dataQuality ?? `Data quality ${modelLeanForGame(row.game).quality}`}</p>
                              </td>
                              <td className="p-3 text-slate-300">{row.market ? formatProbability(row.market.probability?.marketImpliedProbability) : "--"}</td>
                              <td className={`p-3 font-black ${row.market && (row.market.probability?.edge ?? 0) > 0 ? "text-emerald-200" : "text-slate-500"}`}>
                                {row.market ? formatEdge(row.market.probability?.edge) : "--"}
                              </td>
                              <td className="max-w-[150px] p-3 text-slate-300">
                                <StatusBadge status={row.game.weather?.status} />
                                <p className="mt-1 text-xs text-slate-500">{shortContext(row.game.weather?.summary, "Weather source needed")}</p>
                              </td>
                              <td className="max-w-[160px] p-3 text-slate-300">
                                <p className="text-xs leading-5 text-slate-300">{shortContext(row.game.keyPlayerStatus, "Pitchers not connected")}</p>
                              </td>
                              <td className="p-3">
                                <div className="astro-score" style={{ ["--score" as string]: `${row.market?.score?.total ?? modelLeanForGame(row.game).score}%` }}>
                                  <span>{row.market?.score?.total ?? modelLeanForGame(row.game).score}</span>
                                </div>
                                <p className="mt-2 text-xs text-slate-300">{row.market?.confidence?.replace(/_/g, " ") ?? "MODEL PICK / DATA ONLY"}</p>
                                <p className="mt-1 text-[10px] font-bold text-slate-500">{row.market?.probability?.dataQuality ?? `Data ${modelLeanForGame(row.game).quality}`}</p>
                              </td>
                              <td className="p-3">
                                {row.market && canPaperTradePick(row.market) ? (
                                  <div className="grid gap-2">
                                    <DecisionBadge decision={row.market.decision} />
                                    <button
                                      type="button"
                                      onClick={() => addPaperTrade(row.game, row.market as AstroddsMarketScan)}
                                      disabled={exposure >= MAX_ACTIVE_EXPOSURE || paperTrades.some((trade) => row.market && trade.id === paperTradeId(row.market))}
                                      className="inline-flex min-h-10 items-center justify-center border border-emerald-300/35 bg-emerald-400/12 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-emerald-50 disabled:opacity-45"
                                    >
                                      Paper Trade 5%
                                    </button>
                                  </div>
                                ) : (
                                  <Badge className={modelActionClass(modelLeanForGame(row.game).action)}>{modelLeanForGame(row.game).action}</Badge>
                                )}
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={11} className="p-8 text-center text-sm font-bold text-slate-400">
                              No live MLB rows returned. Open Show Debug Details.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>

                <aside className="grid content-start gap-4">
                  <div className="astro-panel-soft p-4">
                    <div className="mb-4 flex items-center justify-between gap-3 border-b border-white/10 pb-3">
                      <h3 className="text-xs font-black uppercase tracking-[0.2em] text-[#f4d274]">Paper Trading Summary</h3>
                      <button type="button" onClick={() => jumpTo("paper")} className="text-[10px] font-black uppercase tracking-[0.14em] text-[#f4d274]">View All</button>
                    </div>
                    <div className="grid grid-cols-3 gap-0 text-sm">
                      <div className="border-r border-white/10 pr-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">Bankroll</p>
                        <p className="mt-2 text-xl font-black text-white">${bankroll.toFixed(0)}</p>
                        <p className="text-xs text-slate-500">$1000 simulated</p>
                      </div>
                      <div className="border-r border-white/10 px-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">Stake</p>
                        <p className="mt-2 text-xl font-black text-white">${DEFAULT_PAPER_STAKE}</p>
                        <p className="text-xs text-slate-500">5% default</p>
                      </div>
                      <div className="pl-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">Exposure</p>
                        <p className="mt-2 text-xl font-black text-white">${exposure.toFixed(0)}</p>
                        <p className="text-xs text-slate-500">Max ${MAX_ACTIVE_EXPOSURE}</p>
                      </div>
                      <div className="mt-4 border-r border-white/10 pr-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">Open Trades</p>
                        <p className="mt-2 text-xl font-black text-white">{openPaperTrades.length}</p>
                        <p className="text-xs text-slate-500">Active positions</p>
                      </div>
                      <div className="mt-4 border-r border-white/10 px-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">Paper P/L</p>
                        <p className="mt-2 text-xl font-black text-emerald-300">{currency(paperPnl)}</p>
                        <p className="text-xs text-emerald-300">Virtual only</p>
                      </div>
                      <div className="mt-4 pl-3">
                        <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">ROI / Win Rate</p>
                        <p className="mt-2 text-xl font-black text-emerald-300">{formatPercent(paperRoi)}</p>
                        <p className="text-xs text-slate-500">{formatPercent(winRate)} win rate</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => jumpTo("best-picks")}
                      className="mt-5 inline-flex h-11 w-full items-center justify-center gap-2 border border-[#f4d274]/60 bg-[#d6af55]/12 px-4 text-xs font-black uppercase tracking-[0.16em] text-[#ffe59b] shadow-[0_0_20px_rgba(214,175,85,0.16)]"
                    >
                      <LineChart className="size-4" aria-hidden="true" />
                      Paper Trade Now
                    </button>
                  </div>

                  <div className="astro-feature-card p-4">
                    <div className="mb-4 flex items-center justify-between gap-3 border-b border-white/10 pb-3">
                      <h3 className="text-xs font-black uppercase tracking-[0.2em] text-[#f4d274]">Card Vault</h3>
                      <button type="button" onClick={() => jumpTo("vault")} className="text-[10px] font-black uppercase tracking-[0.14em] text-[#f4d274]">View All Cards</button>
                    </div>
                    <div className="grid gap-4 md:grid-cols-[minmax(150px,0.95fr)_1fr] 2xl:grid-cols-[minmax(170px,0.92fr)_1fr]">
                      <div className="astro-reference-frame astro-sidebar-card-frame" style={{ minHeight: 322 }}>
                        {!cardImageMissing ? (
                          <Image
                            src={CARD_REFERENCE_SRC}
                            alt="ASTRODDS gold refractor card reference"
                            width={320}
                            height={480}
                            className="h-full w-full object-contain"
                            onError={() => setCardImageMissing(true)}
                          />
                        ) : (
                          <div className="grid h-full min-h-[250px] place-items-center border border-yellow-300/25 bg-black/50 p-4 text-center text-xs text-yellow-100">
                            Reference Image Missing
                          </div>
                        )}
                      </div>
                      <div>
                        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-[#f4d274]">Featured NFT</p>
                        <h3 className="mt-2 text-xl font-black uppercase tracking-[0.08em] text-white">ASTRO CAT #34</h3>
                        <p className="mt-1 text-xs font-bold uppercase tracking-[0.16em] text-[#f4d274]">Gold Refractor</p>
                        <dl className="mt-4 grid gap-2 text-xs text-slate-300">
                          {[
                            ["Rarity", "1 of 1"],
                            ["Card Type", "Rookie Card"],
                            ["Team", "ASTRODDS"],
                            ["Serial", "#34"],
                          ].map(([label, value]) => (
                            <div key={label} className="flex justify-between gap-3 border-b border-white/10 pb-2">
                              <dt className="text-slate-500">{label}</dt>
                              <dd className="font-bold text-white">{value}</dd>
                            </div>
                          ))}
                        </dl>
                        <button
                          type="button"
                          onClick={() => jumpTo("vault")}
                          className="mt-4 inline-flex h-10 w-full items-center justify-center border border-[#f4d274]/60 bg-[#d6af55]/12 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-[#ffe59b]"
                        >
                          View NFT Details
                        </button>
                      </div>
                    </div>
                  </div>
                </aside>
              </div>

              <div className="astro-bottom-strip mt-3 grid gap-0 md:grid-cols-2 xl:grid-cols-[1fr_1fr_1fr_1fr_1.75fr_1.35fr]">
                {[
                  ["Opportunities Found", rows.length.toString(), Activity],
                  ["Avg Max Confidence", `${maxScore}%`, ShieldAlert],
                  ["Sports Covered", sportsCovered ? sportsCovered.toString() : "0", DatabaseZap],
                  ["Avg Scan Time", "< 2s", Gauge],
                ].map(([label, value, Icon]) => {
                  const StatIcon = Icon as typeof Activity;

                  return (
                    <div key={label as string} className="astro-stat-cell">
                      <StatIcon className="size-7 text-[#f4d274]" aria-hidden="true" />
                      <div>
                        <p className="text-2xl font-black text-white">{value as string}</p>
                        <p className="text-xs text-slate-400">{label as string}</p>
                      </div>
                    </div>
                  );
                })}
                <div className="astro-stat-cell">
                  <div>
                    <p className="text-sm font-black uppercase tracking-[0.18em] text-[#f4d274]">Real Data. Real Edges.</p>
                    <p className="mt-1 text-sm text-slate-300">
                      {bestPick ? `${bestPick.pick} is currently the top unified paper opportunity.` : "No fluff. Just numbers."}
                    </p>
                  </div>
                </div>
                <div className="astro-stat-cell border-[#d6af55]/45 bg-[#d6af55]/10">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-black uppercase tracking-[0.14em] text-[#f4d274]">Wallet Tracker</p>
                    <Badge className="border-yellow-200/70 bg-yellow-300/15 text-yellow-50">Soon</Badge>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-slate-300">Whale wallet intelligence, profitable wallet scans, and performance tracking.</p>
                </div>
              </div>
            </section>

            <Panel id="best-picks" title="Best Picks" kicker="Top Ranked Entries After Scan">
              {result?.bestPicks.length ? (
                <div className="grid gap-4 xl:grid-cols-2">
                  {result.bestPicks.map((pick) => (
                    <article key={`${pick.id}-${pick.market.marketId}-${pick.market.pick}`} className="astro-pick-card p-5">
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                          <div className="flex flex-wrap gap-2">
                            <Badge className="border-[#d6af55]/45 bg-[#d6af55]/10 text-[#ffe7a1]">{pick.sport}</Badge>
                            <DecisionBadge decision={pick.market.decision} />
                          </div>
                          <h3 className="mt-3 text-xl font-black uppercase tracking-[0.06em] text-white">{pick.game}</h3>
                          <p className="mt-1 text-sm text-slate-300">
                            {clearBetText(pick.market)} - {pick.market.marketTitle}
                          </p>
                        </div>
                        <div className="grid size-20 place-items-center rounded-full bg-[conic-gradient(#f8d66a_var(--score),rgba(255,255,255,0.12)_0)] text-xl font-black text-white" style={{ ["--score" as string]: `${pick.market.score?.total ?? 0}%` }}>
                          {pick.market.score?.total ?? 0}
                        </div>
                      </div>

                      <p className="mt-4 text-sm leading-6 text-slate-300">{pick.market.why}</p>
                      {pick.market.score?.missingDataWarnings.length ? (
                        <div className="mt-4 border border-yellow-300/25 bg-yellow-400/10 p-3 text-xs font-bold text-yellow-100">
                          Missing data: {pick.market.score.missingDataWarnings.join(" ")}
                        </div>
                      ) : null}
                      <p className="mt-3 text-xs font-bold text-slate-300">{orderBookSummary(pick.market)}</p>
                      {canPaperTradePick(pick.market) ? (
                        <button
                          type="button"
                          onClick={() => addPaperTrade(pick, pick.market)}
                          disabled={exposure >= MAX_ACTIVE_EXPOSURE || paperTrades.some((trade) => trade.id === paperTradeId(pick.market))}
                          className="mt-4 inline-flex min-h-10 items-center justify-center border border-emerald-300/35 bg-emerald-400/12 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-emerald-50 disabled:opacity-45"
                        >
                          Paper Trade 5%
                        </button>
                      ) : (
                        <Badge className="mt-4 border-yellow-300/45 bg-yellow-400/10 text-yellow-100">Watch Only</Badge>
                      )}
                    </article>
                  ))}
                </div>
              ) : (
                <div className="astro-panel-soft p-6 text-center">
                  <p className="text-lg font-black uppercase tracking-[0.1em] text-white">No strong MLB edge detected. Best action: WAIT.</p>
                  <p className="mt-2 text-sm text-slate-400">Run a scan to rank current sport data and Polymarket market prices.</p>
                </div>
              )}
            </Panel>

            <Panel id="sports-data" title="Sports Data" kicker="Honest Source Status">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {sourceStatusRows(result).map(([label, status, detail]) => (
                  <article key={label} className="astro-panel-soft p-4">
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="text-sm font-black uppercase tracking-[0.14em] text-white">{label}</h3>
                      <StatusBadge status={status} />
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-400">{detail}</p>
                  </article>
                ))}
              </div>
            </Panel>

            <Panel id="paper" title="Paper Trading" kicker="$1000 Bankroll, 5% Position Size">
              <div className="mb-4 flex flex-col gap-3 border border-[#d6af55]/25 bg-black/30 p-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <h3 className="text-sm font-black uppercase tracking-[0.16em] text-white">MLB Paper Resolver</h3>
                  <p className="mt-1 text-xs leading-5 text-slate-400">
                    Settles local paper trades only after MLB games are final. Unknown mappings are never marked as losses.
                  </p>
                  <p className="mt-1 text-xs text-slate-500">Last resolved: {lastResolvedAt ? formatDate(lastResolvedAt) : "Never"}</p>
                </div>
                <button
                  type="button"
                  onClick={resolveMlbPaperTrades}
                  disabled={isResolvingPaper || !paperTrades.length}
                  className="inline-flex min-h-11 items-center justify-center gap-2 border border-[#f4d274]/70 bg-[#d6af55]/12 px-4 text-[10px] font-black uppercase tracking-[0.16em] text-[#ffe59b] disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {isResolvingPaper ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Trophy className="size-4" aria-hidden="true" />}
                  Resolve MLB Paper Trades
                </button>
              </div>
              {paperResolveSummary ? (
                <div className="mb-4 border border-white/10 bg-black/30 p-3 text-xs text-slate-300">
                  <p className="font-black uppercase tracking-[0.16em] text-[#f4d274]">Last Resolver Summary</p>
                  <p className="mt-2">
                    Results fetched: {paperResolveSummary.resultsFetched ?? 0} | Resolved: {paperResolveSummary.resolved} | Pending: {paperResolveSummary.pending} |
                    Wins: {paperResolveSummary.wins} | Losses: {paperResolveSummary.losses} | Voids: {paperResolveSummary.voids} | Unknown: {paperResolveSummary.unknown}
                  </p>
                  {paperResolveSummary.errors.length ? <p className="mt-2 font-bold text-red-300">{paperResolveSummary.errors.join(" | ")}</p> : null}
                </div>
              ) : null}
              <div className="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {metric("Official Picks", (serverPaperSummary?.totalOfficialPaperPicks ?? 0).toString(), "Server paper ledger", BellRing)}
                {metric("Ledger ROI", formatRoi(serverPaperSummary?.roi ?? 0), "Official picks only", LineChart)}
                {metric("Model Leans", (serverPaperSummary?.modelLeans.total ?? 0).toString(), "Tracked separately", DatabaseZap)}
                {metric("Lean Accuracy", formatPercent((serverPaperSummary?.modelLeans.accuracy ?? 0) * 100), "Settled model leans", Trophy)}
              </div>
              <div className="mb-4 border border-cyan-300/20 bg-cyan-400/10 p-3 text-xs font-bold leading-5 text-cyan-100">
                Official paper picks require a real odds source or matched Polymarket price. Model leans are saved for validation only and never count as executable bets.
              </div>              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-10">
                {metric("Bankroll", `$${bankroll.toFixed(0)}`, "Virtual only", CircleDollarSign)}
                {metric("Stake", `$${DEFAULT_PAPER_STAKE}`, "5% per trade", BadgeDollarSign)}
                {metric("Exposure", `$${exposure.toFixed(0)}`, `Max $${MAX_ACTIVE_EXPOSURE}`, ShieldAlert)}
                {metric("Pending", openPaperTrades.length.toString(), "Open paper entries", Activity)}
                {metric("Resolved", resolvedPaperTrades.length.toString(), "Settled/unknown", CheckCircle2)}
                {metric("Trades", paperTrades.length.toString(), "Target 1000", Activity)}
                {metric("Record", `${wins}-${losses}-${voids}-${unknowns}`, "W-L-V-U", Trophy)}
                {metric("Win Rate", formatPercent(winRate), "Wins / decisions", Trophy)}
                {metric("PnL", currency(paperPnl), "Paper only", BadgeDollarSign)}
                {metric("ROI", formatPercent(paperRoi), "Settled stake", LineChart)}
              </div>
              <div className="mt-4 astro-table-wrap overflow-x-auto">
                <table className="min-w-[1500px] w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-[#d6af55]/25 text-[10px] uppercase tracking-[0.16em] text-slate-400">
                      <th className="p-3">Sport</th>
                      <th className="p-3">Game</th>
                      <th className="p-3">Market</th>
                      <th className="p-3">Pick</th>
                      <th className="p-3">Decision</th>
                      <th className="p-3">Confidence</th>
                      <th className="p-3">Score</th>
                      <th className="p-3">Entry</th>
                      <th className="p-3">Stake</th>
                      <th className="p-3">Status</th>
                      <th className="p-3">PnL</th>
                      <th className="p-3">ROI</th>
                      <th className="p-3">Data</th>
                      <th className="p-3">Why</th>
                      <th className="p-3">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedPaperTrades.length ? (
                      displayedPaperTrades.map((trade) => (
                        <tr key={trade.id} className="border-b border-white/[0.08]">
                          <td className="p-3 text-[#f1d27a]">{trade.sport}</td>
                          <td className="p-3 text-white">{trade.game}</td>
                          <td className="p-3 text-slate-300">
                            <p>{trade.marketType}</p>
                            <p className="mt-1 text-xs text-slate-500">{trade.market}</p>
                          </td>
                          <td className="p-3 font-bold text-white">{trade.pick}</td>
                          <td className="p-3 text-slate-300">{trade.decision}</td>
                          <td className="p-3 text-slate-300">{trade.confidence}</td>
                          <td className="p-3 font-black text-white">{trade.score}</td>
                          <td className="p-3 text-cyan-100">{formatPrice(trade.entryPrice)}</td>
                          <td className="p-3 text-white">${trade.stake}</td>
                          <td className="p-3"><PaperStatusBadge status={trade.status} /></td>
                          <td className={trade.pnl < 0 ? "p-3 text-red-100" : "p-3 text-emerald-100"}>{currency(trade.pnl)}</td>
                          <td className="p-3 text-slate-300">{formatRoi(trade.roi)}</td>
                          <td className="p-3"><StatusBadge status={trade.dataConfidence} /></td>
                          <td className="max-w-[360px] p-3 text-slate-300">
                            <p>{trade.result ?? trade.why}</p>
                            <p className="mt-1 text-xs text-slate-500">{trade.why}</p>
                          </td>
                          <td className="p-3 text-slate-300">
                            <p>{formatDate(trade.createdAt)}</p>
                            {trade.resolvedAt ? <p className="mt-1 text-xs text-emerald-200">Resolved {formatDate(trade.resolvedAt)}</p> : null}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={15} className="p-6 text-center text-sm font-bold text-slate-400">
                          No paper trades yet. Add one from Scan Results or Best Picks.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </Panel>

            <Panel id="cashout" title="Live Cashout" kicker="Profit Lock Engine Prepared">
              <div className="astro-panel-soft p-5">
                <p className="text-sm leading-6 text-slate-300">
                  Live exit logic is wired into the decision engine: when a market has an entry price and current price moves far enough in favor,
                  ASTRODDS can return HEDGE, PROFIT LOCK, or CASH OUT. Real-time CLOB orderbook polling and open-position persistence are the next connection points.
                </p>
              </div>
            </Panel>

            <Panel id="record" title="Official Record" kicker="Separate From Wallet Performance">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                {metric("Official Picks", (serverPaperSummary?.totalOfficialPaperPicks ?? 0).toString(), "Real-price paper picks", BellRing)}
                {metric("Open Official", (serverPaperSummary?.openPicks ?? 0).toString(), "Awaiting settlement", CircleDollarSign)}
                {metric("Official Record", `${serverPaperSummary?.wins ?? 0}-${serverPaperSummary?.losses ?? 0}-${serverPaperSummary?.pushes ?? 0}`, "W-L-P", Activity)}
                {metric("Official PnL", currency(serverPaperSummary?.pnlUnits ?? 0), "Server paper ledger", BadgeDollarSign)}
                {metric("Model Leans", (serverPaperSummary?.modelLeans.total ?? 0).toString(), "Non-executable tracking", LineChart)}
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <div className="astro-panel-soft p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">Daily Report</p>
                  <p className="mt-2 text-lg font-black text-white">{dailyReport?.date ?? "Not loaded"}</p>
                  <p className="mt-1 text-xs text-slate-400">Daily ROI {formatRoi(dailyReport?.roi ?? 0)} | Signals {dailyReport?.signalsSent ?? 0}</p>
                </div>
                <div className="astro-panel-soft p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">30 / 90 Day Prep</p>
                  <p className="mt-2 text-lg font-black text-white">Performance API Connected</p>
                  <p className="mt-1 text-xs text-slate-400">/api/astrodds/performance returns ROI by sport, whale grade, and signal type.</p>
                </div>
                <div className="astro-panel-soft p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">Risk Rule</p>
                  <p className="mt-2 text-lg font-black text-white">Paper Only</p>
                  <p className="mt-1 text-xs text-slate-400">No real-money execution. Official picks need real odds and strict BUY thresholds.</p>
                </div>
              </div>
            </Panel>

            <Panel id="wallets" title="Wallet Intelligence" kicker="Additional Public Whale Alert Layer">
              <div className="grid gap-4">
                <div className="flex flex-col gap-3 border border-cyan-300/20 bg-cyan-400/10 p-4 md:flex-row md:items-center md:justify-between">
                  <p className="text-sm font-bold leading-6 text-cyan-100">{whaleSourcePolicy}</p>
                  <button
                    type="button"
                    onClick={scanPublicWhales}
                    disabled={isScanningWhales}
                    className="inline-flex min-h-11 shrink-0 items-center justify-center border border-[#d6af55]/55 bg-[#d6af55]/12 px-4 text-xs font-black uppercase tracking-[0.16em] text-[#ffe7a1] disabled:opacity-45"
                  >
                    {isScanningWhales ? <Loader2 className="mr-2 size-4 animate-spin" aria-hidden="true" /> : <WalletCards className="mr-2 size-4" aria-hidden="true" />}
                    Scan Public Whale Data
                  </button>
                </div>

                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                  {metric("Whale Watch", whaleWatchlist.length.toString(), "Priority handles", WalletCards)}
                  {metric("All Whale Trades", whalePositions.length.toString(), "All public categories", Activity)}
                  {metric("Copyable Now", whaleCopyability.filter((item) => item.status === "COPYABLE_NOW" || item.status === "NEAR_WHALE_ENTRY").length.toString(), "Near whale entry", CheckCircle2)}
                  {metric("Watch Only", whaleCopyability.filter((item) => item.status === "WATCH_ONLY" || item.status === "UNKNOWN").length.toString(), "Needs better entry/data", DatabaseZap)}
                  {metric("Stale Entries", whaleCopyability.filter((item) => item.status === "STALE_ENTRY" || item.status === "TOO_LATE" || item.status === "NO_LIQUIDITY").length.toString(), "Skipped by alerts", Diamond)}
                </div>

                {lastWhaleScanAt ? (
                  <p className="border border-white/10 bg-black/30 p-3 text-xs font-bold text-slate-300">
                    Last public whale scan: {formatDate(lastWhaleScanAt)}
                  </p>
                ) : null}

                {whaleErrors.length ? (
                  <div className="border border-red-300/30 bg-red-500/10 p-3 text-xs font-bold leading-5 text-red-100">
                    {whaleErrors.slice(0, 4).join(" | ")}
                  </div>
                ) : null}

                <div className="astro-table-wrap overflow-x-auto">
                  <div className="border-b border-[#d6af55]/25 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.22em] text-[#f4d274]">Priority Whale Watch</p>
                    <h3 className="mt-1 text-lg font-black uppercase tracking-[0.08em] text-white">Public Profile Candidates</h3>
                  </div>
                  <table className="min-w-[1500px] w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-[#d6af55]/25 text-[10px] uppercase tracking-[0.16em] text-slate-400">
                        <th className="p-3">Handle</th>
                        <th className="p-3">Address</th>
                        <th className="p-3">Rank</th>
                        <th className="p-3">Source</th>
                        <th className="p-3">PnL</th>
                        <th className="p-3">Volume</th>
                        <th className="p-3">Predictions</th>
                        <th className="p-3">Open</th>
                        <th className="p-3">Closed</th>
                        <th className="p-3">Win Rate</th>
                        <th className="p-3">ROI</th>
                        <th className="p-3">Avg Bet</th>
                        <th className="p-3">Sport Focus</th>
                        <th className="p-3">Entry Discipline</th>
                        <th className="p-3">Hold Score</th>
                        <th className="p-3">Copyability</th>
                        <th className="p-3">Next Rescan</th>
                      </tr>
                    </thead>
                    <tbody>
                      {whaleWatchlist.length ? (
                        whaleWatchlist.map((wallet) => {
                          const profile = whaleProfiles.find((item) => item.handle.toLowerCase() === wallet.handle.toLowerCase());
                          const metrics = wallet.metrics ?? whaleMetrics.find((item) => item.handle.toLowerCase() === wallet.handle.toLowerCase());

                          return (
                            <tr key={wallet.handle} className="border-b border-white/[0.08] align-top">
                              <td className="p-3">
                                <a href={wallet.profileUrl} target="_blank" rel="noreferrer" className="font-black text-[#f4d274] underline-offset-4 hover:underline">
                                  @{wallet.handle}
                                </a>
                                <p className="mt-1 max-w-[240px] text-xs leading-5 text-slate-500">{wallet.notes}</p>
                              </td>
                              <td className="max-w-[180px] truncate p-3 font-mono text-xs text-slate-300" title={wallet.address ?? profile?.address}>{wallet.address ?? profile?.address ?? "--"}</td>
                              <td className="p-3"><Badge className="border-[#d6af55]/45 bg-[#d6af55]/10 text-[#ffe7a1]">{wallet.rank.replace(/_/g, " ")}</Badge></td>
                              <td className="p-3"><WhaleSourceBadge status={profile?.sourceStatus ?? wallet.sourceStatus} /></td>
                              <td className="p-3 text-white">{compactCurrency(profile?.totalPnl)}</td>
                              <td className="p-3 text-white">{compactCurrency(profile?.totalVolume)}</td>
                              <td className="p-3 text-slate-300">{numberText(profile?.predictions)}</td>
                              <td className="p-3 text-slate-300">{metrics?.openPositions ?? profile?.openPositions.length ?? "--"}</td>
                              <td className="p-3 text-slate-300">{metrics?.closedPositions ?? profile?.closedPositions.length ?? "--"}</td>
                              <td className="p-3 text-slate-300">{metrics ? formatPercent(metrics.winRate * 100) : "--"}</td>
                              <td className="p-3 text-slate-300">{metrics ? formatPercent(metrics.roi * 100) : "--"}</td>
                              <td className="p-3 text-slate-300">{compactCurrency(metrics?.averageBetSize)}</td>
                              <td className="p-3 text-slate-300">{metrics ? `${metrics.sportFocus ?? "OTHER"} ${metrics.sportFocusPercent}%` : "--"}</td>
                              <td className="p-3 text-slate-300">{metrics?.limitEntryDiscipline?.replace(/_/g, " ") ?? "--"}</td>
                              <td className="p-3 text-slate-300">{metrics?.holdToResolution?.replace(/_/g, " ") ?? "--"}</td>
                              <td className="p-3 text-slate-300">{metrics?.copyabilityScore?.replace(/_/g, " ") ?? "--"}</td>
                              <td className="p-3 text-slate-300">{formatDate(metrics?.nextRescan ?? wallet.nextRescan)}</td>
                            </tr>
                          );
                        })
                      ) : (
                        <tr>
                          <td colSpan={17} className="p-6 text-center text-sm font-bold text-slate-400">
                            Whale watchlist is loading.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="astro-table-wrap overflow-x-auto">
                  <div className="border-b border-[#d6af55]/25 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.22em] text-[#f4d274]">All Whale Trades</p>
                    <h3 className="mt-1 text-lg font-black uppercase tracking-[0.08em] text-white">Copyability Check</h3>
                  </div>
                  <table className="min-w-[1420px] w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-[#d6af55]/25 text-[10px] uppercase tracking-[0.16em] text-slate-400">
                        <th className="p-3">Whale</th>
                        <th className="p-3">Category</th>
                        <th className="p-3">Market</th>
                        <th className="p-3">Side</th>
                        <th className="p-3">Sport</th>
                        <th className="p-3">Type</th>
                        <th className="p-3">Whale Entry</th>
                        <th className="p-3">Current</th>
                        <th className="p-3">Delta</th>
                        <th className="p-3">Copyability</th>
                        <th className="p-3">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {whalePositions.length ? (
                        whalePositions.slice(0, 20).map((position) => {
                          const copy = whaleCopyability.find((item) => item.positionId === position.id);
                          const copyable = copy?.status === "COPYABLE_NOW" || copy?.status === "NEAR_WHALE_ENTRY";

                          return (
                            <tr key={position.id} className="border-b border-white/[0.08] align-top">
                              <td className="p-3 font-black text-[#f4d274]">@{position.handle}</td>
                              <td className="p-3 text-slate-300">{(position.category ?? "UNKNOWN").replace(/_/g, " ")}</td>
                              <td className="max-w-[320px] p-3 text-white">
                                <p>{position.marketTitle}</p>
                                <p className="mt-1 text-xs text-slate-500">{copy?.reason ?? "Copyability pending public price data."}</p>
                              </td>
                              <td className="p-3 font-bold text-white">{position.side}</td>
                              <td className="p-3 text-slate-300">{position.sport ?? "OTHER"}</td>
                              <td className="p-3 text-slate-300">{position.marketType}</td>
                              <td className="p-3 text-cyan-100">{formatPrice(position.avgEntryPrice)}</td>
                              <td className="p-3 text-cyan-100">{formatPrice(position.currentPrice)}</td>
                              <td className={copy && (copy.priceDeltaFromWhaleEntry ?? 0) <= 0.02 ? "p-3 text-emerald-100" : "p-3 text-yellow-100"}>
                                {formatEdge(copy?.priceDeltaFromWhaleEntry)}
                              </td>
                              <td className="p-3"><Badge className={copyable ? "border-emerald-300/55 bg-emerald-400/12 text-emerald-100" : "border-yellow-300/55 bg-yellow-400/12 text-yellow-100"}>{copy?.status.replace(/_/g, " ") ?? "UNKNOWN"}</Badge></td>
                              <td className="p-3"><Badge className={copyable ? "border-cyan-300/45 bg-cyan-400/10 text-cyan-100" : "border-slate-300/35 bg-slate-400/10 text-slate-200"}>{copyable ? "WATCH / PAPER ONLY" : "IGNORE / WAIT"}</Badge></td>
                            </tr>
                          );
                        })
                      ) : (
                        <tr>
                          <td colSpan={11} className="p-6 text-center text-sm font-bold text-slate-400">
                            No public open whale positions loaded yet. Run a public whale scan to populate all categories.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="astro-table-wrap overflow-x-auto">
                  <div className="border-b border-[#d6af55]/25 p-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.22em] text-[#f4d274]">Whale Consensus</p>
                    <h3 className="mt-1 text-lg font-black uppercase tracking-[0.08em] text-white">Same-Side Public Wallet Signals</h3>
                  </div>
                  <table className="min-w-[1180px] w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-[#d6af55]/25 text-[10px] uppercase tracking-[0.16em] text-slate-400">
                        <th className="p-3">Market</th>
                        <th className="p-3">Side</th>
                        <th className="p-3">Same Side</th>
                        <th className="p-3">Opposite</th>
                        <th className="p-3">Avg Entry</th>
                        <th className="p-3">Current</th>
                        <th className="p-3">Copyability</th>
                        <th className="p-3">Signal</th>
                      </tr>
                    </thead>
                    <tbody>
                      {whaleConsensus.length ? (
                        whaleConsensus.slice(0, 20).map((signal) => (
                          <tr key={signal.id} className="border-b border-white/[0.08] align-top">
                            <td className="max-w-[340px] p-3 text-white">{signal.marketTitle}</td>
                            <td className="p-3 font-bold text-white">{signal.side}</td>
                            <td className="p-3 text-emerald-100">{signal.walletsOnSameSide.join(", ") || "--"}</td>
                            <td className="p-3 text-red-100">{signal.walletsOnOppositeSide.join(", ") || "--"}</td>
                            <td className="p-3 text-cyan-100">{formatPrice(signal.averageWhaleEntry)}</td>
                            <td className="p-3 text-cyan-100">{formatPrice(signal.currentPrice)}</td>
                            <td className="p-3 text-slate-300">{signal.copyabilityStatus.replace(/_/g, " ")}</td>
                            <td className="p-3"><Badge className="border-[#d6af55]/45 bg-[#d6af55]/10 text-[#ffe7a1]">{signal.consensusStrength.replace(/_/g, " ")}</Badge></td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={8} className="p-6 text-center text-sm font-bold text-slate-400">
                            No same-side whale consensus loaded yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
              <p className="mt-3 border border-yellow-300/25 bg-yellow-400/10 p-3 text-xs font-bold text-yellow-100">
                Pending trades do not count as wins. Voids are displayed but never help win rate. Whale support is a bonus signal only and cannot override model edge, sports data, or order book quality.
              </p>
            </Panel>

            <Panel id="telegram" title="Telegram" kicker="Alerts Prepared">
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="astro-panel-soft p-4">
                  <h3 className="text-sm font-black uppercase tracking-[0.16em] text-white">Commands</h3>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {["/astatus", "/scanreport", "/bestpicks", "/paper", "/cashout", "/official", "/walletwatch"].map((command) => (
                      <Badge key={command} className="border-cyan-300/35 bg-cyan-300/10 font-mono text-cyan-100">{command}</Badge>
                    ))}
                  </div>
                </div>
                <div className="astro-panel-soft p-4">
                  <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <h3 className="text-sm font-black uppercase tracking-[0.16em] text-white">Status</h3>
                    <TelegramStatusBadge status={telegramStatus?.status} />
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-300">
                    Telegram reads only environment variables from <span className="font-mono text-white">frontend/.env.local</span>. Full tokens are never shown.
                    Whale alerts are paper-only and disabled unless both signal flags are enabled.
                  </p>
                  <div className="mt-3 grid gap-2 text-xs">
                    <div className="flex items-center justify-between border-b border-white/10 pb-2">
                      <span className="text-slate-400">Bot Token</span>
                      <span className="font-mono font-bold text-white">{telegramStatus?.botTokenMasked ?? "Not configured"}</span>
                    </div>
                    <div className="flex items-center justify-between border-b border-white/10 pb-2">
                      <span className="text-slate-400">Signals Enabled</span>
                      <TelegramStatusBadge status={telegramStatus?.signalsEnabled ? "CONFIGURED" : "DISABLED"} />
                    </div>
                    <div className="flex items-center justify-between border-b border-white/10 pb-2">
                      <span className="text-slate-400">Whale Alerts</span>
                      <TelegramStatusBadge status={telegramStatus?.whaleAlertsEnabled ? "CONFIGURED" : "DISABLED"} />
                    </div>
                    <div className="flex items-center justify-between border-b border-white/10 pb-2">
                      <span className="text-slate-400">Alert Mode</span>
                      <span className="font-bold uppercase text-white">{telegramStatus?.mode ?? "conservative"}</span>
                    </div>
                    <div className="flex items-center justify-between border-b border-white/10 pb-2">
                      <span className="text-slate-400">Signals Chat</span>
                      <TelegramStatusBadge status={telegramStatus?.signalsChatConfigured ? "CONFIGURED" : "MISSING_CHAT_ID"} />
                    </div>
                    <div className="flex items-center justify-between border-b border-white/10 pb-2">
                      <span className="text-slate-400">Dev Chat</span>
                      <TelegramStatusBadge status={telegramStatus?.devChatConfigured ? "CONFIGURED" : "MISSING_CHAT_ID"} />
                    </div>
                    <div className="flex items-center justify-between border-b border-white/10 pb-2">
                      <span className="text-slate-400">Real money trading</span>
                      <span className="font-bold text-red-100">OFF</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-3">
                <div className="astro-panel-soft p-4">
                  <h3 className="text-sm font-black uppercase tracking-[0.16em] text-white">Test Telegram</h3>
                  <p className="mt-2 text-xs leading-5 text-slate-400">Sends a manual test to DEV chat if configured, otherwise the default chat. This does not require whale alerts to be enabled.</p>
                  <button
                    type="button"
                    onClick={testTelegram}
                    disabled={isTestingTelegram}
                    className="mt-4 inline-flex min-h-10 w-full items-center justify-center border border-cyan-300/35 bg-cyan-400/10 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-cyan-100 disabled:opacity-45"
                  >
                    {isTestingTelegram ? <Loader2 className="mr-2 size-4 animate-spin" aria-hidden="true" /> : <Bot className="mr-2 size-4" aria-hidden="true" />}
                    Test Telegram
                  </button>
                  {telegramTestResult ? (
                    <div className="mt-3 grid gap-2 text-xs">
                      <TelegramStatusBadge status={telegramTestResult.status} />
                      <p className="leading-5 text-slate-300">{telegramTestResult.reason}</p>
                      {lastTelegramTestAt ? <p className="text-slate-500">Last test: {formatDate(lastTelegramTestAt)}</p> : null}
                    </div>
                  ) : null}
                </div>

                <div className="astro-panel-soft p-4">
                  <h3 className="text-sm font-black uppercase tracking-[0.16em] text-white">Test Whale Alert</h3>
                  <p className="mt-2 text-xs leading-5 text-slate-400">Sends a sample whale alert only when Telegram is configured and whale alerts are enabled.</p>
                  <button
                    type="button"
                    onClick={testWhaleAlert}
                    disabled={isTestingWhaleAlert}
                    className="mt-4 inline-flex min-h-10 w-full items-center justify-center border border-[#d6af55]/45 bg-[#d6af55]/10 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-[#ffe7a1] disabled:opacity-45"
                  >
                    {isTestingWhaleAlert ? <Loader2 className="mr-2 size-4 animate-spin" aria-hidden="true" /> : <BellRing className="mr-2 size-4" aria-hidden="true" />}
                    Test Whale Alert
                  </button>
                  {whaleAlertTestResult ? (
                    <div className="mt-3 grid gap-2 text-xs">
                      <TelegramStatusBadge status={whaleAlertTestResult.status} />
                      <p className="leading-5 text-slate-300">{whaleAlertTestResult.reason}</p>
                      {lastWhaleAlertTestAt ? <p className="text-slate-500">Last whale alert test: {formatDate(lastWhaleAlertTestAt)}</p> : null}
                    </div>
                  ) : null}
                </div>

                <div className="astro-panel-soft p-4">
                  <h3 className="text-sm font-black uppercase tracking-[0.16em] text-white">Run Whale Scan Once</h3>
                  <p className="mt-2 text-xs leading-5 text-slate-400">Runs the public wallet scan once and updates Wallet Intelligence. No Telegram signal is sent from this button.</p>
                  <button
                    type="button"
                    onClick={scanPublicWhales}
                    disabled={isScanningWhales}
                    className="mt-4 inline-flex min-h-10 w-full items-center justify-center border border-emerald-300/35 bg-emerald-400/10 px-3 text-[10px] font-black uppercase tracking-[0.14em] text-emerald-100 disabled:opacity-45"
                  >
                    {isScanningWhales ? <Loader2 className="mr-2 size-4 animate-spin" aria-hidden="true" /> : <WalletCards className="mr-2 size-4" aria-hidden="true" />}
                    Run Whale Scan Once
                  </button>
                  <div className="mt-3 grid gap-2 text-xs">
                    <p className="text-slate-300">Duplicates skipped: handled by <span className="font-mono">.astrodds/telegram-whale-signals.json</span></p>
                    <p className="text-slate-300">Stale entries skipped: STALE_ENTRY / TOO_LATE never send whale alerts.</p>
                    {lastWhaleScanAt ? <p className="text-slate-500">Last whale scan: {formatDate(lastWhaleScanAt)}</p> : null}
                  </div>
                </div>
              </div>
              <p className="mt-4 border border-cyan-300/20 bg-cyan-400/10 p-3 text-xs font-bold text-cyan-100">
                ASTRODDS uses public Polymarket wallet/profile data only. Whale alerts are Smart Money Watch signals, not guarantees.
              </p>
            </Panel>

            <Panel id="vault" title="Card Vault" kicker="Concept Only - No Smart Contracts">
              <div className="grid gap-5 xl:grid-cols-[minmax(280px,460px)_1fr]">
                <article className="astro-feature-card p-4">
                  <div className="astro-reference-frame">
                    {!cardImageMissing ? (
                      <Image
                        src={CARD_REFERENCE_SRC}
                        alt="ASTRODDS gold refractor card reference"
                        width={460}
                        height={690}
                        className="h-full w-full object-contain"
                        onError={() => setCardImageMissing(true)}
                      />
                    ) : (
                      <div className="grid h-full min-h-[520px] place-items-center border border-yellow-300/25 bg-black/50 p-6 text-center">
                        <div>
                          <p className="text-sm font-black uppercase tracking-[0.2em] text-yellow-100">Reference Image Missing</p>
                          <p className="mt-3 text-sm leading-6 text-slate-300">
                            Add the uploaded gold refractor card to <span className="font-mono text-white">/public/astrodds/card-reference.png</span>.
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="mt-4 border border-[#d6af55]/35 bg-black/35 p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge className="border-yellow-200/70 bg-yellow-300/15 text-yellow-50">Gold Card</Badge>
                      <Badge className="border-red-300/50 bg-red-400/12 text-red-100">1 of 1 Energy</Badge>
                    </div>
                    <h3 className="mt-3 text-2xl font-black uppercase tracking-[0.06em] text-white">Featured Gold Refractor</h3>
                    <p className="mt-2 text-sm leading-6 text-slate-300">
                      Main visual direction for ASTRODDS access cards: black and gold frame, glossy chrome finish, premium patch/relic feel,
                      and Superfractor collector energy. Concept only. No smart contracts yet.
                    </p>
                  </div>
                </article>

                <div className="grid gap-4 md:grid-cols-2">
                  {[
                    ["Normal Card", "Base", "Basic dashboard access, daily summary, paper leaderboard"],
                    ["Silver Refractor", "Silver", "Stronger signals, wallet intelligence dashboard, sport-specific reports"],
                    ["Gold Card", "Gold", "Best signals, advanced ASTRODDS data, live trading alerts, cashout alerts"],
                    ["Superfractor Gold / 1 of 1", "1 of 1", "Elite AI terminal, private beta auto-trading, custom bankroll settings, founder analytics"],
                  ].map(([name, rarity, utility], index) => (
                    <article key={name} className={`astro-tier-card astro-tier-${index} p-4`}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-[#d6af55]">{rarity}</p>
                          <h3 className="mt-2 text-xl font-black uppercase tracking-[0.06em] text-white">{name}</h3>
                        </div>
                        <Badge className={index >= 2 ? "border-yellow-200/70 bg-yellow-300/15 text-yellow-50" : "border-slate-300/35 bg-slate-400/10 text-slate-200"}>
                          Coming Soon
                        </Badge>
                      </div>
                      <div className="astro-tier-strip mt-5" />
                      <p className="mt-5 text-sm leading-6 text-slate-300">{utility}</p>
                    </article>
                  ))}
                </div>
              </div>
            </Panel>
          </div>
        </div>
      </div>
    </main>
  );
}
