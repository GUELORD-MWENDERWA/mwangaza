import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { Button, DialogContent, DialogRoot } from "@mwangaza/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ARTICLE_TEXT } from "./HelpButton";

const storageKey = (userId: string) => `mwangaza.whatsnew.${userId}`;

function seenDay(userId: string): string {
  try {
    return localStorage.getItem(storageKey(userId)) ?? "";
  } catch {
    return "";
  }
}

function markSeen(userId: string, day: string) {
  try {
    localStorage.setItem(storageKey(userId), day);
  } catch {
    // Stockage indisponible : le dialogue reviendra à la prochaine ouverture.
  }
}

/** « Quoi de neuf » (maquette `quoi-de-neuf`) : la dernière mise en ligne qui concerne cette
 *  application, une fois par compte et par appareil ; rien n'est écrit sur le serveur.
 *  `enabled` faux (guide de première connexion en cours, session support) : rien n'est montré. */
export function WhatsNew({
  app,
  userId,
  enabled,
}: {
  app: "gestion" | "portail";
  userId: string;
  enabled: boolean;
}) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language.startsWith("en") ? "en" : "fr";
  const [dismissed, setDismissed] = useState(false);
  const news = useQuery({
    queryKey: ["help", "whats-new", app, lang],
    enabled,
    retry: false,
    staleTime: 3_600_000,
    queryFn: () => call(api.GET("/api/help/whats-new/", { params: { query: { app, lang } } })),
  });
  const entry = news.data;
  if (!enabled || !entry || dismissed || seenDay(userId) >= entry.day) return null;
  const date = new Intl.DateTimeFormat(lang, { dateStyle: "long", timeZone: "UTC" }).format(
    new Date(entry.day),
  );
  const done = () => {
    markSeen(userId, entry.day);
    setDismissed(true);
  };
  return (
    <DialogRoot open onOpenChange={(open) => !open && done()}>
      <DialogContent
        title={t("help.whatsNew", { date })}
        footer={
          <>
            <Button variant="ghost" asChild>
              <a href={entry.url} target="_blank" rel="noopener noreferrer" onClick={done}>
                {t("help.readAll")}
              </a>
            </Button>
            <Button onClick={done}>{t("help.understood")}</Button>
          </>
        }
      >
        <p className="text-base font-semibold">{entry.summary}</p>
        <div className={ARTICLE_TEXT} dangerouslySetInnerHTML={{ __html: entry.html }} />
      </DialogContent>
    </DialogRoot>
  );
}
