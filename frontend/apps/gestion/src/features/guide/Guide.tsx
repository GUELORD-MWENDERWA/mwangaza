// Guide de première connexion (maquette `guide-premiere-connexion`, M20) : démarre à la première
// ouverture de la Gestion par un caissier ou un comptable, reprend à la même étape (croix : fermé
// jusqu'à la prochaine ouverture), « Passer le guide » le termine, « Aide et guide » le relance. L'élément de l'étape est entouré, le reste assombri ; la page reste
// utilisable (le calque ne prend pas les clics). Sans réseau aussi : rien ne vient du serveur.
import { useTranslation } from "@mwangaza/i18n";
import { Button, cn, Icon } from "@mwangaza/ui";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useLocation, useNavigate } from "react-router";

import type { Me } from "../../lib/queries";
import {
  guideFor,
  guideSteps,
  readProgress,
  saveProgress,
  type GuideKey,
  type GuideStep,
} from "./guides";

const GuideContext = createContext<{ restart: (() => void) | null }>({ restart: null });

/** « Aide et guide » du menu : `restart` est nul si le compte n'a pas de guide. */
export const useGuide = () => useContext(GuideContext);

export function GuideProvider({ me, children }: { me: Me; children: ReactNode }) {
  const navigate = useNavigate();
  const guide = guideFor(me);
  const steps = useMemo(() => (guide ? guideSteps(me, guide) : []), [me, guide]);
  // Étape affichée ; null : guide terminé, passé ou fermé jusqu'à la prochaine ouverture.
  const [step, setStep] = useState<number | null>(() => {
    if (!guide || steps.length === 0) return null;
    const progress = readProgress(me.id, guide);
    if (progress?.done) return null;
    return Math.min(progress?.step ?? 0, steps.length - 1);
  });

  const go = useCallback(
    (index: number) => {
      if (!guide) return;
      saveProgress(me.id, guide, { step: index, done: false });
      setStep(index);
      void navigate(steps[index]!.path);
    },
    [guide, me.id, navigate, steps],
  );

  // À l'ouverture de l'application sur l'accueil : l'écran de l'étape. Ailleurs (adresse ouverte
  // exprès, page rechargée), l'utilisateur reste où il est.
  const { pathname } = useLocation();
  const opened = useRef(false);
  useEffect(() => {
    if (opened.current) return;
    opened.current = true;
    if (pathname === "/" && step !== null) void navigate(steps[step]!.path);
  }, [navigate, pathname, step, steps]);

  const finish = () => {
    if (guide) saveProgress(me.id, guide, { step: 0, done: true });
    setStep(null);
  };

  const context = useMemo(
    () => ({ restart: guide && steps.length > 0 ? () => go(0) : null }),
    [go, guide, steps.length],
  );
  const current = step === null ? undefined : steps[step];

  return (
    <GuideContext.Provider value={context}>
      {children}
      {guide && current && (
        <Coach
          guide={guide}
          step={current}
          index={step!}
          total={steps.length}
          onNext={() => (step! + 1 < steps.length ? go(step! + 1) : finish())}
          onSkip={finish}
          onClose={() => setStep(null)}
        />
      )}
    </GuideContext.Provider>
  );
}

const GAP = 16;

