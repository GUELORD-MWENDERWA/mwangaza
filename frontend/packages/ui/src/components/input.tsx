import { useState, type ComponentProps } from "react";

import { Icon } from "../icons";
import { cn } from "../lib/cn";

// `.inp` des maquettes : 40 px au moins ; focus = bordure lac + anneau ; erreur = `aria-invalid`.
export const inputClasses =
  "min-h-10 w-full rounded-field border border-field bg-card px-3 py-2 text-base text-ink shadow-button transition-[border-color,box-shadow] duration-150 placeholder:text-ink-3 hover:border-ink-3 focus:border-lake focus:ring-4 focus:ring-lake-100 focus:outline-none aria-invalid:border-due aria-invalid:ring-4 aria-invalid:ring-due-50 disabled:bg-surface disabled:text-ink-2 read-only:bg-surface";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return <input className={cn(inputClasses, className)} {...props} />;
}

export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return <textarea className={cn(inputClasses, "min-h-21 resize-y", className)} {...props} />;
}

type PasswordInputProps = Omit<ComponentProps<"input">, "type"> & {
  showLabel: string;
  hideLabel: string;
};

/** Mot de passe avec l'œil de la maquette de connexion pour l'afficher ou le masquer. */
export function PasswordInput({ className, showLabel, hideLabel, ...props }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        type={visible ? "text" : "password"}
        className={cn(inputClasses, "pr-11", className)}
        {...props}
      />
      <button
        type="button"
        className="absolute inset-y-0 right-0 grid w-11 cursor-pointer place-items-center rounded-r-field text-ink-3 hover:text-ink-2"
        aria-label={visible ? hideLabel : showLabel}
        aria-pressed={visible}
        onClick={() => setVisible((shown) => !shown)}
      >
        <Icon name="eye" size={18} />
      </button>
    </div>
  );
}
