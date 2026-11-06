// Séance photo (lot 10, 6.1, maquette `cartes-seance-photo.html`) : une classe ou le personnel dans
// l'ordre de la liste ; « Garder » envoie la photo officielle (au journal) et passe au suivant. Le
// réseau tombe : les photos attendent dans la file et partent au retour. Jamais la personne
// elle-même : le droit `attendance.cards` suffit.
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardHeader,
  CardTitle,
  Icon,
  PageHeader,
  Segmented,
  Select,
  StatusPill,
} from "@mwangaza/ui";
import { useEffect, useRef, useState } from "react";

import { useClasses, useYears } from "../organisation/data";
import { useCardRefresh } from "./data";
import {
  type Person,
  type SessionKind,
  frameToFile,
  shrinkPhoto,
  uploadSessionPhoto,
  useSessionPeople,
} from "./photoSession";

type Queued = { kind: SessionKind; id: string; file: File };
type Mark = "taken" | "skipped";

export function PhotoSession({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const refresh = useCardRefresh();
  const [kind, setKind] = useState<SessionKind>("students");
  const [classGroup, setClassGroup] = useState("");
  const years = useYears();
  const year = years.data?.find((candidate) => candidate.is_current)?.id ?? "";
  const classes = useClasses(year);
  const people = useSessionPeople(kind, classGroup);
  const [marks, setMarks] = useState<Record<string, Mark>>({});
  const [cursor, setCursor] = useState(0);
  const [queue, setQueue] = useState<Queued[]>([]);
  const [sent, setSent] = useState(0);
  const [online, setOnline] = useState(navigator.onLine);
  const [error, setError] = useState(false);
  const flushing = useRef(false);

  const list: Person[] = people.data ?? [];
  const todo = list.filter((person) => !person.photo && marks[person.id] !== "taken");
  const total = list.length;
  const done = total - todo.length;
  const current = list[cursor];

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  // Envoi dans l'ordre ; un échec garde la photo en tête de file et attend le prochain essai.
  useEffect(() => {
    const first = queue[0];
    if (!first || !online || flushing.current) return;
    flushing.current = true;
    uploadSessionPhoto(first.kind, first.id, first.file)
      .then(() => {
        setQueue((rest) => rest.slice(1));
        setSent((count) => count + 1);
        void refresh();
        setError(false);
      })
      .catch(() => setError(true))
      .finally(() => {
        flushing.current = false;
      });
  }, [queue, online, sent, refresh]);

  function change(next: SessionKind, group: string) {
    setKind(next);
    setClassGroup(group);
    setMarks({});
    setCursor(0);
  }

  function advance(from: number, marked: Record<string, Mark>) {
    // Prochain « à prendre » après la position, puis depuis le début.
    const order = [...list.slice(from + 1), ...list.slice(0, from + 1)];
    const next = order.find((person) => !person.photo && marked[person.id] !== "taken");
    setCursor(next ? list.indexOf(next) : from);
  }

  function keep(file: File) {
    if (!current) return;
    const marked: Record<string, Mark> = { ...marks, [current.id]: "taken" };
    setMarks(marked);
    setQueue((rest) => [...rest, { kind, id: current.id, file }]);
    advance(cursor, marked);
  }

  function skip() {
    if (!current) return;
    const marked: Record<string, Mark> = {
      ...marks,
      [current.id]: marks[current.id] === "taken" ? "taken" : "skipped",
    };
    setMarks(marked);
    advance(cursor, marked);
  }

  return (
    <>
      <PageHeader
        title={t("cards.session.title")}
        subtitle={
          total ? t("cards.session.subtitle", { done, total, todo: todo.length }) : undefined
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Segmented
              value={kind}
              onValueChange={(next) => change(next, "")}
              options={[
                { value: "students", label: t("cards.tabs.students") },
                { value: "staff", label: t("cards.tabs.staff") },
              ]}
              label={t("cards.session.kind")}
            />
            {kind === "students" && (
              <Select
                aria-label={t("cards.filter.class")}
                value={classGroup}
                onChange={(event) => change("students", event.target.value)}
              >
                <option value="">{t("cards.session.pickClass")}</option>
                {(classes.data ?? []).map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </Select>
            )}
            <Button onClick={onClose}>{t("cards.session.finish")}</Button>
          </div>
        }
      />
      {todo.length > 0 && (
        <Banner tone="info" className="mt-4">
          {t("cards.session.withoutPhoto", { count: todo.length })}
        </Banner>
      )}
      {!total ? (
        <p className="mt-6 text-ink-3">
          {people.isFetching ? t("common.loading") : t("cards.session.empty")}
        </p>
      ) : (
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
          {current && (
            <Shot
              key={current.id}
              person={current}
              position={cursor + 1}
              total={total}
              state={marks[current.id] === "taken" || current.photo ? "taken" : "todo"}
              onKeep={keep}
              onSkip={skip}
            />
          )}
          <div className="flex flex-col gap-4">
            <Card>
              <div className="p-4">
                <div className="flex justify-between">
                  <b>{t("cards.session.progress")}</b>
                  <span className="text-sm text-ink-3">
                    {done} / {total}
                  </span>
                </div>
                <progress className="mt-2 h-2 w-full" value={done} max={total} />
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm text-ink-3">
                    {t("cards.session.queue", { count: queue.length })}
                  </span>
                  <StatusPill tone={online && !error ? "ok" : "warn"}>
                    {online && !error ? t("cards.session.online") : t("cards.session.offline")}
                  </StatusPill>
                </div>
              </div>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>{t("cards.session.list")}</CardTitle>
              </CardHeader>
              <ul className="divide-y divide-line-soft">
                {list.map((person, index) => {
                  const mark = marks[person.id];
                  const label =
                    mark === "taken"
                      ? "taken"
                      : person.photo
                        ? "had"
                        : mark === "skipped"
                          ? "skipped"
                          : "todo";
                  return (
                    <li key={person.id}>
                      <button
                        type="button"
                        onClick={() => setCursor(index)}
                        className={`flex w-full items-center justify-between gap-3 px-4 py-2 text-left ${index === cursor ? "bg-lake-50" : ""}`}
                      >
                        <span className="min-w-0">
                          <b className="block truncate">{person.name}</b>
                          <span className="text-sm text-ink-3">{person.detail}</span>
                        </span>
                        <StatusPill
                          tone={label === "todo" ? "warn" : label === "skipped" ? undefined : "ok"}
                        >
                          {t(`cards.session.state.${label}`)}
                        </StatusPill>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}

/** Caméra (ou, à défaut, l'appareil photo du téléphone) pour la personne en cours. */
function Shot({
  person,
  position,
  total,
  state,
  onKeep,
  onSkip,
}: {
  person: Person;
  position: number;
  total: number;
  state: "taken" | "todo";
  onKeep: (file: File) => void;
  onSkip: () => void;
}) {
  const { t } = useTranslation();
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const [facing, setFacing] = useState<"user" | "environment">("environment");
  const [asked, setAsked] = useState(false);
  const [denied, setDenied] = useState(false);
  const [taken, setTaken] = useState<{ file: File; url: string } | null>(null);
  const canStream = typeof navigator.mediaDevices?.getUserMedia === "function";

  useEffect(() => {
    if (!asked || !canStream || taken) return;
    let stopped = false;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: facing } })
      .then((media) => {
        if (stopped) return media.getTracks().forEach((track) => track.stop());
        stream.current = media;
        if (video.current) video.current.srcObject = media;
      })
      .catch(() => setDenied(true));
    return () => {
      stopped = true;
      stream.current?.getTracks().forEach((track) => track.stop());
      stream.current = null;
    };
  }, [asked, canStream, facing, taken]);

  useEffect(() => {
    if (!taken) return undefined;
    return () => URL.revokeObjectURL(taken.url);
  }, [taken]);

  async function shoot() {
    const file = video.current ? await frameToFile(video.current) : null;
    if (file) setTaken({ file, url: URL.createObjectURL(file) });
  }

  async function fromFile(file: File | undefined) {
    if (!file) return;
    const small = await shrinkPhoto(file);
    setTaken({ file: small, url: URL.createObjectURL(small) });
  }

  const live = asked && canStream && !denied;
  return (
    <Card>
      <div className="p-4">
        <div className="mx-auto flex max-w-[420px] items-center justify-between gap-3">
          <div className="min-w-0">
            <span className="text-sm text-ink-3">
              {t("cards.session.position", { position, total })}
            </span>
            <b className="block text-xl leading-tight">{person.name}</b>
            <span className="text-sm text-ink-3">{person.detail}</span>
          </div>
          <StatusPill tone={state === "taken" ? "ok" : "warn"}>
            {t(state === "taken" ? "cards.session.state.had" : "cards.session.state.todo")}
          </StatusPill>
        </div>
        <div className="relative mx-auto mt-3 aspect-[4/5] w-full max-w-[420px] overflow-hidden rounded-tr-2xl rounded-bl-2xl bg-[#1d2230]">
          {taken ? (
            <img src={taken.url} alt="" className="h-full w-full object-cover" />
          ) : live ? (
            <>
              <video
                ref={video}
                autoPlay
                playsInline
                muted
                className="h-full w-full object-cover"
              />
              <div className="pointer-events-none absolute left-1/2 top-[13%] aspect-[3/4] w-[46%] -translate-x-1/2 rounded-full border-[3px] border-dashed border-white/75" />
              <p className="absolute inset-x-0 top-3 text-center text-sm text-white">
                {t("cards.session.tip")}
              </p>
              <button
                type="button"
                aria-label={t("cards.session.flip")}
                onClick={() => setFacing(facing === "user" ? "environment" : "user")}
                className="absolute bottom-3 right-3 grid size-11 place-items-center rounded-full bg-white/20 text-white"
              >
                <Icon name="camera" />
              </button>
            </>
          ) : person.photo ? (
            <img src={person.photo} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="grid h-full place-items-center p-6 text-center text-white/90">
              {denied ? t("cards.session.denied") : t("cards.session.why")}
            </div>
          )}
        </div>
        <div className="mx-auto mt-3 grid max-w-[420px] grid-cols-[2fr_1fr] gap-2">
          {taken ? (
            <>
              <Button
                variant="default"
                size="lg"
                onClick={() => {
                  onKeep(taken.file);
                  setTaken(null);
                }}
              >
                {t("cards.session.keep")}
              </Button>
              <Button size="lg" onClick={() => setTaken(null)}>
                {t("cards.session.retake")}
              </Button>
            </>
          ) : live ? (
            <>
              <Button variant="default" size="lg" onClick={() => void shoot()}>
                {t("cards.session.shoot")}
              </Button>
              <Button size="lg" onClick={onSkip}>
                {t("cards.session.skip")}
              </Button>
            </>
          ) : (
            <>
              {canStream && !denied ? (
                <Button variant="default" size="lg" onClick={() => setAsked(true)}>
                  {t("cards.session.enable")}
                </Button>
              ) : (
                <label className="inline-flex">
                  <input
                    type="file"
                    accept="image/*"
                    capture="user"
                    className="sr-only"
                    onChange={(event) => void fromFile(event.target.files?.[0])}
                  />
                  <span className="inline-flex h-12 w-full cursor-pointer items-center justify-center rounded-md bg-lake px-4 font-medium text-white">
                    {t("cards.session.shoot")}
                  </span>
                </label>
              )}
              <Button size="lg" onClick={onSkip}>
                {t("cards.session.skip")}
              </Button>
            </>
          )}
        </div>
      </div>
    </Card>
  );
}
