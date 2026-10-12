// Convocations des parents (5.7, maquette `convocations`) : à gauche la nouvelle convocation
// (élève cherché par nom ou matricule, jour, heure, personne à voir, motif) ; à droite celles
// déjà faites, avec la lettre PDF à remettre à l'élève et « vue » quand le parent l'a ouverte
// dans le portail. Jamais modifiée : on l'annule et on en fait une autre.
// Droit `announcements.publish` (vérifié par le serveur).
import { zodResolver } from "@hookform/resolvers/zod";
import { formatDateTime, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  Field,
  Input,
  List,
  PageHeader,
  Skeleton,
  StatusPill,
  Tag,
  Textarea,
} from "@mwangaza/ui";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { applyServerErrors, errorMessage, firstErrorMessage } from "../../lib/errors";
import { studentName } from "../../lib/people";
import { useCurrentSchool } from "../../lib/school";
import { useSettled } from "../../lib/settled";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import { type StudentRow, useStudentSearch } from "../students/data";
import { letterUrl, PAGE_SIZE, type Summons, useCancel, useIssue, useSummons } from "./data";

const SHOWN = 6;
type Values = { student: string; day: string; time: string; meet_with: string; reason: string };
const EMPTY: Values = { student: "", day: "", time: "", meet_with: "", reason: "" };

export function SummonsPage() {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const settled = useSettled(search.trim());
  const list = useSummons(settled, page);

  if (list.isError && !list.data) {
    return <LoadError error={list.error} onRetry={() => void list.refetch()} />;
  }
  const results = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  return (
    <>
      <PageHeader title={t("summons.title")} subtitle={t("summons.subtitle")} />
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <NewSummonsCard />
        <Card>
          <CardHeader className="flex-wrap gap-2">
            <CardTitle>{t("summons.list")}</CardTitle>
            <Input
              type="search"
              className="w-full min-[520px]:max-w-64"
              aria-label={t("summons.search")}
              placeholder={t("summons.search")}
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
            />
          </CardHeader>
          <CardContent>
            {!list.data ? (
              <Skeleton label={t("common.loading")} />
            ) : results.length === 0 ? (
              <p className="text-ink-3">{t(settled ? "summons.none" : "summons.empty")}</p>
            ) : (
              <List>
                {results.map((summons) => (
                  <SummonsItem key={summons.id} summons={summons} />
                ))}
              </List>
            )}
          </CardContent>
          {count > PAGE_SIZE && (
            <Pagination
              page={page}
              hasPrevious={Boolean(list.data?.previous)}
              hasNext={Boolean(list.data?.next)}
              onPage={setPage}
              summary={t("summons.range", { from, to: from + results.length - 1, count })}
            />
          )}
        </Card>
      </div>
    </>
  );
}

