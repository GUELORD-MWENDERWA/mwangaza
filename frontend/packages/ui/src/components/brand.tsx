import { cn } from "../lib/cn";

/** Marque Mwangaza : la lampe (`.brand .mark` des maquettes) et le nom, qui n'est pas traduit. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block size-[30px] shrink-0 rounded-full bg-basalt-2 bg-[radial-gradient(circle_at_50%_55%,var(--color-lamp)_0_38%,transparent_40%)] shadow-[inset_0_0_0_2px_var(--color-lamp)]",
        className,
      )}
    />
  );
}

export function Brand({ className, large }: { className?: string; large?: boolean }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <BrandMark />
      <b className={cn("tracking-[.01em]", large ? "text-xl" : "text-[1.1rem]")}>Mwangaza</b>
    </div>
  );
}
