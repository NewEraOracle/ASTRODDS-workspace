const pillars = [
  {
    title: "Productive Treasury",
    text: "Liquid reserves protect the system while productive allocations grow the economy through disciplined capital deployment.",
  },
  {
    title: "Reserve-Backed Value Accrual",
    text: "Realized profits can strengthen treasury reserves and improve long-term economic resilience without relying on emissions.",
  },
  {
    title: "Credit / Monetary Engine",
    text: "The Credit Engine manages borrowing capacity, liquidity conditions, redemption pressure, and capital circulation.",
  },
  {
    title: "PCS Risk Brain",
    text: "PCS monitors treasury health, credit utilization, collateral risk, liquidation pressure, solvency, and system stress.",
  },
  {
    title: "MegaETH Execution",
    text: "MegaETH provides the real-time execution layer for fast credit, settlement, monitoring, and treasury infrastructure.",
  },
  {
    title: "UtopiaByFaith Utility Layer",
    text: "UtopiaByFaith brings culture, gameplay utility, artifacts, marketplace activity, and ecosystem identity to FAITH.",
  },
];

export function FaithEconomicOSSection() {
  return (
    <section id="economic-os" className="relative mx-auto max-w-7xl px-6 py-20">
      <div className="rounded-[2rem] border border-amber-400/20 bg-slate-950/80 p-8 shadow-2xl shadow-amber-950/20 backdrop-blur md:p-12">
        <div className="max-w-4xl">
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.35em] text-amber-300">
            FAITH Economic Operating System
          </p>

          <h2 className="text-3xl font-semibold tracking-tight text-white md:text-5xl">
            A human-built, AI/PCS-regulated economy for productive digital growth.
          </h2>

          <p className="mt-6 text-base leading-8 text-slate-300 md:text-lg">
            FAITH connects productive treasury reserves, programmable credit, PCS risk regulation,
            and MegaETH real-time execution into one disciplined financial economy.
          </p>

          <div className="mt-6 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-5 text-lg font-medium text-amber-100">
            Humans build. RWA anchors value. Treasury protects. Credit Engine circulates.
            PCS regulates. MegaETH executes. The economy grows.
          </div>
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {pillars.map((pillar) => (
            <article
              key={pillar.title}
              className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 transition hover:border-amber-300/40 hover:bg-white/[0.07]"
            >
              <h3 className="text-lg font-semibold text-white">{pillar.title}</h3>
              <p className="mt-3 text-sm leading-6 text-slate-400">{pillar.text}</p>
            </article>
          ))}
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 p-5">
            <p className="text-3xl font-semibold text-emerald-200">70%</p>
            <p className="mt-2 text-sm text-emerald-50">Liquid / near-liquid reserve target</p>
          </div>

          <div className="rounded-2xl border border-amber-400/20 bg-amber-400/10 p-5">
            <p className="text-3xl font-semibold text-amber-200">30%</p>
            <p className="mt-2 text-sm text-amber-50">Diversified productive allocation</p>
          </div>

          <div className="rounded-2xl border border-sky-400/20 bg-sky-400/10 p-5">
            <p className="text-3xl font-semibold text-sky-200">1–5%</p>
            <p className="mt-2 text-sm text-sky-50">Early RWA / venture exposure target</p>
          </div>
        </div>

        <p className="mt-8 text-sm leading-6 text-slate-500">
          MVP note: treasury and RWA allocation values are conceptual demo parameters until real
          treasury assets and compliant RWA integrations are connected.
        </p>
      </div>
    </section>
  );
}
