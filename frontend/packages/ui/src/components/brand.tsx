import { usePlatform } from "../platform";
import { cn } from "../lib/cn";

/**
 * Symbole M-flamme (`maquettes/assets/logo/symbole.svg`) : marque de la plateforme sans logo.
 * Carré arrondi à la couleur d'accent (`lamp`, que la plateforme peut remplacer : toujours
 * lisible avec le basalte, 4,5:1 vérifié par le serveur), M et flamme en basalte ; le même sur
 * fond sombre ou clair. 36 px dans les barres, 48 px sur les pages de connexion.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 64 64" className={cn("size-9 shrink-0", className)}>
      <rect width="64" height="64" rx="16" fill="var(--color-lamp)" />
      <g transform="translate(0 1.5)" fill="var(--color-basalt)">
        <path
          d="M15.5 49V24L32 40.5L48.5 24V49"
          fill="none"
          stroke="var(--color-basalt)"
          strokeWidth="8.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path d="M33.5 4.5C35 10 40 12.5 40 19.5A8 8 0 0 1 24 19.5C24 15.6 25.9 13.2 28.4 11.6C28.5 14 29.4 15.6 31 16.3C30.3 12 31.3 7.8 33.5 4.5Z" />
        <path
          d="M32 14.5C33.6 17 35 18.3 35 20.5A3 3 0 0 1 29 20.5C29 18.6 30.3 16.8 32 14.5Z"
          fill="var(--color-lamp)"
        />
      </g>
    </svg>
  );
}

/** Logo de la plateforme, sinon le symbole ; `large` : pages de connexion (48 px de haut). */
export function PlatformMark({ className, large }: { className?: string; large?: boolean }) {
  const { logo } = usePlatform();
  if (!logo) return <BrandMark className={cn(large && "size-12", className)} />;
  return (
    <img
      src={logo}
      alt=""
      className={cn(
        "w-auto shrink-0 object-contain",
        large ? "h-12 max-w-[180px]" : "h-9 max-w-[140px]",
        className,
      )}
    />
  );
}

/** Marque de la plateforme : son logo (sinon le symbole) et son nom, qui n'est pas traduit. */
export function Brand({ className, large }: { className?: string; large?: boolean }) {
  const { name } = usePlatform();
  return (
    <div className={cn("flex items-center", large ? "gap-3.5" : "gap-2.5", className)}>
      <PlatformMark large={large} />
      <b className={cn("leading-tight tracking-[-.01em]", large ? "text-2xl" : "text-xl")}>
        {name}
      </b>
    </div>
  );
}
