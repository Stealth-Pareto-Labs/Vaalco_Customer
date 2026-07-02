"use client";

import {
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  forwardRef
} from "react";
import type { FormEvent } from "react";
import { Send, Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useToast } from "@/components/Toast";
import ChartView from "@/components/ChartView";
import type { ChartSpec, ChatMessage, TraceItem } from "@/lib/types";

interface ThreadMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  pending?: boolean;
  trace?: TraceItem[];
  charts?: ChartSpec[];
}

export interface AskHandle {
  sendProbe: (text: string) => void;
}

/** Remove markdown images and inline data-URIs from answer text. */
function sanitizeAnswer(text: string): string {
  let out = text.replace(/!\[[^\]]*\]\([^)]*\)/g, "");
  out = out.replace(/data:[^\s)"']+/g, "");
  return out.trim();
}

function formatTrace(item: TraceItem): string {
  let args = "";
  try {
    args = JSON.stringify(item.arguments ?? {});
  } catch {
    args = "{…}";
  }
  return `→ called ${item.tool}(${args})`;
}

const Ask = forwardRef<AskHandle>(function Ask(_props, ref) {
  const { t } = useI18n();
  const { toast } = useToast();
  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const historyRef = useRef<ChatMessage[]>([]);
  const counter = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const nextId = () => {
    counter.current += 1;
    return counter.current;
  };

  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [messages]);

  const send = useCallback(
    async (raw: string) => {
      const message = raw.trim();
      if (!message || loading) return;

      const history = [...historyRef.current];
      const userMsg: ThreadMessage = {
        id: nextId(),
        role: "user",
        content: message
      };
      const pendingId = nextId();
      const pendingMsg: ThreadMessage = {
        id: pendingId,
        role: "assistant",
        content: "",
        pending: true
      };

      setMessages((prev) => [...prev, userMsg, pendingMsg]);
      setInput("");
      setLoading(true);

      try {
        const res = await api.ask(message, history);
        const answer = sanitizeAnswer(res.answer ?? "");
        setMessages((prev) =>
          prev.map((m) =>
            m.id === pendingId
              ? {
                  ...m,
                  pending: false,
                  content: answer,
                  trace: res.trace ?? [],
                  charts: res.charts ?? []
                }
              : m
          )
        );
        historyRef.current = [
          ...history,
          { role: "user", content: message },
          { role: "assistant", content: answer }
        ];
      } catch (err) {
        const msg =
          err instanceof ApiError ? err.message : t("common.error");
        setMessages((prev) => prev.filter((m) => m.id !== pendingId));
        toast(msg, "error");
      } finally {
        setLoading(false);
        inputRef.current?.focus();
      }
    },
    [loading, t, toast]
  );

  useImperativeHandle(
    ref,
    () => ({
      sendProbe: (text: string) => {
        void send(text);
      }
    }),
    [send]
  );

  const chips = [
    t("ask.chip.fuel"),
    t("ask.chip.fuelSpike"),
    t("ask.chip.dp"),
    t("ask.chip.maintenance")
  ];

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void send(input);
  };

  return (
    <div className="flex h-[calc(100vh-14rem)] min-h-[420px] flex-col">
      <div
        ref={scrollRef}
        className="scroll-thin flex-1 overflow-y-auto px-1 py-4"
      >
        <p className="mb-4 px-1 text-[14px] leading-relaxed text-mut">
          {t("ask.hint")}
        </p>

        {messages.length === 0 ? (
          <div className="rounded-xl border border-dashed border-line2 bg-surface/50 px-4 py-8 text-center text-[14px] text-mut">
            {t("ask.emptyThread")}
          </div>
        ) : (
          <ul className="flex flex-col gap-4">
            {messages.map((m) => (
              <li key={m.id}>
                <MessageBubble message={m} thinkingLabel={t("ask.thinking")} />
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border-t border-line pt-3">
        <div className="mb-3 flex flex-wrap gap-2">
          {chips.map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => void send(chip)}
              disabled={loading}
              className="focus-ring cursor-pointer rounded-full border border-line bg-surface2 px-3 py-1.5 text-[13px] text-mut transition-colors duration-150 hover:border-line2 hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
            >
              {chip}
            </button>
          ))}
        </div>

        <form onSubmit={onSubmit} className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t("ask.placeholder")}
            aria-label={t("ask.placeholder")}
            className="focus-ring min-w-0 flex-1 rounded-lg border border-line bg-surface px-3.5 py-2.5 text-[15px] text-ink placeholder:text-mut2 focus:border-line2"
          />
          <button
            type="submit"
            disabled={loading || input.trim().length === 0}
            className="focus-ring flex shrink-0 cursor-pointer items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-[15px] font-medium text-white transition-colors duration-150 hover:bg-primary-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? (
              <Loader2 size={16} className="spin" aria-hidden="true" />
            ) : (
              <Send size={16} aria-hidden="true" />
            )}
            <span className="hidden sm:inline">{t("ask.send")}</span>
          </button>
        </form>
      </div>
    </div>
  );
});

function MessageBubble({
  message,
  thinkingLabel
}: {
  message: ThreadMessage;
  thinkingLabel: string;
}) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-[15px] leading-relaxed text-white">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] rounded-2xl rounded-bl-sm border border-line bg-surface px-4 py-3">
        {message.pending ? (
          <div className="flex items-center gap-2 py-0.5 text-[14px] text-mut" aria-live="polite">
            <Loader2 size={16} className="spin text-primary" aria-hidden="true" />
            <span>{thinkingLabel}…</span>
          </div>
        ) : (
          <>
            {message.trace && message.trace.length > 0 && (
              <div className="mb-2 space-y-0.5">
                {message.trace.map((item, i) => (
                  <p
                    key={i}
                    className="mono truncate text-[12px] leading-snug text-mut2"
                    title={formatTrace(item)}
                  >
                    {formatTrace(item)}
                  </p>
                ))}
              </div>
            )}
            <div className="whitespace-pre-wrap text-[15px] leading-relaxed text-ink">
              {message.content}
            </div>
            {message.charts &&
              message.charts.map((chart, i) => (
                <ChartView key={i} spec={chart} />
              ))}
          </>
        )}
      </div>
    </div>
  );
}

export default Ask;
