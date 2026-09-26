// Pages d'état (M8) : ce qui se passe, pourquoi, et quoi faire. Dans la coquille quand le compte
// est connecté (menu visible), sinon seules sur la page (`StandaloneStatus`).
import { ApiError } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { Brand, Button, StateCard, Tag } from "@mwangaza/ui";
import type { ReactNode } from "react";
import { isRouteErrorResponse, Link, useLocation, useRouteError } from "react-router";

/** Page d'état seule, hors de la coquille (avant la connexion, école suspendue…). */
export function StandaloneStatus({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-screen place-items-center bg-surface p-4">
      <div className="flex w-full max-w-[480px] flex-col gap-4">
        <Brand className="self-center" />
        {children}
      </div>
    </main>
  );
}

function HomeButton() {
  const { t } = useTranslation();
  return (
    <Button asChild>
      <Link to="/">{t("status.home")}</Link>
    </Button>
  );
}

/** 403 : jamais de données, même partielles (le serveur refuse de toute façon). */
export function Forbidden({ page }: { page?: string }) {
  const { t } = useTranslation();
  return (
    <StateCard
      icon="lock"
      tone="due"
      title={t("status.forbidden.title")}
      tag={<Tag>{t("status.forbidden.tag")}</Tag>}
      actions={<HomeButton />}
    >
      {page ? t("status.forbidden.text", { page }) : t("status.forbidden.generic")}
    </StateCard>
  );
}

export function NotFound() {
  const { t } = useTranslation();
  return (
    <StateCard
      icon="search"
      tone="gray"
      title={t("status.notFound.title")}
      tag={<Tag>{t("status.notFound.tag")}</Tag>}
      actions={<HomeButton />}
    >
      {t("status.notFound.text")}
    </StateCard>
  );
}

/** Erreur du serveur ou de l'application. Pas encore de référence : pas de suivi d'erreurs. */
export function ErrorState({ status, onRetry }: { status?: number; onRetry: () => void }) {
  const { t } = useTranslation();
  return (
    <StateCard
      icon="alert"
      tone="warn"
      title={t("status.error.title")}
      tag={status ? <Tag>{t("status.error.tag", { status })}</Tag> : undefined}
      actions={
        <Button variant="outline" onClick={onRetry}>
          {t("common.retry")}
        </Button>
      }
    >
      {t("status.error.text")}
    </StateCard>
  );
}

export function Offline({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation();
  return (
    <StateCard
      icon="wifioff"
      tone="warn"
      title={t("status.offline.title")}
      actions={
        <Button variant="outline" onClick={onRetry}>
          {t("common.retry")}
        </Button>
      }
    >
      {t("status.offline.text")}
    </StateCard>
  );
}

/** A1 : aucune donnée de l'école ; le serveur refuse tout à son adresse (même la déconnexion). */
export function Suspended() {
  const { t } = useTranslation();
  return (
    <StateCard icon="shield" tone="gray" title={t("status.suspended.title")}>
      {t("status.suspended.text")}
    </StateCard>
  );
}

export function NoSchool() {
  const { t } = useTranslation();
  return (
    <StateCard icon="school" tone="gray" title={t("status.noSchool.title")}>
      {t("status.noSchool.text")}
    </StateCard>
  );
}

/** Session fermée pendant le travail (délai, mot de passe changé ailleurs…) : se reconnecter
 *  ramène à la page où l'on était. */
export function SessionExpired() {
  const { t } = useTranslation();
  const { pathname, search } = useLocation();
  const next = `${pathname}${search}`;
  return (
    <StateCard
      icon="clock"
      tone="lake"
      title={t("status.sessionExpired.title")}
      actions={
        <Button asChild>
          <Link
            to={next === "/" ? "/login" : `/login?next=${encodeURIComponent(next)}`}
            reloadDocument
          >
            {t("status.sessionExpired.action")}
          </Link>
        </Button>
      }
    >
      {t("status.sessionExpired.text")}
    </StateCard>
  );
}

/** Entrée du menu dont l'écran arrive avec une tâche suivante du plan. */
export function ComingSoon({ page }: { page: string }) {
  const { t } = useTranslation();
  return (
    <StateCard
      icon="sparkle"
      tone="lake"
      title={t("status.comingSoon.title")}
      actions={<HomeButton />}
    >
      {t("status.comingSoon.text", { page })}
    </StateCard>
  );
}

/** Erreur imprévue pendant l'affichage d'un écran (`errorElement` des routes). */
export function RouteError({ standalone = false }: { standalone?: boolean }) {
  const error = useRouteError();
  const content =
    isRouteErrorResponse(error) && error.status === 404 ? (
      <NotFound />
    ) : (
      <ErrorState
        status={error instanceof ApiError && error.status > 0 ? error.status : undefined}
        onRetry={() => window.location.reload()}
      />
    );
  return standalone ? <StandaloneStatus>{content}</StandaloneStatus> : content;
}
