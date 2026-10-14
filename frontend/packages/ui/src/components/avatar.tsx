import { cn } from "../lib/cn";

/** Initiales : première lettre du prénom (ou du post-nom) et du nom (`.avatar` des maquettes). */
export function initials(lastName: string, firstName: string, middleName = ""): string {
  const first = (firstName || middleName).trim().charAt(0);
  const last = lastName.trim().charAt(0);
  return (first + last).toUpperCase() || "?";
}

export function Avatar({ text, className }: { text: string; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid size-[34px] shrink-0 place-items-center rounded-full bg-lake-50 text-sm font-bold text-lake",
        className,
      )}
    >
      {text}
    </span>
  );
}
