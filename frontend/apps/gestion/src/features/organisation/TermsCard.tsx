// Découpage de l'année (C1) : semestres ou trimestres, leurs périodes et examens. « Modifier les
// dates » passe la carte en saisie : noms, dates, éléments ajoutés ou retirés ; tout part d'un seul
// envoi, les refus du serveur s'affichent sous le champ concerné.
import { ApiError, api, call } from "@mwangaza/api";
import { formatDay, type TFunction, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardFooter,
  CardHeader,
  CardTitle,
  Icon,
  Input,
  Table,
  cn,
} from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { Fragment, useState } from "react";

import { errorMessage, fieldMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { termLabels, type TermKind } from "../../lib/terms";
import { useRefresh, type Term, type Year } from "./data";

/** Élément du découpage en cours de saisie ; `key` : repère local (un nouvel élément n'a pas
 *  encore d'`id`). */
type Draft = {
  key: string;
  id?: string;
  kind: TermKind;
  name: string;
  starts_on: string;
  ends_on: string;
  children: Draft[];
};

let lastKey = 0;
const newKey = () => `new-${++lastKey}`;

function toDraft(term: Term | Term["children"][number]): Draft {
  return {
    key: term.id,
    id: term.id,
    kind: term.kind,
    name: term.name,
    starts_on: term.starts_on ?? "",
    ends_on: term.ends_on ?? "",
    children: "children" in term ? term.children.map(toDraft) : [],
  };
}

function blank(kind: TermKind): Draft {
  return { key: newKey(), kind, name: "", starts_on: "", ends_on: "", children: [] };
}

function toBody(draft: Draft) {
  return {
    ...(draft.id ? { id: draft.id } : {}),
    kind: draft.kind,
    name: draft.name.trim(),
    starts_on: draft.starts_on || null,
    ends_on: draft.ends_on || null,
  };
}

const isGroup = (kind: TermKind) => kind === "semester" || kind === "trimester";

/** Nom par défaut de chaque élément (sans le nom donné par l'école), par `key`. */
function defaultLabels(drafts: Draft[], t: TFunction): Map<string, string> {
  const stripped = drafts.map((draft) => ({
    ...draft,
    name: "",
    children: draft.children.map((child) => ({ ...child, name: "" })),
  }));
  const labels = termLabels(stripped, t);
  const byKey = new Map<string, string>();
  for (const node of stripped) {
    for (const item of [node, ...node.children]) byKey.set(item.key, labels.get(item) ?? "");
  }
  return byKey;
}

export function TermsCard({ year }: { year: Year }) {
  const { t } = useTranslation();
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("organisation.terms.title")}</CardTitle>
        {!drafts && (
          <Button variant="outline" size="sm" onClick={() => setDrafts(year.terms.map(toDraft))}>
            {t("organisation.terms.edit")}
          </Button>
        )}
      </CardHeader>
      {drafts ? (
        <TermsEditor
          year={year}
          drafts={drafts}
          onChange={setDrafts}
          onDone={() => setDrafts(null)}
        />
      ) : (
        <TermsView terms={year.terms} />
      )}
    </Card>
  );
}

function TermsView({ terms }: { terms: Term[] }) {
  const { t, i18n } = useTranslation();
  const labels = termLabels(terms, t);
  const day = (value: string | null) =>
    value ? formatDay(value, i18n.language) : t("common.none");
  const rows = terms.flatMap((term) => [
    { term, child: false },
    ...term.children.map((child) => ({ term: child, child: true })),
  ]);
  const missing = rows.some(({ term }) => !term.starts_on || !term.ends_on);
  if (terms.length === 0) {
    return <p className="px-[18px] py-4 text-ink-3">{t("organisation.terms.empty")}</p>;
  }
  return (
    <>
      {missing && (
        <div className="px-[18px] pt-3">
          <Banner tone="warn">{t("organisation.terms.missingDates")}</Banner>
        </div>
      )}
      <Table>
        <thead>
          <tr>
            <th>{t("organisation.terms.period")}</th>
            <th>{t("organisation.terms.starts")}</th>
            <th>{t("organisation.terms.ends")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ term, child }) => (
            <tr key={term.id}>
              <td className={cn(child ? "pl-7" : "font-bold")}>{labels.get(term)}</td>
              <td className="tabular-nums">{day(term.starts_on)}</td>
              <td className="tabular-nums">{day(term.ends_on)}</td>
            </tr>
          ))}
        </tbody>
      </Table>
    </>
  );
}

type EditorProps = {
  year: Year;
  drafts: Draft[];
  onChange: (drafts: Draft[]) => void;
  onDone: () => void;
};

