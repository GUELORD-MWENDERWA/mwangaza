import { ToggleGroup } from "radix-ui";

import { cn } from "../lib/cn";

type Option<T extends string> = { value: T; label: string };

type SegmentedProps<T extends string> = {
  value: T;
  options: Option<T>[];
  onValueChange: (value: T) => void;
  label: string;
  disabled?: boolean;
  className?: string;
};

/** `.seg` des maquettes : un seul choix (ex. Français / English, USD / FC). Étiré sur toute la
 *  largeur (téléphone), les choix se partagent la place, texte centré. */
export function Segmented<T extends string>({
  value,
  options,
  onValueChange,
  label,
  disabled,
  className,
}: SegmentedProps<T>) {
  return (
    <ToggleGroup.Root
      type="single"
      value={value}
      onValueChange={(next) => next && onValueChange(next as T)}
      aria-label={label}
      disabled={disabled}
      className={cn(
        "inline-flex overflow-hidden rounded-field border border-line bg-card",
        className,
      )}
    >
      {options.map((option) => (
        <ToggleGroup.Item
          key={option.value}
          value={option.value}
          className="min-h-10 flex-auto cursor-pointer px-4 py-2 text-center text-md leading-tight font-bold text-ink-2 focus-visible:relative focus-visible:ring-3 focus-visible:ring-lake-50 focus-visible:outline-none disabled:cursor-not-allowed data-[state=on]:bg-lake data-[state=on]:text-white"
        >
          {option.label}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
