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
        "inline-flex gap-1 rounded-box bg-gray-50 p-1 ring-1 ring-line ring-inset",
        className,
      )}
    >
      {options.map((option) => (
        <ToggleGroup.Item
          key={option.value}
          value={option.value}
          className="min-h-9 flex-auto cursor-pointer rounded-field px-4 py-1.5 text-center text-md leading-tight font-semibold text-ink-3 transition-colors hover:text-ink focus-visible:relative focus-visible:ring-4 focus-visible:ring-lake-100 focus-visible:outline-none disabled:cursor-not-allowed data-[state=on]:bg-card data-[state=on]:text-lake-700 data-[state=on]:shadow-raised"
        >
          {option.label}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
