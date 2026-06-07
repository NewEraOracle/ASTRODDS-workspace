import { compactId, normalizeText, safeNumber } from "../sports-data/normalize";
import { safeFetch, safeFetchJson, type SafeFetchResult } from "../shared/safe-fetch";
import { classifyPolymarketMarket } from "./market-classifier";
import type {
  WalletActivity,
  WalletFetchDiagnostic,
  WalletMarketType,
  WalletPosition,
  WalletPositionStatus,
  WalletProfile,
  WalletSourceStatus,
} from "./types";

const POLYMARKET_PROFILE_BASE_URL = "https://polymarket.com";
const POLYMARKET_PUBLIC_SEARCH_URL = "https://gamma-api.polymarket.com/public-search";
const POLYMARKET_DATA_ACTIVITY_URL = "https://data-api.polymarket.com/activity";
const POLYMARKET_DATA_POSITIONS_URL = "https://data-api.polymarket.com/positions";
const POLYMARKET_DATA_CLOSED_POSITIONS_URL = "https://data-api.polymarket.com/closed-positions";

type PublicHandleResolution = {
  handle: string;
  address?: string;
  profileUrl: string;
  sourceStatus: WalletSourceStatus;
  error?: string;
  diagnostic: WalletFetchDiagnostic;
};

type FetchOutcome<T> = {
  data: T;
  diagnostic: WalletFetchDiagnostic;
  error?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function publicProfileUrl(handleOrAddress: string) {
  return handleOrAddress.startsWith("0x") ? `${POLYMARKET_PROFILE_BASE_URL}/profile/${handleOrAddress}` : `${POLYMARKET_PROFILE_BASE_URL}/@${handleOrAddress}`;
}

function getString(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return undefined;
}

function getNumber(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = safeNumber(record[key]);
    if (typeof value === "number") return value;
  }
  return undefined;
}

function asArray(value: unknown): Record<string, unknown>[] {
  if (Array.isArray(value)) return value.filter(isRecord);
  if (!isRecord(value)) return [];

  const candidates = [value.data, value.results, value.items, value.activity, value.positions, value.users, value.profiles];
  for (const candidate of candidates) {
    if (Array.isArray(candidate)) return candidate.filter(isRecord);
  }

  return [];
}

function diagnosticFromFetch(
  label: WalletFetchDiagnostic["label"],
  result: SafeFetchResult,
  resolved: boolean,
  count?: number,
  extraError?: string,
): WalletFetchDiagnostic {
  const status: WalletSourceStatus = resolved ? "CONNECTED" : result.ok ? "PARTIAL" : "FAILED";

  return {
    label,
    resolved,
    sourceUrl: result.url,
    httpStatus: result.httpStatus,
    status,
    count,
    error: extraError ?? result.error ?? result.cause,
    responseTextSnippet: result.responseTextSnippet,
    tlsFallback: result.tlsFallback,
  };
}

function failedDiagnostic(label: WalletFetchDiagnostic["label"], sourceUrl: string, error: string): WalletFetchDiagnostic {
  return {
    label,
    resolved: false,
    sourceUrl,
    status: "FAILED",
    error,
  };
}

function extractNextData(html?: string) {
  if (!html) return undefined;
  const start = html.indexOf('<script id="__NEXT_DATA__"');
  if (start < 0) return undefined;
  const jsonStart = html.indexOf(">", start) + 1;
  const jsonEnd = html.indexOf("</script>", jsonStart);
  if (jsonStart <= 0 || jsonEnd <= jsonStart) return undefined;

  try {
    return JSON.parse(html.slice(jsonStart, jsonEnd)) as unknown;
  } catch {
    return undefined;
  }
}

function deepAddressSearch(value: unknown): string | undefined {
  if (!value) return undefined;
  if (typeof value === "string" && looksLikeAddress(value)) return value;
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = deepAddressSearch(item);
      if (found) return found;
    }
    return undefined;
  }
  if (isRecord(value)) {
    const preferredKeys = ["proxyAddress", "proxyWallet", "primaryAddress", "baseAddress", "address", "walletAddress", "wallet"];
    for (const key of preferredKeys) {
      const candidate = value[key];
      if (typeof candidate === "string" && looksLikeAddress(candidate)) return candidate;
    }
    for (const child of Object.values(value)) {
      const found = deepAddressSearch(child);
      if (found) return found;
    }
  }
  return undefined;
}

