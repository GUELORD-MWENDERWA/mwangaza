import { Switch as SwitchPrimitive } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

// `.toggle` des maquettes : 40 × 22 px, lac quand il est activé.
export function Switch({ className, ...props }: ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      className={cn(
        "relative h-[22px] w-10 shrink-0 cursor-pointer rounded-full bg-field focus-visible:ring-3 focus-visible:ring-lake-50 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-55 data-[state=checked]:bg-lake",
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="absolute top-[3px] left-[3px] size-4 rounded-full bg-white transition-[left] data-[state=checked]:left-[21px]" />
    </SwitchPrimitive.Root>
  );
}
