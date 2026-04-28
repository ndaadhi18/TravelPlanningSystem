import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { TravelPlanOutput } from "@workspace/api-client-react/src/generated/api.schemas";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  ArrowLeft,
  Backpack,
  Banknote,
  BedDouble,
  Building2,
  CalendarDays,
  Car,
  CheckCircle2,
  ChevronDown,
  CircleDollarSign,
  Clock3,
  CreditCard,
  Download,
  Edit3,
  Hotel,
  IndianRupee,
  Landmark,
  Loader2,
  Luggage,
  Map,
  MapPin,
  MessageCircle,
  Plane,
  RefreshCcw,
  Route,
  SendHorizonal,
  Shield,
  ShoppingBag,
  Sparkles,
  Star,
  ThumbsUp,
  TicketCheck,
  Train,
  Utensils,
  WalletCards,
  WandSparkles,
  Waves,
  Wifi,
} from "lucide-react";

interface ItineraryProps {
  plan: TravelPlanOutput;
  onRestart: () => void;
}

type Mode = "plan" | "improve" | "checkout" | "booked";
type Tab = "itinerary" | "map" | "hotels" | "prep" | "analytics";

type Activity = {
  time: string;
  title: string;
  description: string;
  category: "Food" | "Adventure" | "Sightseeing" | "Relaxation" | "Shopping" | "Transit" | "Hotel";
  cost: number;
  place: string;
  duration: string;
};

const tabItems: Array<{ key: Tab; label: string; icon: typeof CalendarDays }> = [
  { key: "itinerary", label: "Itinerary", icon: CalendarDays },
  { key: "map", label: "Map", icon: Map },
  { key: "hotels", label: "Hotels", icon: Hotel },
  { key: "prep", label: "Prep", icon: Backpack },
  { key: "analytics", label: "Analytics", icon: CircleDollarSign },
];

const categoryColors: Record<Activity["category"], string> = {
  Food: "from-orange-400 to-amber-500",
  Adventure: "from-yellow-500 to-orange-500",
  Sightseeing: "from-rose-400 to-red-500",
  Relaxation: "from-zinc-400 to-stone-500",
  Shopping: "from-cyan-300 to-teal-400",
  Transit: "from-sky-400 to-cyan-500",
  Hotel: "from-emerald-300 to-teal-500",
};

const categoryIcons: Record<Activity["category"], typeof Utensils> = {
  Food: Utensils,
  Adventure: Waves,
  Sightseeing: Landmark,
  Relaxation: Sparkles,
  Shopping: ShoppingBag,
  Transit: Car,
  Hotel: BedDouble,
};

const scoreRows = [
  { label: "Safety", value: 7, icon: Shield, color: "bg-orange-400" },
  { label: "Affordability", value: 9, icon: WalletCards, color: "bg-teal-300" },
  { label: "Connectivity", value: 8, icon: Wifi, color: "bg-cyan-300" },
  { label: "Tourist-Friendliness", value: 9, icon: Star, color: "bg-teal-300" },
];

const tips = [
  {
    title: "Dress Code",
    body: "Light cottons, breathable shoes, sunglasses, sunscreen, and one smart casual outfit for nicer dinners.",
  },
  {
    title: "Getting Around",
    body: "Use airport transfers for arrival, scooters/taxis for beach hops, and keep buffer time for traffic.",
  },
  {
    title: "Food & Dining",
    body: "Try local seafood, thalis, bakeries, beach shacks, and one nicer coastal dinner reservation.",
  },
  {
    title: "Local Etiquette",
    body: "Respect beach rules, negotiate transport politely, carry cash for markets, and avoid isolated late-night routes.",
  },
];

function clonePlan(plan: TravelPlanOutput): TravelPlanOutput {
  return JSON.parse(JSON.stringify(plan));
}

