import * as React from "react"

import { cn } from "@/lib/utils"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-16 w-full rounded-md border border-border bg-surface-1 px-3 py-2 text-body-md text-text-primary outline-none transition-[border-color,box-shadow,background-color] duration-150 placeholder:text-text-muted hover:border-border-strong focus-visible:border-primary focus-visible:shadow-[0_0_0_3px_var(--color-primary-light)] disabled:cursor-not-allowed disabled:bg-surface-0 disabled:opacity-70 aria-invalid:border-error aria-invalid:shadow-[0_0_0_3px_var(--color-error-light)]",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
