import { cn } from "../lib/cn";

type SchoolBadgeProps = {
  code: string;
  name: string;
  color: string;
  textColor: string;
  logo: string | null;
  size?: "sm" | "md" | "lg";
  className?: string;
};

const sizes = {
  sm: "size-9 rounded-[8px] text-[.7rem]",
  md: "size-12 rounded-box text-[.85rem]",
  lg: "size-[72px] rounded-[14px] text-base",
};

/** Logo de l'école, ou son code sur sa couleur (texte blanc ou encre : contraste vérifié par le
 *  serveur, Q8). Couleur et logo viennent des paramètres de l'école, jamais du code. */
export function SchoolBadge({
  code,
  name,
  color,
  textColor,
  logo,
  size = "md",
  className,
}: SchoolBadgeProps) {
  if (logo) {
    return (
      <span
        className={cn(
          "grid shrink-0 place-items-center overflow-hidden bg-white p-1",
          sizes[size],
          className,
        )}
      >
        <img src={logo} alt={name} className="max-h-full max-w-full object-contain" />
      </span>
    );
  }
  return (
    <span
      aria-hidden="true"
      className={cn("grid shrink-0 place-items-center font-bold uppercase", sizes[size], className)}
      style={{ backgroundColor: color, color: textColor }}
    >
      {code.slice(0, 4)}
    </span>
  );
}
