const treasuryCards = [
  {
    label: "Treasury Health",
    value: "HEALTHY",
    detail: "Liquid reserves protect the system during stress.",
  },
  {
    label: "Liquid Reserves",
    value: "70%",
    detail: "Target liquid / near-liquid reserve layer.",
  },
  {
    label: "Productive Allocation",
    value: "30%",
    detail: "Diversified productive capital allocation.",
  },
  {
    label: "Early RWA / Venture",
    value: "1–5%",
    detail: "Limited early exposure for disciplined growth.",
  },
  {
    label: "PCS Risk Score",
    value: "24 / 100",
    detail: "Normal mode. No emergency response required.",
  },
  {
    label: "Credit Mode",
    value: "NEUTRAL",
    detail: "Credit expansion remains controlled.",
  },
];

const actionQueue = [
  "Maintain liquid reserve ratio",
  "Monitor credit utilization",
  "Tighten borrowing if utilization rises",
  "Increase reserve targets during stress",
  "Activate emergency mode if solvency risk rises",
];

const stressTimeline = [
  {
    scenario: "Current state",
    risk: "Normal",
    recommendation: "Maintain current parameters",
  },
  {
    scenario: "-10% collateral shock",
    risk: "Watch",
    recommendation: "Monitor liquidation pressure",
  },
  {
    scenario: "-20% collateral shock",
    risk: "Stress",
    recommendation: "Tighten credit conditions",
  },
  {
    scenario: "-30% collateral shock",
    risk: "Emergency",
    recommendation: "Activate emergency risk mode",
  },
];

export function FaithEconomicControlRoom() {
  return (
    <section className="mt-10 rounded-[2rem] border border-amber-400/20 bg-slate-950/80 p-6 shadow-2xl shadow-amber-950/20 md:p-8">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.35em] text-amber-300">
            Economic Control Room
          </p>
          <h2 className="mt-3 text-2xl font-semibold text-white md:text-4xl">
            Productive Treasury + Credit Engine + PCS
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
            Demo control layer showing how FAITH can monitor treasury reserves, credit conditions,
            PCS risk score, reserve-backed value strength, and MegaETH execution readiness.
          </p>
        </div>

        <div className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 px-5 py-4 text-sm text-emerald-100">
          Demo data — MVP simulation
        </div>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {treasuryCards.map((card) => (
          <article key={card.label} className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
            <p className="text-sm text-slate-400">{card.label}</p>
            <p className="mt-2 text-3xl font-semibold text-white">{card.value}</p>
            <p className="mt-3 text-sm leading-6 text-slate-500">{card.detail}</p>
          </article>
        ))}
      </div>

      <div className="mt-8 grid gap-4 xl:grid-cols-2">
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
          <h3 className="text-lg font-semibold text-white">PCS Action Queue</h3>
          <div className="mt-4 space-y-3">
            {actionQueue.map((action, index) => (
              <div key={action} className="flex gap-3 rounded-xl border border-white/10 bg-slate-900/80 p-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-300/20 text-sm font-semibold text-amber-200">
                  {index + 1}
                </span>
                <p className="text-sm text-slate-300">{action}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
          <h3 className="text-lg font-semibold text-white">PCS Stress Timeline</h3>
          <div className="mt-4 space-y-3">
            {stressTimeline.map((item) => (
              <div key={item.scenario} className="rounded-xl border border-white/10 bg-slate-900/80 p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium text-white">{item.scenario}</p>
                  <span className="rounded-full border border-amber-300/20 bg-amber-300/10 px-3 py-1 text-xs text-amber-100">
                    {item.risk}
                  </span>
                </div>
                <p className="mt-2 text-sm text-slate-400">{item.recommendation}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <p className="mt-6 text-xs leading-5 text-slate-500">
        FAITH does not guarantee price appreciation. MVP values are simulated until live treasury,
        RWA, and protocol parameters are connected.
      </p>
    </section>
  );
}
