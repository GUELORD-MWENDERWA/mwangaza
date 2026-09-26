import type { ReactNode } from "react";

import { cn } from "../lib/cn";

export type FieldControlProps = {
  id: string;
  "aria-invalid"?: true;
  "aria-describedby"?: string;
};

type FieldProps = {
  id: string;
  label: ReactNode;
  required?: boolean;
  help?: ReactNode;
  error?: ReactNode;
  className?: string;
  children: (control: FieldControlProps) => ReactNode;
};

/** `label.f` des maquettes : libellé, champ, aide ou erreur (lue par les lecteurs d'écran). */
export function Field({ id, label, required, help, error, className, children }: FieldProps) {
  const noteId = error ? `${id}-error` : help ? `${id}-help` : undefined;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-[.87rem] font-bold text-ink-2">
        {label}
        {required && (
          <span className="text-due" aria-hidden="true">
            {" "}
            *
          </span>
        )}
      </label>
      {children({
        id,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": noteId,
      })}
      {error ? (
        <p id={noteId} className="text-[.8rem] text-due" role="alert">
          {error}
        </p>
      ) : help ? (
        <p id={noteId} className="text-[.8rem] text-ink-3">
          {help}
        </p>
      ) : null}
    </div>
  );
}
