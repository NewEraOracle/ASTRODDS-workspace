import Link from "next/link";

const modules = [
  {
    title: "Vaults",
    image: "/faith/design/icon-vaults.png",
    body: "Overcollateralized on-chain vaults for sustainable real-time credit minting.",
  },
  {
    title: "PCS",
    image: "/faith/design/icon-pcs.png",
    body: "Protocol Control System governing risk, issuance, oracle shocks, and parameters.",
  },
  {
    title: "Treasury",
    image: "/faith/design/icon-treasury.png",
    body: "Protocol-owned liquidity and reserves aligned for long-term solvency.",
  },
  {
    title: "FUSD Activation",
    image: "/faith/design/token-fusd.png",
    body: "Activate FUSD for payments, trading, and composable real-time applications.",
  },
];

const loop = [
  ["Collateral", "Deposited", "/faith/design/icon-vaults.png"],
  ["Credit", "Minted", "/faith/design/token-fusd.png"],
  ["PCS", "Monitor", "/faith/design/icon-pcs.png"],
  ["FUSD", "Activated", "/faith/design/token-fusd.png"],
  ["Real-Time", "Utilization", "/faith/design/icon-real-time-execution.png"],
];

const stats = [
  ["Total Value Locked", "$128.7M", "+12.3% 24H"],
  ["FUSD Supply", "$84.2M", "+9.7% 24H"],
  ["Active Vaults", "2,431", "+8.1% 24H"],
  ["Collateral Ratio", "176%", "Healthy"],
  ["Protocol Revenue", "$312.9K", "+15.4% 24H"],
  ["MegaETH Block Time", "<10MS", "Real-Time"],
];

