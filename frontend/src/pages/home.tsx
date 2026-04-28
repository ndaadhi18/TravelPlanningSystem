import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useCreateTravelPlan } from "@workspace/api-client-react";
import { TripForm } from "@/components/trip-form";
import { LoadingSteps } from "@/components/loading-steps";
import { Itinerary } from "@/components/itinerary";
import { Bot, BrainCircuit, Compass, GitBranch, Globe2, Route, Sparkles } from "lucide-react";
import type { TravelPlanOutput } from "@workspace/api-client-react/src/generated/api.schemas";

const pageVariants = {
  hidden: { opacity: 0, y: 18, filter: "blur(10px)" },
  visible: { opacity: 1, y: 0, filter: "blur(0px)" },
  exit: { opacity: 0, y: -18, filter: "blur(10px)" },
};

const trustSignals = [
  { icon: BrainCircuit, label: "Multi-agent reasoning" },
  { icon: GitBranch, label: "Editable planning loop" },
  { icon: Sparkles, label: "Progressive itinerary" },
];

export default function Home() {
  const [plan, setPlan] = useState<TravelPlanOutput | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const createPlan = useCreateTravelPlan();

  const handleRestart = () => {
    setPlan(null);
    setErrorMessage(null);
    createPlan.reset();
  };

  return (
    <div className="relative min-h-[100dvh] overflow-hidden bg-[#06080f] text-white">
      <div className="pointer-events-none absolute inset-0 premium-grid opacity-40" />
      <div className="pointer-events-none absolute -top-56 left-1/2 h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-cyan-400/20 blur-3xl" />
      <div className="pointer-events-none absolute bottom-[-260px] right-[-160px] h-[520px] w-[520px] rounded-full bg-amber-300/10 blur-3xl" />
      <div className="pointer-events-none absolute left-[-180px] top-1/3 h-[420px] w-[420px] rounded-full bg-blue-500/10 blur-3xl" />

      <header className="relative z-10 mx-auto flex w-full max-w-7xl items-center justify-between px-5 py-6 md:px-8">
        <motion.div
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="flex items-center gap-3"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-white/15 bg-white/10 shadow-2xl shadow-cyan-500/10 backdrop-blur-xl">
            <Compass className="h-5 w-5 text-cyan-200" />
          </div>
          <div>
            <p className="text-sm uppercase tracking-[0.32em] text-white/45">AI Travel OS</p>
            <h1 className="font-sans text-lg font-semibold tracking-tight text-white">Aura Planner</h1>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="hidden rounded-full border border-white/10 bg-white/[0.06] px-4 py-2 text-sm text-white/70 backdrop-blur-xl md:flex md:items-center md:gap-2"
        >
          <Bot className="h-4 w-4 text-cyan-100" />
          Interactive multi-agent planning
        </motion.div>
      </header>

      <main className="relative z-10 mx-auto w-full max-w-7xl px-5 pb-16 md:px-8">
        <AnimatePresence mode="wait">
          {!createPlan.isPending && !plan && (
            <motion.section
              key="landing"
              variants={pageVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
              className="grid min-h-[calc(100dvh-112px)] items-center gap-10 py-10 lg:grid-cols-[0.95fr_560px]"
            >
              <div className="max-w-3xl">
                <motion.div
                  initial={{ opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.6, delay: 0.08 }}
                  className="mb-6 inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-sm text-cyan-100 shadow-2xl shadow-cyan-500/10 backdrop-blur-xl"
                >
                  <span className="h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_18px_rgba(103,232,249,0.9)]" />
                  Conversational AI travel workflow
                </motion.div>

                <motion.h2
                  initial={{ opacity: 0, y: 24 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.75, delay: 0.16, ease: [0.22, 1, 0.36, 1] }}
                  className="max-w-4xl font-sans text-6xl font-semibold leading-[0.92] tracking-[-0.065em] text-white md:text-7xl xl:text-8xl"
                >
                  Plan with an
                  <span className="block bg-gradient-to-r from-cyan-200 via-white to-amber-100 bg-clip-text text-transparent">
                    AI agent team.
                  </span>
                </motion.h2>

                <motion.p
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.65, delay: 0.28 }}
                  className="mt-7 max-w-2xl text-lg leading-8 text-slate-300 md:text-xl"
                >
                  Chat through your trip details, watch each planning agent work, then edit, regenerate, approve, and move into a booking-ready flow.
                </motion.p>

                <motion.div
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.65, delay: 0.38 }}
                  className="mt-10 grid max-w-2xl gap-3 sm:grid-cols-3"
                >
                  {trustSignals.map((item) => (
                    <div key={item.label} className="group rounded-3xl border border-white/10 bg-white/[0.055] p-4 text-white/75 shadow-2xl shadow-black/20 backdrop-blur-xl transition duration-300 hover:-translate-y-1 hover:border-cyan-200/30 hover:bg-white/[0.085]">
                      <item.icon className="mb-5 h-5 w-5 text-cyan-200 transition duration-300 group-hover:scale-110" />
                      <p className="text-sm font-medium leading-5">{item.label}</p>
                    </div>
                  ))}
                </motion.div>

                <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.65, delay: 0.5 }} className="mt-8 flex flex-wrap gap-2 text-xs text-white/45">
                  {[
                    "Planner",
                    "Transport",
                    "Accommodation",
                    "Local Expert",
                    "Constraint",
                    "MCP-ready",
                  ].map((agent) => (
                    <span key={agent} className="rounded-full border border-white/10 bg-white/[0.045] px-3 py-1.5 backdrop-blur-xl">
                      {agent}
                    </span>
                  ))}
                </motion.div>

                <motion.button
                  type="button"
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.65, delay: 0.58 }}
                  onClick={() => {
                    setErrorMessage(null);
                    createPlan.mutate(
                      {
                        data: {
                          origin: "Bangalore",
                          destination: "Goa",
                          days: "3",
                          budget: "moderate",
                          style: "cultural & activity",
                          preferences: "beaches, churches, food, local markets, hotel and activity bookings",
                        },
                      },
                      {
                        onSuccess: (res) => setPlan(res),
                        onError: () => setErrorMessage("The Goa demo could not start. Please try again."),
                      },
                    );
                  }}
                  className="mt-7 rounded-2xl border border-[#ff7a59]/40 bg-[#ff7a59]/12 px-5 py-3 text-sm font-black text-[#ffd0c7] shadow-[0_16px_60px_rgba(255,107,95,0.12)] transition hover:-translate-y-0.5 hover:bg-[#ff7a59]/20 hover:text-white"
                >
                  Launch Bangalore → Goa demo
                </motion.button>
              </div>

              <motion.div
                initial={{ opacity: 0, y: 28, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.7, delay: 0.26, ease: [0.22, 1, 0.36, 1] }}
                className="relative"
              >
                <div className="absolute -inset-1 rounded-[2.25rem] bg-gradient-to-br from-cyan-300/30 via-white/10 to-amber-300/20 blur-2xl" />
                <TripForm
                  isSubmitting={createPlan.isPending}
                  errorMessage={errorMessage}
                  onSubmit={(data) => {
                    setErrorMessage(null);
                    createPlan.mutate(
                      { data },
                      {
                        onSuccess: (res) => setPlan(res),
                        onError: () => {
                          setErrorMessage("The planning agents could not start. Please review the trip details and try again.");
                        },
                      },
                    );
                  }}
                />
              </motion.div>
            </motion.section>
          )}

          {createPlan.isPending && (
            <motion.section
              key="loading"
              variants={pageVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
              className="flex min-h-[calc(100dvh-112px)] items-center justify-center py-16"
            >
              <LoadingSteps />
            </motion.section>
          )}

          {plan && !createPlan.isPending && (
            <motion.section
              key="result"
              variants={pageVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
              className="py-8"
            >
              <Itinerary plan={plan} onRestart={handleRestart} />
            </motion.section>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
