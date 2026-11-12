import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useLocation } from "react-router-dom";
import { useLang } from "../app/lang";
import { useT } from "../app/useT";
import { useTitle } from "../app/useTitle";
import { TranslationNotice } from "../components/ui/Badges";
import { Breadcrumbs } from "../components/ui/Breadcrumbs";
import { ExternalLink } from "../components/ui/ExternalLink";
import { Icon } from "../components/ui/Icon";
import { ErrorState, Loading } from "../components/ui/States";
import { apiGet } from "../lib/api";
import type { FaqGroup } from "../lib/types";

/**
 * Отзыв о работе сайта — единственная публичная форма отправки. Не является официальным обращением
 * (Д §1): нет заявлений, заказов, загрузки документов; ПДн — только необязательный e-mail с согласием.
 */
export function FeedbackForm() {
  const { t } = useT();
  const { pathname } = useLocation();
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);
  const send = useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, page: pathname, email: email.trim() || null, consent }),
      });
      if (res.status === 429) throw new Error(t("feedback.tooMany"));
      if (!res.ok) throw new Error(t("feedback.error"));
      return (await res.json()) as { notice: string };
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (email.trim() && !consent) {
      setClientError(t("feedback.consentRequired"));
      return;
    }
    setClientError(null);
    send.mutate();
  };

  if (send.isSuccess) {
    return (
      <div className="card flex gap-3 p-5" role="status">
        <Icon name="check" className="shrink-0 text-ok" />
        <p>{send.data.notice}</p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="card space-y-4 p-5" aria-labelledby="feedback-h" data-form="feedback">
      <h2 id="feedback-h" className="text-xl">{t("feedback.title")}</h2>
      <div role="note" className="flex gap-2 rounded-lg border border-warn/50 bg-warn/10 p-3 text-sm">
        <Icon name="info" size={18} className="mt-0.5 shrink-0 text-warn" />
        <p>
          <strong>{t("feedback.disclaimer")}</strong>{" "}
          <ExternalLink href="https://eotinish.kz">{t("feedback.eotinish")}</ExternalLink>
        </p>
      </div>
      <div>
        <label htmlFor="fb-message" className="mb-1 block font-medium">{t("feedback.message")}</label>
        <textarea
          id="fb-message"
          className="input min-h-28"
          required
          minLength={10}
          maxLength={2000}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          aria-describedby="fb-hint"
        />
        <p id="fb-hint" className="mt-1 text-xs text-muted">{t("feedback.messageHint")}</p>
      </div>
      <div>
        <label htmlFor="fb-email" className="mb-1 block font-medium">{t("feedback.email")}</label>
        <input id="fb-email" type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={255} autoComplete="email" />
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" className="mt-1" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        {t("feedback.consent")}
      </label>
      {(clientError || send.isError) && (
        <p className="text-sm text-danger" role="alert">{clientError ?? (send.error as Error).message}</p>
      )}
      <button type="submit" className="btn-primary" disabled={send.isPending}>
        {send.isPending ? t("feedback.sending") : t("feedback.submit")}
      </button>
    </form>
  );
}

export function FaqPage() {
  const { t } = useT();
  const lang = useLang();
  useTitle(t("faqPage.title"), t("faqPage.lead"));
  const q = useQuery({ queryKey: ["faq", lang], queryFn: () => apiGet<FaqGroup[]>("/faq", lang) });
  return (
    <div className="container-page py-6">
      <Breadcrumbs items={[{ label: t("faqPage.title") }]} />
      <h1 className="text-3xl">{t("faqPage.title")}</h1>
      <p className="mt-2 text-muted">{t("faqPage.lead")}</p>
      <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-[1fr_24rem]">
        <div className="space-y-8">
          {q.isLoading && <Loading />}
          {q.isError && <ErrorState error={q.error} onRetry={() => void q.refetch()} />}
          {q.data?.map((g) => (
            <section key={g.slug} aria-labelledby={`faq-${g.slug}`}>
              <h2 id={`faq-${g.slug}`} className="text-2xl">{g.title}</h2>
              <div className="mt-3 space-y-2">
                {g.items.map((item) => (
                  <details key={item.id} className="card group p-4">
                    <summary className="cursor-pointer list-none font-medium marker:hidden">
                      <span className="flex items-start justify-between gap-3">
                        {item.question}
                        <Icon name="right" size={18} className="mt-0.5 shrink-0 transition-transform group-open:rotate-90" />
                      </span>
                    </summary>
                    <p className="mt-3 leading-relaxed">{item.answer}</p>
                    {item.translation.is_fallback && (
                      <div className="mt-2">
                        <TranslationNotice info={item.translation} />
                      </div>
                    )}
                  </details>
                ))}
              </div>
            </section>
          ))}
        </div>
        <aside>
          <FeedbackForm />
        </aside>
      </div>
    </div>
  );
}
