import { useTranslation } from "@mwangaza/i18n";
import { Button, CheckboxField, CodeList, Icon } from "@mwangaza/ui";
import { useState } from "react";

/** Les 8 codes de secours, montrés une seule fois : liste, téléchargement, et « Terminer »
 *  bloqué tant que la personne n'a pas coché qu'elle les a gardés (M1, M4). */
export function RecoveryCodes({
  codes,
  phone,
  onDone,
}: {
  codes: string[];
  /** Compte, écrit en tête du fichier (inconnu pendant la connexion). */
  phone?: string;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const [saved, setSaved] = useState(false);

  const text = [
    phone ? t("auth.setup.fileHeader", { phone }) : t("auth.setup.fileTitle"),
    "",
    ...codes,
    "",
    t("auth.setup.fileHelp"),
    "",
  ].join("\n");

  function download() {
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = t("auth.setup.fileName");
    link.click();
    URL.revokeObjectURL(url);
  }

  /** Imprime seulement les codes (pas l'écran) : feuille à garder en lieu sûr. */
  function print() {
    const frame = document.createElement("iframe");
    frame.setAttribute("aria-hidden", "true");
    frame.style.cssText = "position:fixed;width:0;height:0;border:0";
    document.body.append(frame);
    const sheet = frame.contentDocument;
    if (sheet) {
      const pre = sheet.createElement("pre");
      pre.style.cssText = "font:14pt ui-monospace,Consolas,monospace;line-height:1.8";
      pre.textContent = text;
      sheet.body.append(pre);
      frame.contentWindow?.print();
    }
    frame.remove();
  }

  return (
    <>
      <CodeList codes={codes} />
      <div className="flex flex-wrap gap-2.5">
        <Button variant="outline" onClick={print}>
          <Icon name="print" size={16} />
          {t("auth.setup.print")}
        </Button>
        <Button variant="outline" onClick={download}>
          <Icon name="download" size={16} />
          {t("auth.setup.download")}
        </Button>
      </div>
      <CheckboxField
        id="codes-saved"
        label={t("auth.setup.confirmCodes")}
        checked={saved}
        onCheckedChange={(checked) => setSaved(checked === true)}
        className="text-sm"
      />
      <Button disabled={!saved} onClick={onDone}>
        {t("auth.setup.finish")}
      </Button>
    </>
  );
}
