import type { ComponentProps } from "react";

import { cn } from "../lib/cn";
import { inputClasses } from "./input";

// Liste de choix native (clavier, lecteur d'écran et téléphone la gèrent d'eux-mêmes), avec
// l'apparence de `.inp` et la flèche des maquettes.
export function Select({ className, ...props }: ComponentProps<"select">) {
  return (
    <select
      className={cn(
        inputClasses,
        "cursor-pointer appearance-none bg-[image:url('data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20width=%2212%22%20height=%2212%22%20viewBox=%220%200%2024%2024%22%20fill=%22none%22%20stroke=%22%234A5568%22%20stroke-width=%222.5%22%3E%3Cpath%20d=%22M6%209l6%206%206-6%22/%3E%3C/svg%3E')] bg-[length:12px] bg-[right_12px_center] bg-no-repeat pr-9",
        className,
      )}
      {...props}
    />
  );
}
