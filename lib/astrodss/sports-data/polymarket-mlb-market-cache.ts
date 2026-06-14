import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import type { PolymarketMlbMoneylineMarket, PolymarketMlbSourceDiagnostic } from "./polymarket-mlb-markets";

export type PolymarketMlbCacheStatus = "fresh" | "stale" | "missing" | "not_used";

export type PolymarketMlbMarketsCacheSnapshot = {
  generatedAt: string;
  marketPricesConnected: boolean;
  markets: PolymarketMlbMoneylineMarket[];
  warnings: string[];
  sourceDiagnostics: PolymarketMlbSourceDiagnostic[];
  totalGammaMarketsScanned?: number;
  acceptedMlbMarkets?: number;
  rejectedBySportCategory?: number;
  rejectedByTeamAlias?: number;
  rejectedByDate?: number;
  rejectedBySingleGameFilter?: number;
};

export type PolymarketMlbMarketsCacheMetadata = {
  cacheUsed: boolean;
  cacheStatus: PolymarketMlbCacheStatus;
  cacheAgeSeconds?: number;
  cacheGeneratedAt?: string;
};

export const DEFAULT_POLYMARKET_MLB_CACHE_FRESHNESS_SECONDS = 30 * 60;
export const POLYMARKET_MLB_MARKETS_CACHE_PATH = path.join(/* turbopackIgnore: true */ process.cwd(), ".astrodds", "polymarket-mlb-markets-cache.json");

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isMarket(value: unknown): value is PolymarketMlbMoneylineMarket {
  if (!isRecord(value)) return false;
  return typeof value.marketId === "string" && typeof value.question === "string" && Array.isArray(value.outcomeProbabilities);
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function numberOrUndefined(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function diagnosticArray(value: unknown): PolymarketMlbSourceDiagnostic[] {
  return Array.isArray(value) ? value.filter((item): item is PolymarketMlbSourceDiagnostic => isRecord(item) && typeof item.endpointLabel === "string") : [];
}

function normalizeSnapshot(raw: unknown): PolymarketMlbMarketsCacheSnapshot | undefined {
  if (!isRecord(raw)) return undefined;
  const generatedAt = typeof raw.generatedAt === "string" ? raw.generatedAt : undefined;
  const markets = Array.isArray(raw.markets) ? raw.markets.filter(isMarket) : [];
  if (!generatedAt || !markets.length) return undefined;

  return {
    generatedAt,
    marketPricesConnected: raw.marketPricesConnected === true,
    markets,
    warnings: stringArray(raw.warnings),
    sourceDiagnostics: diagnosticArray(raw.sourceDiagnostics),
    totalGammaMarketsScanned: numberOrUndefined(raw.totalGammaMarketsScanned),
    acceptedMlbMarkets: numberOrUndefined(raw.acceptedMlbMarkets),
    rejectedBySportCategory: numberOrUndefined(raw.rejectedBySportCategory),
    rejectedByTeamAlias: numberOrUndefined(raw.rejectedByTeamAlias),
    rejectedByDate: numberOrUndefined(raw.rejectedByDate),
    rejectedBySingleGameFilter: numberOrUndefined(raw.rejectedBySingleGameFilter),
  };
}

function cacheAgeSeconds(generatedAt: string) {
  const parsed = new Date(generatedAt).getTime();
  if (!Number.isFinite(parsed)) return undefined;
  return Math.max(0, Math.round((Date.now() - parsed) / 1000));
}

export async function writePolymarketMlbMarketsCache(snapshot: PolymarketMlbMarketsCacheSnapshot, cachePath = POLYMARKET_MLB_MARKETS_CACHE_PATH) {
  if (!snapshot.marketPricesConnected || !snapshot.markets.length) return;
  await mkdir(path.dirname(cachePath), { recursive: true });
  await writeFile(cachePath, JSON.stringify(snapshot, null, 2), "utf8");
}

export async function loadPolymarketMlbMarketsCache(options: { freshnessSeconds?: number; cachePath?: string } = {}): Promise<{
  metadata: PolymarketMlbMarketsCacheMetadata;
  snapshot?: PolymarketMlbMarketsCacheSnapshot;
}> {
  const freshnessSeconds = options.freshnessSeconds ?? DEFAULT_POLYMARKET_MLB_CACHE_FRESHNESS_SECONDS;
  const cachePath = options.cachePath ?? POLYMARKET_MLB_MARKETS_CACHE_PATH;

  try {
    const raw = await readFile(cachePath, "utf8");
    const snapshot = normalizeSnapshot(JSON.parse(raw));
    if (!snapshot) return { metadata: { cacheUsed: false, cacheStatus: "missing" } };

    const age = cacheAgeSeconds(snapshot.generatedAt);
    const stale = typeof age !== "number" || age > freshnessSeconds;
    return {
      metadata: {
        cacheUsed: !stale,
        cacheStatus: stale ? "stale" : "fresh",
        cacheAgeSeconds: age,
        cacheGeneratedAt: snapshot.generatedAt,
      },
      snapshot: stale ? undefined : snapshot,
    };
  } catch {
    return { metadata: { cacheUsed: false, cacheStatus: "missing" } };
  }
}
