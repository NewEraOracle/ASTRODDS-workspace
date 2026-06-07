const certificateClasses = [
  {
    name: "Class A",
    liquidity: "70%",
    productive: "30%",
    profile: "Highest productive exposure, highest potential surplus participation, more risk, longer redemption terms.",
    ltv: "Lower LTV",
  },
  {
    name: "Class B",
    liquidity: "80%",
    productive: "20%",
    profile: "Growth-focused, balanced risk and upside.",
    ltv: "Medium LTV",
  },
  {
    name: "Class C",
    liquidity: "90%",
    productive: "10%",
    profile: "Conservative growth with stronger liquidity protection.",
    ltv: "Higher LTV",
  },
  {
    name: "Class D",
    liquidity: "95%",
    productive: "5%",
    profile: "Most conservative class, strongest liquidity profile, safest collateral quality.",
    ltv: "Highest / safest LTV",
  },
];

const waterfall = [
  "Protect and rebuild principal reserve",
  "Strengthen liquid reserve coverage",
  "Fund emergency, insurance, and liquidation buffers",
  "Retain growth capital",
  "Allocate realized surplus to Treasury Certificate classes",
  "Fund ecosystem growth, UtopiaByFaith, infrastructure, and protocol development",
];

const pcsControls = [
  "Class-level LTV adjustments",
  "Redemption queues and liquidity checks",
  "Pause new borrowing during stress",
  "Pause surplus allocation if safety thresholds are not met",
  "Increase reserve targets",
  "Reduce productive exposure",
  "Emergency risk mode",
];

