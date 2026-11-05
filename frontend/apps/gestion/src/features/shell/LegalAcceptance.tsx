// Acceptation des conditions de la plateforme (CTR.1, maquette `gestion/conditions-acceptation`) :
// à l'ouverture, l'administrateur principal (droit « rôles ») voit les versions que l'école n'a pas
// encore acceptées. « Plus tard » ferme jusqu'à la prochaine ouverture ; la date, le nom et
// l'adresse IP de l'acceptation sont gardés par le serveur. Les autres membres ne voient rien.
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, CheckboxField, DialogContent, DialogRoot, Tag } from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { can } from "../../lib/permissions";
import type { Me } from "../../lib/queries";

type Doc = Schemas["LegalDocument"];
const KEY = ["legal", "pending"];

function usePendingDocs(me: Me) {
  // Une session support n'accepte jamais au nom de l'école.
  const allowed = can(me, ["roles.manage"]) && !me.support;
  const pending = useQuery({
    queryKey: KEY,
    queryFn: () => call(api.GET("/api/legal/pending/")),
    enabled: allowed,
    retry: false,
    staleTime: Infinity,
  });
  return { allowed, pending };
}

/** Des conditions attendent l'administrateur (ou la réponse n'est pas encore là) : les autres
 *  fenêtres d'accueil, comme « Quoi de neuf », attendent leur tour. */
export function useLegalPending(me: Me) {
  const { allowed, pending } = usePendingDocs(me);
  return allowed && (pending.isPending || (pending.data?.length ?? 0) > 0);
}

export function LegalAcceptance({ me }: { me: Me }) {
  const { allowed, pending } = usePendingDocs(me);
  const [later, setLater] = useState(false);
  if (!allowed || later || !pending.data?.length) return null;
  return <Dialog docs={pending.data} onLater={() => setLater(true)} />;
}

function Dialog({ docs, onLater }: { docs: Doc[]; onLater: () => void }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [index, setIndex] = useState(0);
  const [agreed, setAgreed] = useState(false);
  const doc = docs[index] ?? docs[0]!;
  const english = i18n.language.startsWith("en");
  const accept = useMutation({
    mutationFn: () => call(api.POST("/api/legal/accept/", { body: { document: doc.id } })),
    onSuccess: () => {
      setAgreed(false);
      // Au suivant, s'il y en a ; sinon la liste se vide et la fenêtre disparaît.
      if (index + 1 < docs.length) setIndex(index + 1);
      void queryClient.invalidateQueries({ queryKey: KEY });
      if (index + 1 >= docs.length) onLater();
    },
  });
  return (
    <DialogRoot open onOpenChange={(open) => !open && onLater()}>
      <DialogContent
        title={t("legalAcceptance.title")}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onLater}>
              {t("legalAcceptance.later")}
            </Button>
            <Button disabled={!agreed || accept.isPending} onClick={() => accept.mutate()}>
              {t("legalAcceptance.accept")}
            </Button>
          </div>
        }
      >
        <p>{t("legalAcceptance.intro")}</p>
        <div className="flex flex-wrap gap-1.5">
          {docs.map((d, n) => (
            <Tag key={d.id} className={n === index ? "" : "opacity-60"}>
              {english ? d.title_en : d.title_fr} · v{d.version}
            </Tag>
          ))}
        </div>
        <div className="max-h-64 overflow-auto rounded-md border border-line bg-white p-3 text-md whitespace-pre-line">
          <b>{english ? doc.title_en : doc.title_fr}</b>
          {"\n"}
          {english ? doc.body_en : doc.body_fr}
        </div>
        <CheckboxField
          id="legal-agree"
          label={t("legalAcceptance.agree")}
          checked={agreed}
          onCheckedChange={(on) => setAgreed(on === true)}
        />
        {accept.isError && <Banner tone="due">{errorMessage(accept.error, t)}</Banner>}
      </DialogContent>
    </DialogRoot>
  );
}
