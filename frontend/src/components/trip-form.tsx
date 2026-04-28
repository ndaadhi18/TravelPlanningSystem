import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ArrowRight, Bot, Check, Loader2, MessageSquareText, SendHorizonal, Sparkles, UserRound } from "lucide-react";
import type { TravelPlanInput } from "@workspace/api-client-react/src/generated/api.schemas";

type IntakeKey = "origin" | "destination" | "days" | "budget" | "style" | "preferences";

type IntakeState = Record<IntakeKey, string>;

interface TripFormProps {
  onSubmit: (data: TravelPlanInput) => void;
  isSubmitting?: boolean;
  errorMessage?: string | null;
}

const steps: Array<{
  key: IntakeKey;
  eyebrow: string;
  question: string;
  placeholder: string;
  helper: string;
  choices?: string[];
  optional?: boolean;
  multiline?: boolean;
}> = [
  {
    key: "origin",
    eyebrow: "Route context",
    question: "Where are you starting from?",
    placeholder: "New York",
    helper: "I’ll use this to plan practical arrival and departure flow.",
  },
  {
    key: "destination",
    eyebrow: "Target city",
    question: "Where do you want to go?",
    placeholder: "Tokyo",
    helper: "The local expert agent will build around this destination.",
  },
  {
    key: "days",
    eyebrow: "Trip length",
    question: "How many days should I plan?",
    placeholder: "3",
    helper: "This controls how detailed the day-by-day plan becomes.",
    choices: ["2", "3", "4", "5", "7", "10"],
  },
  {
    key: "budget",
    eyebrow: "Budget model",
    question: "What budget level should the agents optimize for?",
    placeholder: "moderate",
    helper: "Budget affects transport, stay, food, and pacing assumptions.",
    choices: ["budget", "moderate", "luxury"],
  },
  {
    key: "style",
    eyebrow: "Planning style",
    question: "What kind of trip should this feel like?",
    placeholder: "balanced",
    helper: "Choose the travel personality the planner should follow.",
    choices: ["relaxed", "balanced", "action-packed", "culture", "foodie"],
  },
  {
    key: "preferences",
    eyebrow: "Personalization",
    question: "Any preferences, constraints, or things to avoid?",
    placeholder: "Food markets, museums, no early mornings, beach time...",
    helper: "Optional, but this helps the constraint agent tailor the result.",
    optional: true,
    multiline: true,
  },
];

const defaults: IntakeState = {
  origin: "",
  destination: "",
  days: "3",
  budget: "moderate",
  style: "balanced",
  preferences: "",
};

function formatAnswer(key: IntakeKey, value: string) {
  if (!value) return "Skipped";
  if (key === "days") return `${value} ${value === "1" ? "day" : "days"}`;
  return value;
}

