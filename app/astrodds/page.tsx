"use client";

import { useEffect, useMemo, useState } from "react";

type BestBetRow = {
  bestBetId?: string;
  gameId?: string;
  date?: string;
  awayTeam?: string;
  homeTeam?: string;
  selectedSide?: string;
  status?: string;
  marketType?: string;
  marketProbability?: number | string | null;
  calibratedProbability?: number | string | null;
  diagnosticCalibratedEdgePct?: number | string | null;
  matchConfidence?: string;
  riskLevel?: string;
  priceSourceUsed?: string;
  mainReason?: string;
};

type BestBetsResponse = {
  bestBetRows?: BestBetRow[];
  bestBetsDiagnostics?: {
    dailyPickCount?: number;
    buyCount?: number;
    watchCount?: number;
    sportsbookOddsFound?: number;
    rowsWithModelProbability?: number;
    rowsWithRealPrice?: number;
  };
};

function toNum(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const normalized = String(value).replace(",", ".");
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function pct(value: unknown): string {
  const n = toNum(value);
  if (n === null) return "-";
  return `${(n * 100).toFixed(1)}%`;
}

function edgePct(row: BestBetRow): number | null {
  const model = toNum(row.calibratedProbability);
  const market = toNum(row.marketProbability);
  if (model !== null && market !== null) return (model - market) * 100;

  const diagnostic = toNum(row.diagnosticCalibratedEdgePct);
  return diagnostic;
}

function edgeText(row: BestBetRow): string {
  const e = edgePct(row);
  if (e === null) return "-";
  return `${e >= 0 ? "+" : ""}${e.toFixed(1)}%`;
}

function isCleanMoneylinePick(row: BestBetRow): boolean {
  const market = toNum(row.marketProbability);
  const model = toNum(row.calibratedProbability);
  const edge = edgePct(row);

  const selectedIsTeam =
    Boolean(row.selectedSide) &&
    (row.selectedSide === row.awayTeam || row.selectedSide === row.homeTeam);

  const statusOk = row.status === "daily_pick" || row.status === "buy";
  const moneylineOnly = row.marketType === "moneyline";
  const priceOk = row.priceSourceUsed === "sportsbook" || row.priceSourceUsed === "polymarket";
  const confidenceOk = row.matchConfidence === "high" || row.matchConfidence === "medium";
  const riskOk = row.riskLevel !== "high" && row.riskLevel !== "unknown";

  return Boolean(
    statusOk &&
      moneylineOnly &&
      selectedIsTeam &&
      priceOk &&
      market !== null &&
      model !== null &&
      edge !== null &&
      market >= 0.3 &&
      market <= 0.75 &&
      model >= 0.05 &&
      model <= 0.95 &&
      edge > 0 &&
      edge <= 25 &&
      confidenceOk &&
      riskOk,
  );
}

function rank(row: BestBetRow): number {
  const statusScore = row.status === "daily_pick" ? 100000 : 50000;
  const edge = edgePct(row) ?? 0;
  const model = (toNum(row.calibratedProbability) ?? 0) * 100;
  const confidence = row.matchConfidence === "high" ? 1000 : 500;
  return statusScore + confidence + edge * 100 + model;
}

function gameKey(row: BestBetRow): string {
  return `${row.awayTeam ?? ""} @ ${row.homeTeam ?? ""}`;
}

export default function AstroddsSimplePage() {
  const [data, setData] = useState<BestBetsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedCount, setSavedCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await fetch("/api/astrodds/best-bets/today", { cache: "no-store" });
        if (!response.ok) throw new Error(`Best Bets API failed: ${response.status}`);
        const json = (await response.json()) as BestBetsResponse;
        if (!cancelled) setData(json);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unknown error");
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const topRows = useMemo(() => {
    const rows = data?.bestBetRows ?? [];

    const clean = rows
      .filter(isCleanMoneylinePick)
      .sort((a, b) => rank(b) - rank(a));

    const byGame = new Map<string, BestBetRow>();
    for (const row of clean) {
      const key = gameKey(row);
      if (!byGame.has(key)) byGame.set(key, row);
    }

    return Array.from(byGame.values()).slice(0, 10);
  }, [data]);

  useEffect(() => {
    if (!topRows.length) return;

    const existingRaw = localStorage.getItem("astrodds_saved_top10_moneyline");
    const existing = existingRaw ? (JSON.parse(existingRaw) as BestBetRow[]) : [];

    const merged = new Map<string, BestBetRow>();
    for (const row of existing) {
      merged.set(`${row.date}|${row.gameId}|${row.selectedSide}|${row.status}`, row);
    }
    for (const row of topRows) {
      merged.set(`${row.date}|${row.gameId}|${row.selectedSide}|${row.status}`, row);
    }

    const saved = Array.from(merged.values());
    localStorage.setItem("astrodds_saved_top10_moneyline", JSON.stringify(saved));
    setSavedCount(saved.length);
  }, [topRows]);

  function downloadCsv() {
    const header = ["Game", "Pick", "Status", "Market%", "Model%", "Edge%", "Confidence", "Risk", "Why"];
    const lines = topRows.map((row) => [
      gameKey(row),
      row.selectedSide ?? "",
      row.status ?? "",
      pct(row.marketProbability),
      pct(row.calibratedProbability),
      edgeText(row),
      row.matchConfidence ?? "",
      row.riskLevel ?? "",
      row.mainReason ?? "",
    ]);

    const csv = [header, ...lines]
      .map((line) => line.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(","))
      .join("\n");

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "astrodds-top10-moneyline.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const diagnostics = data?.bestBetsDiagnostics;

  return (
    <main className="min-h-screen bg-[#050814] px-6 py-8 text-white">
      <section className="mx-auto max-w-7xl">
        <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-cyan-300">ASTRODDS</p>
            <h1 className="mt-2 text-3xl font-black md:text-5xl">Top 10 MLB Moneyline Picks</h1>
            <p className="mt-2 text-sm text-slate-400">
              Clean mode only. Moneyline only. Real money OFF. Paper/manual review.
            </p>
          </div>

          <button
            onClick={downloadCsv}
            className="rounded-xl border border-cyan-400/40 bg-cyan-400/10 px-5 py-3 text-sm font-bold text-cyan-100 hover:bg-cyan-400/20"
          >
            Download CSV
          </button>
        </div>

        <div className="mb-6 grid gap-3 md:grid-cols-5">
          <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
            <p className="text-xs uppercase text-slate-500">Top Picks</p>
            <p className="mt-1 text-3xl font-black">{topRows.length}</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
            <p className="text-xs uppercase text-slate-500">Daily Picks</p>
            <p className="mt-1 text-3xl font-black text-emerald-300">
              {topRows.filter((row) => row.status === "daily_pick").length}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
            <p className="text-xs uppercase text-slate-500">Buy</p>
            <p className="mt-1 text-3xl font-black text-sky-300">
              {topRows.filter((row) => row.status === "buy").length}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
            <p className="text-xs uppercase text-slate-500">Saved</p>
            <p className="mt-1 text-3xl font-black">{savedCount}</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
            <p className="text-xs uppercase text-slate-500">Mode</p>
            <p className="mt-1 text-lg font-black text-amber-300">Paper Only</p>
          </div>
        </div>

        {error ? (
          <div className="rounded-2xl border border-red-500/40 bg-red-950/30 p-5 text-red-200">{error}</div>
        ) : null}

        <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/70">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-slate-900 text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="p-4">#</th>
                <th className="p-4">Game</th>
                <th className="p-4">Pick</th>
                <th className="p-4">Status</th>
                <th className="p-4">Market</th>
                <th className="p-4">Model</th>
                <th className="p-4">Edge</th>
                <th className="p-4">Confidence</th>
                <th className="p-4">Risk</th>
                <th className="p-4">Why</th>
              </tr>
            </thead>
            <tbody>
              {!data ? (
                <tr>
                  <td className="p-6 text-slate-400" colSpan={10}>Loading best bets...</td>
                </tr>
              ) : topRows.length === 0 ? (
                <tr>
                  <td className="p-6 text-amber-200" colSpan={10}>
                    No clean Top 10 picks passed the filter. The engine may have data, but no row passed the strict quality gate.
                  </td>
                </tr>
              ) : (
                topRows.map((row, index) => (
                  <tr key={`${row.gameId}-${row.selectedSide}-${row.status}`} className="border-t border-slate-800">
                    <td className="p-4 font-bold text-slate-400">{index + 1}</td>
                    <td className="p-4">
                      <div className="font-bold">{gameKey(row)}</div>
                      <div className="mt-1 text-xs text-slate-500">{row.date}</div>
                    </td>
                    <td className="p-4 font-black text-white">{row.selectedSide}</td>
                    <td className="p-4">
                      <span className={row.status === "daily_pick" ? "text-emerald-300 font-black" : "text-sky-300 font-black"}>
                        {row.status}
                      </span>
                    </td>
                    <td className="p-4">{pct(row.marketProbability)}</td>
                    <td className="p-4">{pct(row.calibratedProbability)}</td>
                    <td className="p-4 font-black text-emerald-300">{edgeText(row)}</td>
                    <td className="p-4">{row.matchConfidence}</td>
                    <td className="p-4">{row.riskLevel}</td>
                    <td className="max-w-md p-4 text-slate-300">{row.mainReason}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <details className="mt-6 rounded-2xl border border-slate-800 bg-slate-950/50 p-4">
          <summary className="cursor-pointer font-bold text-slate-300">Advanced diagnostics</summary>
          <div className="mt-4 grid gap-3 text-sm text-slate-400 md:grid-cols-3">
            <div>Sportsbook odds: {diagnostics?.sportsbookOddsFound ?? "-"}</div>
            <div>Rows with model: {diagnostics?.rowsWithModelProbability ?? "-"}</div>
            <div>Rows with price: {diagnostics?.rowsWithRealPrice ?? "-"}</div>
            <div>Raw daily picks: {diagnostics?.dailyPickCount ?? "-"}</div>
            <div>Raw buy: {diagnostics?.buyCount ?? "-"}</div>
            <div>Raw watch: {diagnostics?.watchCount ?? "-"}</div>
          </div>
          <p className="mt-4 text-xs text-slate-500">
            NFT / Card Vault code is kept in the project for future use. It is not shown in this clean betting view.
          </p>
        </details>
      </section>
    </main>
  );
}
