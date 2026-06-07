import { InfoCard, PublicPage } from "../components/PublicPage";

export default function FUSDPage() {
  return (
    <PublicPage
      label="FUSD"
      title="Stable Credit for the FAITH Economy"
      intro="FUSD represents the stable credit layer of FAITH. It shows how collateral-backed programmable credit can circulate through a real-time economy without relying on speculation as the primary growth engine."
    >
      <div className="grid gap-5 md:grid-cols-2">
        <InfoCard title="Role in the Economy">
          <p>
            Vaults create credit. Credit circulates. Activity strengthens the treasury.
            PCS monitors risk. The system grows through utility, not artificial emissions.
          </p>
        </InfoCard>

        <InfoCard title="Separation of Roles">
          <p>
            USDm or FUSD powers stable transactions and settlement. FAITH powers
            coordination, access, progression, risk participation, and protocol utility.
          </p>
        </InfoCard>
      </div>
    </PublicPage>
  );
}