function TermsEditor({ year, drafts, onChange, onDone }: EditorProps) {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const labels = termLabels(drafts, t);
  const defaults = defaultLabels(drafts, t);
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PUT("/api/academic-years/{id}/terms/", {
          params: { path: { id: year.id } },
          body: {
            terms: drafts.map((draft) => ({
              ...toBody(draft),
              children: draft.children.map(toBody),
            })),
          },
        }),
      ),
    onSuccess: async () => {
      await refresh(keys.years);
      onDone();
    },
  });
  const fields = save.error instanceof ApiError ? save.error.fields : {};
  const fieldError = (path: string) => {
    const [first] = fields[path] ?? [];
    return first ? fieldMessage(first.code, t) : undefined;
  };
  const placed = Object.keys(fields).some((path) =>
    /\.(name|starts_on|ends_on|kind|id)$/.test(path),
  );

  const update = (target: Draft, change: Partial<Draft>) =>
    onChange(
      drafts.map((draft) =>
        draft === target
          ? { ...draft, ...change }
          : {
              ...draft,
              children: draft.children.map((child) =>
                child === target ? { ...child, ...change } : child,
              ),
            },
      ),
    );
  const remove = (target: Draft) =>
    onChange(
      drafts
        .filter((draft) => draft !== target)
        .map((draft) => ({
          ...draft,
          children: draft.children.filter((child) => child !== target),
        })),
    );
  const addChild = (parent: Draft, kind: TermKind) =>
    onChange(
      drafts.map((draft) =>
        draft === parent ? { ...draft, children: [...draft.children, blank(kind)] } : draft,
      ),
    );

  const row = (draft: Draft, path: string, child: boolean) => {
    const label = labels.get(draft) ?? "";
    const fallback = defaults.get(draft.key) ?? "";
    const errors = ["name", "starts_on", "ends_on", "kind", "id"]
      .map((field) => fieldError(`${path}.${field}`))
      .filter(Boolean);
    return (
      <tr key={draft.key}>
        <td className={cn(child && "pl-7")}>
          <Input
            aria-label={`${t("organisation.terms.name")} — ${fallback}`}
            value={draft.name}
            placeholder={fallback}
            onChange={(event) => update(draft, { name: event.target.value })}
            className={cn("min-w-[180px]", !child && "font-bold")}
          />
          {errors.map((error) => (
            <p key={error} role="alert" className="mt-1 text-xs text-due">
              {error}
            </p>
          ))}
        </td>
        {(["starts_on", "ends_on"] as const).map((bound) => (
          <td key={bound}>
            <Input
              type="date"
              aria-label={`${t(bound === "starts_on" ? "organisation.terms.starts" : "organisation.terms.ends")} — ${fallback}`}
              aria-invalid={fieldError(`${path}.${bound}`) ? true : undefined}
              value={draft[bound]}
              onChange={(event) => update(draft, { [bound]: event.target.value })}
            />
          </td>
        ))}
        <td className="w-10">
          <Button
            variant="ghost"
            size="sm"
            aria-label={t("organisation.terms.remove", { name: label })}
            onClick={() => remove(draft)}
          >
            <Icon name="x" size={16} />
          </Button>
        </td>
      </tr>
    );
  };

  return (
    <>
      {save.isError && !placed && (
        <div className="px-[18px] pt-3">
          <Banner tone="due">{errorMessage(save.error, t)}</Banner>
        </div>
      )}
      <Table>
        <thead>
          <tr>
            <th>{t("organisation.terms.period")}</th>
            <th>{t("organisation.terms.starts")}</th>
            <th>{t("organisation.terms.ends")}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {drafts.map((draft, index) => (
            <Fragment key={draft.key}>
              {row(draft, `terms.${index}`, false)}
              {draft.children.map((child, childIndex) =>
                row(child, `terms.${index}.children.${childIndex}`, true),
              )}
              {isGroup(draft.kind) && (
                <tr>
                  <td colSpan={4} className="pl-7">
                    <div className="flex flex-wrap gap-2">
                      <Button variant="ghost" size="sm" onClick={() => addChild(draft, "period")}>
                        <Icon name="plus" size={14} />
                        {t("organisation.terms.addPeriod")}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => addChild(draft, "exam")}>
                        <Icon name="plus" size={14} />
                        {t("organisation.terms.addExam")}
                      </Button>
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </Table>
      <CardFooter>
        <div className="flex flex-wrap gap-2">
          {(["semester", "trimester", "period"] as const).map((kind) => (
            <Button
              key={kind}
              variant="outline"
              size="sm"
              onClick={() => onChange([...drafts, blank(kind)])}
            >
              <Icon name="plus" size={14} />
              {t(
                kind === "semester"
                  ? "organisation.terms.addSemester"
                  : kind === "trimester"
                    ? "organisation.terms.addTrimester"
                    : "organisation.terms.addPeriod",
              )}
            </Button>
          ))}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onDone}>
            {t("common.cancel")}
          </Button>
          <Button disabled={save.isPending} onClick={() => save.mutate()}>
            {t("organisation.terms.save")}
          </Button>
        </div>
      </CardFooter>
    </>
  );
}
