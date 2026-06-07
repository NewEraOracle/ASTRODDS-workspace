import { KNOWN_WHALE_WALLETS } from "./known-wallets";
import { categoryAllowed } from "./market-classifier";
import { fetchPolymarketProfile } from "./wallet-profile";
import { buildWhaleConsensus } from "./whale-consensus";
import { calculatePositionCopyability, calculateWhaleStrategy } from "./whale-strategy";
import type { WalletScanResult, WalletSourceStatus, WhaleWalletRank } from "./types";

function statusRank(status: WalletSourceStatus) {
  const rank: Record<WalletSourceStatus, number> = {
    CONNECTED: 4,
    PARTIAL: 3,
    FAILED: 2,
    NOT_CONNECTED: 1,
  };
  return rank[status];
}

function combinedStatus(statuses: WalletSourceStatus[]): WalletSourceStatus {
  if (!statuses.length) return "NOT_CONNECTED";
  if (statuses.every((status) => status === "CONNECTED")) return "CONNECTED";
  if (statuses.some((status) => status === "CONNECTED" || status === "PARTIAL")) return "PARTIAL";
  if (statuses.some((status) => status === "FAILED")) return "FAILED";
  return "NOT_CONNECTED";
}

function rankForHandle(handle: string): WhaleWalletRank {
  return KNOWN_WHALE_WALLETS.find((wallet) => wallet.handle.toLowerCase() === handle.toLowerCase())?.rank ?? "WHALE_WATCH";
}

export async function scanWhaleWallets(input?: { handles?: string[]; addresses?: string[]; sport?: string; category?: string }): Promise<WalletScanResult> {
  // ASTRODDS uses public Polymarket wallet/profile data only. No private or non-public information is used.
  const handles = input?.handles?.length ? input.handles : KNOWN_WHALE_WALLETS.map((wallet) => wallet.handle);
  const targets = Array.from(new Set([...handles, ...(input?.addresses ?? [])].map((target) => target.trim()).filter(Boolean)));
  const scannedAt = new Date().toISOString();
  const settled = await Promise.allSettled(targets.map((target) => fetchPolymarketProfile(target)));
  const profiles = settled.flatMap((result) => (result.status === "fulfilled" ? [result.value] : []));
  const errors = settled.flatMap((result, index) => {
    if (result.status === "fulfilled") return result.value.error ? [`${result.value.handle}: ${result.value.error}`] : [];
    return [`${targets[index]}: ${result.reason instanceof Error ? result.reason.message : "Unknown public wallet scan failure."}`];
  });
  const strategyMetrics = profiles
    .map((profile) => calculateWhaleStrategy(profile, rankForHandle(profile.handle)))
    .sort((a, b) => statusRank(profiles.find((profile) => profile.handle === a.handle)?.sourceStatus ?? "NOT_CONNECTED") - statusRank(profiles.find((profile) => profile.handle === b.handle)?.sourceStatus ?? "NOT_CONNECTED"));
  const activePositions = profiles.flatMap((profile) => profile.openPositions).filter((position) => {
    const sportAllowed = input?.sport ? (position.sport ?? "").toUpperCase() === input.sport.toUpperCase() : true;
    const whaleCategory = position.category ?? "UNKNOWN";
    return sportAllowed && categoryAllowed(whaleCategory, input?.category ?? "all");
  });
  const closedPositions = profiles.flatMap((profile) => profile.closedPositions).filter((position) => {
    const sportAllowed = input?.sport ? (position.sport ?? "").toUpperCase() === input.sport.toUpperCase() : true;
    const whaleCategory = position.category ?? "UNKNOWN";
    return sportAllowed && categoryAllowed(whaleCategory, input?.category ?? "all");
  });
  const copyability = activePositions.map((position) => calculatePositionCopyability(position));
  const consensus = buildWhaleConsensus(profiles, input?.sport);
  const diagnostics = profiles.flatMap((profile) => (profile.diagnostics ? [profile.diagnostics] : []));

  return {
    profiles,
    strategyMetrics,
    activePositions,
    closedPositions,
    copyability,
    consensus,
    sourceStatus: combinedStatus(profiles.map((profile) => profile.sourceStatus)),
    errors,
    diagnostics,
    scannedAt,
  };
}
