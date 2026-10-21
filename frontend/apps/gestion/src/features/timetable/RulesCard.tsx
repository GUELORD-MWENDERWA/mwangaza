// Carte « Règles » de l'écran « Règles et contrôles » (EDT.1c, maquette
// `controles-emploi-du-temps`) : chaque règle en une phrase, obligatoire ou souhait avec son
// poids ; une règle désactivée reste grisée. Les règles générales de l'école se règlent sur la
// grille horaire. Droit `timetable.manage`.
import { useTranslation } from "@mwangaza/i18n";
import { Button, Card, CardContent, CardHeader, CardTitle, StatusPill, cn } from "@mwangaza/ui";
import { Link } from "react-router";

import type { Rule, Rules } from "./data";
import { type Lookup, describe } from "./rules";

type Props = {
  rules: Rule[];
  lookup: Lookup;
  general: Rules | undefined;
  onAdd: () => void;
  onEdit: (rule: Rule) => void;
};

export function RulesCard({ rules, lookup, general, onAdd, onEdit }: Props) {
  const { t, i18n } = useTranslation();
  const generalText =
    general &&
    new Intl.ListFormat(i18n.language, { style: "long", type: "conjunction" }).format([
      t("timetable.constraints.general.course", { count: general.max_same_course_per_day }),
      t("timetable.constraints.general.teacher", { count: general.teacher_max_day_hours }),
      ...(general.no_gaps ? [t("timetable.constraints.general.noGaps")] : []),
      ...(general.main_courses_early ? [t("timetable.constraints.general.early")] : []),
    ]);

  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle>{t("timetable.constraints.title", { number: rules.length })}</CardTitle>
        <Button size="sm" onClick={onAdd}>
          {t("timetable.constraints.add")}
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {generalText && (
          <p className="text-sm text-ink-3">
            {t("timetable.constraints.general.intro", { rules: generalText })}{" "}
            <Link to="/time-grid" className="font-bold underline">
              {t("shell.menu.timeGrid")}
            </Link>
          </p>
        )}
        {rules.length === 0 ? (
          <p className="text-sm text-ink-2">{t("timetable.constraints.empty")}</p>
        ) : (
          <ul className="flex flex-col">
            {rules.map((rule) => {
              const { subject, text } = describe(rule, lookup, t, i18n.language);
              return (
                <li
                  key={rule.id}
                  className={cn(
                    "flex flex-wrap items-start justify-between gap-x-3 gap-y-2 border-b border-line-soft py-3 last:border-b-0",
                    !rule.active && "opacity-60",
                  )}
                >
                  <div className="flex min-w-0 flex-1 basis-[200px] flex-col gap-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <b className="min-w-0 break-words">{subject}</b>
                      <StatusPill tone={!rule.active || rule.strength === "hard" ? "gray" : "info"}>
                        {!rule.active
                          ? t("timetable.constraints.inactive")
                          : rule.strength === "hard"
                            ? t("timetable.constraints.strength.hard")
                            : t("timetable.constraints.wish", { weight: rule.weight })}
                      </StatusPill>
                    </span>
                    <span className="text-sm text-ink-2">{text}</span>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => onEdit(rule)}>
                    {t("timetable.constraints.edit")}
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
