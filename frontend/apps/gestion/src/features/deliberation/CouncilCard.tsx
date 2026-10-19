// Conseil de la classe (NB.5, maquette `deliberation`) : membres calculés par le serveur
// (direction des études, titulaire, enseignants de la classe), présents, président et secrétaire
// choisis parmi les présents, observations. Enregistré par la direction des études tant que la
// session n'est pas proclamée ; les autres membres le lisent. Tout figure au procès-verbal.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  Checkbox,
  Field,
  Select,
  Table,
  Textarea,
} from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { firstErrorMessage } from "../../lib/errors";
import type { ClassDeliberation, CouncilMember } from "./data";

type Props = {
  classId: string;
  termId: string;
  council: ClassDeliberation["council"];
  editable: boolean;
  onSaved: () => void;
};

export function CouncilCard({ classId, termId, council, editable, onSaved }: Props) {
  const { t } = useTranslation();
  const [present, setPresent] = useState(
    () => new Set(council.members.filter((m) => m.present).map((m) => m.id)),
  );
  const [chair, setChair] = useState(council.chair ?? "");
  const [secretary, setSecretary] = useState(council.secretary ?? "");
  const [remarks, setRemarks] = useState(council.remarks);

  const save = useMutation({
    mutationFn: () =>
      call(
        api.PUT("/api/class-groups/{id}/deliberation/council/", {
          params: { path: { id: classId }, query: termId ? { term: termId } : {} },
          body: {
            present: council.members.filter((m) => present.has(m.id)).map((m) => m.id),
            chair: chair || null,
            secretary: secretary || null,
            remarks,
          },
        }),
      ),
    onSuccess: onSaved,
  });

  const quality = (member: CouncilMember) =>
    [
      member.direction && t("deliberation.council.direction"),
      member.homeroom && t("deliberation.council.homeroom"),
      member.courses.join(", "),
    ]
      .filter(Boolean)
      .join(" · ");

  const toggle = (id: string, on: boolean) => {
    const next = new Set(present);
    if (on) next.add(id);
    else next.delete(id);
    setPresent(next);
    if (!on && chair === id) setChair("");
    if (!on && secretary === id) setSecretary("");
  };

  const attending = council.members.filter((m) => present.has(m.id));
  const chooser = (id: string, label: string, value: string, change: (v: string) => void) => (
    <div className="min-w-56">
      <Field id={id} label={label}>
        {(control) => (
          <Select
            {...control}
            disabled={!editable}
            value={value}
            onChange={(event) => change(event.target.value)}
          >
            <option value="">{t("deliberation.council.nobody")}</option>
            {attending.map((member) => (
              <option key={member.id} value={member.id}>
                {member.name}
              </option>
            ))}
          </Select>
        )}
      </Field>
    </div>
  );

  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-semibold">{t("deliberation.council.title")}</h2>
          <span className="text-sm text-ink-3">
            {t("deliberation.council.count", {
              present: attending.length,
              total: council.members.length,
            })}
          </span>
        </div>
        <Table stacked>
          <thead>
            <tr>
              <th className="w-20">{t("deliberation.council.present")}</th>
              <th>{t("deliberation.council.member")}</th>
              <th>{t("deliberation.council.as")}</th>
            </tr>
          </thead>
          <tbody>
            {council.members.map((member) => (
              <tr key={member.id}>
                <td data-label={t("deliberation.council.present")}>
                  <Checkbox
                    aria-label={t("deliberation.council.presentFor", { name: member.name })}
                    disabled={!editable}
                    checked={present.has(member.id)}
                    onCheckedChange={(on) => toggle(member.id, on === true)}
                  />
                </td>
                <td className="font-semibold">{member.name}</td>
                <td data-label={t("deliberation.council.as")} className="text-ink-3" data-wrap>
                  {quality(member)}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
        <div className="flex flex-wrap gap-3">
          {chooser("council-chair", t("deliberation.council.chair"), chair, setChair)}
          {chooser(
            "council-secretary",
            t("deliberation.council.secretary"),
            secretary,
            setSecretary,
          )}
        </div>
        <Field id="council-remarks" label={t("deliberation.council.remarks")}>
          {(control) => (
            <Textarea
              {...control}
              rows={3}
              maxLength={2000}
              disabled={!editable}
              value={remarks}
              onChange={(event) => setRemarks(event.target.value)}
            />
          )}
        </Field>
        {save.isError && <Banner tone="due">{firstErrorMessage(save.error, t)}</Banner>}
        {editable && (
          <div>
            <Button variant="outline" disabled={save.isPending} onClick={() => save.mutate()}>
              {t("deliberation.council.save")}
            </Button>
          </div>
        )}
        <p className="text-xs text-ink-3">{t("deliberation.council.help")}</p>
      </CardContent>
    </Card>
  );
}