function usernameFromNextData(value: unknown): string | undefined {
  if (!isRecord(value)) return undefined;
  const props = isRecord(value.props) ? value.props : undefined;
  const pageProps = props && isRecord(props.pageProps) ? props.pageProps : undefined;
  return pageProps ? getString(pageProps, ["username", "profileSlug", "name"])?.replace(/^@/, "") : undefined;
}

async function resolveFromProfilePage(handle: string): Promise<PublicHandleResolution> {
  const profileUrl = `${POLYMARKET_PROFILE_BASE_URL}/profile/%40${encodeURIComponent(handle)}`;
  const result = await safeFetch(profileUrl, { cache: "no-store", timeoutMs: 10_000, parseJson: false });
  const nextData = extractNextData(result.text);
  const address = deepAddressSearch(nextData);
  const handleFromPayload = usernameFromNextData(nextData) ?? handle;
  const resolved = Boolean(result.ok && address);
  const diagnostic = diagnosticFromFetch(
    "profile",
    result,
    resolved,
    resolved ? 1 : 0,
    result.ok && !address ? "Public profile page loaded, but no proxy wallet address was exposed." : undefined,
  );

  return {
    handle: handleFromPayload,
    address,
    profileUrl,
    sourceStatus: resolved ? "CONNECTED" : result.ok ? "PARTIAL" : "FAILED",
    error: diagnostic.error,
    diagnostic,
  };
}

function looksLikeAddress(value: string) {
  return /^0x[a-f0-9]{40}$/i.test(value);
}

function marketTypeFromTitle(title: string): WalletMarketType {
  const classified = classifyPolymarketMarket(title);
  if (classified.marketType === "OUTRIGHT") return "FUTURE";
  return classified.marketType === "YES_NO" ? "YES_NO" : classified.marketType;
}

function statusFromRecord(record: Record<string, unknown>, fallback: WalletPositionStatus): WalletPositionStatus {
  const text = normalizeText(getString(record, ["status", "outcome", "result", "state"]) ?? "");
  if (text.includes("won") || text === "win") return "WON";
  if (text.includes("lost") || text === "loss") return "LOST";
  if (text.includes("void") || text.includes("push")) return "VOID";
  if (text.includes("closed") || text.includes("sold")) return "CLOSED";
  if (text.includes("open") || text.includes("active")) return "OPEN";
  return fallback;
}

function positionId(record: Record<string, unknown>, handle: string, status: WalletPositionStatus) {
  const explicit = getString(record, ["id", "positionId", "transactionHash", "txHash"]);
  if (explicit) return explicit;
  const parts = [
    handle,
    getString(record, ["marketId", "market_id", "conditionId", "condition_id"]) ?? "",
    getString(record, ["assetId", "asset_id", "tokenId", "token_id"]) ?? "",
    getString(record, ["outcome", "side", "title", "marketTitle", "question"]) ?? "",
    getString(record, ["timestamp", "createdAt", "created_at"]) ?? "",
    status,
  ];
  return compactId(parts.join("-"));
}

function normalizePosition(record: Record<string, unknown>, handle: string, address: string | undefined, fallbackStatus: WalletPositionStatus): WalletPosition {
  const marketTitle =
    getString(record, ["marketTitle", "title", "question", "eventTitle", "conditionTitle", "market"]) ??
    getString(record, ["slug"]) ??
    "Unknown Polymarket market";
  const status = statusFromRecord(record, fallbackStatus);
  const classified = classifyPolymarketMarket(marketTitle, getString(record, ["category", "tags", "eventTitle"]));
  const currentPrice = getNumber(record, ["currentPrice", "curPrice", "price", "outcomePrice"]);
  const avgEntryPrice = getNumber(record, ["avgEntryPrice", "averagePrice", "avgPrice", "entryPrice", "pricePaid"]);
  const position: WalletPosition = {
    id: positionId(record, handle, status),
    handle,
    address,
    marketId: getString(record, ["marketId", "market_id", "id"]),
    conditionId: getString(record, ["conditionId", "condition_id"]),
    assetId: getString(record, ["assetId", "asset_id", "tokenId", "token_id"]),
    sport: classified.sport ?? "OTHER",
    category: classified.category,
    sportCategory: classified.sport,
    marketTitle,
    marketType: classified.marketType === "OUTRIGHT" ? "FUTURE" : marketTypeFromTitle(marketTitle),
    side: getString(record, ["side", "outcome", "direction"]) ?? "Unknown side",
    outcome: getString(record, ["outcome", "side", "asset"]) ?? "Unknown outcome",
    avgEntryPrice,
    currentPrice,
    shares: getNumber(record, ["shares", "size", "quantity"]),
    positionValue: getNumber(record, ["positionValue", "value", "amount", "notional"]),
    realizedPnl: getNumber(record, ["realizedPnl", "realizedPNL", "cashPnl", "cashPnlAmt"]),
    unrealizedPnl: getNumber(record, ["unrealizedPnl", "unrealizedPNL", "pnl"]),
    status,
    createdAt: getString(record, ["createdAt", "created_at", "timestamp"]),
    updatedAt: getString(record, ["updatedAt", "updated_at"]),
    resolvedAt: getString(record, ["resolvedAt", "resolved_at", "closedAt", "closed_at"]),
  };

  return position;
}