function parseNumber(value: string, fallback: number) {
  const parsed = Number(value.replace(/[^0-9.]/g, ""));
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function tripTitle(summary: TravelPlanOutput["summary"]) {
  const destination = summary.route.split("→").pop()?.trim() || "Destination";
  const days = summary.days || "3";
  const style = summary.style ? `${summary.style.charAt(0).toUpperCase()}${summary.style.slice(1)}` : "Curated";
  return `${days} Days ${style} Trip to ${destination}`;
}

function destinationName(summary: TravelPlanOutput["summary"]) {
  return summary.route.split("→").pop()?.trim() || "Goa";
}

function makeActivities(dayIndex: number, dayActivities: string[], destination: string): Activity[] {
  const templates: Activity[] = [
    {
      time: "08:00 AM",
      title: "Breakfast at a local eatery",
      description: "Start your day with a regional breakfast and a slow briefing from the local expert agent.",
      category: "Food",
      cost: 300,
      place: `${destination} center`,
      duration: "45m",
    },
    {
      time: "08:45 AM",
      title: `Travel toward ${dayIndex === 1 ? "Old Town" : dayIndex === 2 ? "Beach Belt" : "Local Quarter"}`,
      description: "Private transfer staged in the demo booking layer with buffer time included.",
      category: "Transit",
      cost: 80 + dayIndex * 20,
      place: "Hotel pickup",
      duration: "30m",
    },
    {
      time: "09:30 AM",
      title: dayActivities[0] || "Explore the main cultural anchor",
      description: "The planner locks this as the day’s first major activity while energy is highest.",
      category: dayIndex === 2 ? "Relaxation" : "Sightseeing",
      cost: dayIndex === 1 ? 0 : 120,
      place: destination,
      duration: "1h 15m",
    },
    {
      time: "11:30 AM",
      title: dayActivities[1] || "Add a local discovery block",
      description: "Balanced discovery window with nearby attractions grouped to reduce travel friction.",
      category: dayIndex === 2 ? "Adventure" : "Sightseeing",
      cost: dayIndex === 3 ? 250 : 0,
      place: "Nearby area",
      duration: "1h",
    },
    {
      time: "12:45 PM",
      title: "Lunch at a recommended local restaurant",
      description: "Booked as a demo reservation with budget-aware menu suggestions.",
      category: "Food",
      cost: 450 + dayIndex * 100,
      place: destination,
      duration: "1h 15m",
    },
    {
      time: "02:30 PM",
      title: dayActivities[2] || "Flexible neighborhood exploration",
      description: "A flexible agent block for weather, energy, and last-minute local recommendations.",
      category: dayIndex === 2 ? "Shopping" : "Relaxation",
      cost: dayIndex === 2 ? 250 : 0,
      place: "Flexible zone",
      duration: "1h 30m",
    },
    {
      time: "05:00 PM",
      title: "Sunset reset and hotel return",
      description: "Light transfer and recovery window before dinner or evening plans.",
      category: "Transit",
      cost: 120,
      place: "Hotel route",
      duration: "40m",
    },
    {
      time: "08:00 PM",
      title: "Dinner at a curated local restaurant",
      description: "Demo reservation and purchase flow prepared for the final checkout step.",
      category: "Food",
      cost: 500 + dayIndex * 120,
      place: destination,
      duration: "1h 30m",
    },
  ];

  return templates;
}

function formatMoney(value: number) {
  return `₹${value.toLocaleString("en-IN")}`;
}

function SectionActions({ onEdit, onRegenerate, label }: { onEdit: () => void; onRegenerate: () => void; label: string }) {
  return (
    <div className="flex flex-wrap gap-2">
      <Button type="button" variant="ghost" onClick={onEdit} className="h-8 rounded-full border border-white/10 bg-white/[0.055] px-3 text-xs text-white/66 hover:bg-white/10 hover:text-white">
        <Edit3 className="mr-1.5 h-3.5 w-3.5" />
        Edit {label}
      </Button>
      <Button type="button" variant="ghost" onClick={onRegenerate} className="h-8 rounded-full border border-[#ff6b5f]/25 bg-[#ff6b5f]/12 px-3 text-xs text-[#ffb0a8] hover:bg-[#ff6b5f]/20 hover:text-white">
        <RefreshCcw className="mr-1.5 h-3.5 w-3.5" />
        AI Edit
      </Button>
    </div>
  );
}

export function Itinerary({ plan, onRestart }: ItineraryProps) {
  const [workingPlan, setWorkingPlan] = useState<TravelPlanOutput>(() => clonePlan(plan));
  const [activeTab, setActiveTab] = useState<Tab>("itinerary");
  const [expandedDay, setExpandedDay] = useState(0);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [mode, setMode] = useState<Mode>("plan");
  const [improveText, setImproveText] = useState("");
  const [isLooping, setIsLooping] = useState(false);
  const [purchaseStep, setPurchaseStep] = useState(0);

  useEffect(() => {
    setWorkingPlan(clonePlan(plan));
    setActiveTab("itinerary");
    setExpandedDay(0);
    setEditingKey(null);
    setMode("plan");
    setPurchaseStep(0);
  }, [plan]);

  useEffect(() => {
    if (mode !== "checkout") return;
    const timers = [500, 1200, 1900, 2600].map((delay, index) => window.setTimeout(() => setPurchaseStep(index + 1), delay));
    return () => timers.forEach(window.clearTimeout);
  }, [mode]);

  const { summary, highlights, plan: dayPlans, budget } = workingPlan;
  const destination = destinationName(summary);
  const dayCount = parseNumber(summary.days, dayPlans.length || 3);
  const activityDays = useMemo(
    () => dayPlans.map((day, index) => makeActivities(index + 1, day.activities, destination)),
    [dayPlans, destination],
  );
  const activityTotal = activityDays.flat().reduce((sum, activity) => sum + activity.cost, 0);
  const hotelTotal = dayCount * 1200;
  const transportTotal = dayCount * 650;
  const totalCost = activityTotal + hotelTotal + transportTotal;
  const perPerson = Math.round(totalCost / 2);
  const timelineItems = activityDays.flatMap((activities, dayIndex) =>
    activities.map((activity, activityIndex) => ({ ...activity, dayIndex, activityIndex })),
  );

  const startEdit = (key: string, value: string) => {
    setEditingKey(key);
    setDraft(value);
  };

  const saveEdit = () => {
    if (!editingKey) return;
    setWorkingPlan((current) => {
      const next = clonePlan(current);
      if (editingKey === "summary") next.summary.route = draft.trim() || next.summary.route;
      if (editingKey === "highlights") {
        const values = draft.split("\n").map((item) => item.trim()).filter(Boolean);
        if (values.length) next.highlights = values;
      }
      if (editingKey.startsWith("day-")) {
        const dayIndex = Number(editingKey.replace("day-", ""));
        const values = draft.split("\n").map((item) => item.trim()).filter(Boolean);
        if (next.plan[dayIndex] && values.length) next.plan[dayIndex].activities = values;
      }
      return next;
    });
    setEditingKey(null);
    setDraft("");
  };

  const regenerateSection = (key: string) => {
    setWorkingPlan((current) => {
      const next = clonePlan(current);
      if (key === "summary") next.summary.route = `${next.summary.route} · Dawn mode`;
      if (key === "highlights") {
        next.highlights = [
          "AI booking layer added: airport transfer, hotel, food blocks, and demo activity purchases are ready.",
          ...next.highlights.slice(0, 2),
        ];
      }
      if (key.startsWith("day-")) {
        const dayIndex = Number(key.replace("day-", ""));
        if (next.plan[dayIndex]) {
          next.plan[dayIndex].activities = [
            ...next.plan[dayIndex].activities,
            "AI upgrade: add one purchasable local experience with instant checkout in the demo booking flow.",
          ];
        }
      }
      return next;
    });
  };

  const runImproveLoop = () => {
    if (!improveText.trim()) return;
    setIsLooping(true);
    window.setTimeout(() => {
      setWorkingPlan((current) => {
        const next = clonePlan(current);
        next.highlights = [`Feedback applied: ${improveText.trim()}`, ...next.highlights.slice(0, 2)];
        if (next.plan[0]) next.plan[0].activities = [`Feedback loop adjustment: ${improveText.trim()}`, ...next.plan[0].activities];
        return next;
      });
      setImproveText("");
      setIsLooping(false);
      setMode("plan");
    }, 850);
  };

  if (mode === "checkout" || mode === "booked") {
    const bookingItems = [
      { label: "Flights / Train", value: transportTotal, icon: Plane, detail: "Demo tickets reserved" },
      { label: "Hotel stay", value: hotelTotal, icon: Hotel, detail: `${Math.max(dayCount - 1, 1)} nights locked` },
      { label: "Activities", value: activityTotal, icon: TicketCheck, detail: "Timed experiences bundled" },
      { label: "Food & transfers", value: dayCount * 900, icon: Utensils, detail: "Wallet estimate prepared" },
    ];

    return (
      <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} className="mx-auto max-w-7xl pb-16">
        <Button variant="ghost" onClick={() => setMode("plan")} className="mb-6 rounded-full border border-white/10 bg-white/[0.06] text-white/70 hover:bg-white/10 hover:text-white">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to command center
        </Button>

        <div className="relative overflow-hidden rounded-[2.2rem] border border-[#ff7a59]/40 bg-[#242323]/90 p-6 shadow-[0_30px_160px_rgba(255,107,95,0.12)] md:p-8">
          <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[#ff5f6d] via-[#ff9b54] to-[#34e6d1]" />
          <div className="absolute -right-28 -top-28 h-80 w-80 rounded-full bg-[#ff6b5f]/20 blur-3xl" />
          <div className="absolute -bottom-32 left-0 h-72 w-72 rounded-full bg-[#34e6d1]/12 blur-3xl" />
          <div className="relative z-10 grid gap-8 lg:grid-cols-[1fr_420px]">
            <div>
              <p className="mb-3 text-xs font-black uppercase tracking-[0.28em] text-[#34e6d1]">Demo purchase engine</p>
              <h2 className="max-w-4xl text-5xl font-black leading-[0.9] tracking-[-0.07em] text-white md:text-7xl">
                {mode === "booked" ? "Everything is booked." : "Book the whole trip in one shot."}
              </h2>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-white/62">
                This is a demo checkout: it simulates buying transport, hotel, activities, transfers, and local reservations as one bundled itinerary.
              </p>

              <div className="mt-8 grid gap-3 md:grid-cols-2">
                {bookingItems.map((item, index) => {
                  const Icon = item.icon;
                  const done = mode === "booked" || purchaseStep > index;
                  return (
                    <motion.div
                      key={item.label}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.08 }}
                      className={`rounded-[1.4rem] border p-4 transition ${done ? "border-[#34e6d1]/35 bg-[#34e6d1]/10" : "border-white/10 bg-white/[0.045]"}`}
                    >
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                          <div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${done ? "bg-[#34e6d1] text-black" : "bg-white/10 text-white/70"}`}>
                            {done ? <CheckCircle2 className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
                          </div>
                          <div>
                            <p className="font-bold text-white">{item.label}</p>
                            <p className="text-sm text-white/45">{item.detail}</p>
                          </div>
                        </div>
                        <p className="font-black text-[#ff875f]">{formatMoney(item.value)}</p>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            </div>

            <div className="rounded-[2rem] border border-white/10 bg-black/24 p-5 backdrop-blur-xl">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.25em] text-white/38">Final cart</p>
                  <h3 className="mt-2 text-2xl font-black text-white">{tripTitle(summary)}</h3>
                </div>
                <CreditCard className="h-7 w-7 text-[#34e6d1]" />
              </div>
              <div className="space-y-3 rounded-[1.4rem] border border-white/10 bg-white/[0.04] p-4">
                <div className="flex justify-between text-white/65"><span>Transport</span><strong className="text-white">{formatMoney(transportTotal)}</strong></div>
                <div className="flex justify-between text-white/65"><span>Hotel</span><strong className="text-white">{formatMoney(hotelTotal)}</strong></div>
                <div className="flex justify-between text-white/65"><span>Activities</span><strong className="text-white">{formatMoney(activityTotal)}</strong></div>
                <div className="border-t border-white/10 pt-3 text-3xl font-black text-[#ff875f]">{formatMoney(totalCost)}</div>
                <p className="text-sm text-white/42">≈ {formatMoney(perPerson)} / person · demo mode</p>
              </div>
              <Button onClick={() => setMode("booked")} disabled={mode === "booked"} className="mt-5 h-14 w-full rounded-2xl bg-gradient-to-r from-[#ff5f6d] to-[#ff9b54] font-black text-white shadow-[0_16px_60px_rgba(255,107,95,0.24)] hover:scale-[1.01]">
                {mode === "booked" ? <CheckCircle2 className="mr-2 h-5 w-5" /> : <CreditCard className="mr-2 h-5 w-5" />}
                {mode === "booked" ? "Demo booking complete" : "Pay & purchase all"}
              </Button>
            </div>
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mx-auto w-full max-w-7xl pb-16 text-white">
      <div className="mb-6 flex items-center justify-between gap-4">
        <Button variant="ghost" onClick={onRestart} className="rounded-full border border-white/10 bg-white/[0.06] px-4 text-white/70 hover:bg-white/10 hover:text-white">
          <ArrowLeft className="mr-2 h-4 w-4" />
          New trip
        </Button>
        <div className="hidden items-center gap-2 rounded-full border border-[#34e6d1]/25 bg-[#34e6d1]/10 px-4 py-2 text-sm font-bold text-[#9ffdf3] md:flex">
          <Sparkles className="h-4 w-4" />
          Planning + demo booking command center
        </div>
      </div>

      <motion.section initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="relative mb-6 overflow-hidden rounded-[1.7rem] border border-[#ff7a59]/70 bg-[#3b3431]/86 p-5 shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_30px_120px_rgba(255,107,95,0.14)] md:p-7">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[#ff5f6d] via-[#ff9b54] to-[#34e6d1]" />
        <div className="absolute -right-20 -top-24 h-80 w-80 rounded-full bg-[#ff8a3d]/22 blur-3xl" />
        <div className="absolute -bottom-28 left-1/3 h-64 w-64 rounded-full bg-[#34e6d1]/12 blur-3xl" />
        <div className="relative z-10 grid gap-6 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-black/30 text-[#ff9b54]"><Sparkles className="h-5 w-5" /></span>
              <h2 className="text-3xl font-black tracking-[-0.04em] text-white md:text-4xl">{tripTitle(summary)}</h2>
            </div>
            <div className="mb-4 flex flex-wrap gap-2 text-sm font-bold text-white/68">
              <span className="rounded-xl bg-black/20 px-3 py-2"><MapPin className="mr-1.5 inline h-4 w-4 text-[#ff6b5f]" />{destination.toLowerCase()}</span>
              <span className="rounded-xl bg-black/20 px-3 py-2"><CalendarDays className="mr-1.5 inline h-4 w-4 text-[#ff9b54]" />19 May 2026 - 21 May 2026</span>
              <span className="rounded-xl bg-black/20 px-3 py-2"><Luggage className="mr-1.5 inline h-4 w-4 text-[#34e6d1]" />2 travelers</span>
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <p className="flex items-center text-5xl font-black tracking-[-0.06em] text-[#ff7b54]"><IndianRupee className="h-9 w-9" />{totalCost.toLocaleString("en-IN")}</p>
                <div className="mt-2 flex flex-wrap gap-2 text-xs font-black">
                  <span className="rounded-lg bg-[#ff7b54]/16 px-2 py-1 text-[#ffb09b]">Activities {formatMoney(activityTotal)}</span>
                  <span className="rounded-lg bg-[#34e6d1]/16 px-2 py-1 text-[#9ffdf3]">Hotel {formatMoney(hotelTotal)}</span>
                  <span className="rounded-lg bg-white/10 px-2 py-1 text-white/58">{formatMoney(perPerson)}/person</span>
                </div>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button className="h-14 rounded-2xl bg-gradient-to-r from-[#ff5f6d] to-[#ff9b54] px-7 font-black text-white shadow-[0_16px_60px_rgba(255,107,95,0.22)] hover:scale-[1.02]">
              <MessageCircle className="mr-2 h-5 w-5" />
              Share on WhatsApp
            </Button>
            <Button variant="ghost" className="h-14 rounded-2xl border border-white/14 bg-black/14 px-7 font-black text-[#ffaba3] hover:bg-white/10 hover:text-white">
              <Download className="mr-2 h-5 w-5" />
              Download Itinerary
            </Button>
          </div>
        </div>
      </motion.section>

      <div className="mb-6 flex flex-wrap gap-3">
        {tabItems.map((item) => {
          const Icon = item.icon;
          const active = activeTab === item.key;
          return (
            <button key={item.key} onClick={() => setActiveTab(item.key)} className={`flex items-center gap-2 rounded-2xl px-5 py-3 font-black transition ${active ? "bg-gradient-to-r from-[#ff5f6d] to-[#ff9b54] text-white shadow-[0_12px_50px_rgba(255,107,95,0.22)]" : "border border-white/10 bg-[#343333] text-white/62 hover:-translate-y-0.5 hover:text-white"}`}>
              <Icon className="h-4 w-4" />
              {item.label}
            </button>
          );
        })}
      </div>

      <AnimatePresence mode="wait">
        {activeTab === "itinerary" && (
          <motion.div key="itinerary" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }} className="space-y-5">
            <div className="grid gap-5 lg:grid-cols-2">
              <div className="rounded-[1.4rem] border border-white/10 bg-[#343333] p-5 shadow-[0_24px_80px_rgba(0,0,0,0.24)]">
                <h3 className="mb-5 flex items-center gap-2 text-xl font-black"><MapPin className="h-5 w-5 text-[#ff5f6d]" /> Getting There</h3>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="flex gap-4">
                    <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#ff7b54]/16 text-[#ff8a54]"><Plane className="h-6 w-6" /></span>
                    <div>
                      <p className="font-black text-white">{destination} International Airport</p>
                      <span className="mt-2 inline-block rounded-md bg-[#ff7b54]/20 px-2 py-1 text-[10px] font-black text-[#ffab86]">GO!</span>
                      <p className="mt-2 text-sm text-white/52">In the city<br />Direct access</p>
                    </div>
                  </div>
                  <div className="flex gap-4">
                    <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#34e6d1]/14 text-[#34e6d1]"><Train className="h-6 w-6" /></span>
                    <div>
                      <p className="font-black text-white">Central Railway Station</p>
                      <p className="mt-2 text-sm text-white/52">35 km away<br />1 hour by road</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-[1.4rem] border border-white/10 bg-[#343333] p-5 shadow-[0_24px_80px_rgba(0,0,0,0.24)]">
                <div className="mb-5 flex items-start justify-between">
                  <h3 className="text-xl font-black">Destination Score</h3>
                  <div className="rounded-2xl bg-gradient-to-br from-[#34e6d1] to-[#58f4df] px-4 py-2 text-3xl font-black text-white shadow-[0_10px_40px_rgba(52,230,209,0.2)]">8/10<p className="text-center text-xs font-bold text-black/45">Excellent</p></div>
                </div>
                <div className="space-y-4">
                  {scoreRows.map((row) => {
                    const Icon = row.icon;
                    return (
                      <div key={row.label} className="grid grid-cols-[150px_1fr_24px] items-center gap-4 text-sm">
                        <div className="flex items-center gap-2 text-white/70"><Icon className="h-4 w-4" />{row.label}</div>
                        <div className="h-3 overflow-hidden rounded-full bg-white/12"><motion.div initial={{ width: 0 }} animate={{ width: `${row.value * 10}%` }} transition={{ duration: 0.8 }} className={`h-full rounded-full ${row.color}`} /></div>
                        <strong>{row.value}</strong>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="overflow-hidden rounded-[1.4rem] border border-white/10 bg-[#343333] shadow-[0_24px_80px_rgba(0,0,0,0.24)]">
              <div className="h-1 bg-gradient-to-r from-[#ff5f6d] via-[#ff9b54] to-[#34e6d1]" />
              <div className="relative min-h-[320px] p-6">
                <div className="absolute inset-x-20 bottom-16 top-8 grid grid-cols-6 border-x border-white/8">
                  {Array.from({ length: 6 }).map((_, index) => <div key={index} className="border-r border-white/8" />)}
                </div>
                {[0, 1, 2].map((day) => (
                  <div key={day} className="relative mb-14 grid grid-cols-[70px_1fr] items-center gap-4">
                    <p className="font-black text-white/82">Day {day + 1}</p>
                    <div className="relative h-px border-t border-dashed border-white/18">
                      {activityDays[day]?.slice(0, 8).map((activity, index) => {
                        const Icon = categoryIcons[activity.category];
                        return (
                          <motion.div key={`${activity.time}-${index}`} initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: day * 0.1 + index * 0.04 }} title={activity.title} className={`absolute -top-4 flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br ${categoryColors[activity.category]} text-white shadow-[0_0_0_4px_rgba(255,255,255,0.06)]`} style={{ left: `${7 + index * 12}%` }}>
                            <Icon className="h-4 w-4" />
                          </motion.div>
                        );
                      })}
                    </div>
                  </div>
                ))}
                <div className="ml-[86px] mt-2 flex flex-wrap gap-4 text-xs font-bold text-white/55">
                  {Object.keys(categoryColors).slice(0, 5).map((category) => <span key={category} className="flex items-center gap-1"><span className={`h-3 w-3 rounded-full bg-gradient-to-br ${categoryColors[category as Activity["category"]]}`} />{category}</span>)}
                  <span>· Dot size = duration</span>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              {dayPlans.map((day, index) => {
                const activities = activityDays[index] || [];
                const dayCost = activities.reduce((sum, activity) => sum + activity.cost, 0);
                const open = expandedDay === index;
                return (
                  <motion.div key={day.day} initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.06 }} className="overflow-hidden rounded-[1.35rem] border border-white/10 bg-[#252525] shadow-[0_22px_80px_rgba(0,0,0,0.28)]">
                    <button onClick={() => setExpandedDay(open ? -1 : index)} className="flex w-full items-center justify-between gap-4 border-b border-white/8 bg-[#202020] p-4 text-left">
                      <div className="flex items-center gap-4">
                        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#ff5f6d] to-[#ff9b54] font-black text-white">{index + 1}</span>
                        <div>
                          <h3 className="font-black text-white">{day.day}</h3>
                          <p className="text-xs font-bold text-white/45">{activities.length} activities · 10h 30m · {formatMoney(dayCost)}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <SectionActions label={day.day} onEdit={() => startEdit(`day-${index}`, day.activities.join("\n"))} onRegenerate={() => regenerateSection(`day-${index}`)} />
                        <ChevronDown className={`h-5 w-5 text-white/50 transition ${open ? "rotate-180" : ""}`} />
                      </div>
                    </button>
                    <AnimatePresence initial={false}>
                      {open && (
                        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="space-y-3 p-4">
                          {activities.map((activity, activityIndex) => {
                            const Icon = categoryIcons[activity.category];
                            return (
                              <div key={`${activity.time}-${activity.title}`}>
                                {activityIndex > 0 ? <div className="mx-auto my-2 h-8 w-px bg-gradient-to-b from-white/10 to-white/25" /> : null}
                                <motion.div initial={{ opacity: 0, x: -14 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: activityIndex * 0.03 }} className="rounded-[1rem] border border-white/8 bg-[#343333] p-4 hover:border-[#ff7a59]/35 hover:bg-[#3a3836]">
                                  <div className="flex items-start justify-between gap-4">
                                    <div className="flex gap-3">
                                      <span className="rounded-lg bg-[#ff8a54]/20 px-2 py-1 text-xs font-black text-[#ffb086]">{activity.time}</span>
                                      <div>
                                        <p className="font-black text-white">{activity.title}</p>
                                        <p className="mt-2 max-w-3xl text-sm leading-6 text-white/56">{activity.description}</p>
                                        <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-bold text-white/50">
                                          <span className={`rounded-full bg-gradient-to-r ${categoryColors[activity.category]} px-2 py-1 text-white`}><Icon className="mr-1 inline h-3 w-3" />{activity.category}</span>
                                          <span className="rounded-full bg-white/8 px-2 py-1"><MapPin className="mr-1 inline h-3 w-3" />{activity.place}</span>
                                          <span className="rounded-full bg-white/8 px-2 py-1"><Clock3 className="mr-1 inline h-3 w-3" />{activity.duration}</span>
                                        </div>
                                      </div>
                                    </div>
                                    <strong className="text-[#ff875f]">{activity.cost ? formatMoney(activity.cost) : "₹0"}</strong>
                                  </div>
                                </motion.div>
                              </div>
                            );
                          })}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                );
              })}
            </div>
          </motion.div>
        )}

        {activeTab === "map" && (
          <motion.div key="map" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }} className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="relative min-h-[540px] overflow-hidden rounded-[1.5rem] border border-white/10 bg-[#333] p-6">
              <div className="absolute inset-0 opacity-45 premium-grid" />
              <div className="absolute left-[18%] top-[20%] h-36 w-36 rounded-full border border-[#ff7a59]/30 bg-[#ff7a59]/12 blur-sm" />
              <div className="absolute right-[22%] top-[34%] h-48 w-48 rounded-full border border-[#34e6d1]/30 bg-[#34e6d1]/12 blur-sm" />
              <div className="absolute bottom-[18%] left-[38%] h-40 w-40 rounded-full border border-[#ff9b54]/30 bg-[#ff9b54]/12 blur-sm" />
              {timelineItems.slice(0, 14).map((item, index) => (
                <motion.div key={`${item.title}-${index}`} initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: index * 0.04 }} className={`absolute flex h-11 w-11 items-center justify-center rounded-full bg-gradient-to-br ${categoryColors[item.category]} font-black text-white shadow-[0_0_0_5px_rgba(0,0,0,0.22)]`} style={{ left: `${12 + (index * 17) % 72}%`, top: `${18 + (index * 23) % 62}%` }}>
                  {index + 1}
                </motion.div>
              ))}
              <div className="relative z-10 max-w-md rounded-[1.3rem] border border-white/10 bg-black/30 p-5 backdrop-blur-xl">
                <h3 className="text-2xl font-black">Live route map</h3>
                <p className="mt-2 text-white/58">A stylized demo map showing clustered route anchors, booked transfers, food stops, hotel area, and purchasable activities.</p>
              </div>
            </div>
            <div className="space-y-3">
              {timelineItems.slice(0, 8).map((item, index) => <div key={`${item.title}-${index}`} className="rounded-2xl border border-white/10 bg-[#343333] p-4"><p className="text-sm font-black text-[#ff9b54]">Stop {index + 1} · {item.time}</p><h4 className="mt-1 font-black text-white">{item.title}</h4><p className="mt-1 text-sm text-white/48">{item.place}</p></div>)}
            </div>
          </motion.div>
        )}

        {activeTab === "hotels" && (
          <motion.div key="hotels" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }} className="grid gap-5 md:grid-cols-3">
            {["Boutique Beach Stay", "Central Smart Hotel", "Luxury Resort Demo"].map((hotel, index) => <div key={hotel} className="rounded-[1.4rem] border border-white/10 bg-[#343333] p-5"><div className="mb-5 h-40 rounded-[1rem] bg-gradient-to-br from-[#ff7a59]/35 via-[#343333] to-[#34e6d1]/25" /><h3 className="text-xl font-black">{hotel}</h3><p className="mt-2 text-sm text-white/52">Walkable area · breakfast · refundable demo booking</p><p className="mt-5 text-3xl font-black text-[#ff875f]">{formatMoney(1200 + index * 1600)}</p><Button className="mt-4 w-full rounded-2xl bg-[#34e6d1] font-black text-black hover:bg-white">Reserve demo room</Button></div>)}
          </motion.div>
        )}

        {activeTab === "prep" && (
          <motion.div key="prep" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }} className="rounded-[1.4rem] border border-[#34e6d1]/25 bg-[#123c39]/60 p-5">
            <h3 className="mb-5 flex items-center gap-2 text-2xl font-black"><Backpack className="text-[#34e6d1]" /> {destination} Travel Tips</h3>
            <div className="grid gap-4 md:grid-cols-2">
              {tips.map((tip) => <div key={tip.title} className="rounded-2xl border border-white/10 bg-white/[0.08] p-4"><h4 className="font-black text-white">{tip.title}</h4><p className="mt-2 text-sm leading-6 text-white/56">{tip.body}</p></div>)}
            </div>
            <div className="mt-5 rounded-2xl border border-[#ff9b54]/35 bg-[#ff9b54]/10 p-4 text-sm font-bold text-[#ffd0a9]">Festival alert: Check local events and closures before final purchase.</div>
          </motion.div>
        )}

        {activeTab === "analytics" && (
          <motion.div key="analytics" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }} className="grid gap-5 lg:grid-cols-2">
            <div className="rounded-[1.4rem] border border-white/10 bg-[#343333] p-5"><h3 className="text-2xl font-black">Spend Analytics</h3>{[["Activities", activityTotal, "#ff7b54"], ["Hotel", hotelTotal, "#34e6d1"], ["Transport", transportTotal, "#ff9b54"]].map(([label, value, color]) => <div key={label as string} className="mt-5"><div className="mb-2 flex justify-between text-sm font-bold"><span>{label}</span><span>{formatMoney(value as number)}</span></div><div className="h-4 rounded-full bg-white/10"><motion.div initial={{ width: 0 }} animate={{ width: `${Math.min(((value as number) / totalCost) * 100, 100)}%` }} className="h-full rounded-full" style={{ background: color as string }} /></div></div>)}</div>
            <div className="rounded-[1.4rem] border border-white/10 bg-[#343333] p-5"><h3 className="text-2xl font-black">Purchase Readiness</h3>{["Transport tickets", "Hotel booking", "Activities", "Food reservations", "Local transfers"].map((item, index) => <div key={item} className="mt-4 flex items-center justify-between rounded-2xl bg-white/[0.055] p-4"><span className="font-bold text-white/72">{item}</span><span className={`rounded-full px-3 py-1 text-xs font-black ${index < 4 ? "bg-[#34e6d1]/18 text-[#9ffdf3]" : "bg-[#ff9b54]/18 text-[#ffd0a9]"}`}>{index < 4 ? "Ready" : "Optional"}</span></div>)}</div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.section initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mt-6 rounded-[1.5rem] border border-white/10 bg-[#2c2c2c] p-5">
        {mode === "improve" ? (
          <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr] lg:items-end">
            <div><p className="text-xs font-black uppercase tracking-[0.28em] text-[#34e6d1]">Feedback loop</p><h3 className="mt-2 text-3xl font-black">What should the agents improve?</h3></div>
            <div className="space-y-3"><Textarea value={improveText} onChange={(event) => setImproveText(event.target.value)} placeholder="Make it cheaper, add more beach clubs, reduce travel, upgrade hotel..." className="premium-textarea" /><div className="flex flex-wrap gap-3"><Button onClick={runImproveLoop} disabled={isLooping || !improveText.trim()} className="rounded-2xl bg-[#34e6d1] px-5 font-black text-black hover:bg-white">{isLooping ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <SendHorizonal className="mr-2 h-4 w-4" />}Run improvement loop</Button><Button variant="ghost" onClick={() => setMode("plan")} className="rounded-2xl border border-white/10 bg-white/[0.055] text-white/70 hover:bg-white/10 hover:text-white">Cancel</Button></div></div>
          </div>
        ) : (
          <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
            <div><p className="text-xs font-black uppercase tracking-[0.28em] text-[#ff9b54]">Approval checkpoint</p><h3 className="mt-2 text-3xl font-black">Ready to purchase the demo trip?</h3><p className="mt-2 max-w-2xl text-white/52">Approve to simulate booking tickets, hotel, activities, transfers, and food reservations.</p></div>
            <div className="flex flex-wrap gap-3"><Button onClick={() => setMode("checkout")} className="h-12 rounded-2xl bg-gradient-to-r from-[#ff5f6d] to-[#ff9b54] px-5 font-black text-white"><ThumbsUp className="mr-2 h-4 w-4" />Proceed to booking</Button><Button variant="ghost" onClick={() => setMode("improve")} className="h-12 rounded-2xl border border-white/10 bg-white/[0.055] px-5 font-black text-white/70 hover:bg-white/10 hover:text-white"><WandSparkles className="mr-2 h-4 w-4" />Improve</Button></div>
          </div>
        )}
      </motion.section>

      <AnimatePresence>
        {editingKey && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-xl">
            <motion.div initial={{ opacity: 0, y: 24, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 24, scale: 0.96 }} className="w-full max-w-2xl rounded-[2rem] border border-[#ff7a59]/35 bg-[#242323] p-6 shadow-[0_30px_120px_rgba(0,0,0,0.65)]">
              <p className="mb-2 text-xs font-black uppercase tracking-[0.3em] text-[#34e6d1]">Inline AI editor</p>
              <h3 className="text-3xl font-black tracking-[-0.045em] text-white">Edit this section</h3>
              <p className="mt-2 text-sm leading-6 text-white/50">Use one line per item for daily activities and highlights.</p>
              <Textarea value={draft} onChange={(event) => setDraft(event.target.value)} className="premium-textarea mt-5 min-h-52" />
              <div className="mt-5 flex flex-wrap justify-end gap-3"><Button variant="ghost" onClick={() => setEditingKey(null)} className="rounded-2xl border border-white/10 bg-white/[0.055] text-white/65 hover:bg-white/10 hover:text-white">Cancel</Button><Button onClick={saveEdit} className="rounded-2xl bg-[#34e6d1] font-black text-black hover:bg-white">Save changes</Button></div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
