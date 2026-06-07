const classes = [
  {
    name: "Class A",
    liquid: "70%",
    productive: "30%",
    ltv: "Lower",
    mode: "Growth / higher surplus potential",
  },
  {
    name: "Class B",
    liquid: "80%",
    productive: "20%",
    ltv: "Medium",
    mode: "Balanced growth",
  },
  {
    name: "Class C",
    liquid: "90%",
    productive: "10%",
    ltv: "Higher",
    mode: "Conservative growth",
  },
  {
    name: "Class D",
    liquid: "95%",
    productive: "5%",
    ltv: "Highest",
    mode: "Most liquid / safest collateral",
  },
];

const pcsReview = [
  "Treasury liquidity",
  "Redemption pressure",
  "Productive capital performance",
  "Realized vs unrealized profit",
  "Reserve coverage",
  "Credit utilization",
  "Debt coverage",
  "Portfolio drawdown",
  "LTV safety",
  "System risk score",
];

export function FaithCertificateControlRoom() {
  return (
    <section className="mt-10 rounded-[2rem] border border-emerald-400/20 bg-slate-950/85 p-6 shadow-2xl shadow-emerald-950/20 md:p-8">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.35em] text-emerald-300">
            Treasury Certificate Control
          </p>
          <h2 className="mt-3 text-2xl font-semibold text-white md:text-4xl">
            Class-based capital, LTV, redemption, and PCS risk monitoring.
          </h2>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-400">
            This demo module shows how FAITH Treasury Certificates can be classed by liquidity,
            productive exposure, collateral quality, redemption speed, and PCS-adjusted LTV.
          </p>
        </div>

        <div className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 px-5 py-4 text-sm text-emerald-100">
          Certificate model — demo only
        </div>
      </div>

      <div className="mt-8 grid gap-4 xl:grid-cols-4">
        {classes.map((item) => (
          <article key={item.name} className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-xl font-semibold text-white">{item.name}</h3>
              <span className="rounded-full border border-amber-300/20 bg-amber-300/10 px-3 py-1 text-xs text-amber-100">
                {item.ltv} LTV
              </span>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/10 p-3">
                <p className="text-2xl font-semibold text-emerald-200">{item.liquid}</p>
                <p className="mt-1 text-xs text-emerald-50/80">Liquid target</p>
              </div>

              <div className="rounded-xl border border-amber-400/20 bg-amber-400/10 p-3">
                <p className="text-2xl font-semibold text-amber-200">{item.productive}</p>
                <p className="mt-1 text-xs text-amber-50/80">Productive</p>
              </div>
            </div>

            <p className="mt-4 text-sm leading-6 text-slate-400">{item.mode}</p>
          </article>
        ))}
      </div>

      <div className="mt-8 grid gap-4 xl:grid-cols-2">
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
          <h3 className="text-lg font-semibold text-white">Quarterly PCS Review</h3>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {pcsReview.map((item) => (
              <div key={item} className="rounded-xl border border-white/10 bg-slate-900/80 p-3 text-sm text-slate-300">
                {item}
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
          <h3 className="text-lg font-semibold text-white">Protocol Rules</h3>
          <div className="mt-4 space-y-3">
            <div className="rounded-xl border border-white/10 bg-slate-900/80 p-4">
              <p className="text-sm font-medium text-amber-100">No surplus allocation unless safety thresholds are met.</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-900/80 p-4">
              <p className="text-sm font-medium text-emerald-100">Liquidity protects LTV. Productive risk earns upside.</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-900/80 p-4">
              <p className="text-sm font-medium text-sky-100">PCS advises and regulates the protocol, not individual users.</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-900/80 p-4">
              <p className="text-sm font-medium text-red-100">Redemptions can be queued, limited, or paused during stress.</p>
            </div>
          </div>
        </div>
      </div>

      <p className="mt-6 text-xs leading-5 text-slate-500">
        MVP note: this is a conceptual treasury-certificate dashboard. Real certificate issuance,
        redemption rights, treasury accounting, RWA exposure, and surplus participation require
        legal, compliance, and accounting review before launch.
      </p>
    </section>
  );
}
