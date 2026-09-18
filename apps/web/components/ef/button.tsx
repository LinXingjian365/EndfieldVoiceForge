import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * 形状语义:
 *  primary   白胶囊 + 圆形图标章(工作室主行动)
 *  action    黄色切角块(系统行动 / 导航级)
 *  secondary 深色胶囊
 *  ghost     文字链接
 *  danger
 */
const button = cva(
  "inline-flex items-center justify-center gap-2 select-none whitespace-nowrap text-sm font-medium transition-colors duration-[var(--dur-fast)] disabled:pointer-events-none disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-action focus-visible:outline-offset-2",
  {
    variants: {
      variant: {
        primary: "rounded-capsule bg-ink text-canvas hover:bg-ink/90 pl-1.5 pr-5 h-11",
        action: "cut-corner bg-action text-on-action font-bold hover:bg-action-deep h-10 px-5",
        secondary: "rounded-capsule bg-surface-2 text-ink border border-line-2 hover:bg-surface-hover h-9 px-4",
        ghost: "text-ink-2 hover:text-ink hover:bg-surface-hover h-9 px-3",
        danger: "bg-danger/15 text-danger border border-danger/40 hover:bg-danger/25 h-9 px-4",
        icon: "h-9 w-9 text-ink-2 hover:text-ink hover:bg-surface-hover",
      },
      size: {
        md: "",
        sm: "h-8 text-xs px-3",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof button> {
  icon?: React.ReactNode;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, icon, loading, children, disabled, ...props }, ref) => (
    <button ref={ref} className={cn(button({ variant, size }), className)} disabled={disabled || loading} {...props}>
      {variant === "primary" && (
        <span className="rounded-full flex h-8 w-8 items-center justify-center bg-action text-on-action" aria-hidden>
          {loading ? <span className="h-3 w-3 animate-spin border-2 border-on-action border-t-transparent rounded-full" /> : icon}
        </span>
      )}
      {variant !== "primary" && icon}
      {children}
    </button>
  ),
);
Button.displayName = "Button";