export function FaithTreasuryCertificateSection() {
  return (
    <section id="treasury-certificates" className="relative mx-auto w-full max-w-7xl px-6 py-20">
      <div className="w-full rounded-[2rem] border border-amber-400/20 bg-slate-950/85 p-8 shadow-2xl shadow-amber-950/20 backdrop-blur md:p-12">
        <div className="max-w-5xl">
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.35em] text-amber-300">
            Updated Financial Structure
          </p>

          <h2 className="max-w-4xl text-3xl font-semibold tracking-tight text-white md:text-4xl xl:text-5xl">
            FAITH now separates utility from reserve-backed capital.
          </h2>

          <p className="mt-6 max-w-4xl text-base leading-8 text-slate-300 md:text-lg">
            FAITH Protocol uses a dual-asset model: the FAITH token coordinates access, utility,
            UtopiaByFaith participation, and protocol privileges, while FAITH Treasury Certificates
            represent restricted treasury-backed capital accounts with controlled inflow, controlled
            redemption, class-based risk, and PCS-regulated credit eligibility.
          </p>

          <div className="mt-6 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-5 text-lg font-medium text-amber-100">
            Principal protects the system. Profits grow the economy. PCS regulates the risk.
          </div>
        </div>

        <div className="mt-10 grid gap-5 lg:grid-cols-2">
          <article className="rounded-2xl border border-white/10 bg-white/[0.04] p-6">
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-500">
              Asset 01
            </p>
            <h3 className="mt-3 text-2xl font-semibold text-white">FAITH Token</h3>
            <p className="mt-4 text-sm leading-7 text-slate-400">
              The FAITH token remains the ecosystem utility and coordination asset. It can support
              access, membership, UtopiaByFaith gameplay utility, forge and minting utility,
              protocol privileges, governance later, vault access, and lower-LTV collateral if PCS
              approves.
            </p>
            <p className="mt-4 text-sm font-medium text-amber-200">
              FAITH opens access to the economy.
            </p>
          </article>

          <article className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 p-6">
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-emerald-200/80">
              Asset 02
            </p>
            <h3 className="mt-3 text-2xl font-semibold text-white">
              FAITH Treasury NFT / Certificate
            </h3>
            <p className="mt-4 text-sm leading-7 text-emerald-50/80">
              The Treasury Certificate is the reserve-backed capital account layer. It can represent
              contributed capital, class-based treasury participation, controlled redemption,
              higher-LTV collateral eligibility, and account-value changes based only on realized
              treasury surplus.
            </p>
            <p className="mt-4 text-sm font-medium text-emerald-100">
              Treasury Certificates hold the reserve-backed capital value.
            </p>
          </article>
        </div>

        <div className="mt-10 overflow-x-auto rounded-2xl border border-white/10">
          <div className="grid min-w-[980px] grid-cols-5 bg-white/[0.06] text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
            <div className="p-4">Class</div>
            <div className="p-4">Liquid</div>
            <div className="p-4">Productive</div>
            <div className="p-4">LTV</div>
            <div className="p-4">Profile</div>
          </div>

          {certificateClasses.map((item) => (
            <div
              key={item.name}
              className="grid min-w-[980px] grid-cols-5 border-t border-white/10 text-sm text-slate-300"
            >
              <div className="p-4 font-semibold text-white">{item.name}</div>
              <div className="p-4 text-emerald-200">{item.liquidity}</div>
              <div className="p-4 text-amber-200">{item.productive}</div>
              <div className="p-4 text-sky-200">{item.ltv}</div>
              <div className="p-4 leading-6 text-slate-400">{item.profile}</div>
            </div>
          ))}
        </div>

        <div className="mt-10 grid gap-5 lg:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6">
            <h3 className="text-lg font-semibold text-white">Quarterly Review</h3>
            <p className="mt-4 text-sm leading-7 text-slate-400">
              Every 3 months, PCS, governance, and treasury management can review treasury
              performance, realized surplus, liquidity health, redemption pressure, class-level risk,
              and LTV eligibility. Reviews should be transparent, rules-based, and protective of
              existing certificate holders.
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6">
            <h3 className="text-lg font-semibold text-white">Value Accrual Logic</h3>
            <p className="mt-4 text-sm leading-7 text-slate-400">
              Treasury Certificate value can increase only when realized treasury surplus is
              allocated to a class. This is NAV/account-value based, not speculative price pumping.
            </p>
            <p className="mt-4 rounded-xl border border-amber-300/20 bg-amber-300/10 p-3 text-xs leading-6 text-amber-100">
              Account Value = Initial Contribution + Allocated Realized Surplus - Realized Losses -
              Fees / Risk Reserves / Haircuts
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6">
            <h3 className="text-lg font-semibold text-white">LTV Principle</h3>
            <p className="mt-4 text-sm leading-7 text-slate-400">
              High LTV belongs mainly to Treasury Certificates, not the FAITH token. Liquidity
              protects LTV. Productive risk earns upside. PCS decides how much credit is safe.
            </p>
          </div>
        </div>

        <div className="mt-10 grid gap-5 lg:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-slate-900/80 p-6">
            <h3 className="text-lg font-semibold text-white">Profit Waterfall</h3>
            <div className="mt-4 space-y-3">
              {waterfall.map((step, index) => (
                <div key={step} className="flex gap-3 rounded-xl border border-white/10 bg-black/20 p-3">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-300/20 text-xs font-semibold text-amber-200">
                    {index + 1}
                  </span>
                  <p className="text-sm leading-6 text-slate-300">{step}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-slate-900/80 p-6">
            <h3 className="text-lg font-semibold text-white">PCS Controls</h3>
            <div className="mt-4 space-y-3">
              {pcsControls.map((control) => (
                <div key={control} className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <p className="text-sm leading-6 text-slate-300">{control}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-10 rounded-2xl border border-red-400/20 bg-red-400/10 p-5">
          <h3 className="text-sm font-semibold uppercase tracking-[0.25em] text-red-100">
            Legal / Compliance Note
          </h3>
          <p className="mt-3 text-sm leading-7 text-red-50/80">
            Treasury Certificates may be legally sensitive because they can resemble capital
            contribution, treasury participation, redemption rights, account value, surplus
            participation, or investment contract characteristics. This structure should be reviewed
            by legal counsel before launch. FAITH should not market Treasury Certificates as
            guaranteed yield, guaranteed profit, guaranteed principal protection, or guaranteed
            redemption.
          </p>
        </div>
      </div>
    </section>
  );
}


