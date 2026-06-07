import { FaithTreasuryCertificateSection } from '../components/FaithTreasuryCertificateSection';
import { InfoCard, PublicPage } from "../components/PublicPage";

const docLinks = [
  ["Core Positioning", "#core-positioning"],
  ["Economic Flywheel", "#economic-flywheel"],
  ["Protocol Architecture", "#protocol-architecture"],
  ["PCS Risk Layer", "#pcs-risk-layer"],
  ["Treasury Layer", "#treasury-layer"],
  ["Public Safety Boundary", "#public-safety-boundary"],
];

export default function DocsPage() {
  return (
    <PublicPage
      label="Public Docs v0.1"
      title="FAITH Public Whitepaper"
      intro="This public documentation explains FAITH Protocol's vision, architecture, and economic thesis. Proprietary PCS scoring models, treasury parameters, advanced risk thresholds, and private economic strategy are intentionally excluded from this public version."
    >
      <div className="grid gap-4 md:grid-cols-2">
        {docLinks.map(([label, href]) => (
          <a
            key={label}
            href={href}
            className="rounded-2xl border border-white/10 bg-slate-950/70 p-5 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300 transition hover:border-cyan-300/60 hover:bg-cyan-300/5 hover:text-white"
          >
            {label}
          </a>
        ))}
      </div>

      <div className="mt-10 space-y-5">
        <section id="core-positioning" className="scroll-mt-24">
          <InfoCard title="Core Positioning">
            <p>
              FAITH is building a growing and flourishing machine-regulated economy,
              not through speculation, but through productive value, programmable credit,
              treasury resilience, PCS risk regulation, and real utility.
            </p>
          </InfoCard>
        </section>

        <section id="economic-flywheel" className="scroll-mt-24">
          <InfoCard title="Economic Flywheel">
            <p>
              Vaults create credit. Credit creates activity. Activity strengthens the
              treasury. Treasury protects the system. PCS regulates risk. Stronger
              infrastructure attracts more usage. The economy grows.
            </p>
          </InfoCard>
        </section>

        <section id="protocol-architecture" className="scroll-mt-24">
          <InfoCard title="Protocol Architecture">
            <p>
              FAITH is organized around vaults, CreditEngine, PCS Monitor, Treasury,
              SettlementAdapter, and FUSD / MockUSDm. This public version explains the
              system at a high level without exposing the private engine.
            </p>
          </InfoCard>
        </section>

        <section id="pcs-risk-layer" className="scroll-mt-24">
          <InfoCard title="PCS Risk Layer">
            <p>
              PCS monitors vault health, oracle shocks, liquidation pressure, borrow
              utilization, treasury coverage, and system stress. PCS recommends
              protocol-level responses so growth can remain disciplined.
            </p>
          </InfoCard>
        </section>

        <section id="treasury-layer" className="scroll-mt-24">
          <InfoCard title="Treasury Layer">
            <p>
              The treasury is the reserve engine of the FAITH economy. Fees and reserves
              strengthen system resilience, support development, and help protect the
              protocol during stress.
            </p>
          </InfoCard>
        </section>

        <section id="public-safety-boundary" className="scroll-mt-24">
          <InfoCard title="Public Safety Boundary">
            <p>
              Public docs explain the system, not the private engine. Exact PCS formulas,
              treasury defense thresholds, advanced liquidation parameters, token
              allocation ranges, and private strategy are intentionally kept outside this
              public version.
            </p>
          </InfoCard>
        
      <FaithTreasuryCertificateSection />
</section>

        <InfoCard title="Core Line">
          <p className="text-base font-semibold text-white md:text-lg">
            Humans build. PCS regulates. Treasury protects. MegaETH executes. The economy grows.
          </p>
        </InfoCard>
      </div>
    </PublicPage>
  );
}




