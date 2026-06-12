export const STRONG_BUY_STARTING_BANKROLL = 1000;
export const STRONG_BUY_STAKE_PERCENT = 5;

export type StrongBuyExposureLabel = "normal exposure" | "elevated exposure" | "high exposure warning";

export type StrongBuyOpenLedgerLikeRow = {
  status?: string;
  stakeAmount?: number | null;
};

export type StrongBuyBankrollSnapshot = {
  startingBankroll: number;
  currentBankroll: number;
  stakePercent: number;
  stakeAmount: number;
  openStrongBuyCount: number;
  totalOpenStakeAmount: number;
  totalOpenExposurePercent: number;
  remainingUnexposedBankroll: number;
  exposureLabel: StrongBuyExposureLabel;
  warnings: string[];
};

type StrongBuyBankrollInput = {
  realizedSettledPaperPnL?: number | null;
  openRows?: StrongBuyOpenLedgerLikeRow[];
};

function roundToCents(value: number) {
  return Math.round(value * 100) / 100;
}

function exposureLabel(exposurePercent: number): StrongBuyExposureLabel {
  if (exposurePercent >= 40) return "high exposure warning";
  if (exposurePercent >= 20) return "elevated exposure";
  return "normal exposure";
}

export function buildStrongBuyBankrollSnapshot(input: StrongBuyBankrollInput = {}): StrongBuyBankrollSnapshot {
  const realizedSettledPaperPnL = typeof input.realizedSettledPaperPnL === "number" && Number.isFinite(input.realizedSettledPaperPnL)
    ? input.realizedSettledPaperPnL
    : 0;
  const currentBankroll = roundToCents(Math.max(0, STRONG_BUY_STARTING_BANKROLL + realizedSettledPaperPnL));
  const openRows = input.openRows ?? [];
  const totalOpenStakeAmount = roundToCents(
    openRows.reduce((total, row) => total + (typeof row.stakeAmount === "number" && Number.isFinite(row.stakeAmount) ? row.stakeAmount : 0), 0),
  );
  const openStrongBuyCount = openRows.filter((row) => row.status === "open").length;
  const safeBankroll = currentBankroll > 0 ? currentBankroll : STRONG_BUY_STARTING_BANKROLL;
  const totalOpenExposurePercent = safeBankroll > 0 ? roundToCents((totalOpenStakeAmount / safeBankroll) * 100) : 0;
  const remainingUnexposedBankroll = roundToCents(Math.max(0, safeBankroll - totalOpenStakeAmount));
  const stakeAmount = roundToCents(safeBankroll * (STRONG_BUY_STAKE_PERCENT / 100));
  const warnings: string[] = [];

  if (currentBankroll <= 0) warnings.push("Current bankroll is at or below zero. Stake sizing is capped at safe minimum handling.");
  if (totalOpenExposurePercent >= 40) warnings.push("Open exposure is already above 40% of current bankroll.");
  else if (totalOpenExposurePercent >= 20) warnings.push("Open exposure is above 20% of current bankroll.");

  return {
    startingBankroll: STRONG_BUY_STARTING_BANKROLL,
    currentBankroll: safeBankroll,
    stakePercent: STRONG_BUY_STAKE_PERCENT,
    stakeAmount,
    openStrongBuyCount,
    totalOpenStakeAmount,
    totalOpenExposurePercent,
    remainingUnexposedBankroll,
    exposureLabel: exposureLabel(totalOpenExposurePercent),
    warnings,
  };
}
