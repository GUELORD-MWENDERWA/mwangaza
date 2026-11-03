// Contrats (CTR.1) : brouillon, signature (scan ou acceptation en ligne), avenant, PDF. Un contrat
// signé ne change plus : pour le modifier, un avenant (nouveau brouillon lié).
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import { parseAmount, type Currency } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardHeader,
  CardTitle,
  CheckboxField,
  ConfirmDialog,
  Field,
  Input,
  Select,
  Skeleton,
  StatusPill,
  Table,
  buttonVariants,
} from "@mwangaza/ui";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Pager } from "../shell/Pager";
import { PLANS_KEY } from "./PlansTab";
import { money, pdfUrl, useDay } from "./shared";

type Contract = Schemas["Contract"];
const KEY = ["console", "billing", "contracts"];
const TONE = { draft: "warn", active: "ok", ended: "gray" } as const;

export function ContractsTab() {
  const { t } = useTranslation();
  const day = useDay();
  const [page, setPage] = useState(1);
  const [dialog, setDialog] = useState<
    { kind: "new" } | { kind: "sign" | "amend"; contract: Contract } | null
  >(null);
  const contracts = useQuery({
    queryKey: [...KEY, page],
    queryFn: () =>
      call(api.GET("/api/console/billing/contracts/", { params: { query: { page } } })),
    placeholderData: keepPreviousData,
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.billing.contracts.title")}</CardTitle>
        <Button size="sm" variant="outline" onClick={() => setDialog({ kind: "new" })}>
          {t("console.billing.contracts.new")}
        </Button>
      </CardHeader>
      {contracts.isPending ? (
        <Skeleton label={t("console.billing.loading")} />
      ) : contracts.isError ? (
        <Banner tone="due" className="m-4">
          {errorMessage(contracts.error, t)}
        </Banner>
      ) : contracts.data.results.length === 0 ? (
        <p className="p-4 text-md text-ink-3">{t("console.billing.contracts.empty")}</p>
      ) : (
        <>
          <Table stacked>
            <thead>
              <tr>
                <th>{t("console.billing.number")}</th>
                <th>{t("console.billing.school")}</th>
                <th>{t("console.billing.contracts.plan")}</th>
                <th>{t("console.billing.contracts.dates")}</th>
                <th className="text-right">{t("console.billing.contracts.price")}</th>
                <th>{t("console.billing.state")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {contracts.data.results.map((c) => (
                <tr key={c.id}>
                  <td data-label={t("console.billing.number")}>
                    <b>{c.number}</b>
                  </td>
                  <td data-label={t("console.billing.school")}>{c.school}</td>
                  <td data-label={t("console.billing.contracts.plan")}>{c.plan}</td>
                  <td
                    data-label={t("console.billing.contracts.dates")}
                    className="whitespace-nowrap"
                  >
                    {day(c.start_date)} → {day(c.end_date)}
                  </td>
                  <td
                    data-label={t("console.billing.contracts.price")}
                    className="text-right whitespace-nowrap"
                  >
                    {money(c.price_per_student, c.currency)} ·{" "}
                    {t(`console.billing.period.${c.period}`)}
                  </td>
                  <td data-label={t("console.billing.state")}>
                    <StatusPill tone={TONE[c.status]}>
                      {t(`console.billing.contracts.status.${c.status}`)}
                    </StatusPill>
                  </td>
                  <td>
                    <div className="flex flex-wrap gap-1.5">
                      <a
                        href={pdfUrl("contracts", c.id)}
                        target="_blank"
                        rel="noreferrer"
                        className={buttonVariants({ variant: "ghost", size: "sm" })}
                      >
                        {t("console.billing.pdf")}
                      </a>
                      {c.status === "draft" && (
                        <Button size="sm" onClick={() => setDialog({ kind: "sign", contract: c })}>
                          {t("console.billing.contracts.sign")}
                        </Button>
                      )}
                      {c.status === "active" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setDialog({ kind: "amend", contract: c })}
                        >
                          {t("console.billing.contracts.amend")}
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
          <Pager
            page={page}
            onPage={setPage}
            previous={contracts.data.previous}
            next={contracts.data.next}
          />
        </>
      )}
      {dialog?.kind === "new" && <NewDialog onClose={() => setDialog(null)} />}
      {dialog?.kind === "sign" && (
        <SignDialog contract={dialog.contract} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === "amend" && (
        <AmendDialog contract={dialog.contract} onClose={() => setDialog(null)} />
      )}
    </Card>
  );
}

type Dates = { start_date: string; end_date: string };

function NewDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const plans = useQuery({
    queryKey: PLANS_KEY,
    queryFn: () => call(api.GET("/api/console/billing/plans/")),
  });
  const onSale = plans.data?.results.filter((p) => p.active) ?? [];
  const [form, setForm] = useState({
    school: "",
    plan: "",
    start_date: "",
    end_date: "",
    price: "",
    trial: "0",
    auto: false,
  });
  const [bad, setBad] = useState(false);
  const plan = onSale.find((p) => p.code === (form.plan || onSale[0]?.code));
  const create = useMutation({
    mutationFn: () => {
      const price = form.price.trim()
        ? parseAmount(form.price, (plan?.currency ?? "USD") as Currency)
        : undefined;
      if (price === null) {
        setBad(true);
        throw new Error("price");
      }
      return call(
        api.POST("/api/console/billing/contracts/", {
          body: {
            school: form.school.trim(),
            plan: plan?.code ?? "",
            start_date: form.start_date,
            end_date: form.end_date,
            price_per_student: price,
            trial_days: Number(form.trial) || 0,
            auto_renew: form.auto,
          },
        }),
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: KEY });
      onClose();
    },
  });
  const set = (name: keyof typeof form) => ({
    value: form[name] as string,
    onChange: (e: { target: { value: string } }) => {
      setBad(false);
      setForm({ ...form, [name]: e.target.value });
    },
  });
  return (
    <ConfirmDialog
      open
      onOpenChange={onClose}
      title={t("console.billing.contracts.new")}
      confirmLabel={t("console.billing.contracts.create")}
      cancelLabel={t("common.cancel")}
      onConfirm={() => create.mutate()}
      pending={create.isPending}
    >
      <div className="flex flex-col gap-4">
        <Field
          id="ctr-school"
          label={t("console.billing.school")}
          help={t("console.billing.contracts.schoolHelp")}
          required
        >
          {(c) => <Input {...c} autoComplete="off" {...set("school")} />}
        </Field>
        <Field id="ctr-plan" label={t("console.billing.contracts.plan")} required>
          {(c) => (
            <Select
              {...c}
              value={plan?.code ?? ""}
              onChange={(e) => setForm({ ...form, plan: e.target.value })}
            >
              {onSale.map((p) => (
                <option key={p.id} value={p.code}>
                  {p.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <div className="grid gap-4 min-[600px]:grid-cols-2">
          <Field id="ctr-start" label={t("console.billing.contracts.start")} required>
            {(c) => <Input {...c} type="date" {...set("start_date")} />}
          </Field>
          <Field id="ctr-end" label={t("console.billing.contracts.end")} required>
            {(c) => <Input {...c} type="date" {...set("end_date")} />}
          </Field>
          <Field
            id="ctr-price"
            label={t("console.billing.contracts.ownPrice")}
            help={t("console.billing.contracts.ownPriceHelp")}
            error={bad ? t("console.billing.badAmount") : undefined}
          >
            {(c) => <Input {...c} inputMode="decimal" {...set("price")} />}
          </Field>
          <Field id="ctr-trial" label={t("console.billing.contracts.trial")}>
            {(c) => <Input {...c} type="number" min={0} max={365} {...set("trial")} />}
          </Field>
        </div>
        <CheckboxField
          id="ctr-auto"
          label={t("console.billing.contracts.autoRenew")}
          checked={form.auto}
          onCheckedChange={(on) => setForm({ ...form, auto: on === true })}
        />
        {create.isError && !bad && <Banner tone="due">{errorMessage(create.error, t)}</Banner>}
      </div>
    </ConfirmDialog>
  );
}

function SignDialog({ contract, onClose }: { contract: Contract; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [signature, setSignature] = useState<"upload" | "online">("upload");
  const [signer, setSigner] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const sign = useMutation({
    mutationFn: () => {
      const body = new FormData();
      body.append("signature", signature);
      body.append("signer_name", signer);
      if (signature === "upload" && file) body.append("signed_file", file);
      return call(
        api.POST("/api/console/billing/contracts/{id}/sign/", {
          params: { path: { id: contract.id } },
          body: body as never,
        }),
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: KEY });
      onClose();
    },
  });
  return (
    <ConfirmDialog
      open
      onOpenChange={onClose}
      title={t("console.billing.contracts.signTitle", { number: contract.number })}
      confirmLabel={t("console.billing.contracts.sign")}
      cancelLabel={t("common.cancel")}
      onConfirm={() => sign.mutate()}
      pending={sign.isPending}
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-3">{t("console.billing.contracts.signHelp")}</p>
        <Field id="sign-kind" label={t("console.billing.contracts.signature")}>
          {(c) => (
            <Select
              {...c}
              value={signature}
              onChange={(e) => setSignature(e.target.value as typeof signature)}
            >
              <option value="upload">{t("console.billing.contracts.signUpload")}</option>
              <option value="online">{t("console.billing.contracts.signOnline")}</option>
            </Select>
          )}
        </Field>
        <Field id="sign-name" label={t("console.billing.contracts.signer")}>
          {(c) => (
            <Input
              {...c}
              maxLength={120}
              value={signer}
              onChange={(e) => setSigner(e.target.value)}
            />
          )}
        </Field>
        {signature === "upload" && (
          <Field id="sign-file" label={t("console.billing.contracts.scan")} required>
            {(c) => (
              <Input
                {...c}
                type="file"
                accept="application/pdf,image/jpeg,image/png"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            )}
          </Field>
        )}
        {sign.isError && <Banner tone="due">{errorMessage(sign.error, t)}</Banner>}
      </div>
    </ConfirmDialog>
  );
}

function AmendDialog({ contract, onClose }: { contract: Contract; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [dates, setDates] = useState<Dates>({
    start_date: contract.start_date,
    end_date: contract.end_date,
  });
  const amend = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/console/billing/contracts/{id}/amend/", {
          params: { path: { id: contract.id } },
          body: dates as never,
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: KEY });
      onClose();
    },
  });
  return (
    <ConfirmDialog
      open
      onOpenChange={onClose}
      title={t("console.billing.contracts.amendTitle", { number: contract.number })}
      confirmLabel={t("console.billing.contracts.amendConfirm")}
      cancelLabel={t("common.cancel")}
      onConfirm={() => amend.mutate()}
      pending={amend.isPending}
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-3">{t("console.billing.contracts.amendHelp")}</p>
        <div className="grid gap-4 min-[600px]:grid-cols-2">
          <Field id="amend-start" label={t("console.billing.contracts.start")}>
            {(c) => (
              <Input
                {...c}
                type="date"
                value={dates.start_date}
                onChange={(e) => setDates({ ...dates, start_date: e.target.value })}
              />
            )}
          </Field>
          <Field id="amend-end" label={t("console.billing.contracts.end")}>
            {(c) => (
              <Input
                {...c}
                type="date"
                value={dates.end_date}
                onChange={(e) => setDates({ ...dates, end_date: e.target.value })}
              />
            )}
          </Field>
        </div>
        {amend.isError && <Banner tone="due">{errorMessage(amend.error, t)}</Banner>}
      </div>
    </ConfirmDialog>
  );
}
