import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "btn-press inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-md border border-transparent text-body-sm font-medium outline-none select-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:pointer-events-none disabled:opacity-50 disabled:hover:scale-100 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-primary text-text-inverse hover:bg-primary-hover",
        outline:
          "border-border bg-surface-1 text-text-primary hover:border-border-strong hover:bg-surface-0",
        secondary:
          "border-border bg-surface-0 text-text-primary hover:border-border-strong",
        ghost:
          "bg-transparent text-text-secondary hover:bg-surface-0 hover:text-text-primary",
        destructive:
          "bg-error text-text-inverse hover:bg-error",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default:
          "h-9 gap-2 px-4",
        xs: "h-7 gap-1 px-2 text-label-sm [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1.5 px-3",
        lg: "h-11 gap-2 px-5",
        icon: "size-9 p-0",
        "icon-xs":
          "size-7 p-0 [&_svg:not([class*='size-'])]:size-3",
        "icon-sm":
          "size-7 p-0 [&_svg:not([class*='size-'])]:size-4",
        "icon-lg": "size-11 p-0 [&_svg:not([class*='size-'])]:size-5",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
