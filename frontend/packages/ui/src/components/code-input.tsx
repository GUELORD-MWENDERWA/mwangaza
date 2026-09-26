import { useState, type ComponentProps } from "react";

import { cn } from "../lib/cn";

type CodeInputProps = Omit<ComponentProps<"input">, "value" | "onChange" | "maxLength"> & {
  value: string;
  onValueChange: (value: string) => void;
  length?: number;
};

/** Code à 6 chiffres en cases (`.inp.big` des maquettes de double authentification). Un seul vrai
 *  champ sous les cases : coller le code, remplissage automatique du téléphone
 *  (`one-time-code`) et lecteurs d'écran marchent comme pour un champ normal. */
export function CodeInput({
  value,
  onValueChange,
  length = 6,
  className,
  disabled,
  ...props
}: CodeInputProps) {
  const [focused, setFocused] = useState(false);
  const digits = value.split("");
  const current = Math.min(value.length, length - 1);
  return (
    <div className={cn("relative inline-flex gap-2", className)}>
      {Array.from({ length }, (_, index) => (
        <span
          key={index}
          aria-hidden="true"
          className={cn(
            "grid h-16 w-[52px] place-items-center rounded-field border border-field bg-card text-[1.9rem] font-bold tabular-nums",
            focused && index === current && "border-lake ring-3 ring-lake-50",
            props["aria-invalid"] && "border-due",
            disabled && "bg-surface",
          )}
        >
          {digits[index] ?? ""}
        </span>
      ))}
      <input
        {...props}
        disabled={disabled}
        value={value}
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern="[0-9]*"
        // Pas de `maxLength` : il couperait un code collé avec une espace (« 876 157 »).
        onChange={(event) => onValueChange(event.target.value.replace(/\D/g, "").slice(0, length))}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        className="absolute inset-0 h-full w-full cursor-text opacity-0"
      />
    </div>
  );
}
