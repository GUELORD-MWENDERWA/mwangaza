import { usePlatform } from "../platform";
import { cn } from "../lib/cn";

/** Lampe des maquettes (`.brand .mark`) : marque de la plateforme sans logo. */
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

/** Logo de la plateforme, sinon la lampe. */
export function PlatformMark({ className }: { className?: string }) {
  const { logo } = usePlatform();
  if (!logo) return <BrandMark className={className} />;
  return (
    <img
      src={logo}
      alt=""
      className={cn("h-[30px] w-auto max-w-[120px] shrink-0 object-contain", className)}
    />
  );
}

/** Marque de la plateforme : son logo (sinon la lampe) et son nom, qui n'est pas traduit. */
export function Brand({ className, large }: { className?: string; large?: boolean }) {
  const { name } = usePlatform();
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <PlatformMark />
      <b className={cn("tracking-[.01em]", large ? "text-xl" : "text-[1.1rem]")}>{name}</b>
    </div>
  );
}
