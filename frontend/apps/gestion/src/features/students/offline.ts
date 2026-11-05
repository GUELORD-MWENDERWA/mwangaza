// Inscription d'un nouvel élève sur un appareil mémorisé sans réseau (HL.1) : élève, famille,
// inscription et frais dus créés ici (UUID v7), dans une seule opération `student.enroll` de la
// file. L'inscription provisoire part avec l'opération : la caisse de l'appareil l'ajoute à ce
// qu'elle sait (`queuedEnrollments`), l'élève est encaissable tout de suite. Le serveur donne le
// matricule et le code famille définitifs ; la descente suivante les apporte (même identifiant).
import type { Schemas } from "@mwangaza/api";
import { liveQuery } from "dexie";
import { useEffect, useState } from "react";

import type { LocalDb, LocalEnrollment, QueuedOperation } from "../../lib/sync/db";
import type { Config, Enrollment } from "../../lib/sync/engine";
import { syncNow } from "../../lib/sync/session";

type Charge = Schemas["StudentCharge"];

/** Contenu de l'opération `student.enroll` (serveur : `OfflineEnrollmentSerializer`) : les champs
 *  de « Inscrire un élève », avec les identifiants de l'appareil. */
export type OfflineEnrollment = Record<string, unknown> & {
  id: string;
  enrollment_id: string;
  class_group: string;
  enrolled_on: string;
  last_name: string;
  first_name: string;
  birth_date: string | null;
  family?: string;
  family_id?: string;
  charges: { id: string; installment_template: string }[];
  distinct_from: string[];
};

// Sans 0/O ni 1/I/L : lu à voix haute au guichet sans confusion.
const ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ";

/** Code provisoire tiré de la fin (aléatoire) d'un UUID v7 : le même à chaque lecture. */
export function provisionalCode(id: string, length: number): string {
  let value = parseInt(id.replace(/-/g, "").slice(-12), 16);
  let code = "";
  for (let index = 0; index < length; index += 1) {
    code = ALPHABET[value % ALPHABET.length] + code;
    value = Math.floor(value / ALPHABET.length);
  }
  return code;
}

export const provisionalMatricule = (student: string) => `PRV-${provisionalCode(student, 4)}`;
export const provisionalFamilyCode = (family: string) => `FAM-PRV-${provisionalCode(family, 3)}`;

/** Frais dus d'un élève inscrit dans `classGroup`, tirés des barèmes de la config comme le
 *  serveur (`fee_rules_by_class` : une ligne par tranche du barème le plus précis de chaque type
 *  de frais), chacun avec l'identifiant que le serveur reprendra. Sans droit sur les finances :
 *  aucun. */
export function deviceCharges(
  config: Config,
  classGroup: string,
  enrollment: string,
  newId: () => string,
): { charge: Charge; template: string }[] {
  const types = new Map((config.fee_types ?? []).map((type) => [type.id, type]));
  return (config.fee_rules ?? [])
    .filter((rule) => rule.class_groups.includes(classGroup))
    .flatMap((rule) =>
      [...rule.installments]
        .sort((a, b) => a.order - b.order)
        .map((template) => ({
          template: template.id,
          charge: {
            id: newId(),
            enrollment,
            fee_type: rule.fee_type,
            fee_type_name: types.get(rule.fee_type)?.name ?? "",
            fee_category: types.get(rule.fee_type)?.category ?? "custom",
            label: template.label,
            amount_minor: template.amount_minor,
            currency: rule.currency,
            due_on: template.due_on,
            source: "rule",
            status: "active",
            discount_minor: 0,
            paid_minor: 0,
            remaining_minor: template.amount_minor,
            state: null,
          } satisfies Charge,
        })),
    )
    .sort((a, b) => a.charge.due_on.localeCompare(b.charge.due_on));
}

const same = (a: string, b: string) =>
  a.trim().toLocaleLowerCase() === b.trim().toLocaleLowerCase();

/** Élèves que l'appareil connaît aux mêmes nom, prénom et date de naissance (règle du serveur,
 *  `possible_duplicates`) ; sans date de naissance, aucun. */
