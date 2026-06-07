import { InfoCard, PublicPage } from "../components/PublicPage";

export default function GovernancePage() {
  return (
    <PublicPage
      label="Governance"
      title="Risk-Aware Governance Direction"
      intro="FAITH governance is designed to evolve from core-team execution into risk-aware protocol coordination, where PCS monitors system conditions, recommends parameter responses, and governance approves disciplined changes."
    >
      <div className="grid gap-5 md:grid-cols-2">
        <InfoCard title="Governance Principle">
          <p>
            PCS does not replace governance. PCS upgrades governance with risk intelligence.
            The long-term goal is not blind voting, but informed protocol coordination.
          </p>
        </InfoCard>

        <InfoCard title="Public Boundary">
          <p>
            Public governance can explain principles and direction without exposing exact
            private risk formulas, liquidation thresholds, or treasury defense mechanics.
          </p>
        </InfoCard>
      </div>
    </PublicPage>
  );
}

