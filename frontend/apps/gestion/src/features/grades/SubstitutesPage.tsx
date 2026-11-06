// Remplaçants des cours (8.2.5, maquette `remplacant-cours`) : le directeur des études
// (`grades.validate`) désigne une personne qui saisit à la place de l'enseignant d'un cours (un
// total et l'examen par élève, jamais les devoirs), et la retire. Un cours commun se remplace pour
// tout son groupe (le serveur le fait). En ligne.
import { api, call, type Schemas } from "@mwangaza/api";
import { firstErrorMessage, formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  ConfirmDialog,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  PageHeader,
  Select,
  Skeleton,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { fullName } from "../../lib/people";
import { keys } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { LoadError } from "../status/StatusPages";
import { useValidation } from "./data";
import { todayIn } from "./SheetControl";

type Substitute = Schemas["CourseSubstitute"];

export function SubstitutesPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const list = useQuery({
    queryKey: keys.courseSubstitutes,
    queryFn: () => call(api.GET("/api/course-substitutes/")),
  });
  const [creating, setCreating] = useState(false);
  const [removing, setRemoving] = useState<Substitute | null>(null);
  const remove = useMutation({
    mutationFn: (row: Substitute) =>
      call(api.DELETE("/api/course-substitutes/{id}/", { params: { path: { id: row.id } } })),
    onSuccess: async () => {
      setRemoving(null);
      await queryClient.invalidateQueries({ queryKey: keys.courseSubstitutes });
    },
  });

  return (
    <>
      <PageHeader
        crumbs={
          <>
            <Link to="/grade-validation" className="text-lake underline">
              {t("gradeValidation.title")}
            </Link>{" "}
            / {t("grades.substitutes.title")}
          </>
        }
        title={t("grades.substitutes.title")}
        subtitle={t("grades.substitutes.subtitle")}
        actions={<Button onClick={() => setCreating(true)}>{t("grades.substitutes.add")}</Button>}
      />
      {remove.isError && <Banner tone="due">{firstErrorMessage(remove.error, t)}</Banner>}
      {list.isPending ? (
        <Skeleton label={t("common.loading")} />
      ) : list.isError ? (
        <LoadError error={list.error} onRetry={() => void list.refetch()} />
      ) : list.data.length === 0 ? (
        <Banner tone="info">{t("grades.substitutes.empty")}</Banner>
      ) : (
        <Card>
          <Table stacked>
            <thead>
              <tr>
                <th>{t("grades.substitutes.columns.course")}</th>
                <th>{t("grades.substitutes.columns.teacher")}</th>
                <th>{t("grades.substitutes.columns.substitute")}</th>
                <th>{t("grades.substitutes.columns.since")}</th>
                <th>{t("grades.substitutes.columns.until")}</th>
                <th>
                  <span className="sr-only">{t("grades.substitutes.remove")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {list.data.map((row) => (
                <tr key={row.id}>
                  <td>
                    <b>
                      {row.course_group
                        ? t("grades.substitutes.joint", { label: row.label })
                        : row.label}
                    </b>
                    <span className="block text-sm text-ink-3">{row.reason}</span>
                  </td>
                  <td data-label={t("grades.substitutes.columns.teacher")}>
                    {row.teacher ? fullName(row.teacher) : t("courses.unassigned")}
                  </td>
                  <td data-label={t("grades.substitutes.columns.substitute")}>
                    {fullName(row.substitute)}
                  </td>
                  <td data-label={t("grades.substitutes.columns.since")}>
                    {formatDay(row.since, i18n.language)}
                  </td>
                  <td data-label={t("grades.substitutes.columns.until")}>
                    {row.ends_on ? (
                      formatDay(row.ends_on, i18n.language)
                    ) : (
                      <span className="text-ink-3">{t("grades.substitutes.noEnd")}</span>
                    )}
                  </td>
                  <td className="text-right">
                    <Button variant="outline" size="sm" onClick={() => setRemoving(row)}>
                      {t("grades.substitutes.remove")}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(value) => !value && setRemoving(null)}
        title={t("grades.substitutes.removeTitle", {
          name: removing ? fullName(removing.substitute) : "",
        })}
        confirmLabel={t("grades.substitutes.remove")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={() => removing && remove.mutate(removing)}
      >
        {t("grades.substitutes.removeBody", { course: removing?.label ?? "" })}
      </ConfirmDialog>
      {creating && (
        <DesignateDialog
          onClose={() => setCreating(false)}
          onDone={async () => {
            setCreating(false);
            await queryClient.invalidateQueries({ queryKey: keys.courseSubstitutes });
          }}
        />
      )}
    </>
  );
}

function DesignateDialog({ onClose, onDone }: { onClose: () => void; onDone(): Promise<void> }) {
  const { t } = useTranslation();
  const school = useCurrentSchool();
  // Classes et cours de l'école, avec leur enseignant : le tableau « À valider » les donne déjà.
  const board = useValidation("");
  const people = useQuery({
    queryKey: [...keys.courseSubstitutes, "candidates"],
    queryFn: () => call(api.GET("/api/course-substitutes/candidates/")),
  });
  const [classId, setClassId] = useState("");
  const [courseId, setCourseId] = useState("");
  const [substitute, setSubstitute] = useState("");
  const [reason, setReason] = useState("");
  const [until, setUntil] = useState("");
  const classes = (board.data?.classes ?? []).filter((item) => item.courses.length > 0);
  const group = classes.find((item) => item.id === classId) ?? classes[0];
  const course = group?.courses.find((item) => item.id === courseId) ?? group?.courses[0];
  const choices = (people.data ?? []).filter((person) => person.id !== course?.teacher_id);
  const designate = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/course-substitutes/", {
          body: {
            course: course!.id,
            substitute_id: substitute,
            reason: reason.trim(),
            ends_on: until || null,
          },
        }),
      ),
    onSuccess: onDone,
  });
  const ready = Boolean(course && substitute && reason.trim().length >= 3);

  return (
    <DialogRoot open onOpenChange={(value) => !value && onClose()}>
      <DialogContent
        title={t("grades.substitutes.add")}
        description={t("grades.substitutes.addHelp")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button disabled={!ready || designate.isPending} onClick={() => designate.mutate()}>
              {t("grades.substitutes.confirm")}
            </Button>
          </>
        }
      >
        {designate.isError && <Banner tone="due">{firstErrorMessage(designate.error, t)}</Banner>}
        {board.isError || people.isError ? (
          <LoadError
            error={board.error ?? people.error}
            onRetry={() => void Promise.all([board.refetch(), people.refetch()])}
          />
        ) : board.isPending || people.isPending ? (
          <Skeleton label={t("common.loading")} />
        ) : (
          <>
            <div className="grid gap-4 min-[600px]:grid-cols-2">
              <Field id="substitute-class" label={t("grades.classChoice")} required>
                {(control) => (
                  <Select
                    {...control}
                    value={group?.id ?? ""}
                    onChange={(event) => {
                      setClassId(event.target.value);
                      setCourseId("");
                    }}
                  >
                    {classes.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field id="substitute-course" label={t("grades.courseChoice")} required>
                {(control) => (
                  <Select
                    {...control}
                    value={course?.id ?? ""}
                    onChange={(event) => setCourseId(event.target.value)}
                  >
                    {group?.courses.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.teacher ? `${item.name} · ${item.teacher}` : item.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </div>
            <Field id="substitute-person" label={t("grades.substitutes.person")} required>
              {(control) => (
                <Select
                  {...control}
                  value={substitute}
                  onChange={(event) => setSubstitute(event.target.value)}
                >
                  <option value="">{t("grades.substitutes.choose")}</option>
                  {choices.map((person) => (
                    <option key={person.id} value={person.id}>
                      {fullName(person)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field
              id="substitute-reason"
              label={t("grades.substitutes.reason")}
              help={t("grades.substitutes.reasonHelp")}
              required
            >
              {(control) => (
                <Input
                  {...control}
                  value={reason}
                  maxLength={200}
                  onChange={(event) => setReason(event.target.value)}
                />
              )}
            </Field>
            <Field
              id="substitute-until"
              label={t("grades.substitutes.until")}
              help={t("grades.substitutes.untilHelp")}
            >
              {(control) => (
                <Input
                  {...control}
                  type="date"
                  min={todayIn(school.timezone)}
                  value={until}
                  onChange={(event) => setUntil(event.target.value)}
                />
              )}
            </Field>
          </>
        )}
      </DialogContent>
    </DialogRoot>
  );
}
