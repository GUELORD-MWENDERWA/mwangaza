// Identité de la plateforme (5.1) : nom, logo, couleurs, support, mentions légales. Lue dans ses
// paramètres par chaque application (`/api/platform/`), jamais écrite dans le code.
import { createContext, use, useState } from "react";

import { Button } from "./components/button";
import { DialogClose, DialogContent, DialogRoot } from "./components/sheet";
import { cn } from "./lib/cn";

/** Ce que renvoie l'API (`Platform`), sans dépendre du client. */
export interface PlatformIdentity {
  name: string;
  short_name: string;
  site_name: string;
  logo: string | null;
  icon: string | null;
  primary_color: string;
  accent_color: string;
  support_phone: string;
  support_email: string;
  legal_notice: string;
}

/** Avant la première réponse sur un appareil neuf : la lampe, sans nom. */
export const NO_PLATFORM: PlatformIdentity = {
  name: "",
  short_name: "",
  site_name: "",
  logo: null,
  icon: null,
  primary_color: "",
  accent_color: "",
  support_phone: "",
  support_email: "",
  legal_notice: "",
};

export const PlatformContext = createContext<PlatformIdentity>(NO_PLATFORM);

export function usePlatform() {
  return use(PlatformContext);
}

/** Couleurs de la plateforme dans le thème (jetons `lake` et `lamp`, teintes calculées comme
 *  celles du design) et icône de l'onglet. Le serveur a vérifié qu'elles restent lisibles. */
export function applyPlatform(platform: PlatformIdentity) {
  if (typeof document === "undefined") return;
  const style = document.documentElement.style;
  const primary = platform.primary_color;
  if (primary) {
    const tint = `color-mix(in srgb, ${primary} 10%, white)`;
    style.setProperty("--color-lake", primary);
    style.setProperty("--color-lake-700", `color-mix(in srgb, ${primary} 76%, black)`);
    style.setProperty("--color-lake-50", tint);
    style.setProperty("--color-info", primary);
    style.setProperty("--color-info-50", tint);
  }
  const accent = platform.accent_color;
  if (accent) {
    style.setProperty("--color-lamp", accent);
    style.setProperty("--color-lamp-soft", `color-mix(in srgb, ${accent} 17%, white)`);
  }
  if (platform.icon) {
    const links = document.querySelectorAll<HTMLLinkElement>(
      'link[rel="icon"], link[rel="apple-touch-icon"]',
    );
    for (const link of links) {
      link.href = platform.icon;
      if (link.rel === "icon") link.type = "image/png";
    }
  }
}

/** Lien vers les mentions légales de la plateforme ; rien si elle n'en a pas. */
export function LegalNotice({
  label,
  closeLabel,
  className,
}: {
  label: string;
  closeLabel: string;
  className?: string;
}) {
  const { legal_notice: text } = usePlatform();
  const [open, setOpen] = useState(false);
  if (!text) return null;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn("cursor-pointer underline-offset-2 hover:underline", className)}
      >
        {label}
      </button>
      <DialogRoot open={open} onOpenChange={setOpen}>
        <DialogContent
          title={label}
          footer={
            <DialogClose asChild>
              <Button variant="outline">{closeLabel}</Button>
            </DialogClose>
          }
        >
          <p className="text-sm whitespace-pre-line text-ink-2">{text}</p>
        </DialogContent>
      </DialogRoot>
    </>
  );
}
