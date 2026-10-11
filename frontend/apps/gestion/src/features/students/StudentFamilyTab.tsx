// Onglet Famille de la fiche élève (M9, D4) : tuteurs et contacts, frères et sœurs de cette école
// seulement (la famille appartient à l'école, Q10), liaison à une autre famille quand la même a
// été saisie deux fois (l'ancienne fiche disparaît si plus aucun enfant n'y est rattaché).
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardFooter,
  CardHeader,
  CardTitle,
  Code,
  DialogContent,
  DialogRoot,
  Input,
  List,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { errorMessage } from "../../lib/errors";
import { formatPhone, studentName } from "../../lib/people";
import { keys } from "../../lib/queries";
import { useSettled } from "../../lib/settled";
import { LoadError } from "../status/StatusPages";
import { FamilyCard } from "./NewStudentPage";
import { type Family, type Guardian, type Student, useFamily, useFamilySearch } from "./data";

export function GuardianRole({ guardian }: { guardian: Guardian }) {
  const { t } = useTranslation();
  if (guardian.is_primary) {
    return <StatusPill tone="info">{t("students.family.primary")}</StatusPill>;
  }
  if (guardian.is_emergency_contact) {
    return <StatusPill tone="warn">{t("students.family.emergency")}</StatusPill>;
  }
  return <span className="text-sm text-ink-3">{t("students.family.other")}</span>;
}

export function StudentFamilyTab({ student, canEdit }: { student: Student; canEdit: boolean }) {
  const { t } = useTranslation();
  const family = useFamily(student.family.id);
  const [linking, setLinking] = useState(false);
  if (family.error) return <LoadError error={family.error} onRetry={() => void family.refetch()} />;
  if (!family.data) return <Skeleton label={t("common.loading")} />;
  const siblings = family.data.students.filter((child) => child.id !== student.id);
  return (
    <div className="grid grid-cols-1 items-start gap-4 min-[1100px]:grid-cols-[2fr_1fr]">
      <div className="flex flex-col gap-4">
        <Card>
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>{t("students.family.title", { name: student.last_name })}</CardTitle>
              <span className="text-sm text-ink-3">
                {t("students.card.familyCode")} <Code>{family.data.code}</Code>
              </span>
            </div>
            <Button asChild size="sm" variant="outline">
              <Link to={`/families/${family.data.id}`}>{t("students.family.open")}</Link>
            </Button>
          </CardHeader>
          <GuardianTable guardians={family.data.guardians} />
          {canEdit && (
            <CardFooter className="justify-end">
              <Button size="sm" variant="outline" onClick={() => setLinking(true)}>
                {t("students.family.link")}
              </Button>
            </CardFooter>
          )}
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("students.family.siblings")}</CardTitle>
          </CardHeader>
          {siblings.length ? (
            <List className="px-[18px]">
              {siblings.map((child) => (
                <div key={child.id}>
                  <div>
                    <b>{studentName(child)}</b>
                    <br />
                    <span className="text-sm text-ink-3">
                      {[child.class_group_name, child.matricule].filter(Boolean).join(" · ")}
                    </span>
                  </div>
                  <Button asChild size="sm" variant="ghost">
                    <Link to={`/students/${child.id}`}>{t("students.family.openStudent")}</Link>
                  </Button>
                </div>
              ))}
            </List>
          ) : (
            <p className="px-5 pb-5 text-sm text-ink-3">{t("students.family.noSiblings")}</p>
          )}
        </Card>
      </div>
      <Banner tone="info">{t("students.family.primaryHelp")}</Banner>
      {linking && (
        <LinkDialog student={student} current={family.data} onClose={() => setLinking(false)} />
      )}
    </div>
  );
}

export function GuardianTable({
  guardians,
  withEmail = false,
}: {
  guardians: Guardian[];
  withEmail?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <Table>
      <thead>
        <tr>
          <th>{t("students.family.columns.contact")}</th>
          <th>{t("students.family.columns.relationship")}</th>
          <th>{t("students.family.columns.phone")}</th>
          {withEmail && <th>{t("students.family.columns.email")}</th>}
          <th>{t("students.family.columns.role")}</th>
        </tr>
      </thead>
      <tbody>
        {guardians.map((guardian) => (
          <tr key={guardian.id}>
            <td>
              <b>{guardian.full_name}</b>
            </td>
            <td>{t(`students.relationships.${guardian.relationship}`)}</td>
            <td className="whitespace-nowrap tabular-nums">
              {guardian.phone ? formatPhone(guardian.phone) : t("common.none")}
            </td>
            {withEmail && <td className="text-sm">{guardian.email || t("common.none")}</td>}
            <td>
              <GuardianRole guardian={guardian} />
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function LinkDialog({
  student,
  current,
  onClose,
}: {
  student: Student;
  current: Family;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [chosen, setChosen] = useState<Family | null>(null);
  const settled = useSettled(search.trim());
  const families = useFamilySearch(settled);
  const results = (families.data?.results ?? []).filter(
    (family) => family.id !== current.id && family.id !== chosen?.id,
  );
  const link = useMutation({
    mutationFn: (family: Family) =>
      call(
        api.PATCH("/api/students/{id}/", {
          params: { path: { id: student.id } },
          body: { family: family.id, allow_duplicate: false },
        }),
      ),
    onSuccess: async (updated) => {
      queryClient.setQueryData([...keys.students, "detail", student.id], updated);
      await Promise.all(
        [keys.students, keys.families].map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      );
      onClose();
    },
  });
  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("students.family.linkTitle", { name: studentName(student) })}
        description={t("students.family.linkHelp")}
        footer={
          <>
            <Button variant="outline" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button
              disabled={!chosen || link.isPending}
              onClick={() => chosen && link.mutate(chosen)}
            >
              {t("students.family.linkConfirm")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <Input
            type="search"
            aria-label={t("students.new.familySearch")}
            placeholder={t("students.new.familySearch")}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          {link.error && (
            <p role="alert" className="text-sm text-due">
              {errorMessage(link.error, t)}
            </p>
          )}
          {chosen && <FamilyCard family={chosen} chosen />}
          {results.slice(0, 5).map((family) => (
            <FamilyCard key={family.id} family={family} onChoose={() => setChosen(family)} />
          ))}
          {families.data && results.length === 0 && !chosen && (
            <p className="text-sm text-ink-3">{t("students.family.linkNone")}</p>
          )}
        </div>
      </DialogContent>
    </DialogRoot>
  );
}
