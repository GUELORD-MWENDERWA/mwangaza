import { changeLanguage, LANGUAGES, useTranslation } from "@mwangaza/i18n";
import { Brand, cn, LegalNotice } from "@mwangaza/ui";
import type { ReactNode } from "react";

/** Écrans sans compte connecté (maquettes `connexion`, `activation`, `mot-de-passe-oublie`) :
 *  en-tête bleu nuit avec la marque et le titre, cartes en dessous, langues en bas ; sur
 *  ordinateur, panneau bleu nuit à gauche et cartes centrées à droite. */
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
    <div className="min-h-screen bg-background lg:grid lg:grid-cols-2">
      <header className="bg-night px-4 pt-6 pb-8 text-night-ink lg:flex lg:items-center lg:px-16 lg:py-14">
        <div className="mx-auto flex max-w-[440px] flex-col gap-5 lg:mx-0 lg:max-w-[460px] lg:gap-8">
          <Brand large inverse />
          <div className="flex flex-col gap-2 lg:gap-3">
            <h1 className="text-2xl leading-tight lg:text-3xl">{title}</h1>
            <p className="text-base text-night-soft">{subtitle}</p>
          </div>
        </div>
      </header>
      <main className="mx-auto flex max-w-[440px] flex-col gap-4 px-4 py-4 lg:w-full lg:max-w-[488px] lg:justify-center lg:px-6 lg:py-12">
        {children}
        <LanguageLinks />
      </main>
    </div>
  );
}

/** « Français · English · Mentions légales » en bas de page. */
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
      <LegalNotice
        label={t("common.legalNotice")}
        closeLabel={t("common.close")}
        className="before:mr-1 before:content-['·']"
      />
    </nav>
  );
}
