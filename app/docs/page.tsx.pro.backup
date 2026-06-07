import Link from "next/link";

export default function DocsPage() {
  return (
    <main className="min-h-screen bg-black px-6 py-16 text-white lg:px-10">
      <Link href="/" className="text-xs font-black uppercase tracking-[0.28em] text-cyan-300 hover:text-white">
        Back to FAITH
      </Link>

      <section className="mx-auto mt-12 max-w-5xl">
        <p className="text-sm font-black uppercase tracking-[0.38em] text-cyan-300">
          Public Docs v0.1
        </p>

        <h1 className="mt-5 text-5xl font-black uppercase tracking-[0.12em] text-white">
          FAITH Public Whitepaper
        </h1>

        <p className="mt-6 text-lg leading-8 text-slate-400">
          This public documentation explains FAITH Protocol&apos;s vision, architecture,
          and economic thesis. Proprietary PCS scoring models, treasury parameters,
          advanced risk thresholds, and private economic strategy are intentionally
          excluded from this public version.
        </p>

        <div className="mt-10 grid gap-4 md:grid-cols-2">
          {[
            ["Core Positioning", "#core-positioning"],
            ["Economic Flywheel", "#economic-flywheel"],
            ["Protocol Architecture", "#protocol-architecture"],
            ["PCS Risk Layer", "#pcs-risk-layer"],
            ["Treasury Layer", "#treasury-layer"],
            ["Public Safety Boundary", "#public-safety-boundary"],
          ].map(([label, href]) => (
            <a
              key={label}
              href={href}
              className="faith-card block p-5 text-sm font-black uppercase tracking-[0.18em] text-cyan-300 transition hover:border-cyan-300/60 hover:text-white"
            >
              {label}
            </a>
          ))}
        </div>

        <div className="mt-12 space-y-6">
          <section id="core-positioning" className="faith-card scroll-mt-24 p-6">
            <h2 className="text-2xl font-black uppercase tracking-[0.16em] text-white">
              Core Positioning
            </h2>
            <p className="mt-5 text-sm leading-7 text-slate-400">
              FAITH is building a growing and flourishing machine-regulated economy,
              not through speculation, but through productive value, programmable credit,
              treasury resilience, PCS risk regulation, and real utility.
            </p>
          </section>

          <section id="economic-flywheel" className="faith-card scroll-mt-24 p-6">
            <h2 className="text-2xl font-black uppercase tracking-[0.16em] text-white">
              Economic Flywheel
            </h2>
            <p className="mt-5 text-sm leading-7 text-slate-400">
              Vaults create credit. Credit creates activity. Activity strengthens the
              treasury. Treasury protects the system. PCS regulates risk. Stronger
              infrastructure attracts more usage. The economy grows.
            </p>
          </section>

          <section id="protocol-architecture" className="faith-card scroll-mt-24 p-6">
            <h2 className="text-2xl font-black uppercase tracking-[0.16em] text-white">
              Protocol Architecture
            </h2>
            <p className="mt-5 text-sm leading-7 text-slate-400">
              FAITH is organized around vaults, CreditEngine, PCS Monitor, Treasury,
              SettlementAdapter, and tfUSD / MockUSDm. This public version explains the
              system at a high level without exposing the private engine.
            </p>
          </section>

          <section id="pcs-risk-layer" className="faith-card scroll-mt-24 p-6">
            <h2 className="text-2xl font-black uppercase tracking-[0.16em] text-white">
              PCS Risk Layer
            </h2>
            <p className="mt-5 text-sm leading-7 text-slate-400">
              PCS monitors vault health, oracle shocks, liquidation pressure, borrow
              utilization, treasury coverage, and system stress. PCS recommends
              protocol-level responses so growth can remain disciplined.
            </p>
          </section>

          <section id="treasury-layer" className="faith-card scroll-mt-24 p-6">
            <h2 className="text-2xl font-black uppercase tracking-[0.16em] text-white">
              Treasury Layer
            </h2>
            <p className="mt-5 text-sm leading-7 text-slate-400">
              The treasury is the reserve engine of the FAITH economy. Fees and reserves
              strengthen system resilience, support development, and help protect the
              protocol during stress.
            </p>
          </section>

          <section id="public-safety-boundary" className="faith-card scroll-mt-24 p-6">
            <h2 className="text-2xl font-black uppercase tracking-[0.16em] text-white">
              Public Safety Boundary
            </h2>
            <p className="mt-5 text-sm leading-7 text-slate-400">
              Public docs explain the system, not the private engine. Exact PCS formulas,
              treasury defense thresholds, advanced liquidation parameters, token allocation
              ranges, and private strategy are intentionally kept outside this public version.
            </p>
          </section>

          <section className="faith-card p-6">
            <h2 className="text-2xl font-black uppercase tracking-[0.16em] text-white">
              Core Line
            </h2>
            <p className="mt-5 text-xl font-black leading-8 text-white">
              Humans build. PCS regulates. Treasury protects. MegaETH executes. The economy grows.
            </p>
          </section>
        </div>
      </section>
    </main>
  );
}
