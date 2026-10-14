import { usePlatform } from "../platform";
import { cn } from "../lib/cn";

/**
 * Lampe-tempête (`maquettes/assets/logo/`) : marque de la plateforme sans logo.
 * Le cadre prend la couleur du texte autour (clair sur basalte, sombre sur fond clair) ;
 * le verre suit `lamp`, que la couleur d'accent de la plateforme remplace.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 64 64" className={cn("size-[30px] shrink-0", className)}>
      <path
        d="M23 14C23 5 41 5 41 14"
        fill="none"
        stroke="currentColor"
        strokeWidth="4.5"
        strokeLinecap="round"
      />
      <path d="M18.5 14.5H45.5L41.5 21H22.5Z" fill="currentColor" />
      <path
        d="M22.5 21H41.5C48.5 27.5 48.5 43.5 41.5 50H22.5C15.5 43.5 15.5 27.5 22.5 21Z"
        fill="var(--color-lamp)"
      />
      <path
        d="M32 27C35.6 32 37 35.3 37 38.8A5 5 0 0 1 27 38.8C27 35.3 28.4 32 32 27Z"
        fill="white"
        fillOpacity="0.9"
      />
      <path d="M16.5 50H47.5L45 58H19Z" fill="currentColor" />
    </svg>
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
      <b className={cn("tracking-[.01em]", large ? "text-xl" : "text-lg")}>{name}</b>
    </div>
  );
}