function normalizeActivity(record: Record<string, unknown>, handle: string, address?: string): WalletActivity {
  return {
    id: getString(record, ["id", "transactionHash", "txHash"]) ?? compactId(`${handle}-${JSON.stringify(record).slice(0, 80)}`),
    handle,
    address,
    marketId: getString(record, ["marketId", "market_id"]),
    conditionId: getString(record, ["conditionId", "condition_id"]),
    assetId: getString(record, ["assetId", "asset_id", "tokenId", "token_id"]),
    marketTitle: getString(record, ["marketTitle", "title", "question", "eventTitle"]),
    side: getString(record, ["side", "type"]),
    outcome: getString(record, ["outcome", "asset"]),
    price: getNumber(record, ["price", "avgPrice"]),
    amount: getNumber(record, ["amount", "size", "quantity", "value"]),
    transactionHash: getString(record, ["transactionHash", "txHash"]),
    timestamp: getString(record, ["timestamp", "createdAt", "created_at"]),
    rawType: getString(record, ["type", "action"]),
  };
}

export async function resolvePolymarketHandle(handle: string): Promise<PublicHandleResolution> {
  const normalizedHandle = handle.trim().replace(/^@/, "");
  if (looksLikeAddress(normalizedHandle)) {
    const profileUrl = publicProfileUrl(normalizedHandle);
    return {
      handle: normalizedHandle,
      address: normalizedHandle,
      profileUrl,
      sourceStatus: "CONNECTED",
      diagnostic: {
        label: "profile",
        resolved: true,
        sourceUrl: profileUrl,
        status: "CONNECTED",
        count: 1,
      },
    };
  }

  const url = new URL(POLYMARKET_PUBLIC_SEARCH_URL);
  url.searchParams.set("q", normalizedHandle);

  const searchResult = await safeFetch(url, { cache: "no-store", timeoutMs: 8000 });
  if (searchResult.ok) {
    const candidates = asArray(searchResult.json);
    const match = candidates.find((candidate) => {
      const username = getString(candidate, ["username", "handle", "name"]);
      return normalizeText(username) === normalizeText(normalizedHandle);
    }) ?? candidates[0];
    const address = match ? getString(match, ["proxyWallet", "address", "wallet", "walletAddress"]) : undefined;
    const handleFromPayload = match ? getString(match, ["username", "handle", "name"]) : undefined;

    if (address) {
      const profileUrl = publicProfileUrl(handleFromPayload ?? normalizedHandle);

      return {
        handle: handleFromPayload ?? normalizedHandle,
        address,
        profileUrl,
        sourceStatus: "CONNECTED",
        diagnostic: diagnosticFromFetch("profile", searchResult, true, candidates.length),
      };
    }
  }

  const profileResolution = await resolveFromProfilePage(normalizedHandle);
  if (profileResolution.address) return profileResolution;

  const publicSearchDiagnostic = diagnosticFromFetch(
    "profile",
    searchResult,
    false,
    searchResult.ok ? asArray(searchResult.json).length : undefined,
    searchResult.ok
      ? "Public search returned no wallet address and profile page did not expose a proxy wallet."
      : searchResult.error ?? searchResult.cause ?? "Public search failed and profile page fallback did not resolve.",
  );

  return {
    handle: profileResolution.handle || normalizedHandle,
    profileUrl: profileResolution.profileUrl || publicProfileUrl(normalizedHandle),
    sourceStatus: profileResolution.sourceStatus === "PARTIAL" ? "PARTIAL" : "FAILED",
    error: [publicSearchDiagnostic.error, profileResolution.error].filter(Boolean).join(" | "),
    diagnostic: {
      ...profileResolution.diagnostic,
      error: [publicSearchDiagnostic.error, profileResolution.error].filter(Boolean).join(" | "),
      responseTextSnippet: profileResolution.diagnostic.responseTextSnippet ?? publicSearchDiagnostic.responseTextSnippet,
    },
  };
}

