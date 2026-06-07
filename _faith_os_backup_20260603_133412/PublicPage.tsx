import Link from "next/link";
import type { ReactNode } from "react";

type PublicPageProps = {
  label: string;
  title: string;
  intro: string;
  children: ReactNode;
};

export function PublicPage({ label, title, intro, children }: PublicPageProps) {
  return (
    <main className="relative min-h-screen overflow-hidden bg-black px-6 py-10 text-white lg:px-10">
      <div className="pointer-events-none fixed inset-0">
        <img
          src="/faith/design/background-cosmic.png"
          alt=""
          className="h-full w-full object-cover opacity-80"
        />
      </div>

      <div className="pointer-events-none fixed inset-0 bg-black/55" />
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.16),transparent_34%),linear-gradient(to_bottom,rgba(2,6,23,0.25),rgba(0,0,0,0.94))]" />
      <div className="pointer-events-none fixed inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.035)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.035)_1px,transparent_1px)] bg-[size:96px_96px] opacity-20" />

      <section className="relative z-10 mx-auto max-w-6xl">
        <div className="flex items-center justify-between gap-4">
          <Link
            href="/"
            className="inline-flex rounded-full border border-cyan-300/25 bg-black/35 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-300 backdrop-blur-md transition hover:border-cyan-300/70 hover:bg-cyan-300/10 hover:text-white"
          >
            Back to FAITH
          </Link>

          <Link
            href="/dashboard"
            className="hidden rounded-full border border-white/10 bg-black/35 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-300 backdrop-blur-md transition hover:border-cyan-300/50 hover:bg-cyan-300/10 hover:text-white sm:inline-flex"
          >
            Dashboard
          </Link>
        </div>

        <div className="mt-16 max-w-4xl">
          <p className="text-xs font-semibold uppercase tracking-[0.32em] text-cyan-300">
            {label}
          </p>

          <h1 className="mt-5 text-3xl font-semibold tracking-tight text-white md:text-5xl">
            {title}
          </h1>

          <p className="mt-6 max-w-3xl text-base leading-8 text-slate-300">
            {intro}
          </p>
        </div>

        <div className="mt-12">
          {children}
        </div>
      </section>
    </main>
  );
}

export function InfoCard({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/45 p-6 shadow-2xl shadow-cyan-950/20 backdrop-blur-xl">
      <h2 className="text-xl font-semibold tracking-tight text-white">
        {title}
      </h2>
      <div className="mt-4 text-sm leading-7 text-slate-300">
        {children}
      </div>
    </div>
  );
}

