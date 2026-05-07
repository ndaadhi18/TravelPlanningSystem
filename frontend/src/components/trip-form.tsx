import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Bot, Loader2, SendHorizonal, UserRound } from "lucide-react";
import type { TravelPlanInput } from "@workspace/api-client-react/src/generated/api.schemas";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

export interface TripFormProps {
  onSubmit: (data: TravelPlanInput) => void;
  isSubmitting?: boolean;
  errorMessage?: string | null;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const INTENT_MARKER = "__INTENT__";

const GREETING: Message = {
  id: "greeting",
  role: "assistant",
  content:
    "Hi! I'm Aura, your AI travel planning assistant. Tell me about the trip you have in mind — where are you thinking of going, and roughly when?",
};

// ── Component ─────────────────────────────────────────────────────────────────

export function TripForm({
  onSubmit,
  isSubmitting = false,
  errorMessage = null,
}: TripFormProps) {
  const [messages, setMessages] = useState<Message[]>([GREETING]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [intentReady, setIntentReady] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // ── Auto-scroll: runs on every message update (including streamed chunks) ──
  useEffect(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // ── Focus input on mount ──────────────────────────────────────────────────
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // ── Send & stream ─────────────────────────────────────────────────────────
  async function send() {
    const text = input.trim();
    if (!text || isStreaming || isSubmitting || intentReady) return;

    setInput("");

    // Snapshot current history (no stale streaming entries)
    const history = messages.filter((m) => !m.streaming);
    const userMsg: Message = { id: `u-${Date.now()}`, role: "user", content: text };
    const assistantId = `a-${Date.now()}`;

    // Optimistically add user msg + empty streaming assistant msg
    setMessages([
      ...history,
      userMsg,
      { id: assistantId, role: "assistant", content: "", streaming: true },
    ]);
    setIsStreaming(true);

    let accumulated = "";

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [...history, userMsg].map(({ role, content }) => ({ role, content })),
        }),
      });

      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let sseBuffer = "";

      // Read stream
      outer: while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        sseBuffer += decoder.decode(value, { stream: true });

        // Split on SSE event boundaries (\n\n)
        const events = sseBuffer.split("\n\n");
        sseBuffer = events.pop() ?? "";

