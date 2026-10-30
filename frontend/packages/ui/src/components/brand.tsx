import { usePlatform } from "../platform";
import { cn } from "../lib/cn";

// Tracés du symbole sur une grille de 64 (`maquettes/outils/marque.py`) : carré arrondi, m.
const TILE =
  "M18 0H46A18 18 0 0 1 64 18V46A18 18 0 0 1 46 64H18A18 18 0 0 1 0 46V18A18 18 0 0 1 18 0Z";
const M =
  "M10 54V34A13 13 0 0 1 32 24.62A13 13 0 0 1 54 34V54H46V34A5 5 0 0 0 36 34V54H28V34A5 5 0 0 0 18 34V54Z";

/**
 * Symbole de la plateforme sans logo (lot 1, `maquettes/assets/logo/mwangaza-symbole.svg`) :
 * carré arrondi à la couleur principale (`lake`), m blanc, soleil à la couleur d'accent (`lamp`),
 * couleurs que la plateforme peut changer. `inverse` : sur les barres, qui ont la couleur
 * principale — carré blanc, m à la couleur principale.
 */
export function BrandMark({ className, inverse }: { className?: string; inverse?: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 64 64" className={cn("size-9 shrink-0", className)}>
      <path d={TILE} fill={inverse ? "white" : "var(--color-lake)"} />
      <path d={M} fill={inverse ? "var(--color-lake)" : "white"} />
      <circle cx="32" cy="14.5" r="5.5" fill="var(--color-lamp)" />
    </svg>
  );
}

/** Logo de la plateforme, sinon le symbole ; `large` : pages de connexion (48 px de haut). */
export function PlatformMark({
  className,
  large,
  inverse,
}: {
  className?: string;
  large?: boolean;
  inverse?: boolean;
}) {
  const { logo } = usePlatform();
  if (!logo) return <BrandMark inverse={inverse} className={cn(large && "size-12", className)} />;
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

/**
 * Logo de la plateforme : son logo envoyé, sinon le symbole et son nom (non traduit) en logotype —
 * Poppins SemiBold, minuscules, lettres serrées de 3,5 % ; symbole de 1,2 fois la taille du nom,
 * à 0,26 fois cette taille du nom, centré sur sa ligne (livre de marque, « Proportions »).
 * `large` : pages de connexion ; `inverse` : sur une barre à la couleur principale.
 */
export function Brand({
  className,
  large,
  inverse,
}: {
  className?: string;
  large?: boolean;
  inverse?: boolean;
}) {
  const { name, logo } = usePlatform();
  return (
    <div
      className={cn(
        "flex min-w-0 items-center",
        logo ? (large ? "gap-3.5" : "gap-2.5") : "gap-[.26em]",
        large ? "text-3xl" : "text-2xl",
        className,
      )}
    >
      <PlatformMark large={large} inverse={inverse} className={logo ? undefined : "size-[1.2em]"} />
      <b
        className={cn(
          "min-w-0 truncate font-brand leading-[1.3] font-semibold tracking-[-.035em]",
          logo ? (large ? "text-2xl" : "text-xl") : "lowercase",
          !logo && !inverse && "text-lake",
        )}
      >
        {name}
      </b>
    </div>
  );
}
