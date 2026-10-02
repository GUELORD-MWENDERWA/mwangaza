import { formatDay, useTranslation } from "@mwangaza/i18n";
import { formatAmount } from "@mwangaza/money";
import { Avatar, Brand, Button, Card, CardContent, cn, Icon, StatusPill } from "@mwangaza/ui";
import { useRef, useState, type ReactNode } from "react";
import { useNavigate, useOutletContext, useSearchParams } from "react-router";

import type { Account } from "../../lib/account";
import { shouldOfferInstall } from "../../lib/install";

const STEPS = ["children", "payments", "news"] as const;
type Step = (typeof STEPS)[number];

/** Guide du parent (maquette `guide`, I3, M20) : juste après l'activation (`?first=1`, puis
 *  « Installer » s'il est proposé), ou depuis Profil → « Revoir le guide ». « Suivant » ou glisser
 *  à gauche / à droite. Exemples fixes : rien ne dépend des données de la famille. */
export function GuidePage() {
  const { t } = useTranslation();
  const account = useOutletContext<Account>();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const first = params.has("first");
  const [index, setIndex] = useState(0);
  const touchX = useRef<number | null>(null);
  const step = STEPS[index]!;
  const last = index === STEPS.length - 1;

  const leave = () =>
    void navigate(first && shouldOfferInstall() ? "/install" : "/", { replace: true });
  const move = (delta: number) =>
    setIndex((current) => Math.max(0, Math.min(STEPS.length - 1, current + delta)));

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-basalt px-5 pt-7 pb-8 text-basalt-ink">
        <div className="mx-auto max-w-[640px]">
          <Brand />
          <h1 className="mt-5 text-[1.5rem]">{t("portal.guide.title", { name: account.name })}</h1>
          <p className="mt-1.5 text-basalt-muted">
            {t(first ? "portal.guide.activated" : "portal.guide.again")}
          </p>
        </div>
      </header>
      <main className="mx-auto flex max-w-[640px] flex-col gap-4 px-4 py-5">
        <Card>
          <CardContent
            className="flex flex-col items-center gap-3.5 px-5 py-[26px] text-center"
            onTouchStart={(event) => (touchX.current = event.touches[0]?.clientX ?? null)}
            onTouchEnd={(event) => {
              const start = touchX.current;
              const end = event.changedTouches[0]?.clientX;
              touchX.current = null;
              if (start === null || end === undefined || Math.abs(end - start) < 50) return;
              move(end < start ? 1 : -1);
            }}
          >
            <span className="text-[.78rem] text-ink-3" aria-live="polite">
              {t("portal.guide.step", { step: index + 1, total: STEPS.length })}
            </span>
            <Example step={step} />
            <h2>{t(`portal.guide.steps.${step}.title`)}</h2>
            <p className="text-[.88rem] text-ink-3">{t(`portal.guide.steps.${step}.text`)}</p>
            <span aria-hidden="true" className="flex gap-1.5">
              {STEPS.map((key, dot) => (
                <i
                  key={key}
                  className={cn(
                    "h-2 rounded-full",
                    dot === index ? "w-[22px] bg-lake" : "w-2 bg-line",
                  )}
                />
              ))}
            </span>
            <Button size="lg" className="w-full" onClick={() => (last ? leave() : move(1))}>
              {t(last ? "portal.guide.start" : "portal.guide.next")}
            </Button>
            {!last && (
              <button
                type="button"
                onClick={leave}
                className="min-h-11 cursor-pointer text-[.88rem] text-lake underline"
              >
                {t("portal.guide.skip")}
              </button>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="text-[.88rem]">
            <b>{t("portal.guide.stepsTitle")}</b>{" "}
            {STEPS.map(
              (key, number) => `${number + 1}. ${t(`portal.guide.steps.${key}.summary`)}`,
            ).join(" · ")}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}

/** Illustration de l'étape : un exemple fixe, décoratif (le texte dessous dit tout). */
function Example({ step }: { step: Step }) {
  const { t, i18n } = useTranslation();
  const frame = (children: ReactNode) => (
    <div
      aria-hidden="true"
      className="flex w-full flex-col gap-2 rounded-xl border border-line p-3 text-left text-[.88rem]"
    >
      {children}
    </div>
  );
  if (step === "children") {
    return frame(
      ([1, 2] as const).map((number) => (
        <div key={number} className="flex items-center gap-2.5">
          <Avatar text={t(`portal.guide.example.child${number}`).slice(0, 1)} />
          <span className="min-w-0 flex-1">
            <b>{t(`portal.guide.example.child${number}`)}</b>
            <span className="block text-ink-3">
              {t(`portal.guide.example.class${number}`)} ·{" "}
              {t(`portal.guide.example.school${number}`)}
            </span>
          </span>
        </div>
      )),
    );
  }
  if (step === "payments") {
    return frame(
      <>
        <div className="flex items-center justify-between gap-2">
          <b>{t("portal.guide.example.fee")}</b>
          <StatusPill>{formatDay("2027-01-15", i18n.language)}</StatusPill>
        </div>
        <div className="flex justify-between gap-2">
          <span>{t("portal.guide.example.rest")}</span>
          <b className="tabular-nums">{formatAmount(12000, "USD")}</b>
        </div>
        <div className="flex items-center justify-between gap-2 border-t border-line pt-2">
          <span>{t("portal.guide.example.receipt")}</span>
          <span className="inline-flex items-center gap-1 rounded-field border border-line px-2.5 py-1 font-bold">
            <Icon name="download" size={16} />
            {t("portal.child.pdf")}
          </span>
        </div>
      </>,
    );
  }
  return frame(
    <>
      <div className="flex items-start gap-2.5">
        <Icon name="megaphone" size={20} className="mt-0.5 shrink-0 text-lake" />
        <span>
          <b>{t("portal.guide.example.announcement")}</b>
          <span className="block text-ink-3">{t("portal.guide.example.announcementText")}</span>
        </span>
      </div>
      <div className="flex items-center gap-2.5 border-t border-line pt-2">
        <Icon name="phone" size={20} className="shrink-0 text-lake" />
        <span>{t("portal.guide.example.phone")}</span>
      </div>
    </>,
  );
}
