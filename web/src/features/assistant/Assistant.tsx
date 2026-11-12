import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useLang, useLocalePath } from "../../app/lang";
import { useT } from "../../app/useT";
import { Icon } from "../../components/ui/Icon";
import type { Lang } from "../../lib/types";

interface Source {
  id: string;
  cipher: string;
  title: string;
  period: string;
  file_access: string;
  url: string;
}

interface AskResponse {
  status: "found" | "not_found" | "restricted";
  text: string;
  speech: string;
  sources: Source[];
  suggestions: string[];
  provider: string;
  is_llm: boolean;
  degraded: boolean;
  disclaimer: string;
}

interface Turn {
  q: string;
  a?: AskResponse;
  error?: string;
}

// ── Голос: встроенные в браузер распознавание (Web Speech API) и синтез речи. Без внешних библиотек. ──
interface SpeechResultEvent {
  resultIndex: number;
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
}
interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: SpeechResultEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}
type RecognitionCtor = new () => Recognition;

const VOICE_LANG: Record<Lang, string> = { ru: "ru-RU", kk: "kk-KZ", en: "en-US" };

function recognitionCtor(): RecognitionCtor | undefined {
  if (typeof window === "undefined") return undefined;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

// Серверное распознавание (Groq Whisper): запись в браузере через MediaRecorder — работает и в Firefox
const canRecord = () =>
  typeof window !== "undefined" && typeof MediaRecorder !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
const MAX_RECORD_MS = 30_000;

function pickMime(): string {
  for (const m of ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"]) {
    if (MediaRecorder.isTypeSupported(m)) return m;
  }
  return "";
}

const canSpeak = () => typeof window !== "undefined" && "speechSynthesis" in window;

// нейросетевые голоса браузера (Edge «Natural/Online», Chrome «Google») звучат заметно живее системных
const NICE_VOICE = /natural|online|neural|google|premium|enhanced/i;

function speakBrowser(text: string, lang: Lang, onEnd: () => void): void {
  if (!canSpeak()) return onEnd();
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = VOICE_LANG[lang];
  const voices = synth.getVoices().filter((v) => v.lang.toLowerCase().startsWith(lang));
  const voice = voices.find((v) => NICE_VOICE.test(v.name)) ?? voices[0];
  if (voice) u.voice = voice;
  u.rate = 0.95;
  u.onend = onEnd;
  u.onerror = onEnd;
  synth.speak(u);
}

let player: HTMLAudioElement | null = null;

/** Сначала нейроголос с сервера (edge-tts), при любой ошибке — голос браузера. */
async function speak(text: string, lang: Lang, server: boolean, onEnd: () => void): Promise<void> {
  stopSpeaking();
  if (server) {
    try {
      const res = await fetch("/api/assistant/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.slice(0, 400), lang }),
      });
      if (!res.ok) throw new Error(String(res.status));
      const url = URL.createObjectURL(await res.blob());
      const a = new Audio(url);
      const done = () => {
        URL.revokeObjectURL(url);
        if (player === a) player = null;
        onEnd();
      };
      a.onended = done;
      a.onerror = done;
      player = a;
      await a.play();
      return;
    } catch {
      player = null; // падаем на голос браузера
    }
  }
  speakBrowser(text, lang, onEnd);
}

function stopSpeaking(): void {
  if (player) {
    player.pause();
    player = null;
  }
  if (canSpeak()) window.speechSynthesis.cancel();
}

