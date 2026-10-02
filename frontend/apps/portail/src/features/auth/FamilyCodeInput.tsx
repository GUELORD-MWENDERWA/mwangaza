import { Input } from "@mwangaza/ui";
import type { ComponentProps } from "react";

/** Code famille comme imprimé (« K7M4-P9TX ») : majuscules, sans correction automatique. */
export function FamilyCodeInput(props: ComponentProps<typeof Input>) {
  return (
    <Input
      {...props}
      autoCapitalize="characters"
      autoComplete="off"
      autoCorrect="off"
      spellCheck={false}
      placeholder="K7M4-P9TX"
      maxLength={20}
      className="font-bold tracking-[.25em] uppercase"
    />
  );
}
