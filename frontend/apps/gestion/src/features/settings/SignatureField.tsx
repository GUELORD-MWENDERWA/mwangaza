// Cachet ou signature (DOC.1), enregistré aussitôt choisi (envoi à part du formulaire) : PNG ou
// JPEG, que le serveur détoure (fond blanc rendu transparent). Paramètres de l'école (cachet,
// signature du chef) et Mon compte (ma signature). Image servie au seul personnel connecté.
import { ApiError } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Icon } from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { useRef } from "react";

import { errorMessage, fieldMessage } from "../../lib/errors";

export function SignatureField<T>({
  label,
  help,
  image,
  send,
  remove,
  onSaved,
}: {
  label: string;
  help: string;
  image: string | null;
  send: { (body: FormData): Promise<T> };
  remove: { (): Promise<T> };
  onSaved: (data: T) => void;
}) {
  const { t } = useTranslation();
  const input = useRef<HTMLInputElement>(null);
  const upload = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("image", file);
      return send(body);
    },
    onSuccess: onSaved,
  });
  const removal = useMutation({ mutationFn: remove, onSuccess: onSaved });
  const failed = upload.error ?? removal.error;
  const fieldError = failed instanceof ApiError ? Object.values(failed.fields)[0]?.[0] : undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-bold text-ink-2">{label}</span>
      <div className="flex flex-wrap items-center gap-3">
        {image ? (
          <img
            src={image}
            alt={label}
            className="h-[84px] w-[168px] rounded-box border border-line bg-white object-contain p-1"
          />
        ) : (
          <span className="grid h-[84px] w-[168px] place-items-center rounded-box border border-dashed border-line px-2 text-center text-xs text-ink-3">
            {t("signature.none")}
          </span>
        )}
        <div className="flex min-w-0 flex-1 basis-48 flex-col gap-1.5">
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={upload.isPending}
              onClick={() => input.current?.click()}
            >
              <Icon name="upload" size={14} />
              {t(image ? "signature.change" : "signature.add")}
            </Button>
            {image && (
              <Button
                variant="ghost"
                size="sm"
                disabled={removal.isPending}
                onClick={() => removal.mutate()}
              >
                {t("signature.remove")}
              </Button>
            )}
          </div>
          <span className="text-xs text-ink-3">{help}</span>
        </div>
        <input
          ref={input}
          type="file"
          accept="image/png,image/jpeg"
          className="hidden"
          aria-label={label}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) upload.mutate(file);
          }}
        />
      </div>
      <p role="status" className="text-xs text-ok">
        {upload.isSuccess && t("signature.saved")}
        {removal.isSuccess && t("signature.removed")}
      </p>
      {failed && (
        <Banner tone="due">
          {fieldError ? fieldMessage(fieldError.code, t) : errorMessage(failed, t)}
        </Banner>
      )}
    </div>
  );
}