async function fetchPositionSet(user: string | undefined, status: "open" | "closed"): Promise<FetchOutcome<Record<string, unknown>[]>> {
  const sourceUrl = status === "open" ? POLYMARKET_DATA_POSITIONS_URL : POLYMARKET_DATA_CLOSED_POSITIONS_URL;
  const url = new URL(sourceUrl);
  if (!user) {
    return {
      data: [],
      diagnostic: failedDiagnostic(status === "open" ? "openPositions" : "closedPositions", url.toString(), "No resolved wallet address for positions request."),
      error: "No resolved wallet address for positions request.",
    };
  }
  url.searchParams.set("user", user);
  url.searchParams.set("limit", "200");

  const result = await safeFetch(url, { cache: "no-store", timeoutMs: 10_000 });
  const data = result.ok ? asArray(result.json) : [];
  const label = status === "open" ? "openPositions" : "closedPositions";
  const diagnostic = diagnosticFromFetch(label, result, result.ok, data.length);

  return {
    data,
    diagnostic,
    error: result.ok ? undefined : `${result.url}: ${result.error ?? result.cause ?? "fetch failed"}${result.responseTextSnippet ? ` | ${result.responseTextSnippet}` : ""}`,
  };
}


async function fetchActivitySet(user: string | undefined, handle: string, address?: string): Promise<FetchOutcome<WalletActivity[]>> {
  const url = new URL(POLYMARKET_DATA_ACTIVITY_URL);
  if (!user) {
    return {
      data: [],
      diagnostic: failedDiagnostic("activity", url.toString(), "No resolved wallet address for activity request."),
      error: "No resolved wallet address for activity request.",
    };
  }
  url.searchParams.set("user", user);
  url.searchParams.set("limit", "200");

  const result = await safeFetch(url, { cache: "no-store", timeoutMs: 8000 });
  const records = result.ok ? asArray(result.json) : [];
  const diagnostic = diagnosticFromFetch("activity", result, result.ok, records.length);

  return {
    data: records.map((record) => normalizeActivity(record, handle, address)),
    diagnostic,
    error: result.ok ? undefined : `${result.url}: ${result.error ?? result.cause ?? "fetch failed"}${result.responseTextSnippet ? ` | ${result.responseTextSnippet}` : ""}`,
  };
}
export async function fetchWalletActivity(handleOrAddress: string): Promise<WalletActivity[]> {
  const resolution = await resolvePolymarketHandle(handleOrAddress);
  const user = resolution.address ?? handleOrAddress;
  const url = new URL(POLYMARKET_DATA_ACTIVITY_URL);
  url.searchParams.set("user", user);
  url.searchParams.set("limit", "200");

  const payload = await safeFetchJson(url, { cache: "no-store", timeoutMs: 8000 });
  return asArray(payload).map((record) => normalizeActivity(record, resolution.handle, resolution.address));
}

export async function fetchWalletOpenPositions(handleOrAddress: string): Promise<WalletPosition[]> {
  const resolution = await resolvePolymarketHandle(handleOrAddress);
  const positions = await fetchPositionSet(resolution.address ?? handleOrAddress, "open");
  if (positions.error) throw new Error(positions.error);
  return positions.data.map((record) => normalizePosition(record, resolution.handle, resolution.address, "OPEN"));
}

export async function fetchWalletClosedPositions(handleOrAddress: string): Promise<WalletPosition[]> {
  const resolution = await resolvePolymarketHandle(handleOrAddress);
  const positions = await fetchPositionSet(resolution.address ?? handleOrAddress, "closed");
  if (positions.error) throw new Error(positions.error);
  return positions.data.map((record) => normalizePosition(record, resolution.handle, resolution.address, "CLOSED"));
}

