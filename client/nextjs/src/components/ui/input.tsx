import * as React from "react"
import { Input as InputPrimitive } from "@base-ui/react/input"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      className={cn(
        "h-9 w-full min-w-0 rounded-md border border-border bg-surface-1 px-3 text-body-md text-text-primary outline-none transition-[border-color,box-shadow,background-color] duration-150 file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-body-sm file:font-medium file:text-text-primary placeholder:text-text-muted hover:border-border-strong focus-visible:border-primary focus-visible:shadow-[0_0_0_3px_var(--color-primary-light)] disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-surface-0 disabled:opacity-70 aria-invalid:border-error aria-invalid:shadow-[0_0_0_3px_var(--color-error-light)]",
        className
      )}
      {...props}
    />
  )
}

export { Input }
