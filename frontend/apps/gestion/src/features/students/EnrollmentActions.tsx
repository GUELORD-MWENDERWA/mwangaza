// Inscription de l'année, depuis la fiche élève (2.6.1, droit `students.edit`) : changer de
// classe (le serveur recalcule les frais dus), enregistrer un départ (abandon, transfert,
// exclusion, avec sa date) ou l'annuler, inscrire pour l'année un élève déjà connu.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { Button, CardFooter, ConfirmDialog, Field, Input, Select } from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { errorMessage } from "../../lib/errors";
import { uuidv7 } from "../../lib/ids";
import { keys } from "../../lib/queries";
import { useClasses } from "../organisation/data";
import type { Student } from "./data";

type Enrollment = Student["enrollments"][number];
type Open = "class" | "departure" | "return" | "enroll" | null;
const DEPARTURES = ["dropped", "transferred", "excluded"] as const;
type Departure = (typeof DEPARTURES)[number];

/** Date du jour sur l'appareil, au format des champs date (AAAA-MM-JJ). */
const today = () => new Date().toLocaleDateString("en-CA");

export function EnrollmentActions({
  student,
  enrollment,
  year,
}: {
  student: Student;
  enrollment: Enrollment | undefined;
  year: { id: string; name: string };
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState<Open>(null);
  const [classGroup, setClassGroup] = useState("");
  const [reason, setReason] = useState<Departure>("dropped");
  const [leftOn, setLeftOn] = useState(today);
  const newId = useRef(uuidv7());
  const classes = useClasses(open === "class" || open === "enroll" ? year.id : "");
  const choices = (classes.data ?? []).filter((group) => group.id !== enrollment?.class_group);

  const done = async () => {
    await queryClient.invalidateQueries({ queryKey: keys.students });
    setOpen(null);
  };
  const update = useMutation({
    mutationFn: (body: { class_group?: string; status?: Departure | "active"; left_on?: string }) =>
      call(
        api.PATCH("/api/enrollments/{id}/", {
          params: { path: { id: enrollment?.id ?? "" } },
          body,
        }),
      ),
    onSuccess: done,
  });
  const enroll = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/enrollments/", {
          body: { id: newId.current, student: student.id, class_group: classGroup },
        }),
      ),
    onSuccess: done,
  });
  const pending = update.isPending || enroll.isPending;
  const failed = update.error ?? enroll.error;

  const show = (which: Open) => {
    update.reset();
    enroll.reset();
    setClassGroup("");
    setReason("dropped");
    setLeftOn(today());
    setOpen(which);
  };
  const close = (isOpen: boolean) => {
    if (!isOpen) setOpen(null);
  };
  const error = failed && (
    <p role="alert" className="text-sm text-due">
      {errorMessage(failed, t)}
    </p>
  );
  const classField = (
    <Field id="enrollment-class" label={t("students.new.class")} required>
      {(control) => (
        <Select {...control} value={classGroup} onChange={(e) => setClassGroup(e.target.value)}>
          <option value="">{t("students.enrollment.chooseClass")}</option>
          {choices.map((group) => (
            <option key={group.id} value={group.id}>
              {group.name}
            </option>
          ))}
        </Select>
      )}
    </Field>
  );

  return (
    <CardFooter>
      <span className="text-sm text-ink-3">
        {enrollment ? t("students.enrollment.help") : t("students.list.notEnrolled")}
      </span>
      <div className="flex flex-wrap gap-2">
        {enrollment?.status === "active" && (
          <>
            <Button size="sm" variant="outline" onClick={() => show("class")}>
              {t("students.enrollment.changeClass")}
            </Button>
            <Button size="sm" variant="destructive" onClick={() => show("departure")}>
              {t("students.enrollment.departure")}
            </Button>
          </>
        )}
        {enrollment && enrollment.status !== "active" && (
          <Button size="sm" variant="outline" onClick={() => show("return")}>
            {t("students.enrollment.cancelDeparture")}
          </Button>
        )}
        {!enrollment && (
          <Button size="sm" onClick={() => show("enroll")}>
            {t("students.enrollment.enroll", { year: year.name })}
          </Button>
        )}
      </div>

      <ConfirmDialog
        open={open === "class"}
        onOpenChange={close}
        title={t("students.enrollment.changeClass")}
        confirmLabel={t("students.enrollment.changeClass")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => classGroup && update.mutate({ class_group: classGroup })}
        pending={pending || !classGroup}
      >
        <div className="flex flex-col gap-3">
          <p className="text-sm text-ink-3">{t("students.enrollment.help")}</p>
          {classField}
          {error}
        </div>
      </ConfirmDialog>

      <ConfirmDialog
        open={open === "departure"}
        onOpenChange={close}
        title={t("students.enrollment.departure")}
        confirmLabel={t("students.enrollment.departure")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => leftOn && update.mutate({ status: reason, left_on: leftOn })}
        pending={pending || !leftOn}
        destructive
      >
        <div className="flex flex-col gap-3">
          <p className="text-sm text-ink-3">{t("students.enrollment.departureHelp")}</p>
          <Field id="departure-reason" label={t("students.enrollment.reason")} required>
            {(control) => (
              <Select
                {...control}
                value={reason}
                onChange={(e) => setReason(e.target.value as Departure)}
              >
                {DEPARTURES.map((status) => (
                  <option key={status} value={status}>
                    {t(`students.enrollmentStatus.${status}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field id="departure-date" label={t("students.enrollment.leftOn")} required>
            {(control) => (
              <Input
                {...control}
                type="date"
                max={today()}
                value={leftOn}
                onChange={(e) => setLeftOn(e.target.value)}
              />
            )}
          </Field>
          {error}
        </div>
      </ConfirmDialog>

      <ConfirmDialog
        open={open === "return"}
        onOpenChange={close}
        title={t("students.enrollment.cancelDeparture")}
        confirmLabel={t("students.enrollment.cancelDeparture")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => update.mutate({ status: "active" })}
        pending={pending}
      >
        <p className="text-sm text-ink-3">{t("students.enrollment.returnHelp")}</p>
        {error}
      </ConfirmDialog>

      <ConfirmDialog
        open={open === "enroll"}
        onOpenChange={close}
        title={t("students.enrollment.enroll", { year: year.name })}
        confirmLabel={t("students.enrollment.enrollSubmit")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => classGroup && enroll.mutate()}
        pending={pending || !classGroup}
      >
        <div className="flex flex-col gap-3">
          {classField}
          {error}
        </div>
      </ConfirmDialog>
    </CardFooter>
  );
}