export function localDuplicates(
  enrollments: LocalEnrollment[],
  values: { last_name: string; first_name: string; birth_date: string | null },
): LocalEnrollment[] {
  if (!values.birth_date) return [];
  return enrollments.filter(
    ({ student }) =>
      student.birth_date === values.birth_date &&
      same(student.last_name, values.last_name) &&
      same(student.first_name, values.first_name),
  );
}

/** Inscriptions faites sur l'appareil que l'état du serveur n'a pas encore (opération en
 *  attente ou envoyée) ; refusée : plus montrée. */
export function queuedEnrollments(
  queued: QueuedOperation[],
  known: Map<string, unknown>,
): LocalEnrollment[] {
  return queued.flatMap((op) =>
    op.type === "student.enroll" &&
    op.status !== "rejected" &&
    op.enrollment &&
    !known.has(op.enrollment.id)
      ? [{ ...op.enrollment, gen: -1 }]
      : [],
  );
}

/** Inscription sur l'appareil, avec ou sans réseau : l'opération porte l'inscription provisoire
 *  (`op_id` = l'élève : un double appui n'inscrit qu'une fois). Puis envoi aussitôt. */
export async function enrollOffline(
  db: LocalDb,
  payload: OfflineEnrollment,
  enrollment: Enrollment,
) {
  await db.transaction("rw", db.outbox, async () => {
    if (await db.outbox.where("op_id").equals(payload.id).count()) return;
    await db.outbox.add({
      op_id: payload.id,
      type: "student.enroll",
      payload,
      created_at: new Date().toISOString(),
      status: "pending",
      error: null,
      enrollment,
    });
  });
  void syncNow();
}

export type DeviceStudents = {
  config: Config | null;
  /** Inscriptions de l'appareil, celles faites ici comprises. */
  enrollments: LocalEnrollment[];
  lastSyncAt: string | null;
};

const readDevice = async (db: LocalDb): Promise<DeviceStudents> => {
  const [enrollments, config, queued, meta] = await Promise.all([
    db.enrollments.toArray(),
    db.config.get("config"),
    db.outbox.toArray(),
    db.meta.get("sync"),
  ]);
  const known = new Map(enrollments.map((item) => [item.id, item]));
  return {
    config: config?.value ?? null,
    enrollments: [...enrollments, ...queuedEnrollments(queued, known)],
    lastSyncAt: meta?.lastSyncAt ?? null,
  };
};

/** Ce que l'appareil sait des élèves, relu à chaque changement ; sans appareil, rien. */
export function useDeviceStudents(db: LocalDb | null): DeviceStudents | undefined {
  const [state, setState] = useState<{ db: LocalDb; value: DeviceStudents }>();
  useEffect(() => {
    if (!db) return;
    const subscription = liveQuery(() => readDevice(db)).subscribe({
      next: (value) => setState({ db, value }),
    });
    return () => subscription.unsubscribe();
  }, [db]);
  return state && state.db === db ? state.value : undefined;
}

/** Familles de l'appareil trouvées par le nom d'un enfant ou le code famille (les tuteurs ne
 *  descendent pas sur l'appareil). */
export type LocalFamily = { id: string; code: string; children: LocalEnrollment[] };

export function searchLocalFamilies(
  enrollments: LocalEnrollment[],
  text: string,
  limit: number,
): LocalFamily[] {
  const words = plain(text).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const families = new Map<string, LocalFamily>();
  for (const enrollment of enrollments) {
    const { student } = enrollment;
    const family = families.get(student.family) ?? {
      id: student.family,
      code: student.family_code,
      children: [],
    };
    family.children.push(enrollment);
    families.set(student.family, family);
  }
  return [...families.values()]
    .filter((family) => {
      const haystack = plain(
        `${family.code} ${family.children.map(({ student }) => `${student.last_name} ${student.middle_name} ${student.first_name}`).join(" ")}`,
      );
      return words.every((word) => haystack.includes(word));
    })
    .slice(0, limit);
}

const plain = (text: string) => text.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase();
