import { changeLanguage, LANGUAGES, useTranslation } from "@mwangaza/i18n";
import { Brand, cn, LegalNotice, SchoolBadge } from "@mwangaza/ui";
import type { ReactNode } from "react";

import type { School } from "../../lib/queries";

/** Écrans hors application (`.authgrid` des maquettes) : panneau basalte avec l'école à gauche,
 *  formulaire à droite ; une colonne sous 900 px. */
export function AuthFrame({
  school,
  width = 400,
  children,
}: {
  school: School | null;
  width?: number;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className="grid min-h-screen grid-cols-1 grid-rows-[auto_1fr] min-[900px]:grid-cols-2 min-[900px]:grid-rows-1">
      <aside className="flex flex-col justify-between gap-3 bg-basalt px-4 py-5 text-basalt-ink min-[900px]:gap-6 min-[900px]:p-12">
        <Brand large />
        {/* Téléphone : l'école en une ligne sous la marque (le grand encadré est masqué). */}
        {school && (
          <div className="flex items-center gap-2.5 min-[900px]:hidden">
            <SchoolBadge
              code={school.code}
              name={school.name}
              color={school.primary_color}
              textColor={school.text_color}
              logo={school.logo}
              size="sm"
            />
            <b>{school.name}</b>
          </div>
        )}
        <div className="hidden max-w-[420px] flex-col gap-3 min-[900px]:flex">
          {school ? (
            <>
              <SchoolBadge
                code={school.code}
                name={school.name}
                color={school.primary_color}
                textColor={school.text_color}
                logo={school.logo}
                size="lg"
              />
              <h1 className="text-3xl">{school.name}</h1>
              <p className="text-basalt-soft">{t("auth.side.tagline")}</p>
            </>
          ) : (
            <>
              <h1 className="text-3xl">{t("auth.side.genericTitle")}</h1>
              <p className="text-basalt-soft">{t("auth.side.genericText")}</p>
            </>
          )}
        </div>
        <LanguageLinks className="hidden min-[900px]:flex" />
      </aside>
      <main className="flex items-start justify-center bg-white px-4 py-5 min-[900px]:items-center min-[900px]:p-8">
        <div className="flex w-full flex-col gap-3" style={{ maxWidth: width }}>
          {children}
          <LanguageLinks className="mt-4 text-ink-3 min-[900px]:hidden" />
        </div>
      </main>
    </div>
  );
}

/** « {code}.<domaine> · Français | English · Mentions légales » en bas du panneau. */
function LanguageLinks({ className }: { className?: string }) {
  const { t, i18n } = useTranslation();
  return (
    <nav
      aria-label={t("auth.side.languages")}
      className={cn("flex flex-wrap items-center gap-1 text-sm text-basalt-muted", className)}
    >
      <span>{window.location.host} ·</span>
      {LANGUAGES.map((language, index) => (
        <span key={language} className="flex items-center gap-1">
          {index > 0 && <span aria-hidden="true">|</span>}
          <button
            type="button"
            lang={language}
            aria-pressed={i18n.language === language}
            onClick={() => void changeLanguage(language)}
            className={cn(
              "cursor-pointer underline-offset-2 hover:underline",
              i18n.language === language && "font-bold",
            )}
          >
            {t(`common.languages.${language}`)}
          </button>
        </span>
      ))}
      <LegalNotice
        label={t("common.legalNotice")}
        closeLabel={t("common.close")}
        className="before:mr-1 before:content-['·']"
      />
    </nav>
  );
}
