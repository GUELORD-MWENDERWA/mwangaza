// Pointage à l'entrée (lot 10, 6.3 · maquette `presences-pointage-qr.html`) : une tablette ou un
// téléphone enregistré lit les cartes (caméra) ou reçoit un lecteur USB / un matricule tapé
// (borne). Chaque lecture : couleur + son + vibration ; la photo officielle de la personne est
// montrée (une photo collée sur une carte volée se voit). Sans réseau, les passages attendent dans
// la file et partent au retour.
import { useTranslation } from "@mwangaza/i18n";
import {
  Avatar,
  Banner,
  Button,
  Card,
  CardHeader,
  CardTitle,
  Icon,
  Input,
  Kpi,
  PageHeader,
  Segmented,
  Skeleton,
} from "@mwangaza/ui";
import { useCallback, useEffect, useRef, useState } from "react";

import { useSyncStatus } from "../../lib/sync/session";
import { LoadError } from "../status/StatusPages";
import {
  dayPassages,
  loadRoster,
  localDay,
  read,
  recordPassage,
  type Input as ScanInput,
  type Outcome,
  type Passage,
  type Reading,
  type Roster,
} from "./entrance";
import {
  keepAwake,
  loadSettings,
  saveSettings,
  signal,
  unlockSound,
  type SignalSettings,
} from "./signals";
import { DeviceSignals } from "./DeviceSignals";

type Mode = "camera" | "kiosk";
const TONE = { arrived: "ok", late: "warn", already: "info", refused: "due" } as const;

type Found = { rawValue: string };
type BarcodeDetectorLike = {
  detect(source: HTMLVideoElement): PromiseLike<Found[]>;
};
function detector(): BarcodeDetectorLike | null {
  const Native = (
    window as unknown as {
      BarcodeDetector?: new (options: { formats: string[] }) => BarcodeDetectorLike;
    }
  ).BarcodeDetector;
  return Native ? new Native({ formats: ["qr_code"] }) : null;
}

