import { FaithEconomicOSSection } from "../components/FaithEconomicOSSection";
import { FaithTreasuryCertificateSection } from "../components/FaithTreasuryCertificateSection";
import { InfoCard, PublicPage } from "../components/PublicPage";

export default function ProtocolPage() {
  return (
    <PublicPage
      label="PROTOCOL ARCHITECTURE"
      title="FAITH is a treasury-protected, PCS-regulated economic operating system"
      intro="PROTOCOL ARCHITECTURE represents the stable credit layer of FAITH. It shows how collateral-backed programmable credit can circulate through a real-time economy without relying on speculation as the primary growth engine."
    >
      <div className="grid gap-5 md:grid-cols-2">
        <InfoCard title="Treasury-Protected Economy">
          <p>
            Vaults create credit. Credit circulates. Activity strengthens the treasury.
            PCS monitors risk. The system grows through utility, not artificial emissions.
          </p>
        </InfoCard>

        <InfoCard title="Dual-Asset Structure">
          <p>
            USDm or PROTOCOL ARCHITECTURE powers stable transactions and settlement. FAITH powers
            coordination, access, progression, risk participation, and protocol utility.
          </p>
        </InfoCard>
      </div>
    </PublicPage>
  );
}


