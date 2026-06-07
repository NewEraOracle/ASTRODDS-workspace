import Link from "next/link";

export default function ProtocolPage() {
  return (
    <main className="min-h-screen bg-black px-6 py-16 text-white lg:px-10">
      <Link href="/" className="text-xs font-black uppercase tracking-[0.28em] text-cyan-300">
        Back to FAITH
      </Link>

      <section className="mx-auto mt-12 max-w-5xl">
        <p className="text-sm font-black uppercase tracking-[0.38em] text-cyan-300">
          Protocol
        </p>

        <h1 className="mt-5 text-5xl font-black uppercase tracking-[0.12em] text-white">
          FAITH Protocol Architecture
        </h1>

        <p className="mt-6 text-lg leading-8 text-slate-400">
          FAITH Protocol is a machine-regulated capital system designed around vaults,
          programmable credit, PCS risk monitoring, treasury resilience, and real-time
          MegaETH execution.
        </p>

        <div className="mt-10 grid gap-5 md:grid-cols-2">
          {[
            ["Vaults", "Collateral enters the system and supports programmable credit creation."],
            ["CreditEngine", "Calculates borrowing power and manages credit issuance logic."],
            ["PCS Monitor", "Monitors vault health, oracle shocks, liquidation pressure, utilization, and system stress."],
            ["Treasury", "Protects the system through reserves, coverage, and long-term protocol resilience."],
            ["SettlementAdapter", "Prepares system updates and settlement flows for real-time execution."],
            ["MockUSDm / tfUSD", "Represents the stable credit asset used inside the FAITH economy."],
          ].map(([title, body]) => (
            <div key={title} className="faith-card p-6">
              <h2 className="text-xl font-black uppercase tracking-[0.16em] text-white">{title}</h2>
              <p className="mt-4 text-sm leading-7 text-slate-400">{body}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

