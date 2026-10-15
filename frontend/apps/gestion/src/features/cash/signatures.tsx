// Signatures et cachet posés sur les reçus, reçus d'annulation et bordereaux que la Gestion
// imprime (DOC.1). Images servies au seul personnel connecté de l'école ; adresses gardées avec
// le compte (`me.school.documents`) et images gardées par le navigateur, préchargées à
// l'ouverture de la caisse, pour imprimer hors ligne. Rien de déposé, ou image introuvable :
// l'espace reste pour signer à la main, comme avant.
import { type ReactNode, useEffect, useState } from "react";

import type { Me } from "../../lib/queries";

/** Ma signature (adresse qui change avec elle) ; celle d'une autre personne de l'école, lue au
 *  serveur (aucune : rien n'est posé). */
export function signatureOf(me: Me, userId: string | undefined): string | null {
  if (!userId) return null;
  if (userId === me.id) return me.school?.documents.signature ?? null;
  return `/api/school/signatures/${userId}/`;
}

/** Signature entre le rôle et le nom ; sans elle, le retour à la ligne d'avant. */
export function SignatureMark({ src }: { src: string | null }) {
  const [failed, setFailed] = useState<string | null>(null);
  if (!src || failed === src) return <br />;
  return <img className="receipt__signature" src={src} alt="" onError={() => setFailed(src)} />;
}

/** Cachet de l'école ; `fallback` (case « Cachet ») sans lui. */
export function StampMark({ me, fallback }: { me: Me; fallback?: ReactNode }) {
  const src = me.school?.documents.stamp ?? null;
  const [failed, setFailed] = useState<string | null>(null);
  if (!src || failed === src) return fallback ?? null;
  return <img className="receipt__stamp-image" src={src} alt="" onError={() => setFailed(src)} />;
}

/** Cachet et ma signature chargés dès l'ouverture de la caisse : le navigateur les garde (un
 *  jour) pour les reçus imprimés hors ligne. */
export function usePreloadSignatures(me: Me) {
  const documents = me.school?.documents;
  const stamp = documents?.stamp;
  const signature = documents?.signature;
  useEffect(() => {
    for (const src of [stamp, signature]) if (src) new Image().src = src;
  }, [stamp, signature]);
}
