import { useTranslation } from "@mwangaza/i18n";
import {
  Brand,
  BrandMark,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Icon,
  usePlatform,
} from "@mwangaza/ui";
import { useNavigate } from "react-router";

import { installLater, useInstallPrompt } from "../../lib/install";

const BENEFITS = ["oneTap", "offline", "notifications", "light"] as const;
const IPHONE_STEPS = ["share", "addToHome", "add"] as const;

/** « Installer » (maquette `installer`, H6, M19) : proposé une fois après l'activation, puis par
 *  le bandeau de l'accueil. Android / Chrome : l'invite du navigateur ; iPhone : 3 étapes (pas
 *  d'invite). « Plus tard » masque le bandeau 7 jours. */
export function InstallPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const install = useInstallPrompt();
  const { icon } = usePlatform();
  const home = () => void navigate("/", { replace: true });

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-basalt px-5 pt-7 pb-8 text-basalt-ink">
        <div className="mx-auto max-w-[640px]">
          <Brand />
          <h1 className="mt-5 text-2xl">{t("portal.install.title")}</h1>
          <p className="mt-1.5 text-basalt-muted">{t("portal.install.subtitle")}</p>
        </div>
      </header>
      <main className="mx-auto flex max-w-[640px] flex-col gap-4 px-4 py-5">
        <Card className="overflow-hidden">
          <div
            aria-hidden="true"
            className="grid place-items-center bg-[linear-gradient(160deg,var(--color-basalt),var(--color-lake))] py-6"
          >
            {icon ? (
              <img src={icon} alt="" className="size-[60px] rounded-[14px]" />
            ) : (
              <BrandMark className="size-[60px]" />
            )}
          </div>
          <CardContent className="flex flex-col gap-4">
            <h2 className="text-xl">{t("portal.install.heading")}</h2>
            <ul className="flex flex-col gap-2.5">
              {BENEFITS.map((key) => (
                <li key={key} className="flex items-center gap-2.5">
                  <Icon name="check" size={18} className="shrink-0 text-ok" />
                  {t(`portal.install.benefits.${key}`)}
                </li>
              ))}
            </ul>
            {install ? (
              <Button size="lg" onClick={() => void install().then(home)}>
                {t("portal.install.install")}
              </Button>
            ) : (
              <p className="text-sm text-ink-3">{t("portal.install.browserMenu")}</p>
            )}
            <Button
              variant="ghost"
              onClick={() => {
                installLater();
                home();
              }}
            >
              {t("portal.install.later")}
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("portal.install.iphone")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="flex flex-col gap-2.5">
              {IPHONE_STEPS.map((key, index) => (
                <li key={key} className="flex items-center gap-2.5">
                  <span className="grid size-6 shrink-0 place-items-center rounded-full bg-gray-50 text-xs font-bold">
                    {index + 1}
                  </span>
                  {t(`portal.install.steps.${key}`)}
                </li>
              ))}
            </ol>
            <p className="mt-3 text-sm text-ink-3">{t("portal.install.iphoneNotifications")}</p>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
