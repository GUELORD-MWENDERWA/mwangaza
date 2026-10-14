import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

// `.btn` des maquettes : `default` = `.primary` (lac), `outline` = `.btn`, `ghost` = lien.
export const buttonVariants = cva(
  "inline-flex cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-field border font-bold leading-tight no-underline transition-colors focus-visible:border-lake focus-visible:ring-3 focus-visible:ring-lake-50 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-55 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "border-lake bg-lake text-white hover:border-lake-700 hover:bg-lake-700",
        outline: "border-line bg-card text-ink hover:bg-surface",
        "destructive-outline": "border-due-200 bg-card text-due hover:bg-due-50",
        destructive: "border-due bg-due text-white hover:brightness-95",
        ghost: "border-transparent bg-transparent text-lake hover:bg-lake-50",
      },
      size: {
        sm: "min-h-8 px-2.5 py-[5px] text-sm",
        default: "min-h-10 px-4 py-[9px] text-md",
        lg: "min-h-12 px-[22px] py-3.5 text-base",
        xl: "min-h-15 w-full px-6 py-[18px] text-lg",
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
