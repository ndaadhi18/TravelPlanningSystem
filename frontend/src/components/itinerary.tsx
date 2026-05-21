import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { TravelPlanOutput, TravelPlanInput } from "@workspace/api-client-react/src/generated/api.schemas";
import {
  ArrowLeft, BedDouble, CalendarDays, CheckCircle2, CreditCard,
  ExternalLink, Loader2, MapPin, Plane, RefreshCcw, SendHorizonal, Sparkles,
  ThumbsUp, Utensils, WandSparkles, Globe, Star, Clock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface ItineraryProps {
  plan: TravelPlanOutput;
  onRestart: () => void;
  onImprove?: (data: TravelPlanInput) => void;
  isReimproving?: boolean;
  originalInput?: TravelPlanInput | null;
}

type Mode = "plan" | "improve" | "booked";

// ── Helpers ──────────────────────────────────────────────────────────────────

function pill(text: string, color = "cyan") {
  const map: Record<string, string> = {
    cyan: "border-cyan-300/25 bg-cyan-300/10 text-cyan-200",
    amber: "border-amber-300/25 bg-amber-300/10 text-amber-200",
    emerald: "border-emerald-300/25 bg-emerald-300/10 text-emerald-200",
    rose: "border-rose-300/25 bg-rose-300/10 text-rose-200",
    sky: "border-sky-300/25 bg-sky-300/10 text-sky-200",
  };
  return `inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-semibold tracking-wide ${map[color] ?? map["cyan"]}`;
}

const glass =
  "rounded-2xl border border-white/10 bg-white/[0.06] backdrop-blur-xl shadow-[0_8px_40px_rgba(0,0,0,0.35)]";
const glassStrong =
  "rounded-2xl border border-white/15 bg-white/[0.09] backdrop-blur-2xl shadow-[0_12px_60px_rgba(0,0,0,0.45)]";

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionHeader({ label }: { label: string }) {
  return (
    <p className="mb-4 text-[10px] font-black uppercase tracking-[0.3em] text-white/35">{label}</p>
  );
}

function FlightCard({ item }: { item: { title: string; snippet: string; price_hint: string; source: string } }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`${glass} flex items-start gap-4 p-4`}
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-sky-300/20 bg-sky-300/10">
        <Plane className="h-4 w-4 text-sky-300" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-white">{item.title}</p>
        <p className="mt-0.5 text-sm text-white/55">{item.snippet}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <span className={pill("", "sky")}>{item.source}</span>
          {item.price_hint && item.price_hint !== "0.00 USD" && (
            <span className={pill("", "amber")}>{item.price_hint}</span>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function HotelCard({ item }: { item: { title: string; snippet: string; price_hint: string; source: string; url?: string } }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`${glass} flex items-start gap-4 p-4`}
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-emerald-300/20 bg-emerald-300/10">
        <BedDouble className="h-4 w-4 text-emerald-300" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-white">{item.title}</p>
        <p className="mt-0.5 text-sm text-white/55">{item.snippet}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <span className={pill("", "emerald")}>{item.source}</span>
          {item.price_hint && item.price_hint !== "0.00 USD" && (
            <span className={pill("", "amber")}>{item.price_hint}</span>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function ActivityCard({ item }: { item: { title: string; snippet: string; price_hint: string; category: string; source: string; url?: string } }) {
  const hasLink = item.url && item.url.length > 4;
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`${glass} flex items-start gap-4 p-4`}
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-amber-300/20 bg-amber-300/10">
        <Globe className="h-4 w-4 text-amber-300" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-white">{item.title}</p>
        <p className="mt-0.5 text-sm leading-relaxed text-white/55">{item.snippet}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {item.category && <span className={pill("", "amber")}>{item.category}</span>}
          <span className={pill("", "cyan")}>{item.source}</span>
          {item.price_hint && !item.price_hint.startsWith("0") && item.price_hint !== "Check live site" && (
            <span className={pill("", "rose")}>{item.price_hint}</span>
          )}
          {hasLink && (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1 text-[11px] font-semibold tracking-wide text-cyan-200 transition hover:bg-cyan-300/20"
            >
              <ExternalLink className="h-3 w-3" />
              View source
            </a>
          )}
        </div>
      </div>
    </motion.div>
  );
}

// Time-of-day badge colours
const TIME_COLORS: Record<string, string> = {
  Morning: "border-amber-300/30 bg-amber-300/15 text-amber-200",
  Afternoon: "border-sky-300/30 bg-sky-300/15 text-sky-200",
  Evening: "border-violet-300/30 bg-violet-300/15 text-violet-200",
  Night: "border-slate-300/30 bg-slate-300/15 text-slate-300",
};

const ACTIVITY_ICONS: Record<string, string> = {
  "✈": "✈", "🏨": "🏨",
};

function ActivityItem({ act, i }: { act: string; i: number }) {
  // Detect "Morning: description" pattern
  const colonIdx = act.indexOf(":");
  const timeLabels = ["Morning", "Afternoon", "Evening", "Night"];
  const hasTimeLabel = colonIdx > 0 && timeLabels.includes(act.slice(0, colonIdx).trim());

  // Emoji-prefixed items (flight, hotel)
  const isSpecial = act.startsWith("✈") || act.startsWith("🏨");

  if (hasTimeLabel) {
    const label = act.slice(0, colonIdx).trim();
    const desc = act.slice(colonIdx + 1).trim();
    const badgeClass = TIME_COLORS[label] ?? "border-white/20 bg-white/10 text-white/60";
    return (
      <li className="flex items-start gap-3 rounded-xl border border-white/8 bg-white/[0.04] px-4 py-3">
        <span className={`mt-0.5 shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold tracking-wide ${badgeClass}`}>
          {label}
        </span>
        <p className="text-sm leading-relaxed text-white/80">{desc}</p>
      </li>
    );
  }

  if (isSpecial) {
    return (
      <li className="flex items-start gap-3 rounded-xl border border-cyan-300/15 bg-cyan-300/[0.06] px-4 py-3">
        <span className="mt-0.5 shrink-0 text-base">{act.slice(0, 2)}</span>
        <p className="text-sm leading-relaxed text-cyan-100">{act.slice(2).trim()}</p>
      </li>
    );
  }

  return (
    <li className="flex items-start gap-3 rounded-xl border border-white/8 bg-white/[0.04] px-4 py-3">
      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400" />
      <p className="text-sm leading-relaxed text-white/75">{act}</p>
    </li>
  );
}

function DayBlock({
  day,
  index,
}: {
  day: { day: string; title?: string; activities: string[] };
  index: number;
}) {
  const [open, setOpen] = useState(index === 0);
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.07 }}
      className="overflow-hidden rounded-2xl border border-white/10"
    >
      <button
        onClick={() => setOpen((p) => !p)}
        className="flex w-full items-center gap-4 bg-white/[0.05] p-4 text-left transition hover:bg-white/[0.08]"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-400/40 to-blue-500/40 text-sm font-black text-white">
          {index + 1}
        </span>
        <div className="flex-1">
          <p className="font-semibold text-white">{day.day}</p>
          {day.title && <p className="text-xs text-white/45">{day.title}</p>}
        </div>
        <span className="text-xs text-white/35">{day.activities.length} activities</span>
        <span className={`text-white/30 transition-transform duration-300 ${open ? "rotate-180" : ""}`}>▾</span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.ul
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="space-y-2 overflow-hidden p-4"
          >
            {day.activities.map((act, i) => (
              <ActivityItem key={i} act={act} i={i} />
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function Itinerary({ plan, onRestart, onImprove, isReimproving = false, originalInput }: ItineraryProps) {
  const [mode, setMode] = useState<Mode>("plan");
  const [improveText, setImproveText] = useState("");
  const [activeTab, setActiveTab] = useState<"days" | "flights" | "hotels" | "places">("days");
  const [booked, setBooked] = useState(false);

  const { summary, highlights, plan: dayPlans, budget, live_research } = plan;
  const destination = summary.route.split("→").pop()?.trim() ?? summary.route.split("->").pop()?.trim() ?? "Destination";

  const hasFlights = (live_research?.transport?.length ?? 0) > 0;
  const hasHotels = (live_research?.hotels?.length ?? 0) > 0;
  const hasActivities = (live_research?.activities?.length ?? 0) > 0;

  const handleImprove = () => {
    if (!improveText.trim() || !onImprove || !originalInput) return;
    onImprove({
      ...originalInput,
      preferences: `${originalInput.preferences} | User feedback: ${improveText.trim()}`,
    });
    setImproveText("");
    setMode("plan");
  };

  // ── Booking screen ─────────────────────────────────────────────────────────
  if (mode === "booked" && booked) {
    return (
      <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} className="mx-auto max-w-2xl py-16 text-center text-white">
        <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-emerald-400/20">
          <CheckCircle2 className="h-10 w-10 text-emerald-300" />
        </div>
        <h2 className="text-4xl font-black tracking-tight">Trip confirmed! 🎉</h2>
        <p className="mt-4 text-white/55">Your demo booking is complete. Flights, hotels, and activities are reserved.</p>
        <div className="mt-8 space-y-3 rounded-2xl border border-white/10 bg-white/[0.06] p-6 text-left">
          <div className="flex justify-between text-sm"><span className="text-white/55">Route</span><strong>{summary.route}</strong></div>
          <div className="flex justify-between text-sm"><span className="text-white/55">Duration</span><strong>{summary.days} days</strong></div>
          <div className="flex justify-between text-sm"><span className="text-white/55">Budget tier</span><strong className="capitalize">{summary.budget}</strong></div>
          {budget && (
            <>
              <hr className="border-white/10" />
              <div className="flex justify-between text-sm"><span className="text-white/55">Transport</span><strong>{budget.transport}</strong></div>
              <div className="flex justify-between text-sm"><span className="text-white/55">Stay</span><strong>{budget.stay}</strong></div>
              <div className="flex justify-between text-sm"><span className="text-white/55">Food</span><strong>{budget.food}</strong></div>
            </>
          )}
        </div>
        <Button onClick={onRestart} className="mt-8 rounded-2xl bg-cyan-400 px-8 font-black text-slate-950 hover:bg-white">
          Plan another trip
        </Button>
      </motion.div>
    );
  }

  // ── Improve panel ──────────────────────────────────────────────────────────
  if (mode === "improve") {
    return (
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mx-auto max-w-2xl py-10 text-white">
        <button onClick={() => setMode("plan")} className="mb-6 flex items-center gap-2 text-sm text-white/50 hover:text-white">
          <ArrowLeft className="h-4 w-4" /> Back to plan
        </button>
        <div className={`${glassStrong} p-6`}>
          <div className="mb-1 flex items-center gap-2">
            <WandSparkles className="h-5 w-5 text-cyan-300" />
            <p className="text-xs font-black uppercase tracking-widest text-cyan-300">Planning Agent Feedback Loop</p>
          </div>
          <h2 className="mt-2 text-3xl font-black tracking-tight">What should the agents improve?</h2>
          <p className="mt-2 text-sm text-white/45">Your feedback will re-trigger Transport, Accommodation, Local Expert, and Constraint agents.</p>

          <div className="mt-6 flex flex-wrap gap-2">
            {["Make it cheaper", "Add beach activities", "Upgrade hotel", "More local food", "Shorter travel time"].map((s) => (
              <button
                key={s}
                onClick={() => setImproveText((p) => p ? `${p}, ${s}` : s)}
                className="rounded-full border border-white/15 bg-white/[0.07] px-3 py-1.5 text-xs text-white/65 transition hover:border-cyan-300/40 hover:text-white"
              >
                {s}
              </button>
            ))}
          </div>

          <Textarea
            value={improveText}
            onChange={(e) => setImproveText(e.target.value)}
            placeholder="e.g. Make it budget-friendly, add a cooking class, remove the museum day..."
            className="premium-textarea mt-4 min-h-28"
          />

          <div className="mt-4 flex gap-3">
            <Button
              onClick={handleImprove}
              disabled={!improveText.trim() || isReimproving || !onImprove}
              className="h-11 rounded-xl bg-cyan-400 px-6 font-black text-slate-950 hover:bg-white"
            >
              {isReimproving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <SendHorizonal className="mr-2 h-4 w-4" />}
              {isReimproving ? "Agents working…" : "Re-run planning agents"}
            </Button>
            <Button variant="ghost" onClick={() => setMode("plan")} className="h-11 rounded-xl border border-white/10 text-white/55 hover:text-white">
              Cancel
            </Button>
          </div>

          {!onImprove && (
            <p className="mt-3 text-xs text-amber-300/70">⚠ Re-planning requires the original trip input to be passed. Restart and try again.</p>
          )}
        </div>
      </motion.div>
    );
  }

  // ── Main itinerary view ────────────────────────────────────────────────────
  const tabs = [
    { key: "days" as const, label: "Day-by-Day", icon: CalendarDays },
    ...(hasFlights ? [{ key: "flights" as const, label: "Flights", icon: Plane }] : []),
    ...(hasHotels ? [{ key: "hotels" as const, label: "Hotels", icon: BedDouble }] : []),
    ...(hasActivities ? [{ key: "places" as const, label: "Places", icon: Globe }] : []),
  ];

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mx-auto w-full max-w-5xl pb-20 text-white">

      {/* Top bar */}
      <div className="mb-6 flex items-center justify-between gap-4">
        <button onClick={onRestart} className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.06] px-4 py-2 text-sm text-white/55 backdrop-blur transition hover:text-white">
          <ArrowLeft className="h-4 w-4" /> New trip
        </button>
        <div className="hidden items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-4 py-2 text-sm font-semibold text-emerald-300 md:flex">
          <CheckCircle2 className="h-4 w-4" /> Plan ready
        </div>
      </div>

      {/* Hero card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative mb-6 overflow-hidden rounded-3xl border border-white/15 bg-white/[0.07] p-6 backdrop-blur-2xl shadow-[0_20px_80px_rgba(0,0,0,0.5)] md:p-8"
      >
        {/* gradient bar */}
        <div className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400" />
        {/* ambient glows */}
        <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-cyan-400/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-16 left-1/3 h-48 w-48 rounded-full bg-purple-400/10 blur-3xl" />

        <div className="relative z-10">
          <div className="mb-1 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-cyan-300" />
            <span className="text-[10px] font-black uppercase tracking-[0.3em] text-cyan-300">AI-Generated Itinerary</span>
          </div>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-white md:text-4xl">
            {summary.days} Days in {destination}
          </h1>

          <div className="mt-3 flex flex-wrap gap-2">
            <span className={pill("", "cyan")}><MapPin className="h-3 w-3" />{summary.route}</span>
            <span className={pill("", "sky")}><Clock className="h-3 w-3" />{summary.days} days</span>
            <span className={pill("", "amber")}><Star className="h-3 w-3" />Budget: {summary.budget}</span>
            {summary.style && <span className={pill("", "rose")}>{summary.style}</span>}
          </div>

          {/* Highlights */}
          {highlights.length > 0 && (
            <ul className="mt-5 space-y-2">
              {highlights.slice(0, 4).map((h, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-white/65">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400" />
                  {h}
                </li>
              ))}
            </ul>
          )}

          {/* Budget breakdown */}
          {budget && (
            <div className="mt-5 grid grid-cols-3 gap-3">
              {[
                { label: "Transport", value: budget.transport, icon: Plane },
                { label: "Stay", value: budget.stay, icon: BedDouble },
                { label: "Food", value: budget.food, icon: Utensils },
              ].map(({ label, value, icon: Icon }) => (
                <div key={label} className="rounded-xl border border-white/10 bg-white/[0.05] p-3">
                  <Icon className="mb-1 h-4 w-4 text-white/40" />
                  <p className="text-[10px] text-white/40">{label}</p>
                  <p className="text-sm font-bold text-white">{value}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </motion.div>

      {/* Live research note */}
      {live_research && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="mb-5 flex flex-wrap items-center gap-3 rounded-2xl border border-cyan-300/15 bg-cyan-300/5 px-4 py-3"
        >
          <RefreshCcw className="h-4 w-4 text-cyan-300" />
          <span className="text-sm text-cyan-200/75">
            MCP tools searched at {new Date(live_research.searched_at).toLocaleTimeString()} —&nbsp;
            {live_research.transport.length} flights, {live_research.hotels.length} hotels, {live_research.activities.length} places
          </span>
          {live_research.queries.slice(0, 2).map((q, i) => (
            <span key={i} className={pill("", "cyan")}>{q}</span>
          ))}
        </motion.div>
      )}

      {/* Tabs */}
      <div className="mb-5 flex flex-wrap gap-2">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
              activeTab === key
                ? "bg-cyan-400/20 border border-cyan-400/30 text-cyan-200"
                : "border border-white/10 bg-white/[0.05] text-white/50 hover:text-white"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <AnimatePresence mode="wait">
        {activeTab === "days" && (
          <motion.div key="days" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-3">
            <SectionHeader label="Day-by-Day Plan" />
            {dayPlans.map((day, i) => <DayBlock key={day.day} day={day} index={i} />)}
          </motion.div>
        )}

        {activeTab === "flights" && (
          <motion.div key="flights" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-3">
            <SectionHeader label={`Flight Options — ${live_research?.transport.length ?? 0} results from MCP`} />
            {live_research?.transport.map((f, i) => <FlightCard key={i} item={f} />)}
            {!hasFlights && <p className="text-sm text-white/40">No flight results returned. Check MCP server / Amadeus API.</p>}
          </motion.div>
        )}

        {activeTab === "hotels" && (
          <motion.div key="hotels" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-3">
            <SectionHeader label={`Hotel Options — ${live_research?.hotels.length ?? 0} results from MCP`} />
            {live_research?.hotels.map((h, i) => <HotelCard key={i} item={h} />)}
            {!hasHotels && <p className="text-sm text-white/40">No hotel results returned. Check MCP server / Amadeus API.</p>}
          </motion.div>
        )}

        {activeTab === "places" && (
          <motion.div key="places" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-3">
            <SectionHeader label={`Local Insights — ${live_research?.activities.length ?? 0} results from Tavily`} />
            {live_research?.activities.map((a, i) => <ActivityCard key={i} item={a} />)}
            {!hasActivities && <p className="text-sm text-white/40">No activity results returned. Check Tavily API key.</p>}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Approval / Feedback bar */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className={`mt-8 ${glassStrong} p-5`}
      >
        <p className="text-[10px] font-black uppercase tracking-[0.28em] text-white/35">Human-in-the-loop checkpoint</p>
        <h3 className="mt-2 text-xl font-black">Happy with this plan?</h3>
        <p className="mt-1 text-sm text-white/45">Approve to simulate booking, or give the agents feedback to re-plan.</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Button
            onClick={() => { setBooked(true); setMode("booked"); }}
            className="h-11 rounded-xl bg-gradient-to-r from-emerald-400 to-cyan-400 px-6 font-black text-slate-950 hover:scale-[1.02]"
          >
            <ThumbsUp className="mr-2 h-4 w-4" /> Approve & Book
          </Button>
          <Button
            variant="ghost"
            onClick={() => setMode("improve")}
            className="h-11 rounded-xl border border-white/15 bg-white/[0.06] px-6 font-semibold text-white/65 hover:text-white"
          >
            <WandSparkles className="mr-2 h-4 w-4" />
            Improve Plan
          </Button>
          <Button
            variant="ghost"
            onClick={onRestart}
            className="h-11 rounded-xl border border-white/10 px-6 text-white/35 hover:text-white"
          >
            <ArrowLeft className="mr-2 h-4 w-4" /> Start Over
          </Button>
        </div>
      </motion.div>
    </motion.div>
  );
}
