"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

const agents = [
  {
    id: "builder",
    label: "Builder",
    title: "Builder Agent",
    module: "Productive Value",
    objective: "Bring real activity into the FAITH economy.",
    line: "I create useful activity. FAITH does not begin with speculation — it begins with productive value.",
    x: 15,
    y: 28,
  },
  {
    id: "vault",
    label: "Vault",
    title: "Vault Agent",
    module: "Collateral Layer",
    objective: "Deposit collateral into disciplined vault infrastructure.",
    line: "I receive collateral and create a monitored credit position inside the protocol.",
    x: 32,
    y: 17,
  },
  {
    id: "credit",
    label: "Credit",
    title: "CreditEngine Agent",
    module: "Programmable Credit",
    objective: "Convert collateral into safe programmable credit capacity.",
    line: "I calculate credit capacity while keeping private risk formulas protected from the public layer.",
    x: 68,
    y: 17,
  },
  {
    id: "FUSD",
    label: "FUSD",
    title: "FUSD Agent",
    module: "Stable Settlement",
    objective: "Move stable credit through protocol activity.",
    line: "I circulate as stable credit for payments, commerce, settlement, and future digital utility.",
    x: 85,
    y: 28,
  },
  {
    id: "pcs",
    label: "PCS",
    title: "PCS Agent",
    module: "Risk Intelligence",
    objective: "Monitor the system before stress becomes systemic.",
    line: "I watch vault health, oracle shocks, utilization, liquidation pressure, and treasury coverage in real time.",
    x: 19,
    y: 72,
  },
  {
    id: "treasury",
    label: "Treasury",
    title: "Treasury Agent",
    module: "Reserve Protection",
    objective: "Protect the economy with resilience and reserves.",
    line: "I preserve reserves and strengthen the system so credit expansion does not become fragile.",
    x: 39,
    y: 84,
  },
  {
    id: "megaeth",
    label: "MegaETH",
    title: "MegaETH Agent",
    module: "Real-Time Execution",
    objective: "Execute the economy at internet speed.",
    line: "I provide the real-time execution layer that lets FAITH update quickly and respond to live protocol conditions.",
    x: 61,
    y: 84,
  },
  {
    id: "utopia",
    label: "Utopia",
    title: "Utopia Agent",
    module: "Future Utility",
    objective: "Connect gameplay, artifacts, culture, and digital commerce.",
    line: "I represent future utility demand: marketplace flows, game activity, artifacts, culture, and digital commerce.",
    x: 81,
    y: 72,
  },
];

