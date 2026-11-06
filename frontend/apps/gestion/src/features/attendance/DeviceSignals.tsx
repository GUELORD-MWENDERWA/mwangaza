// Panneau « Cet appareil » (lot 10, SIG.1) : son, vibration, écran allumé, essai des signaux.
// Réglages gardés sur l'appareil seulement ; partagé par le pointage et « Mon compte ».
import { useTranslation } from "@mwangaza/i18n";
import { Button, Card, CardHeader, CardTitle, Switch } from "@mwangaza/ui";

import { canVibrate, signal, unlockSound, type SignalSettings } from "./signals";

export function DeviceSignals({
  settings,
  onChange,
}: {
  settings: SignalSettings;
  onChange: (next: Partial<SignalSettings>) => void;
}) {
  const { t } = useTranslation();
  const rows: { key: keyof SignalSettings; show: boolean }[] = [
    { key: "sound", show: true },
    { key: "vibration", show: canVibrate() },
    { key: "awake", show: true },
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("entrance.device.title")}</CardTitle>
        <Button
          size="sm"
          onClick={() => {
            unlockSound();
            (["arrived", "late", "already", "refused"] as const).forEach((kind, index) =>
              window.setTimeout(() => signal(kind, settings), index * 900),
            );
          }}
        >
          {t("entrance.device.test")}
        </Button>
      </CardHeader>
      <div className="divide-y divide-line">
        {rows
          .filter((row) => row.show)
          .map((row) => (
            <label key={row.key} className="flex items-center justify-between gap-3 px-4 py-3">
              <span>
                <b className="block">{t(`entrance.device.${row.key}`)}</b>
                <span className="text-sm text-ink-3">{t(`entrance.device.${row.key}Hint`)}</span>
              </span>
              <Switch
                checked={settings[row.key]}
                onCheckedChange={(checked) => onChange({ [row.key]: checked })}
              />
            </label>
          ))}
      </div>
      <p className="px-4 pb-3 text-sm text-ink-3">{t("entrance.device.legend")}</p>
    </Card>
  );
}
