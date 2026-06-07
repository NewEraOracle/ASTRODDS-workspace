import { InfoCard, PublicPage } from "../components/PublicPage";

export default function DevelopersPage() {
  return (
    <PublicPage
      label="Developers"
      title="Build on the FAITH Economy"
      intro="FAITH is designed for builders who want to create around programmable credit, real-time vault health, PCS risk monitoring, treasury-aware systems, and MegaETH execution."
    >
      <div className="grid gap-5 md:grid-cols-2">
        <InfoCard title="Builder Layer">
          <p>
            Future builders can plug into dashboards, simulations, vault flows,
            protocol activity layers, and PCS-informed risk infrastructure.
          </p>
        </InfoCard>

        <InfoCard title="Public Integration Direction">
          <p>
            Public documentation explains the architecture without exposing proprietary
            PCS formulas, treasury thresholds, or private strategy.
          </p>
        </InfoCard>
      </div>
    </PublicPage>
  );
}

