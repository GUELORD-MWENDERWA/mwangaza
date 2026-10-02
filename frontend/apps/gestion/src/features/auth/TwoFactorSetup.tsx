import { api, call, type Schemas } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Code,
  CodeInput,
  Field,
  StatusPill,
  Steps,
  Tag,
} from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { errorMessage } from "../../lib/errors";
import { hasCode, type LoginStep } from "../../lib/queries";
import { QrCode } from "./QrCode";
import { RecoveryCodes } from "./RecoveryCodes";

type TotpKey = Schemas["TotpKey"];

/** Activer la double authentification (M1) : application, QR code (ou clé), premier code, puis
 *  les 8 codes de secours, montrés une seule fois. « Terminer » reste bloqué tant que la case
 *  n'est pas cochée. Sert à la connexion (étape obligatoire) et dans Mon compte. */
export function TwoFactorSetup({
  totpKey,
  phone,
  onDone,
  onExpired,
}: {
  totpKey: TotpKey;
  /** Compte, écrit en tête du fichier des codes de secours (inconnu pendant la connexion). */
  phone?: string;
  onDone: (step: LoginStep) => void;
  /** Clé perdue par le serveur (connexion expirée…) : en demander une autre. */
  onExpired?: () => void;
}) {
  const { t } = useTranslation();
  const [code, setCode] = useState("");
  const [missing, setMissing] = useState(false);
  const activate = useMutation({
    mutationFn: () => call(api.POST("/api/auth/totp/activate/", { body: { code } })),
    onError: (error) => {
      setCode("");
      if (hasCode(error, "totp_setup_not_started", "login_expired", "wrong_step")) onExpired?.();
    },
  });
  const codes = activate.data?.recovery_codes ?? null;

  function submit(event: FormEvent) {
    event.preventDefault();
    setMissing(code.length !== 6);
    if (code.length === 6) activate.mutate();
  }

  const codeError = missing
    ? t("validation.codeLength")
    : hasCode(activate.error, "invalid_code")
      ? errorMessage(activate.error, t)
      : undefined;
  const generalError =
    activate.isError && !hasCode(activate.error, "invalid_code")
      ? errorMessage(activate.error, t)
      : null;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardContent>
          <Steps
            steps={[
              { label: t("auth.setup.steps.app"), state: "done" },
              { label: t("auth.setup.steps.scan"), state: codes ? "done" : "current" },
              { label: t("auth.setup.steps.codes"), state: codes ? "current" : "todo" },
            ]}
          />
        </CardContent>
      </Card>
      <div className="grid grid-cols-1 items-start gap-4 min-[900px]:grid-cols-2">
        <Card>
          <form noValidate onSubmit={submit}>
            <CardContent className="flex flex-col gap-3">
              <Instruction number={1} title={t("auth.setup.installTitle")}>
                {t("auth.setup.installText")}
              </Instruction>
              <Instruction number={2} title={t("auth.setup.scanTitle")} />
              <div className="flex justify-center py-1.5">
                <QrCode value={totpKey.otpauth_uri} label={t("auth.setup.qrAlt")} />
              </div>
              <p className="text-center text-sm text-ink-3">
                {t("auth.setup.cantScan")}
                <br />
                <Code className="text-ink">{totpKey.secret.replace(/(.{4})(?=.)/g, "$1 ")}</Code>
              </p>
              <Instruction number={3} title={t("auth.setup.codeTitle")}>
                {t("auth.setup.codeText")}
              </Instruction>
              {generalError && <Banner tone="due">{generalError}</Banner>}
              <Field id="activation-code" label={t("auth.code.label")} error={codeError}>
                {(control) => (
                  <CodeInput
                    {...control}
                    value={code}
                    onValueChange={setCode}
                    disabled={codes !== null}
                  />
                )}
              </Field>
              <Button type="submit" size="lg" disabled={activate.isPending || codes !== null}>
                {t("auth.setup.activate")}
              </Button>
            </CardContent>
          </form>
        </Card>
        <Card className={codes ? undefined : "opacity-55"} aria-disabled={codes ? undefined : true}>
          <CardHeader>
            <CardTitle>{t("auth.setup.codesTitle")}</CardTitle>
            {!codes && <StatusPill tone="gray">{t("auth.setup.codesPending")}</StatusPill>}
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <p className="text-sm">{t("auth.setup.codesText")}</p>
            {codes && (
              <RecoveryCodes
                codes={codes}
                phone={phone}
                onDone={() => onDone(activate.data?.step ?? "done")}
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Instruction({
  number,
  title,
  children,
}: {
  number: number;
  title: string;
  children?: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <Tag>{number}</Tag>
      <div>
        <b>{title}</b>
        {children && <p className="text-sm text-ink-3">{children}</p>}
      </div>
    </div>
  );
}