export default function SimulationPage() {
  const [active, setActive] = useState(0);
  const [autoPlay, setAutoPlay] = useState(false);

  const current = agents[active];

  const progress = useMemo(() => {
    return Math.round(((active + 1) / agents.length) * 100);
  }, [active]);

  const linePoints = useMemo(() => {
    return agents.map((agent) => `${agent.x},${agent.y}`).join(" ");
  }, []);

  const activePath = useMemo(() => {
    return agents
      .slice(0, active + 1)
      .map((agent) => `${agent.x},${agent.y}`)
      .join(" ");
  }, [active]);

  useEffect(() => {
    if (!autoPlay) return;

    const timer = setInterval(() => {
      setActive((value) => (value + 1) % agents.length);
    }, 3600);

    return () => clearInterval(timer);
  }, [autoPlay]);

  return (
    <main className="relative min-h-screen overflow-hidden bg-black text-white">
      <img
        src="/faith/design/background-cosmic.png"
        alt=""
        className="pointer-events-none fixed inset-0 h-full w-full object-cover opacity-85"
      />

      <div className="pointer-events-none fixed inset-0 bg-black/55" />
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_center,rgba(34,211,238,0.18),transparent_34%),linear-gradient(to_bottom,rgba(2,6,23,0.15),rgba(0,0,0,0.97))]" />
      <div className="pointer-events-none fixed inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.035)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.035)_1px,transparent_1px)] bg-[size:90px_90px] opacity-20" />

      <section className="relative z-10 mx-auto flex min-h-screen max-w-[1600px] flex-col px-5 py-7 lg:px-9">
        <div className="flex items-center justify-between gap-4">
          <Link
            href="/"
            className="rounded-full border border-cyan-300/25 bg-black/45 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-300 backdrop-blur-md transition hover:border-cyan-300/70 hover:bg-cyan-300/10 hover:text-white"
          >
            Back to FAITH
          </Link>

          <div className="hidden items-center gap-3 lg:flex">
            <span className="rounded-full border border-cyan-300/20 bg-cyan-300/5 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-200">
              Public Simulation
            </span>

            <Link
              href="/dashboard"
              className="rounded-full border border-white/10 bg-black/45 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-300 backdrop-blur-md transition hover:border-cyan-300/50 hover:bg-cyan-300/10 hover:text-white"
            >
              Enter Dashboard
            </Link>
          </div>
        </div>

        <div className="grid flex-1 gap-6 py-8 lg:grid-cols-[0.82fr_1.18fr]">
          <aside className="flex flex-col justify-between rounded-[2rem] border border-white/10 bg-black/35 p-6 shadow-2xl shadow-cyan-950/20 backdrop-blur-xl">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.34em] text-cyan-300">
                FAITH Command Simulation
              </p>

              <h1 className="mt-5 max-w-3xl text-4xl font-semibold tracking-tight text-white md:text-6xl">
                AI agents operating inside a live protocol economy.
              </h1>

              <p className="mt-6 max-w-2xl text-base leading-8 text-slate-300">
                A cinematic investor walkthrough of FAITH Protocol. Watch the economy move from
                productive value to vaults, credit, PCS regulation, treasury resilience, MegaETH
                execution, and future utility.
              </p>
            </div>

            <div className="mt-8 space-y-4">
              <div className="rounded-3xl border border-cyan-300/15 bg-slate-950/70 p-5">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-cyan-300">
                      Mission Progress
                    </p>
                    <p className="mt-2 text-sm text-slate-400">
                      Step {active + 1} / {agents.length} · {progress}% synchronized
                    </p>
                  </div>

                  <button
                    onClick={() => setAutoPlay((value) => !value)}
                    className={[
                      "rounded-full border px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.2em] transition",
                      autoPlay
                        ? "border-cyan-300/60 bg-cyan-300/15 text-cyan-100"
                        : "border-white/10 bg-white/[0.04] text-slate-300 hover:border-cyan-300/50 hover:text-white",
                    ].join(" ")}
                  >
                    {autoPlay ? "Auto On" : "Auto Play"}
                  </button>
                </div>

                <div className="mt-5 h-2 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-cyan-300 shadow-[0_0_22px_rgba(34,211,238,0.9)] transition-all duration-500"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>

              <div className="rounded-3xl border border-white/10 bg-black/55 p-5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                  Current Objective
                </p>

                <p className="mt-3 text-xl font-semibold leading-8 text-white">
                  {current.objective}
                </p>
              </div>

              <div className="rounded-3xl border border-white/10 bg-black/55 p-5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-cyan-300">
                  Public Safety Boundary
                </p>

                <p className="mt-3 text-sm leading-7 text-slate-400">
                  This simulation explains the public flow only. Exact PCS scoring, treasury
                  thresholds, liquidation parameters, and private economic strategy remain protected.
                </p>
              </div>
            </div>
          </aside>

          <section className="relative min-h-[760px] overflow-hidden rounded-[2.2rem] border border-white/10 bg-black/45 shadow-2xl shadow-cyan-950/20 backdrop-blur-xl">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(34,211,238,0.18),transparent_43%)]" />
            <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(115deg,transparent,rgba(34,211,238,0.08),transparent_48%)]" />

            <div className="pointer-events-none absolute left-1/2 top-1/2 h-[560px] w-[560px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-300/15 shadow-[0_0_80px_rgba(34,211,238,0.12)]" />
            <div className="pointer-events-none absolute left-1/2 top-1/2 h-[410px] w-[410px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-300/10" />
            <div className="pointer-events-none absolute left-1/2 top-1/2 h-[250px] w-[250px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-300/10" />

            <svg
              className="pointer-events-none absolute inset-0 h-full w-full opacity-90"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
            >
              <polyline
                points={linePoints}
                fill="none"
                stroke="rgba(148,163,184,0.18)"
                strokeWidth="0.18"
              />
              <polyline
                points={activePath}
                fill="none"
                stroke="rgba(34,211,238,0.75)"
                strokeWidth="0.28"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>

            <div
              className="absolute z-30 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-100 bg-cyan-300 shadow-[0_0_30px_rgba(34,211,238,1)] transition-all duration-700"
              style={{
                left: `${current.x}%`,
                top: `${current.y}%`,
              }}
            >
              <div className="absolute inset-[-14px] rounded-full border border-cyan-300/40 animate-ping" />
            </div>

            <div className="absolute left-1/2 top-1/2 z-10 grid h-44 w-44 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-cyan-300/30 bg-cyan-300/10 shadow-[0_0_90px_rgba(34,211,238,0.26)]">
              <div className="grid h-28 w-28 place-items-center rounded-full border border-cyan-300/20 bg-black/70">
                <p className="text-center text-[11px] font-semibold uppercase tracking-[0.24em] text-white">
                  FAITH
                  <br />
                  Core
                </p>
              </div>
            </div>

            {agents.map((agent, index) => {
              const isActive = index === active;
              const isComplete = index < active;

              return (
                <button
                  key={agent.id}
                  onClick={() => {
                    setActive(index);
                    setAutoPlay(false);
                  }}
                  className={[
                    "absolute z-20 w-[118px] -translate-x-1/2 -translate-y-1/2 rounded-2xl border p-3 text-center transition duration-300",
                    isActive
                      ? "border-cyan-300/80 bg-cyan-300/15 shadow-[0_0_45px_rgba(34,211,238,0.32)]"
                      : isComplete
                        ? "border-cyan-300/30 bg-cyan-300/8"
                        : "border-white/10 bg-black/60 hover:border-cyan-300/40 hover:bg-cyan-300/8",
                  ].join(" ")}
                  style={{
                    left: `${agent.x}%`,
                    top: `${agent.y}%`,
                  }}
                >
                  <div className="mx-auto grid h-12 w-12 place-items-center rounded-full border border-cyan-300/25 bg-black/65 shadow-[0_0_24px_rgba(34,211,238,0.16)]">
                    <span className="text-[11px] font-semibold text-cyan-200">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                  </div>

                  <p className="mt-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-white">
                    {agent.label}
                  </p>
                </button>
              );
            })}

            <div className="absolute bottom-5 left-5 right-5 z-40 rounded-3xl border border-cyan-300/20 bg-slate-950/90 p-5 shadow-2xl shadow-cyan-950/35 backdrop-blur-xl">
              <div className="grid gap-5 lg:grid-cols-[1fr_270px] lg:items-end">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-cyan-300">
                    {current.module}
                  </p>

                  <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white">
                    {current.title}
                  </h2>

                  <p className="mt-4 text-base leading-8 text-slate-300">
                    “{current.line}”
                  </p>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => {
                      setAutoPlay(false);
                      setActive((value) => Math.max(0, value - 1));
                    }}
                    className="flex-1 rounded-full border border-white/10 bg-white/[0.04] px-4 py-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-300 transition hover:border-cyan-300/40 hover:text-white"
                  >
                    Previous
                  </button>

                  <button
                    onClick={() => {
                      setAutoPlay(false);
                      setActive((value) => Math.min(agents.length - 1, value + 1));
                    }}
                    className="flex-1 rounded-full border border-cyan-300/30 bg-cyan-300/10 px-4 py-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-200 transition hover:border-cyan-300/70 hover:text-white"
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}

