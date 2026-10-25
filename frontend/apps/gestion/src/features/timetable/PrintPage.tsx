import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Icon,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
} from "@mwangaza/ui";
import { Link, useSearchParams } from "react-router";

import { DocumentPreview } from "../students/DocumentPreview";
import { PrintLayoutFields } from "../printing/PrintLayoutFields";
import { DEFAULT_LAYOUT, usePrintOptions } from "../printing/printOptions";
import {
  type PrintKind,
  printUrl,
  useDrafts,
  useRooms,
  useTimetableClasses,
  useTimetableCourses,
  useVersions,
} from "./data";

const KINDS: PrintKind[] = ["class", "teacher", "room", "general"];

/** Imprimer l'horaire (EDT.4c) : le document (classe, enseignant, salle, général), la version
 *  (publiée par défaut, ou une archivée, ou un brouillon), l'aperçu et le PDF. Sans classe,
 *  enseignant ou salle choisi : tous, une page chacun. */
export function PrintPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const versions = useVersions();
  const drafts = useDrafts();
  const classes = useTimetableClasses();
  const courses = useTimetableCourses();
  const rooms = useRooms();
  const [saved, save] = usePrintOptions("timetable", {
    ...DEFAULT_LAYOUT,
    kind: "class" as PrintKind,
    sheet: "a4",
  });
  const kind = saved.kind;
  const subject = params.get("subject") ?? "";
  const queries = [versions, drafts, classes, courses, rooms];
  const published = versions.data?.find((item) => item.status === "published");
  const timetable =
    params.get("version") ?? published?.id ?? versions.data?.[0]?.id ?? drafts.data?.[0]?.id;

  const teachers = new Map<string, string>();
  for (const course of courses.data ?? []) {
    if (course.teacher) teachers.set(course.teacher, course.teacher_name);
  }
  const subjects: Record<Exclude<PrintKind, "general">, { id: string; name: string }[]> = {
    class: (classes.data ?? []).map(({ id, name }) => ({ id, name })),
    teacher: [...teachers]
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name)),
    room: (rooms.data ?? []).filter((room) => room.is_active).map(({ id, name }) => ({ id, name })),
  };
  const choices = kind === "general" ? [] : subjects[kind];
  const chosen = choices.some((item) => item.id === subject) ? subject : "";

  const setVersion = (id: string) =>
    setParams((current) => {
      current.set("version", id);
      return current;
    });
  const setKind = (next: PrintKind) => {
    save({ kind: next });
    setParams((current) => {
      current.delete("subject");
      return current;
    });
  };
  const url = (output: "html" | "pdf") =>
    timetable
      ? printUrl({
          kind,
          subject: chosen,
          timetable,
          output,
          layout: kind === "general" ? { ...saved, paper: saved.sheet as "a4" } : saved,
          sheet: saved.sheet,
        })
      : "";

  return (
    <>
      <PageHeader
        crumbs={
          <>
            <Link to="/timetable" className="text-lake underline">
              {t("timetable.editor.title")}
            </Link>{" "}
            / {t("timetable.print.title")}
          </>
        }
        title={t("timetable.print.title")}
        subtitle={t("timetable.print.subtitle")}
        actions={
          timetable && (
            <Button asChild>
              <a href={url("pdf")} target="_blank" rel="noopener">
                <Icon name="print" size={16} />
                {t("timetable.print.pdf")}
              </a>
            </Button>
          )
        }
      />
      {queries.some((query) => !query.data) ? (
        <Skeleton label={t("common.loading")} />
      ) : !timetable ? (
        <Banner tone="warn">{t("timetable.print.none")}</Banner>
      ) : (
        <div className="grid items-start gap-4 min-[1000px]:grid-cols-[minmax(0,1fr)_320px]">
          <Card className="min-[1000px]:order-2">
            <CardHeader>
              <CardTitle>{t("timetable.print.options")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <Field id="print-document" label={t("timetable.print.document")}>
                {(control) => (
                  <Select
                    {...control}
                    value={kind}
                    onChange={(event) => setKind(event.target.value as PrintKind)}
                  >
                    {KINDS.map((value) => (
                      <option key={value} value={value}>
                        {t(`timetable.print.kind.${value}`)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field id="print-version" label={t("timetable.print.version")}>
                {(control) => (
                  <Select
                    {...control}
                    value={timetable}
                    onChange={(event) => setVersion(event.target.value)}
                  >
                    {(versions.data ?? []).map((item) => (
                      <option key={item.id} value={item.id}>
                        {t(`timetable.print.status.${item.status}`, { name: item.name })}
                      </option>
                    ))}
                    {(drafts.data ?? []).map((item) => (
                      <option key={item.id} value={item.id}>
                        {t("timetable.print.status.draft", { name: item.name })}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              {kind !== "general" && (
                <Field id="print-subject" label={t(`timetable.print.kind.${kind}`)}>
                  {(control) => (
                    <Select
                      {...control}
                      value={chosen}
                      onChange={(event) =>
                        setParams((current) => {
                          if (event.target.value) current.set("subject", event.target.value);
                          else current.delete("subject");
                          return current;
                        })
                      }
                    >
                      <option value="">{t(`timetable.print.all.${kind}`)}</option>
                      {choices.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              )}
              {kind === "general" ? (
                <div className="flex flex-col gap-1.5">
                  <span className="text-sm font-bold text-ink-2">{t("timetable.print.sheet")}</span>
                  <Segmented
                    label={t("timetable.print.sheet")}
                    value={saved.sheet}
                    onValueChange={(sheet) => save({ sheet })}
                    options={[
                      { value: "a4", label: t("timetable.print.sheetA4") },
                      { value: "a3", label: t("timetable.print.sheetA3") },
                    ]}
                  />
                </div>
              ) : (
                <PrintLayoutFields layout={saved} onChange={save} />
              )}
            </CardContent>
          </Card>
          <div className="min-[1000px]:order-1">
            <DocumentPreview title={t("timetable.print.preview")} src={url("html")} />
          </div>
        </div>
      )}
    </>
  );
}