        for (const event of events) {
          const dataLine = event.split("\n").find((l) => l.startsWith("data: "));
          if (!dataLine) continue;

          const raw = dataLine.slice(6).trim();
          if (raw === "[DONE]") break outer;

          try {
            const { type, content } = JSON.parse(raw) as { type: string; content?: string };
            if (type === "delta" && content) {
              accumulated += content;

              // Strip the intent marker from what's displayed while streaming
              const markerIdx = accumulated.indexOf(INTENT_MARKER);
              const displayText =
                markerIdx !== -1 ? accumulated.slice(0, markerIdx).trimEnd() : accumulated;

              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.id === assistantId) {
                  next[next.length - 1] = { ...last, content: displayText };
                }
                return next;
              });
            }
          } catch {
            // malformed SSE chunk — ignore
          }
        }
      }
    } catch {
      // Network / fetch error — show inline error in chat
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.id === assistantId) {
          next[next.length - 1] = {
            ...last,
            content: "Something went wrong. Please try again.",
            streaming: false,
          };
        }
        return next;
      });
      setIsStreaming(false);
      return;
    }

    // ── Stream complete — finalize ────────────────────────────────────────
    const markerIdx = accumulated.indexOf(INTENT_MARKER);
    const finalDisplay =
      markerIdx !== -1 ? accumulated.slice(0, markerIdx).trimEnd() : accumulated.trimEnd();

    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last?.id === assistantId) {
        next[next.length - 1] = { ...last, content: finalDisplay, streaming: false };
      }
      return next;
    });

    setIsStreaming(false);

    // ── If intent is present, extract and transition ──────────────────────
    if (markerIdx !== -1) {
      const jsonRaw = accumulated.slice(markerIdx + INTENT_MARKER.length).trim();
      try {
        const intent = JSON.parse(jsonRaw) as TravelPlanInput;
        setIntentReady(true);
        // Brief pause so the user can read the completion message
        setTimeout(() => onSubmit(intent), 1800);
      } catch {
        // JSON parse failed — treat as normal message, let user continue
      }
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  const inputDisabled = isStreaming || isSubmitting || intentReady;
  const placeholder = intentReady
    ? "Connecting to planning agents…"
    : isStreaming
      ? "Aura is thinking…"
      : "Type your message…";

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <motion.div
      initial={{ opacity: 0, y: 18, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.58, ease: [0.22, 1, 0.36, 1] }}
      className="relative overflow-hidden rounded-[2rem] border border-white/14 bg-white/[0.08] shadow-[0_24px_90px_rgba(0,0,0,0.45)] backdrop-blur-2xl"
    >
      {/* Top glint */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-200/70 to-transparent" />

      {/* Header */}
      <div className="border-b border-white/10 p-5 md:p-6">
        <div className="flex items-center gap-3">
          <div className="relative flex h-11 w-11 items-center justify-center rounded-2xl border border-cyan-200/20 bg-cyan-200/10 text-cyan-100">
            <Bot className="h-5 w-5" />
            {/* Pulse when streaming */}
            {isStreaming && (
              <span className="absolute -right-0.5 -top-0.5 h-3 w-3 rounded-full border-2 border-[#06080f] bg-cyan-300" />
            )}
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-100/60">
              AI Travel Assistant
            </p>
            <h3 className="font-sans text-2xl font-semibold tracking-[-0.04em] text-white">
              Aura
            </h3>
          </div>

          {/* Status pill */}
          <AnimatePresence>
            {(isStreaming || intentReady) && (
              <motion.div
                key="status"
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.85 }}
                transition={{ duration: 0.2 }}
                className="ml-auto flex items-center gap-1.5 rounded-full border border-cyan-200/20 bg-cyan-200/10 px-3 py-1 text-xs text-cyan-100"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-300 animate-pulse" />
                {intentReady ? "Launching agents…" : "Thinking"}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Messages */}
      <div
        ref={containerRef}
        className="h-[400px] space-y-4 overflow-y-auto p-5 md:p-6"
        style={{ scrollbarWidth: "none" }}
      >
        {messages.map((msg) => (
          <motion.div
            key={msg.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className={`flex items-end gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
          >
            {/* Avatar */}
            <div
              className={`mb-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl border ${
                msg.role === "assistant"
                  ? "border-cyan-200/20 bg-cyan-200/10 text-cyan-100"
                  : "border-white/10 bg-white/10 text-white/70"
              }`}
            >
              {msg.role === "assistant" ? (
                <Bot className="h-3.5 w-3.5" />
              ) : (
                <UserRound className="h-3.5 w-3.5" />
              )}
            </div>

            {/* Bubble */}
            <div
              className={`max-w-[82%] rounded-[1.35rem] px-4 py-3 text-sm leading-[1.65] ${
                msg.role === "assistant"
                  ? "rounded-bl-sm border border-white/10 bg-white/[0.08] text-white/88"
                  : "rounded-br-sm border border-cyan-200/20 bg-cyan-200/12 font-medium text-cyan-50"
              }`}
            >
              {/* Typing dots when empty + streaming */}
              {msg.streaming && !msg.content ? (
                <span className="inline-flex items-center gap-1">
                  {[0, 150, 300].map((delay) => (
                    <span
                      key={delay}
                      className="h-1.5 w-1.5 rounded-full bg-white/35 animate-bounce"
                      style={{ animationDelay: `${delay}ms` }}
                    />
                  ))}
                </span>
              ) : (
                <>
                  {msg.content}
                  {/* Blinking cursor while streaming */}
                  {msg.streaming && (
                    <span className="ml-0.5 inline-block h-[14px] w-[2px] translate-y-[1px] animate-pulse bg-cyan-300/80 align-middle" />
                  )}
                </>
              )}
            </div>
          </motion.div>
        ))}

        {/* API error from parent (e.g. /api/plan failure) */}
        {errorMessage && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-red-300/20 bg-red-400/10 px-4 py-3 text-sm text-red-100"
          >
            {errorMessage}
          </motion.div>
        )}
      </div>

      {/* Input bar */}
      <div className="border-t border-white/10 p-4 md:p-5">
        <div
          className={`flex items-center gap-3 rounded-2xl border bg-black/20 px-4 py-3 transition-colors duration-200 ${
            inputDisabled
              ? "border-white/6 opacity-60"
              : "border-white/10 focus-within:border-cyan-200/35"
          }`}
        >
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={inputDisabled}
            className="flex-1 bg-transparent text-sm text-white placeholder:text-white/28 outline-none disabled:cursor-not-allowed"
          />
          <button
            type="button"
            onClick={send}
            disabled={!input.trim() || inputDisabled}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-cyan-200 text-slate-950 transition-all duration-200 hover:bg-white hover:scale-105 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:scale-100"
            aria-label="Send message"
          >
            {isStreaming || isSubmitting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <SendHorizonal className="h-3.5 w-3.5" />
            )}
          </button>
        </div>
        <p className="mt-2.5 text-center text-[11px] text-white/20">
          Press Enter to send · Aura will ask follow-up questions as needed
        </p>
      </div>
    </motion.div>
  );
}
