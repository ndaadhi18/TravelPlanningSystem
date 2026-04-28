import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { BrainCircuit, Building2, Check, DatabaseZap, Map, Plane, Radar, Route, ShieldCheck, Sparkles, WalletCards } from "lucide-react";

const STEPS = [
  { text: "Planner initializing", detail: "Synthesizing your chat intake into a planning brief", icon: BrainCircuit, agent: "Planner" },
  { text: "Transport agent working", detail: "Scoring arrival flow, routing friction, and transfer complexity", icon: Route, agent: "Transport" },
  { text: "Accommodation agent searching", detail: "Choosing stay areas that fit pace, budget, and walkability", icon: Building2, agent: "Accommodation" },
  { text: "Local expert generating", detail: "Building neighborhood-aware highlights and daily anchors", icon: Map, agent: "Local Expert" },
  { text: "Constraint optimizing", detail: "Balancing time, cost, preferences, and practical sequencing", icon: ShieldCheck, agent: "Constraint" },
  { text: "MCP context check", detail: "Preparing booking-ready structure and final summary handoff", icon: DatabaseZap, agent: "MCP" },
];

export function LoadingSteps() {
  const [currentStep, setCurrentStep] = useState(0);
  const [pulse, setPulse] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentStep((prev) => (prev < STEPS.length - 1 ? prev + 1 : prev));
    }, 760);

    const pulseInterval = setInterval(() => setPulse((prev) => prev + 1), 420);

    return () => {
      clearInterval(interval);
      clearInterval(pulseInterval);
    };
  }, []);

  const ActiveIcon = STEPS[currentStep].icon;
  const visibleSteps = useMemo(() => STEPS.slice(0, currentStep + 1), [currentStep]);

  return (
    <div className="relative w-full max-w-5xl px-3">
      <div className="absolute -inset-10 rounded-[3rem] bg-cyan-300/10 blur-3xl" />
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
        className="relative grid overflow-hidden rounded-[2rem] border border-white/12 bg-white/[0.075] shadow-[0_30px_120px_rgba(0,0,0,0.55)] backdrop-blur-2xl lg:grid-cols-[0.8fr_1.2fr]"
      >
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-200/80 to-transparent" />
        <div className="relative overflow-hidden border-b border-white/10 p-6 md:p-10 lg:border-b-0 lg:border-r">
          <div className="absolute -left-28 -top-28 h-64 w-64 rounded-full bg-cyan-300/18 blur-3xl" />
          <div className="relative z-10">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.32em] text-cyan-100/60">Agent pipeline</p>
            <h2 className="font-sans text-4xl font-semibold leading-none tracking-[-0.055em] text-white md:text-6xl">Thinking in layers</h2>
            <p className="mt-5 text-base leading-7 text-white/55">The itinerary is not rendered all at once. Each agent contributes a staged decision layer before the plan appears.</p>

            <div className="relative mx-auto mt-10 flex h-64 w-64 items-center justify-center">
              {[0, 1, 2].map((ring) => (
                <motion.div
                  key={`${ring}-${pulse}`}
                  className="absolute rounded-full border border-cyan-200/20"
                  initial={{ width: 74 + ring * 44, height: 74 + ring * 44, opacity: 0.2 }}
                  animate={{ width: 132 + ring * 56, height: 132 + ring * 56, opacity: [0.2, 0.45, 0.12], rotate: 360 }}
                  transition={{ duration: 4.8 + ring, repeat: Infinity, ease: "linear" }}
                />
              ))}
              <div className="relative flex h-28 w-28 items-center justify-center rounded-[2rem] border border-cyan-200/30 bg-cyan-200/12 shadow-[0_0_80px_rgba(103,232,249,0.18)]">
                <motion.div animate={{ rotate: 360 }} transition={{ duration: 7, repeat: Infinity, ease: "linear" }} className="absolute inset-2 rounded-[1.6rem] border border-dashed border-white/20" />
                <ActiveIcon className="h-10 w-10 text-cyan-100" />
              </div>
            </div>
          </div>
        </div>

        <div className="p-6 md:p-10">
          <div className="mb-7 flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.26em] text-white/40">Live activity</p>
              <AnimatePresence mode="wait">
                <motion.h3
                  key={STEPS[currentStep].agent}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  transition={{ duration: 0.28 }}
                  className="mt-2 font-sans text-2xl font-semibold tracking-[-0.04em] text-white"
                >
                  {STEPS[currentStep].agent} agent active
                </motion.h3>
              </AnimatePresence>
            </div>
            <div className="flex items-center gap-2 rounded-full border border-cyan-200/20 bg-cyan-200/10 px-3 py-2 text-sm text-cyan-100">
              <Radar className="h-4 w-4 animate-pulse" />
              Streaming
            </div>
          </div>

          <div className="space-y-3">
            <AnimatePresence initial={false}>
              {visibleSteps.map((step, index) => {
                const Icon = step.icon;
                const isActive = index === currentStep;
                const isDone = index < currentStep;

                return (
                  <motion.div
                    key={step.text}
                    initial={{ opacity: 0, x: -22, height: 0 }}
                    animate={{ opacity: 1, x: 0, height: "auto" }}
                    exit={{ opacity: 0, x: 18, height: 0 }}
                    transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
                    className={`relative overflow-hidden rounded-2xl border p-4 transition duration-500 ${
                      isActive
                        ? "border-cyan-200/35 bg-cyan-200/12 shadow-[0_18px_70px_rgba(103,232,249,0.11)]"
                        : isDone
                          ? "border-emerald-200/20 bg-white/[0.07]"
                          : "border-white/8 bg-white/[0.035] opacity-55"
                    }`}
                  >
                    {isActive ? <motion.div layoutId="active-step-glow" className="absolute inset-y-0 left-0 w-1 bg-cyan-200 shadow-[0_0_30px_rgba(103,232,249,0.8)]" /> : null}
                    <div className="flex items-center gap-4">
                      <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border ${isDone ? "border-emerald-200/20 bg-emerald-200/12 text-emerald-100" : "border-white/10 bg-white/10 text-cyan-100"}`}>
                        {isDone ? <Check className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="font-sans text-base font-semibold text-white">{step.text}</p>
                        <p className="mt-1 text-sm leading-6 text-cyan-50/60">{step.detail}</p>
                      </div>
                      {isActive ? <Sparkles className="h-5 w-5 text-cyan-100" /> : <Plane className="h-5 w-5 text-white/18" />}
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>

          <div className="mt-8 h-2 overflow-hidden rounded-full bg-white/10">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-cyan-200 via-white to-amber-100"
              initial={{ width: "8%" }}
              animate={{ width: `${((currentStep + 1) / STEPS.length) * 100}%` }}
              transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            />
          </div>
        </div>
      </motion.div>
    </div>
  );
}
