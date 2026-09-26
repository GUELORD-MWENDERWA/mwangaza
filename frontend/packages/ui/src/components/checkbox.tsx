import { Checkbox as CheckboxPrimitive } from "radix-ui";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "../lib/cn";

// `.box` et `.check` des maquettes.
export function Checkbox({ className, ...props }: ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      className={cn(
        "mt-px grid size-[18px] shrink-0 cursor-pointer place-items-center rounded-[4px] border-[1.5px] border-[#9aa5ad] bg-card text-white focus-visible:ring-3 focus-visible:ring-lake-50 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-55 data-[state=checked]:border-lake data-[state=checked]:bg-lake",
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator>
        <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
          <path
            d="M3.5 8.5l3 3 6-7"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}

type CheckboxFieldProps = ComponentProps<typeof CheckboxPrimitive.Root> & {
  id: string;
  label: ReactNode;
};

export function CheckboxField({ id, label, className, ...props }: CheckboxFieldProps) {
  return (
    <div className={cn("flex items-start gap-2.5 text-[.9rem]", className)}>
      <Checkbox id={id} {...props} />
      <label htmlFor={id} className="cursor-pointer">
        {label}
      </label>
    </div>
  );
}
