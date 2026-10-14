import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

// `.btn` des maquettes : `default` = `.primary` (lac), `outline` = `.btn`, `ghost` = lien.
// Graisse 600, ombre légère, anneau de focus large (clavier), un pixel d'enfoncement au clic.
export const buttonVariants = cva(
  "inline-flex cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-field border font-semibold leading-tight no-underline transition-[background-color,border-color,color,box-shadow] duration-150 focus-visible:ring-4 focus-visible:ring-lake-100 focus-visible:outline-none active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50 disabled:active:translate-y-0 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "border-lake bg-lake text-white shadow-button hover:border-lake-700 hover:bg-lake-700",
        outline:
          "border-line bg-card text-ink shadow-button hover:border-field hover:bg-table-head",
        "destructive-outline": "border-due-200 bg-card text-due shadow-button hover:bg-due-50",
        destructive: "border-due bg-due text-white shadow-button hover:bg-due-900",
        ghost: "border-transparent bg-transparent text-lake hover:bg-lake-50",
      },
      size: {
        sm: "min-h-8 px-3 py-1 text-sm",
        default: "min-h-10 px-4 py-2 text-md",
        lg: "min-h-12 px-5 py-3 text-base",
        xl: "min-h-15 w-full px-6 py-4 text-lg",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

type ButtonProps = ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    /** Rendre l'enfant (ex. un lien) avec l'apparence du bouton. */
    asChild?: boolean;
  };

export function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
  const Component = asChild ? Slot.Root : "button";
  return (
    <Component
      type={asChild ? undefined : (props.type ?? "button")}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}