export function EntrancePage() {
  const { t } = useTranslation();
  const { db } = useSyncStatus();
  const [roster, setRoster] = useState<Roster | null>(null);
  const [fresh, setFresh] = useState(true);
  const [failed, setFailed] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [passages, setPassages] = useState<Passage[]>([]);
  const [last, setLast] = useState<{ outcome: Outcome; passage?: Passage; reason?: string } | null>(
    null,
  );
  const [mode, setMode] = useState<Mode>("camera");
  const [settings, setSettings] = useState<SignalSettings>(loadSettings);
  const today = localDay(new Date());

  useEffect(() => {
    if (!db) return;
    let stopped = false;
    void (async () => {
      try {
        const [result, known] = await Promise.all([loadRoster(db), dayPassages(db, today)]);
        if (stopped) return;
        setRoster(result.roster);
        setFresh(result.fresh);
        setPassages(known);
      } catch (error) {
        if (!stopped) setFailed(error);
      } finally {
        if (!stopped) setLoading(false);
      }
    })();
    return () => {
      stopped = true;
    };
  }, [db, today]);

  useEffect(() => (settings.awake ? keepAwake() : undefined), [settings.awake]);

  const passed = useRef(new Map<string, Passage>());
  useEffect(() => {
    passed.current = new Map(passages.map((passage) => [passage.personId, passage]));
  }, [passages]);

  const handle = useCallback(
    async (input: ScanInput) => {
      if (!db || !roster) return;
      const reading: Reading = await read(roster, input, passed.current);
      signal(reading.outcome, settings);
      if (reading.outcome === "refused") {
        setLast({ outcome: "refused", reason: reading.reason });
        return;
      }
      setLast({ outcome: reading.outcome, passage: reading.passage });
      if (reading.outcome !== "already") {
        passed.current.set(reading.person.id, reading.passage);
        await recordPassage(db, reading.passage, "card" in input ? reading.person.cardHash : "");
        setPassages(await dayPassages(db, today));
      }
    },
    [db, roster, settings, today],
  );

  function change(next: Partial<SignalSettings>) {
    const merged = { ...settings, ...next };
    setSettings(merged);
    saveSettings(merged);
  }

  if (db && loading) return <Skeleton label={t("entrance.title")} />;
  if (failed) return <LoadError error={failed} onRetry={() => window.location.reload()} />;
  if (!db)
    return (
      <>
        <PageHeader title={t("entrance.title")} />
        <Banner tone="warn">{t("entrance.noDevice")}</Banner>
      </>
    );
  if (!roster)
    return (
      <>
        <PageHeader title={t("entrance.title")} />
        <Banner tone="warn">{t("entrance.noRoster")}</Banner>
      </>
    );

  const count = (outcome: Outcome) =>
    passages.filter((passage) => passage.outcome === outcome).length;
  const students = roster.people.filter((person) => person.kind === "student").length;
  return (
    <>
      <PageHeader
        title={t("entrance.title")}
        subtitle={t("entrance.subtitle", { date: new Date().toLocaleDateString() })}
        actions={
          <Segmented<Mode>
            label={t("entrance.mode")}
            value={mode}
            onValueChange={setMode}
            options={[
              { value: "camera", label: t("entrance.modes.camera") },
              { value: "kiosk", label: t("entrance.modes.kiosk") },
            ]}
          />
        }
      />
      {!fresh && (
        <Banner tone="info" className="mb-4">
          {t("entrance.keptRoster")}
        </Banner>
      )}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <Card>
          <div className="flex flex-col items-center gap-4 p-4">
            {mode === "camera" ? (
              <CameraReader onRead={(card) => void handle({ card })} />
            ) : (
              <KioskReader
                onCard={(card) => void handle({ card })}
                onMatricule={(matricule) => void handle({ matricule })}
              />
            )}
            <Result last={last} />
          </div>
        </Card>
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Kpi
              label={t("entrance.kpi.arrived")}
              value={count("arrived") + count("late")}
              tone="ok"
            />
            <Kpi label={t("entrance.kpi.late")} value={count("late")} tone="warn" />
            <Kpi
              label={t("entrance.kpi.students")}
              value={passages.filter((p) => p.kind === "student").length}
              sub={t("entrance.kpi.of", { count: students })}
            />
            <Kpi
              label={t("entrance.kpi.staff")}
              value={passages.filter((p) => p.kind === "member").length}
            />
          </div>
          <Card>
            <CardHeader>
              <CardTitle>{t("entrance.recent")}</CardTitle>
            </CardHeader>
            <div className="divide-y divide-line">
              {passages.length === 0 && (
                <p className="p-4 text-sm text-ink-3">{t("entrance.none")}</p>
              )}
              {passages.slice(0, 8).map((passage) => (
                <div key={passage.id} className="flex items-center gap-3 px-4 py-2.5">
                  <Avatar text={passage.name} />
                  <span className="min-w-0 flex-1">
                    <b className="block truncate">{passage.name}</b>
                    <span className="text-sm text-ink-3">{passage.detail}</span>
                  </span>
                  <span className="text-sm tabular-nums text-ink-3">
                    {new Date(passage.seenAt).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  <span className={passage.outcome === "late" ? "text-warn" : "text-ok"}>
                    {t(`entrance.outcome.${passage.outcome}`)}
                  </span>
                </div>
              ))}
            </div>
          </Card>
          <DeviceSignals settings={settings} onChange={change} />
        </div>
      </div>
    </>
  );
}

function Result({
  last,
}: {
  last: { outcome: Outcome; passage?: Passage; reason?: string } | null;
}) {
  const { t } = useTranslation();
  if (!last)
    return (
      <Banner tone="info" className="w-full">
        {t("entrance.ready")}
      </Banner>
    );
  const tone = TONE[last.outcome];
  return (
    <Banner tone={tone} className="w-full text-base" role="status" aria-live="polite">
      {last.passage ? (
        <div className="flex items-center gap-3">
          <Photo passage={last.passage} />
          <div>
            <b className="block text-lg">{last.passage.name}</b>
            <span>{last.passage.detail}</span> ·{" "}
            <span>{t(`entrance.outcome.${last.outcome}`)}</span>
          </div>
        </div>
      ) : (
        <b>
          {last.reason === "mistyped"
            ? t("entrance.refused.mistyped")
            : t("entrance.refused.unknown")}
        </b>
      )}
    </Banner>
  );
}

function Photo({ passage }: { passage: Passage }) {
  const [broken, setBroken] = useState(false);
  return passage.photo && !broken ? (
    <img
      src={passage.photo}
      alt=""
      className="h-20 w-16 rounded-lg object-cover"
      onError={() => setBroken(true)}
    />
  ) : (
    <Avatar text={passage.name} />
  );
}

/** Lecture QR par la caméra : l'API du navigateur (`BarcodeDetector`) ; sans elle, borne ou saisie. */
function CameraReader({ onRead }: { onRead: (card: string) => void }) {
  const { t } = useTranslation();
  const video = useRef<HTMLVideoElement>(null);
  const [state, setState] = useState<"ask" | "live" | "denied" | "unsupported">(
    detector() ? "ask" : "unsupported",
  );

  useEffect(() => {
    if (state !== "live") return undefined;
    const reader = detector();
    let media: MediaStream | null = null;
    let stopped = false;
    let lastText = "";
    let lastAt = 0;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "environment" } })
      .then((stream) => {
        if (stopped) return stream.getTracks().forEach((track) => track.stop());
        media = stream;
        if (video.current) video.current.srcObject = stream;
        const tick = async () => {
          if (stopped) return;
          try {
            const found = video.current ? await reader!.detect(video.current) : [];
            const text = found[0]?.rawValue;
            // La même carte gardée devant la caméra n'est lue qu'une fois toutes les 3 s.
            if (text && (text !== lastText || Date.now() - lastAt > 3000)) {
              lastText = text;
              lastAt = Date.now();
              onRead(text);
            }
          } catch {
            // Image pas prête : on réessaie.
          }
          window.setTimeout(tick, 250);
        };
        void tick();
      })
      .catch(() => setState("denied"));
    return () => {
      stopped = true;
      media?.getTracks().forEach((track) => track.stop());
    };
  }, [state, onRead]);

  if (state === "unsupported")
    return (
      <Banner tone="warn" className="w-full">
        {t("entrance.camera.unsupported")}
      </Banner>
    );
  if (state === "denied")
    return (
      <Banner tone="due" className="w-full">
        {t("entrance.camera.denied")}
      </Banner>
    );
  if (state === "ask")
    return (
      <div className="flex w-full max-w-lg flex-col items-center gap-3 py-6 text-center">
        <Icon name="camera" size={32} />
        <p>{t("entrance.camera.why")}</p>
        <Button
          onClick={() => {
            unlockSound();
            setState("live");
          }}
        >
          {t("entrance.camera.start")}
        </Button>
      </div>
    );
  return (
    <div className="relative aspect-[4/3] w-full max-w-lg overflow-hidden rounded-2xl bg-night">
      <video ref={video} autoPlay playsInline muted className="h-full w-full object-cover" />
      <span className="absolute inset-x-0 bottom-3 text-center text-sm text-white">
        {t("entrance.camera.hint")}
      </span>
    </div>
  );
}

/** Borne : un lecteur USB « tape » le jeton puis Entrée ; sinon on tape un matricule. */
function KioskReader({
  onCard,
  onMatricule,
}: {
  onCard: (card: string) => void;
  onMatricule: (matricule: string) => void;
}) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const field = useRef<HTMLInputElement>(null);
  useEffect(() => field.current?.focus(), []);
  function submit() {
    const value = text.trim();
    setText("");
    if (value) (value.startsWith("MWZ1:") ? onCard : onMatricule)(value);
    field.current?.focus();
  }
  return (
    <form
      className="flex w-full max-w-lg flex-col gap-2 py-4"
      onSubmit={(event) => {
        event.preventDefault();
        unlockSound();
        submit();
      }}
    >
      <label className="text-sm font-semibold" htmlFor="entrance-field">
        {t("entrance.kiosk.label")}
      </label>
      <div className="flex gap-2">
        <Input
          id="entrance-field"
          ref={field}
          value={text}
          autoComplete="off"
          autoCapitalize="characters"
          onChange={(event) => setText(event.target.value)}
        />
        <Button type="submit">{t("entrance.kiosk.submit")}</Button>
      </div>
      <p className="text-sm text-ink-3">{t("entrance.kiosk.hint")}</p>
    </form>
  );
}
