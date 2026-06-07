import { InfoCard, PublicPage } from "../components/PublicPage";

const modules = [
  ["Vaults", "Collateral enters the system and supports programmable credit creation."],
  ["CreditEngine", "Calculates borrowing power and manages credit issuance logic."],
  ["PCS Monitor", "Monitors vault health, oracle shocks, liquidation pressure, utilization, and system stress."],
  ["Treasury", "Protects the system through reserves, coverage, and long-term protocol resilience."],
  ["SettlementAdapter", "Prepares system updates and settlement flows for real-time execution."],
  ["MockUSDm / FUSD", "Represents the stable credit asset used inside the FAITH economy."],
];

export default function ProtocolPage() {
  return (
    <PublicPage
      label="Protocol"
      title="FAITH Protocol Architecture"
      intro="FAITH is a machine-regulated capital system designed around vaults, programmable credit, PCS risk monitoring, treasury resilience, and real-time MegaETH execution."
    >
      <div className="grid gap-5 md:grid-cols-2">
        {modules.map(([title, body]) => (
          <InfoCard key={title} title={title}>
            <p>{body}</p>
          </InfoCard>
        ))}
      </div>
    </PublicPage>
  );
}

