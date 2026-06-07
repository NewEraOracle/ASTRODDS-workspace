import Link from "next/link";

const contacts = [
  ["X / Twitter", "Project updates and public build logs", "#"],
  ["Discord", "Community and builder discussion", "#"],
  ["Telegram", "Direct community channel", "#"],
  ["Email", "Partnerships, investors, and serious inquiries", "mailto:jordansavoie8@gmail.com"],
];

export default function AboutPage() {
  return (
    <main className="min-h-screen bg-black px-6 py-16 text-white lg:px-10">
      <Link href="/" className="text-xs font-black uppercase tracking-[0.28em] text-cyan-300 hover:text-white">
        Back to FAITH
      </Link>

      <section className="mx-auto mt-12 max-w-5xl">
        <p className="text-sm font-black uppercase tracking-[0.38em] text-cyan-300">
          About FAITH
        </p>

        <h1 className="mt-5 text-5xl font-black uppercase tracking-[0.12em] text-white">
          A Machine-Regulated Economy
        </h1>

        <p className="mt-6 text-lg leading-8 text-slate-400">
          FAITH is not only about borrowing. It is about designing an economy that can
          grow without losing discipline. Human productivity creates value. PCS regulates
          risk. Treasury protects the system. MegaETH executes in real time.
        </p>

        <div className="mt-10 faith-card p-6">
          <h2 className="text-2xl font-black uppercase tracking-[0.16em] text-white">
            Vision
          </h2>
          <p className="mt-5 text-sm leading-7 text-slate-400">
            FAITH aims to become a capital operating system for disciplined economic growth,
            where credit expansion is balanced by treasury strength and PCS risk control.
          </p>
        </div>

        <div className="mt-10 faith-card p-6">
          <h2 className="text-2xl font-black uppercase tracking-[0.16em] text-white">
            Contact & Community
          </h2>

          <p className="mt-5 text-sm leading-7 text-slate-400">
            Follow FAITH updates, join the community, or contact the team for serious
            partnerships, investor discussions, and ecosystem collaboration.
          </p>

          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {contacts.map(([title, body, href]) => (
              <a
                key={title}
                href={href}
                className="rounded-2xl border border-cyan-300/20 bg-black/40 p-5 transition hover:border-cyan-300/60 hover:bg-cyan-300/5"
              >
                <p className="text-sm font-black uppercase tracking-[0.22em] text-cyan-300">
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
        </div>
      </section>
    </main>
  );
}
