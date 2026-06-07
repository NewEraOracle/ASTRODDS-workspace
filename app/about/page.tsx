import { InfoCard, PublicPage } from "../components/PublicPage";

const contacts = [
  ["X / Twitter", "Project updates and public build logs", "#"],
  ["Discord", "Community and builder discussion", "#"],
  ["Telegram", "Direct community channel", "#"],
  ["Email", "Partnerships, investors, and serious inquiries", "mailto:jordansavoie8@gmail.com"],
];

export default function AboutPage() {
  return (
    <PublicPage
      label="About FAITH"
      title="A Machine-Regulated Economy"
      intro="FAITH is not only about borrowing. It is about designing an economy that can grow without losing discipline. Human productivity creates value. PCS regulates risk. Treasury protects the system. MegaETH executes in real time."
    >
      <div className="space-y-5">
        <InfoCard title="Vision">
          <p>
            FAITH aims to become a capital operating system for disciplined economic growth,
            where credit expansion is balanced by treasury strength and PCS risk control.
          </p>
        </InfoCard>

        <InfoCard title="Contact and Community">
          <p>
            Follow FAITH updates, join the community, or contact the team for serious
            partnerships, investor discussions, and ecosystem collaboration.
          </p>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {contacts.map(([title, body, href]) => (
              <a
                key={title}
                href={href}
                className="rounded-2xl border border-cyan-300/20 bg-black/40 p-5 transition hover:border-cyan-300/60 hover:bg-cyan-300/5"
              >
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
                  {title}
                </p>
                <p className="mt-3 text-sm leading-6 text-slate-400">
                  {body}
                </p>
              </a>
            ))}
          </div>

          <p className="mt-6 text-xs uppercase tracking-[0.22em] text-slate-500">
            Social links can be updated when the official FAITH channels are finalized.
          </p>
        </InfoCard>
      </div>
    </PublicPage>
  );
}