function Coach({
  guide,
  step,
  index,
  total,
  onNext,
  onSkip,
  onClose,
}: {
  guide: GuideKey;
  step: GuideStep;
  index: number;
  total: number;
  onNext: () => void;
  onSkip: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const titleId = useId();
  const { rect, width, height } = useTarget(step.target);
  const cardWidth = Math.min(340, width - 2 * GAP);
  const last = index + 1 === total;
  const texts = (
    t(`guide.${guide}`, { returnObjects: true }) as Record<string, { title: string; text: string }>
  )[step.key]!;

  // Sous l'élément s'il est dans la moitié haute de l'écran, sinon au-dessus ; sans élément
  // visible (ex. montant avant le choix d'un élève, menu caché sur téléphone) : en bas, centré.
  const below = rect ? rect.top < height / 2 : false;
  const left = rect
    ? Math.max(GAP, Math.min(rect.left, width - cardWidth - GAP))
    : (width - cardWidth) / 2;
  const position = rect
    ? below
      ? { top: rect.bottom + GAP, left }
      : { bottom: height - rect.top + GAP, left }
    : { bottom: GAP, left };
  const arrow = rect ? Math.max(16, Math.min(rect.left + 24 - left, cardWidth - 32)) : null;

  return (
    <>
      {rect && (
        <div
          aria-hidden="true"
          className="pointer-events-none fixed z-40 rounded-[10px] shadow-[0_0_0_4px_var(--color-lamp),0_0_0_100vmax_rgb(26_34_51/.55)]"
          style={{
            top: rect.top - 6,
            left: rect.left - 6,
            width: rect.width + 12,
            height: rect.height + 12,
          }}
        />
      )}
      <section
        role="dialog"
        aria-labelledby={titleId}
        className="fixed z-50 rounded-card bg-card px-[18px] py-4 shadow-[0_12px_40px_rgb(0_0_0/.25)]"
        style={{ ...position, width: cardWidth }}
      >
        {arrow !== null && (
          <span
            aria-hidden="true"
            className={cn("absolute size-4 rotate-45 bg-card", below ? "-top-2" : "-bottom-2")}
            style={{ left: arrow }}
          />
        )}
        <div className="flex items-start justify-between gap-2">
          <span className="text-[.78rem] text-ink-3">
            {t("guide.progress", {
              guide: t(`guide.names.${guide}`),
              step: index + 1,
              total,
            })}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="-m-2.5 grid size-11 cursor-pointer place-items-center text-ink-3"
          >
            <Icon name="x" size={16} />
            <span className="sr-only">{t("guide.close")}</span>
          </button>
        </div>
        <h3 id={titleId} className="mt-1.5">
          {texts.title}
        </h3>
        <p className="mt-1.5 text-sm">{texts.text}</p>
        <div className="mt-3 flex items-center justify-between gap-2">
          <span aria-hidden="true" className="flex gap-[5px]">
            {Array.from({ length: total }, (_, dot) => (
              <i
                key={dot}
                className={cn(
                  "size-2 rounded-full",
                  dot < index ? "bg-ok" : dot === index ? "bg-lake" : "bg-line",
                )}
              />
            ))}
          </span>
          <span className="flex flex-wrap justify-end gap-1">
            {!last && (
              <Button variant="ghost" onClick={onSkip}>
                {t("guide.skip")}
              </Button>
            )}
            <Button onClick={onNext}>{t(last ? "guide.finish" : "guide.next")}</Button>
          </span>
        </div>
      </section>
    </>
  );
}

/** Position de l'élément `data-guide` (il peut paraître, bouger ou disparaître) et taille de
 *  l'écran, relues régulièrement ; ramené au centre de l'écran la première fois qu'il paraît. */
function useTarget(target: string) {
  const [state, setState] = useState<{ rect: DOMRect | null; width: number; height: number }>(
    () => ({ rect: null, width: window.innerWidth, height: window.innerHeight }),
  );
  const shown = useRef(false);

  useEffect(() => {
    shown.current = false;
    const measure = () => {
      const element = document.querySelector(`[data-guide="${target}"]`);
      const box = element?.getBoundingClientRect();
      const rect = box && box.width > 0 && box.height > 0 ? box : null;
      if (element && rect && !shown.current) {
        shown.current = true;
        element.scrollIntoView({ block: "center" });
      }
      setState((previous) =>
        sameBox(previous.rect, rect) &&
        previous.width === window.innerWidth &&
        previous.height === window.innerHeight
          ? previous
          : { rect, width: window.innerWidth, height: window.innerHeight },
      );
    };
    measure();
    const timer = window.setInterval(measure, 200);
    window.addEventListener("scroll", measure, true);
    window.addEventListener("resize", measure);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("scroll", measure, true);
      window.removeEventListener("resize", measure);
    };
  }, [target]);

  return state;
}

function sameBox(a: DOMRect | null, b: DOMRect | null) {
  if (!a || !b) return a === b;
  return a.top === b.top && a.left === b.left && a.width === b.width && a.height === b.height;
}
