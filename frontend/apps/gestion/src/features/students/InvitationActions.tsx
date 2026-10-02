// Lettre et message d'invitation au portail d'une famille (H7) : liste des invitations et fiche
// famille, avec `students.edit`, seulement si la famille peut encore activer son compte. Le
// serveur note chaque lettre imprimée et chaque message ouvert (ils contiennent le code famille).
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { Banner, Button, DialogContent, DialogRoot, Icon, Skeleton, Textarea } from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage } from "../../lib/errors";
import { familyLetterUrl, shareLinks } from "./invitations";

export function InvitationActions({
  familyId,
  name,
  long = false,
}: {
  familyId: string;
  name: string;
  /** Libellés complets (fiche famille) plutôt que courts (ligne d'une liste). */
  long?: boolean;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const message = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/families/{id}/invitation-message/", {
          params: { path: { id: familyId } },
        }),
      ),
  });
  const show = () => {
    setCopied(false);
    setOpen(true);
    message.mutate();
  };
  const copy = (text: string) =>
    void navigator.clipboard?.writeText(text).then(() => setCopied(true));
  const links = message.data && shareLinks(message.data.phone, message.data.text);
  return (
    <>
      <Button asChild size="sm" variant="outline">
        <a href={familyLetterUrl(familyId)} target="_blank" rel="noopener">
          <Icon name="print" size={14} />
          {t(long ? "students.invitations.familyLetter" : "students.invitations.letter")}
        </a>
      </Button>
      <Button size="sm" variant="outline" onClick={show}>
        <Icon name="share" size={14} />
        {t(long ? "students.invitations.familyMessage" : "students.invitations.message")}
      </Button>
      <DialogRoot open={open} onOpenChange={setOpen}>
        <DialogContent
          title={t("students.invitations.messageTitle", { name })}
          footer={
            message.data &&
            links && (
              <>
                <Button variant="outline" onClick={() => copy(message.data.text)}>
                  <Icon name={copied ? "check" : "file"} size={16} />
                  {t(copied ? "students.invitations.copied" : "students.invitations.copy")}
                </Button>
                <Button asChild variant="outline">
                  <a href={links.sms}>
                    <Icon name="phone" size={16} />
                    {t("students.invitations.sms")}
                  </a>
                </Button>
                <Button asChild>
                  <a href={links.whatsapp} target="_blank" rel="noopener">
                    <Icon name="share" size={16} />
                    {t("students.invitations.whatsapp")}
                  </a>
                </Button>
              </>
            )
          }
        >
          {message.isPending && <Skeleton label={t("common.loading")} />}
          {message.isError && <Banner tone="due">{errorMessage(message.error, t)}</Banner>}
          {message.data && (
            <div className="flex flex-col gap-3">
              <Textarea
                readOnly
                rows={7}
                value={message.data.text}
                aria-label={t("students.invitations.messageLabel")}
              />
              <p className="text-sm text-ink-3">{t("students.invitations.messageHelp")}</p>
            </div>
          )}
        </DialogContent>
      </DialogRoot>
    </>
  );
}