/** Чат помощника: ответ всегда с источниками-ссылками и пометкой «сформировано автоматически». */
export function AssistantChat({ compact = false }: { compact?: boolean }) {
  const { t } = useT();
  const lang = useLang();
  const [q, setQ] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const readAloud = useRef(false);
  const recRef = useRef<Recognition | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const [transcribing, setTranscribing] = useState(false);
  const mode = useQuery({
    queryKey: ["assistant-mode"],
    queryFn: async () => (await (await fetch("/api/assistant/mode")).json()) as { is_llm: boolean; stt?: boolean; tts?: boolean },
    staleTime: 10 * 60_000,
  });
  const serverStt = !!mode.data?.stt && canRecord();
  const Rec = serverStt ? undefined : recognitionCtor();
  const voiceAvailable = serverStt || !!Rec;

  const say = (text: string) => {
    setSpeaking(true);
    void speak(text, lang, !!mode.data?.tts, () => setSpeaking(false));
  };
  const hush = () => {
    stopSpeaking();
    setSpeaking(false);
  };

  const ask = useMutation({
    mutationFn: async (query: string) => {
      const res = await fetch("/api/assistant/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, lang }),
      });
      if (res.status === 429) throw new Error(t("assistant.tooMany"));
      if (!res.ok) throw new Error(t("assistant.error"));
      return (await res.json()) as AskResponse;
    },
    onSuccess: (a, query) => {
      setTurns((ts) => ts.map((x) => (x.q === query && !x.a ? { ...x, a } : x)));
      if (readAloud.current) say(a.speech || a.text);
    },
    onError: (e, query) => {
      setTurns((ts) => ts.map((x) => (x.q === query && !x.a ? { ...x, error: (e as Error).message } : x)));
      if (readAloud.current) say((e as Error).message);
    },
  });
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [turns]);
  // уход со страницы/закрытие окна — замолчать и перестать слушать
  useEffect(
    () => () => {
      recRef.current?.stop();
      if (mediaRef.current?.state === "recording") mediaRef.current.stop();
      stopSpeaking();
    },
    [],
  );

  const send = (query: string, byVoice = false) => {
    const v = query.trim();
    if (v.length < 2 || ask.isPending) return;
    readAloud.current = byVoice;
    setTurns((ts) => [...ts, { q: v }]);
    setQ("");
    ask.mutate(v);
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    send(q);
  };

  const recordServer = async () => {
    if (mediaRef.current) {
      mediaRef.current.stop();
      return;
    }
    hush();
    setVoiceError(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setVoiceError(t("voice.denied"));
      return;
    }
    const mime = pickMime();
    const rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
    const chunks: Blob[] = [];
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    const timer = window.setTimeout(() => rec.state === "recording" && rec.stop(), MAX_RECORD_MS);
    rec.onstop = async () => {
      window.clearTimeout(timer);
      stream.getTracks().forEach((tr) => tr.stop());
      mediaRef.current = null;
      setListening(false);
      const blob = new Blob(chunks, { type: (rec.mimeType || "audio/webm").split(";")[0] });
      if (blob.size < 1000) return;
      setTranscribing(true);
      try {
        const fd = new FormData();
        fd.append("audio", blob, "speech");
        fd.append("lang", lang);
        const res = await fetch("/api/assistant/transcribe", { method: "POST", body: fd });
        if (!res.ok) throw new Error(res.status === 429 ? t("assistant.tooMany") : t("assistant.error"));
        const text = ((await res.json()) as { text: string }).text.trim();
        if (text) {
          setQ(text);
          send(text, true);
        } else setVoiceError(t("voice.notHeard"));
      } catch (e) {
        setVoiceError((e as Error).message);
      } finally {
        setTranscribing(false);
      }
    };
    mediaRef.current = rec;
    rec.start();
    setListening(true);
  };

  const listen = () => {
    if (serverStt) {
      void recordServer();
      return;
    }
    if (!Rec) return;
    if (recRef.current) {
      recRef.current.stop();
      return;
    }
    hush();
    setVoiceError(null);
    const r = new Rec();
    r.lang = VOICE_LANG[lang];
    r.interimResults = true;
    r.continuous = false;
    let final = "";
    r.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (!res) continue;
        if (res.isFinal) final += res[0].transcript;
        else interim += res[0].transcript;
      }
      setQ(final + interim);
    };
    r.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") setVoiceError(t("voice.denied"));
    };
    r.onend = () => {
      recRef.current = null;
      setListening(false);
      if (final.trim()) send(final, true);
    };
    recRef.current = r;
    setListening(true);
    try {
      r.start();
    } catch {
      recRef.current = null;
      setListening(false);
    }
  };

  const mic = (big: boolean) => (
    <button
      type="button"
      onClick={listen}
      aria-pressed={listening}
      className={
        big
          ? `mx-auto flex h-24 w-24 items-center justify-center rounded-full text-primary-ink shadow-lg ${listening ? "bg-danger ring-8 ring-danger/25" : "bg-primary hover:opacity-90"}`
          : `btn btn-icon shrink-0 border ${listening ? "border-danger bg-danger text-bg" : "border-line bg-bg text-ink hover:bg-surface"}`
      }
      aria-label={listening ? t("voice.stop") : t("voice.speak")}
      title={listening ? t("voice.stop") : t("voice.speak")}
    >
      <Icon name={listening ? "stop" : "mic"} size={big ? 40 : 22} />
    </button>
  );

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1" aria-live="polite">
        {turns.length === 0 && (
          <div className="space-y-4">
            {Rec ? (
              <div className="py-2 text-center">
                {mic(true)}
                <p className="mx-auto mt-4 max-w-sm text-lg font-medium">{transcribing ? t("voice.transcribing") : listening ? t("voice.listening") : t("voice.hint")}</p>
              </div>
            ) : (
              <p className="text-muted">{t("assistant.lead")}</p>
            )}
          </div>
        )}
        {turns.map((turn, i) => (
          <div key={i} className="space-y-2">
            <p className="ml-auto max-w-[85%] rounded-lg bg-primary px-3 py-2 text-primary-ink">{turn.q}</p>
            {!turn.a && !turn.error && <p className="text-muted">{t("assistant.thinking")}</p>}
            {turn.error && (
              <p className="text-danger" role="alert">
                {turn.error}
              </p>
            )}
            {turn.a && (
              <div className="max-w-[95%] rounded-lg border border-line bg-surface p-3">
                <p className="whitespace-pre-line">{turn.a.text}</p>
                {(canSpeak() || mode.data?.tts) && (
                  <button type="button" className="btn-ghost mt-2 px-3" onClick={() => (speaking ? hush() : say(turn.a!.speech || turn.a!.text))}>
                    <Icon name={speaking ? "stop" : "volume"} size={20} />
                    {speaking ? t("voice.stopReading") : t("voice.replay")}
                  </button>
                )}
                {turn.a.degraded && <p className="mt-2 text-sm text-warn">{t("assistant.degraded")}</p>}
                {turn.a.sources.length > 0 && (
                  <div className="mt-3">
                    <p className="font-semibold">{t("assistant.sources")}</p>
                    <ul className="mt-1 space-y-2">
                      {turn.a.sources.map((s) => (
                        <li key={s.id}>
                          <Link to={s.url} className="block rounded-lg border border-line bg-bg px-3 py-2 no-underline hover:border-ink">
                            <span className="text-ink underline underline-offset-4">{s.title}</span>
                            <span className="cipher mt-1 block text-sm text-muted">
                              {s.cipher}
                              {s.period ? ` · ${s.period}` : ""}
                              {s.file_access !== "open" ? ` · ${t("assistant.closed")}` : ""}
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {turn.a.suggestions.length > 0 && (
                  <div className="mt-3">
                    <p className="font-semibold">{t("assistant.suggestions")}</p>
                    <div className="mt-1 flex flex-wrap gap-2">
                      {turn.a.suggestions.map((s) => (
                        <button key={s} type="button" className="chip" onClick={() => send(s)}>
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                <p className="mt-3 border-t border-line pt-2 text-sm text-muted">{turn.a.disclaimer}</p>
              </div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      {listening && turns.length > 0 && (
        <p className="mt-3 rounded-lg bg-danger/10 px-3 py-2 font-medium text-danger" role="status">
          {t("voice.listening")}
        </p>
      )}
      {voiceError && (
        <p className="mt-3 text-danger" role="alert">
          {voiceError}
        </p>
      )}
      {speaking && (
        <button type="button" className="btn-ghost mt-3" onClick={hush}>
          <Icon name="stop" size={20} /> {t("voice.stopReading")}
        </button>
      )}
      <form role="search" onSubmit={submit} className="mt-3 flex gap-2">
        <label htmlFor={compact ? "ai-q-w" : "ai-q"} className="sr-only">
          {t("assistant.placeholder")}
        </label>
        <input
          id={compact ? "ai-q-w" : "ai-q"}
          className="input"
          value={q}
          maxLength={500}
          placeholder={t("assistant.placeholder")}
          onChange={(e) => setQ(e.target.value)}
          enterKeyHint="send"
        />
        {voiceAvailable && mic(false)}
        <button type="submit" className="btn-primary btn-icon shrink-0" disabled={ask.isPending} aria-label={t("assistant.send")} title={t("assistant.send")}>
          <Icon name="arrow" size={22} />
        </button>
      </form>
      {!voiceAvailable && <p className="mt-2 text-sm text-muted">{t("voice.unsupported")}</p>}
      <p className="mt-2 text-sm text-muted">{t("assistant.privacy")}</p>
    </div>
  );
}

export function AssistantWidget() {
  const { t } = useT();
  const lp = useLocalePath();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  if (pathname.endsWith("/assistant")) return null;
  if (!open)
    return (
      <button
        type="button"
        className="btn-primary btn-lg fixed bottom-4 right-4 z-40 max-w-[calc(100vw-2rem)] rounded-full px-5 shadow-xl ring-4 ring-bg"
        onClick={() => setOpen(true)}
        title={t("assistant.open")}
      >
        <Icon name="mic" size={24} /> {t("assistant.short")}
      </button>
    );
  return (
    // телефон — на весь экран (крупно и без мелких полей), планшет и шире — окно в углу
    <section
      aria-label={t("assistant.title")}
      className="fixed inset-0 z-50 flex flex-col bg-bg p-4 sm:inset-auto sm:bottom-4 sm:right-4 sm:h-[min(40rem,85vh)] sm:w-[26rem] sm:rounded-xl sm:border sm:border-line sm:shadow-2xl"
    >
      <div className="mb-3 flex items-center justify-between gap-2 border-b border-line pb-3">
        <h2 className="text-[1.25rem]">{t("assistant.title")}</h2>
        <div className="flex gap-2">
          <Link to={lp("/assistant")} className="btn-ghost hidden px-3 sm:inline-flex" onClick={() => setOpen(false)}>
            {t("assistant.fullPage")}
          </Link>
          <button type="button" className="btn-ghost px-4" onClick={() => setOpen(false)}>
            <Icon name="close" size={20} /> {t("common.close")}
          </button>
        </div>
      </div>
      <AssistantChat compact />
    </section>
  );
}

export function AssistantPage() {
  const { t } = useT();
  useEffect(() => {
    document.title = t("assistant.title");
  }, [t]);
  return (
    <div className="container-page py-8 sm:py-10">
      <h1>{t("assistant.title")}</h1>
      <p className="lead mt-2">{t("assistant.lead")}</p>
      <div className="card mt-6 flex h-[75vh] min-h-[32rem] flex-col p-4 sm:p-6">
        <AssistantChat />
      </div>
    </div>
  );
}