function NewSummonsCard() {
  const { t } = useTranslation();
  const required = t("fieldErrors.required");
  const schema = z.object({
    student: z.string().min(1, t("summons.noStudent")),
    day: z.string().min(1, required),
    time: z.string().min(1, required),
    meet_with: z.string().trim().min(1, required),
    reason: z.string().trim().min(1, required),
  });
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: EMPTY });
  const [chosen, setChosen] = useState<StudentRow | null>(null);
  const [search, setSearch] = useState("");
  const [general, setGeneral] = useState<string | null>(null);
  const [done, setDone] = useState<Summons | null>(null);
  const settled = useSettled(search.trim());
  const found = useStudentSearch(chosen ? "" : settled);
  const issue = useIssue();
  const errors = form.formState.errors;
  const students = settled.length >= 2 ? (found.data?.results ?? []).slice(0, SHOWN) : [];

  const choose = (student: StudentRow | null) => {
    setChosen(student);
    setSearch("");
    form.setValue("student", student?.id ?? "", { shouldValidate: form.formState.isSubmitted });
  };
  const onSubmit = form.handleSubmit(({ day, time, ...values }) => {
    setGeneral(null);
    setDone(null);
    // Jour et heure saisis à l'école, sur l'appareil de l'école.
    const meeting_at = new Date(`${day}T${time}`).toISOString();
    issue.mutate(
      { ...values, meeting_at },
      {
        onSuccess: (summons) => {
          form.reset(EMPTY);
          setChosen(null);
          setDone(summons);
        },
        // Jour passé : l'erreur du serveur porte sur `meeting_at`, montrée sous le jour.
        onError: (error) =>
          setGeneral(
            applyServerErrors(error, ["student", "meet_with", "reason"], form.setError, t) ??
              firstErrorMessage(error, t),
          ),
      },
    );
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("summons.new")}</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="flex flex-col gap-4" onSubmit={(event) => void onSubmit(event)} noValidate>
          {done && (
            <Banner tone="ok">
              {t("summons.issued", { name: done.student.full_name })}{" "}
              <a
                className="font-bold underline"
                href={letterUrl(done.id)}
                target="_blank"
                rel="noreferrer"
              >
                {t("summons.letter")}
              </a>
            </Banner>
          )}
          {general && <Banner tone="due">{general}</Banner>}
          <Field id="summons-student" label={t("summons.student")} error={errors.student?.message}>
            {(control) =>
              chosen ? (
                <div className="flex flex-wrap items-center gap-2">
                  <Tag className="inline-flex items-center gap-1">
                    {studentName(chosen)}
                    {chosen.enrollment && ` · ${chosen.enrollment.class_group_name}`}
                    <button
                      type="button"
                      className="rounded px-0.5 hover:bg-gray-100"
                      aria-label={t("summons.changeStudent")}
                      onClick={() => choose(null)}
                    >
                      ✕
                    </button>
                  </Tag>
                </div>
              ) : (
                <>
                  <Input
                    {...control}
                    type="search"
                    placeholder={t("summons.studentSearch")}
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />
                  {settled.length >= 2 && found.data && students.length === 0 && (
                    <span className="text-sm text-ink-3">{t("summons.noStudentFound")}</span>
                  )}
                  {students.length > 0 && (
                    <ul className="flex flex-col rounded-field border border-line">
                      {students.map((student) => (
                        <li key={student.id} className="border-t border-line first:border-t-0">
                          <button
                            type="button"
                            className="flex min-h-11 w-full flex-wrap items-center justify-between gap-2 px-3 py-2 text-left hover:bg-surface"
                            onClick={() => choose(student)}
                          >
                            <b>{studentName(student)}</b>
                            <span className="text-sm text-ink-3 tabular-nums">
                              {[student.enrollment?.class_group_name, student.matricule]
                                .filter(Boolean)
                                .join(" · ")}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )
            }
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field id="summons-day" label={t("summons.day")} error={errors.day?.message}>
              {(control) => <Input {...control} type="date" {...form.register("day")} />}
            </Field>
            <Field id="summons-time" label={t("summons.time")} error={errors.time?.message}>
              {(control) => <Input {...control} type="time" {...form.register("time")} />}
            </Field>
          </div>
          <Field
            id="summons-meet-with"
            label={t("summons.meetWith")}
            help={t("summons.meetWithHelp")}
            error={errors.meet_with?.message}
          >
            {(control) => <Input {...control} maxLength={120} {...form.register("meet_with")} />}
          </Field>
          <Field id="summons-reason" label={t("summons.reason")} error={errors.reason?.message}>
            {(control) => (
              <Textarea
                {...control}
                maxLength={500}
                className="min-h-24"
                {...form.register("reason")}
              />
            )}
          </Field>
          <Button type="submit" disabled={issue.isPending}>
            {t("summons.issue")}
          </Button>
          <span className="text-sm text-ink-3">{t("summons.help")}</span>
        </form>
      </CardContent>
    </Card>
  );
}

function SummonsItem({ summons }: { summons: Summons }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const cancel = useCancel();
  const [confirm, setConfirm] = useState(false);
  const cancelled = summons.cancelled_at !== null;
  const state = cancelled ? "cancelled" : summons.seen_at ? "seen" : "sent";
  return (
    <div>
      <div className="flex min-w-0 flex-col gap-0.5">
        <b>{summons.student.full_name}</b>
        <span className="text-sm text-ink-2 tabular-nums">
          {[
            summons.class_name,
            formatDateTime(summons.meeting_at, i18n.language, school.timezone),
            summons.meet_with,
          ].join(" · ")}
        </span>
        <span className="text-sm whitespace-pre-line text-ink-3">{summons.reason}</span>
        <a
          className="self-start text-sm font-bold text-lake underline"
          href={letterUrl(summons.id)}
          target="_blank"
          rel="noreferrer"
        >
          {t("summons.letter")}
        </a>
        {cancel.error && <div className="text-sm text-due">{errorMessage(cancel.error, t)}</div>}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1.5">
        <StatusPill tone={cancelled ? "gray" : summons.seen_at ? "ok" : "info"}>
          {t(`summons.states.${state}`)}
        </StatusPill>
        {!cancelled && (
          <Button variant="ghost" size="sm" onClick={() => setConfirm(true)}>
            {t("summons.cancel")}
          </Button>
        )}
      </div>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={t("summons.cancelTitle", { name: summons.student.full_name })}
        confirmLabel={t("summons.cancel")}
        cancelLabel={t("summons.keep")}
        pending={cancel.isPending}
        onConfirm={() => cancel.mutate(summons.id, { onSuccess: () => setConfirm(false) })}
      >
        {t("summons.cancelText")}
      </ConfirmDialog>
    </div>
  );
}