export default function Home() {
  return (
    <main className="faith-home relative min-h-screen overflow-hidden bg-black text-white">
      <img
        src="/faith/design/background-cosmic.png"
        alt=""
        className="fixed inset-0 h-full w-full object-cover opacity-95"
      />
      <div className="fixed inset-0 bg-black/25" />

      <div className="relative z-10 mx-auto max-w-[1720px] px-4 py-4">
        <div className="faith-shell overflow-hidden rounded-[1.4rem]">
          <nav className="flex items-center justify-between border-b border-white/10 bg-black/25 px-8 py-5 backdrop-blur-md">
            <img
              src="/faith/design/logo-faith-metal.png"
              alt="FAITH"
              className="faith-logo-top h-14 w-auto object-contain"
            />

            <div className="hidden items-center gap-10 text-[11px] font-black uppercase tracking-[0.28em] text-slate-100 lg:flex">
              <Link href="/protocol">Protocol</Link>
              <Link href="/tfusd">FUSD</Link>
              <Link href="/developers">Developers</Link>
              <Link href="/docs">Docs</Link>
              <Link href="/governance">Governance</Link>
              <Link href="/about">About</Link>
              <Link href="/simulation">Simulation</Link>
            </div>

            <Link href="/dashboard" className="faith-button px-7 py-4 text-[11px]">
              Enter Dashboard
            </Link>
          </nav>

          <section className="relative px-6 pb-14 pt-12 text-center">
            <div className="pointer-events-none absolute left-1/2 top-2 h-[560px] w-[920px] -translate-x-1/2 rounded-full bg-cyan-300/10 blur-3xl" />
            <img
              src="/faith/design/logo-faith-metal.png"
              alt="FAITH"
              className="mx-auto w-[430px] max-w-[88vw] object-contain drop-shadow-[0_0_28px_rgba(125,211,252,0.28)]"
            />

            <p className="relative z-10 mt-2 text-sm font-black uppercase tracking-[0.52em] text-cyan-100 md:text-base">
              FAITH Protocol
            </p>

            <p className="relative z-10 mt-2 text-xs font-black uppercase tracking-[0.30em] text-slate-300 md:text-sm">
              Bridging RWA to an Autonomous Digital Economy
            </p>

            <p className="relative z-10 mx-auto mt-4 inline-flex rounded-full border border-cyan-300/30 bg-cyan-300/10 px-5 py-2 text-center text-[10px] font-black uppercase tracking-[0.22em] text-cyan-100 shadow-[0_0_24px_rgba(34,211,238,0.18)] md:text-xs">
              MegaETH-Native Credit, Treasury & Risk Infrastructure
            </p>

            <p className="relative z-10 mx-auto mt-7 max-w-3xl text-sm leading-7 text-slate-300 md:text-base">
              FAITH connects real-world assets and productive infrastructure to autonomous on-chain credit,
              treasury, and risk systems.
            </p>

            <div className="relative z-10 mx-auto mt-7 max-w-4xl border border-cyan-100/15 bg-black/25 p-5 text-center backdrop-blur-sm">
              <p className="text-sm leading-7 text-slate-300">
                FAITH is building a self-growing economy where real-world infrastructure, autonomous digital finance, and virtual worlds reinforce each other.
              </p>

              <div className="mt-5 grid gap-2 text-[10px] font-black uppercase tracking-[0.20em] text-cyan-100 md:grid-cols-2">
                <p>Humans build the world.</p>
                <p>Technology regulates the economy.</p>
                <p>FAITH connects the physical and digital layers.</p>
                <p>Utopia gives people a world to experience it.</p>
              </div>
            </div>

            <div className="relative z-10 mt-8 flex flex-col justify-center gap-4 sm:flex-row">
              <a href="#protocol" className="faith-button px-8 py-4 text-[11px]">
                Read The Protocol
              </a>
              <Link href="/dashboard" className="faith-button px-8 py-4 text-[11px]">
                Enter Dashboard
              </Link>
            </div>
          </section>

          <section id="protocol" className="grid gap-5 px-6 pb-8 md:grid-cols-2 xl:grid-cols-4 lg:px-10">
            {modules.map((module) => (
              <div key={module.title} className="faith-card p-5">
                <div className="flex items-center gap-5">
                  <div className="faith-icon-box">
                    <img
                      src={module.image}
                      alt={module.title}
                      className={module.title.includes("FUSD") ? "faith-asset tfusd-bright" : "faith-asset"}
                    />
                  </div>

                  <div>
                    <h3 className="text-sm font-black uppercase tracking-[0.28em] text-white">
                      {module.title}
                    </h3>
                    <p className="mt-3 text-sm leading-6 text-slate-400">
                      {module.body}
                    </p>
                    <p className="mt-4 text-[10px] font-black uppercase tracking-[0.25em] text-cyan-300">
                      Learn More ?
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </section>

          <section id="loop" className="mx-6 mb-6 grid gap-5 lg:mx-10 lg:grid-cols-[1.25fr_.95fr]">
            <div className="faith-card p-6">
              <p className="text-sm font-black uppercase tracking-[0.38em] text-slate-300">
                The Protocol Loop
              </p>

              <div className="mt-7 grid grid-cols-2 gap-5 md:grid-cols-5">
                {loop.map(([top, bottom, image]) => (
                  <div key={top} className="text-center">
                    <div className="faith-loop-icon">
                      <img
                        src={image}
                        alt={top}
                        className={top === "FUSD" || top === "Credit" ? "faith-asset tfusd-bright" : "faith-asset"}
                      />
                    </div>
                    <p className="mt-3 text-[11px] font-black uppercase tracking-[0.2em] text-white">{top}</p>
                    <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">{bottom}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="faith-card p-6">
              <h2 className="text-3xl font-black uppercase leading-tight tracking-[0.16em] text-white">
                Credit That Moves At Internet Speed.
              </h2>
              <p className="mt-4 text-sm leading-7 text-slate-400">
                FAITH is purpose-built for MegaETH: collateral in, credit out, PCS active,
                treasury aligned, liquidation visible, and settlement prepared for real-time utility.
              </p>
              <Link href="/dashboard" className="mt-5 inline-block text-[11px] font-black uppercase tracking-[0.28em] text-cyan-200">
                Explore The Loop ?
              </Link>
            </div>
          </section>

          <section className="mx-6 mb-6 grid border border-slate-300/20 bg-black/45 md:grid-cols-3 lg:mx-10 xl:grid-cols-6">
            {stats.map(([label, value, sub]) => (
              <div key={label} className="border-b border-r border-white/10 p-5 text-center xl:border-b-0">
                <p className="text-[9px] font-black uppercase tracking-[0.27em] text-slate-500">{label}</p>
                <p className="mt-3 text-2xl font-black tracking-[0.06em] text-white">{value}</p>
                <p className="mt-1 text-[10px] font-black uppercase tracking-[0.2em] text-cyan-200">{sub}</p>
              </div>
            ))}
          </section>

          
          <section className="mx-6 mb-8 lg:mx-10">
            <div className="faith-token-system">
              <div className="text-center">
                <p className="text-[11px] font-black uppercase tracking-[0.45em] text-cyan-100/80">
                  Faith Token System
                </p>
                <p className="mt-2 text-sm uppercase tracking-[0.28em] text-slate-400">
                  Autonomous Credit for the Real-Time Internet
                </p>
              </div>

              <div className="mt-8 grid gap-8 lg:grid-cols-2">
                <div className="faith-token-orb">
                  <div className="faith-token-ring">
                    <img
                      src="/faith/design/token-faith.png"
                      alt="FAITH token"
                      className="faith-token-large"
                    />
                  </div>

                  <div className="mt-6 text-center">
                    <h3 className="text-3xl font-black uppercase tracking-[0.16em] text-white">
                      FAITH
                    </h3>
                    <p className="mt-3 text-sm leading-7 text-slate-400">
                      Protocol collateral identity and future governance coordination layer.
                    </p>
                    <p className="mt-5 text-[10px] font-black uppercase tracking-[0.32em] text-cyan-300">
                      Faith Token
                    </p>
                  </div>
                </div>

                <div className="faith-token-orb">
                  <div className="faith-token-ring">
                    <img
                      src="/faith/design/token-fusd.png"
                      alt="FUSD token"
                      className="faith-token-large tfusd-bright"
                    />
                  </div>

                  <div className="mt-6 text-center">
                    <h3 className="text-3xl font-black uppercase tracking-[0.16em] text-white">
                      FUSD
                    </h3>
                    <p className="mt-3 text-sm leading-7 text-slate-400">
                      Autonomous credit asset minted by FAITH vaults on MegaETH testnet.
                    </p>
                    <p className="mt-5 text-[10px] font-black uppercase tracking-[0.32em] text-cyan-300">
                      FUSD Token
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    
          <section id="developers" className="mx-6 mb-6 lg:mx-10">
            <div className="faith-card p-6">
              <p className="text-sm font-black uppercase tracking-[0.38em] text-cyan-300">
                Developers
              </p>
              <h2 className="mt-4 text-3xl font-black uppercase tracking-[0.16em] text-white">
                Build on the FAITH Economy
              </h2>
              <p className="mt-5 max-w-4xl text-sm leading-7 text-slate-400">
                FAITH is designed as a machine-regulated economy where developers can build
                around vaults, programmable credit, PCS risk monitoring, treasury resilience,
                and real-time MegaETH execution.
              </p>
            </div>
          </section>

          <section id="docs" className="mx-6 mb-6 lg:mx-10">
            <div className="faith-card p-6">
              <p className="text-sm font-black uppercase tracking-[0.38em] text-cyan-300">
                Docs
              </p>
              <h2 className="mt-4 text-3xl font-black uppercase tracking-[0.16em] text-white">
                Protocol Documentation
              </h2>
              <p className="mt-5 max-w-4xl text-sm leading-7 text-slate-400">
                The FAITH documentation explains the protocol architecture, vault system,
                CreditEngine, Treasury, PCS Monitor, SettlementAdapter, MockUSDm, and the
                long-term disciplined economic growth thesis.
              </p>
            </div>
          </section>

          <section id="governance" className="mx-6 mb-6 lg:mx-10">
            <div className="faith-card p-6">
              <p className="text-sm font-black uppercase tracking-[0.38em] text-cyan-300">
                Governance
              </p>
              <h2 className="mt-4 text-3xl font-black uppercase tracking-[0.16em] text-white">
                PCS-Regulated Governance Direction
              </h2>
              <p className="mt-5 max-w-4xl text-sm leading-7 text-slate-400">
                Governance in FAITH is designed to evolve around transparent system health,
                treasury coverage, credit expansion, risk parameters, and PCS recommendations.
                The goal is not blind growth, but disciplined growth.
              </p>
            </div>
          </section>

          <section id="about" className="mx-6 mb-10 lg:mx-10">
            <div className="faith-card p-6">
              <p className="text-sm font-black uppercase tracking-[0.38em] text-cyan-300">
                About
              </p>
              <h2 className="mt-4 text-3xl font-black uppercase tracking-[0.16em] text-white">
                A Machine-Regulated Economy
              </h2>
              <p className="mt-5 max-w-4xl text-sm leading-7 text-slate-400">
                FAITH is not only about borrowing. It is about designing an economy that can
                grow without losing discipline. Humans build. PCS regulates. Treasury protects.
                MegaETH executes. The economy grows.
              </p>
            </div>
          </section>

</main>
  );
}














