import { changeLanguage, LANGUAGES, useTranslation } from "@mwangaza/i18n";
import { Brand, cn } from "@mwangaza/ui";
import type { ReactNode } from "react";

/** Écrans sans compte connecté (maquettes `connexion`, `activation`, `mot-de-passe-oublie`) :
 *  en-tête basalte avec la marque et le titre, cartes en dessous, langues en bas. */
export function AuthFrame({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background">
      <header className="bg-basalt px-4 pt-6 pb-8 text-basalt-ink">
        <div className="mx-auto flex max-w-[440px] flex-col gap-5">
          <Brand large />
          <div className="flex flex-col gap-2">
            <h1 className="text-[1.75rem] leading-tight">{title}</h1>
            <p className="text-[1.05rem] text-basalt-soft">{subtitle}</p>
          </div>
        </div>
      </header>
      <main className="mx-auto flex max-w-[440px] flex-col gap-4 px-4 py-4">
        {children}
        <LanguageLinks />
      </main>
    </div>
  );
}

/** « Français · English » en bas de page. */
export function LanguageLinks({ className }: { className?: string }) {
  const { t, i18n } = useTranslation();
  return (
    <nav
      aria-label={t("portal.languages")}
      className={cn("flex justify-center gap-1 text-sm text-ink-3", className)}
    >
      {LANGUAGES.map((language, index) => (
        <span key={language} className="flex items-center gap-1">
          {index > 0 && <span aria-hidden="true">·</span>}
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
    </nav>
  );
}