export async function fetchPolymarketProfile(handleOrAddress: string): Promise<WalletProfile> {
  // ASTRODDS uses public Polymarket wallet/profile data only. No private or non-public information is used.
  const resolution = await resolvePolymarketHandle(handleOrAddress);
  const user = resolution.address ?? (looksLikeAddress(handleOrAddress) ? handleOrAddress : undefined);
  const errors: string[] = resolution.error ? [resolution.error] : [];
  const [activityOutcome, openOutcome, closedOutcome] = await Promise.allSettled([
    fetchActivitySet(user, resolution.handle, resolution.address),
    fetchPositionSet(user, "open"),
    fetchPositionSet(user, "closed"),
  ]);
  const activityFetch = activityOutcome.status === "fulfilled" ? activityOutcome.value : undefined;
  const openFetch = openOutcome.status === "fulfilled" ? openOutcome.value : undefined;
  const closedFetch = closedOutcome.status === "fulfilled" ? closedOutcome.value : undefined;
  const activity = activityFetch?.data ?? [];
  const openPositions = (openFetch?.data ?? []).map((record) => normalizePosition(record, resolution.handle, resolution.address, "OPEN"));
  const closedPositions = (closedFetch?.data ?? []).map((record) => normalizePosition(record, resolution.handle, resolution.address, "CLOSED"));

  if (activityOutcome.status === "rejected") errors.push(activityOutcome.reason instanceof Error ? activityOutcome.reason.message : "Activity fetch failed.");
  if (openOutcome.status === "rejected") errors.push(openOutcome.reason instanceof Error ? openOutcome.reason.message : "Open position fetch failed.");
  if (closedOutcome.status === "rejected") errors.push(closedOutcome.reason instanceof Error ? closedOutcome.reason.message : "Closed position fetch failed.");
  if (activityFetch?.error) errors.push(activityFetch.error);
  if (openFetch?.error) errors.push(openFetch.error);
  if (closedFetch?.error) errors.push(closedFetch.error);

  const checks = [
    resolution.diagnostic,
    activityFetch?.diagnostic,
    openFetch?.diagnostic,
    closedFetch?.diagnostic,
  ].filter((diagnostic): diagnostic is WalletFetchDiagnostic => Boolean(diagnostic));
  const allPositions = [...openPositions, ...closedPositions];
  const totalVolume = allPositions.reduce((total, position) => total + (position.positionValue ?? 0), 0);
  const totalPnl = allPositions.reduce((total, position) => total + (position.realizedPnl ?? position.unrealizedPnl ?? 0), 0);
  const biggestWin = Math.max(0, ...allPositions.map((position) => position.realizedPnl ?? position.unrealizedPnl ?? 0));
  const sourceStatus: WalletSourceStatus =
    errors.length === 0 && (activity.length || allPositions.length)
      ? "CONNECTED"
      : activity.length || allPositions.length || resolution.address
        ? "PARTIAL"
        : errors.length
          ? "FAILED"
          : "NOT_CONNECTED";

  return {
    handle: resolution.handle,
    address: resolution.address,
    profileUrl: resolution.profileUrl,
    totalPnl: totalPnl || undefined,
    totalVolume: totalVolume || undefined,
    predictions: allPositions.length || undefined,
    portfolioValue: openPositions.reduce((total, position) => total + (position.positionValue ?? 0), 0) || undefined,
    biggestWin: biggestWin || undefined,
    openPositions,
    closedPositions,
    activity,
    sourceStatus,
    error: errors.length ? Array.from(new Set(errors)).join(" | ") : undefined,
    diagnostics: {
      handle: resolution.handle,
      profileUrl: resolution.profileUrl,
      address: resolution.address,
      profileResolved: resolution.sourceStatus === "CONNECTED",
      activityResolved: Boolean(activityFetch?.diagnostic.resolved),
      openPositionsResolved: Boolean(openFetch?.diagnostic.resolved),
      closedPositionsResolved: Boolean(closedFetch?.diagnostic.resolved),
      attemptedUrls: checks.map((check) => check.sourceUrl).filter((url): url is string => Boolean(url)),
      checks,
    },
  };
}