export function TripForm({ onSubmit, isSubmitting = false, errorMessage = null }: TripFormProps) {
  const [answers, setAnswers] = useState<IntakeState>(defaults);
  const [stepIndex, setStepIndex] = useState(0);
  const [draft, setDraft] = useState(defaults[steps[0].key]);
  const activeStep = steps[stepIndex];
  const isLastStep = stepIndex === steps.length - 1;

  const completedMessages = useMemo(
    () =>
      steps.slice(0, stepIndex).map((step) => ({
        key: step.key,
        question: step.question,
        answer: formatAnswer(step.key, answers[step.key]),
      })),
    [answers, stepIndex],
  );

  const progress = ((stepIndex + 1) / steps.length) * 100;
  const canContinue = activeStep.optional || draft.trim().length > 0;

  const handleChoice = (value: string) => {
    setDraft(value);
  };

  const handleNext = () => {
    if (!canContinue || isSubmitting) return;
    const nextAnswers = { ...answers, [activeStep.key]: draft.trim() };
    setAnswers(nextAnswers);

    if (isLastStep) {
      onSubmit({
        origin: nextAnswers.origin,
        destination: nextAnswers.destination,
        days: nextAnswers.days || "3",
        budget: nextAnswers.budget,
        style: nextAnswers.style,
        preferences: nextAnswers.preferences,
      } as TravelPlanInput);
      return;
    }

    const nextIndex = stepIndex + 1;
    setStepIndex(nextIndex);
    setDraft(nextAnswers[steps[nextIndex].key]);
  };

  const handleBackTo = (index: number) => {
    if (isSubmitting) return;
    setStepIndex(index);
    setDraft(answers[steps[index].key]);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 18, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.58, ease: [0.22, 1, 0.36, 1] }}
      className="relative overflow-hidden rounded-[2rem] border border-white/14 bg-white/[0.08] shadow-[0_24px_90px_rgba(0,0,0,0.45)] backdrop-blur-2xl"
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-200/70 to-transparent" />
      <div className="border-b border-white/10 p-5 md:p-6">
        <div className="mb-5 flex items-center justify-between gap-5">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-cyan-200/20 bg-cyan-200/10 text-cyan-100">
              <MessageSquareText className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-100/60">Conversational intake</p>
              <h3 className="font-sans text-2xl font-semibold tracking-[-0.04em] text-white">Talk to the planner</h3>
            </div>
          </div>
          <div className="rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs text-white/55">{stepIndex + 1}/{steps.length}</div>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-cyan-200 via-white to-amber-100"
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
          />
        </div>
      </div>

      <div className="max-h-[510px] space-y-4 overflow-y-auto p-5 md:p-6">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="flex items-start gap-3">
          <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-cyan-200/20 bg-cyan-200/10 text-cyan-100">
            <Bot className="h-4 w-4" />
          </div>
          <div className="rounded-[1.4rem] rounded-tl-md border border-white/10 bg-white/[0.08] px-4 py-3 text-sm leading-6 text-white/78">
            I’ll ask for the essentials, then activate Planner, Transport, Accommodation, Local Expert, and Constraint agents.
          </div>
        </motion.div>

        {completedMessages.map((message, index) => (
          <div key={message.key} className="space-y-3">
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.03 }} className="flex items-start gap-3">
              <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-cyan-200/20 bg-cyan-200/10 text-cyan-100">
                <Bot className="h-4 w-4" />
              </div>
              <button onClick={() => handleBackTo(index)} className="rounded-[1.4rem] rounded-tl-md border border-white/10 bg-white/[0.055] px-4 py-3 text-left text-sm leading-6 text-white/64 transition hover:border-cyan-200/25 hover:text-white/90">
                {message.question}
              </button>
            </motion.div>
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.03 + 0.04 }} className="flex items-start justify-end gap-3">
              <div className="max-w-[80%] rounded-[1.4rem] rounded-tr-md border border-cyan-200/20 bg-cyan-200/12 px-4 py-3 text-sm font-medium leading-6 text-cyan-50">
                {message.answer}
              </div>
              <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/10 text-white/70">
                <UserRound className="h-4 w-4" />
              </div>
            </motion.div>
          </div>
        ))}

        <AnimatePresence mode="wait">
          <motion.div
            key={activeStep.key}
            initial={{ opacity: 0, y: 18, filter: "blur(8px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -12, filter: "blur(8px)" }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            className="space-y-4 pt-2"
          >
            <div className="flex items-start gap-3">
              <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-cyan-200/20 bg-cyan-200/10 text-cyan-100">
                <Bot className="h-4 w-4" />
              </div>
              <div className="flex-1 rounded-[1.4rem] rounded-tl-md border border-white/10 bg-white/[0.08] p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.25em] text-cyan-100/50">{activeStep.eyebrow}</p>
                <p className="text-lg font-semibold leading-7 text-white">{activeStep.question}</p>
                <p className="mt-2 text-sm leading-6 text-white/50">{activeStep.helper}</p>
              </div>
            </div>

            <div className="ml-0 rounded-[1.5rem] border border-white/10 bg-black/18 p-3 md:ml-12">
              {activeStep.choices ? (
                <div className="grid gap-2 sm:grid-cols-3">
                  {activeStep.choices.map((choice) => (
                    <button
                      key={choice}
                      type="button"
                      onClick={() => handleChoice(choice)}
                      className={`rounded-2xl border px-4 py-3 text-left text-sm font-semibold capitalize transition duration-300 hover:-translate-y-0.5 ${
                        draft === choice
                          ? "border-cyan-200/45 bg-cyan-200/18 text-cyan-50 shadow-[0_12px_42px_rgba(103,232,249,0.13)]"
                          : "border-white/10 bg-white/[0.04] text-white/62 hover:border-white/20 hover:bg-white/[0.07] hover:text-white"
                      }`}
                    >
                      {draft === choice ? <Check className="mb-3 h-4 w-4 text-cyan-100" /> : <Sparkles className="mb-3 h-4 w-4 text-white/30" />}
                      {formatAnswer(activeStep.key, choice)}
                    </button>
                  ))}
                </div>
              ) : activeStep.multiline ? (
                <Textarea
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder={activeStep.placeholder}
                  className="premium-textarea min-h-28"
                />
              ) : (
                <Input
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder={activeStep.placeholder}
                  className="premium-input"
                  onKeyDown={(event) => {
                    if (event.key === "Enter") handleNext();
                  }}
                />
              )}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="border-t border-white/10 p-5 md:p-6">
        {errorMessage ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-4 rounded-2xl border border-red-300/20 bg-red-400/10 px-4 py-3 text-sm leading-6 text-red-100"
          >
            {errorMessage}
          </motion.div>
        ) : null}
        <Button
          type="button"
          disabled={!canContinue || isSubmitting}
          onClick={handleNext}
          className="group h-14 w-full rounded-2xl bg-cyan-200 text-base font-semibold text-slate-950 shadow-[0_16px_60px_rgba(103,232,249,0.24)] transition duration-300 hover:-translate-y-0.5 hover:bg-white hover:shadow-[0_20px_80px_rgba(255,255,255,0.18)]"
        >
          {isSubmitting ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : isLastStep ? <SendHorizonal className="mr-2 h-5 w-5 transition group-hover:translate-x-1" /> : <ArrowRight className="mr-2 h-5 w-5 transition group-hover:translate-x-1" />}
          {isLastStep ? "Activate agents" : activeStep.optional && !draft.trim() ? "Skip and continue" : "Continue"}
        </Button>
      </div>
    </motion.div>
  );
}
