"use client";

import * as React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

/* ---------- Field:label + 控件 + 微标 ---------- */
export function Field({ label, hint, value, children, className }: { label: string; hint?: string; value?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <label className={cn("flex flex-col gap-1.5", className)}>
      <span className="flex items-baseline justify-between">
        <span className="text-xs text-ink-2">{label}</span>
        {value !== undefined && <span className="font-mono text-xs tabular-nums text-ink">{value}</span>}
      </span>
      {children}
      {hint && <span className="micro normal-case tracking-normal">{hint}</span>}
    </label>
  );
}

/* ---------- Slider ---------- */
export function Slider({ value, onChange, min, max, step, className, ariaLabel }: { value: number; onChange: (v: number) => void; min: number; max: number; step: number; className?: string; ariaLabel?: string }) {
  return (
    <SliderPrimitive.Root
      className={cn("relative flex h-5 w-full touch-none select-none items-center", className)}
      value={[value]}
      onValueChange={([v]) => onChange(v)}
      min={min}
      max={max}
      step={step}
      aria-label={ariaLabel}
    >
      <SliderPrimitive.Track className="relative h-1 w-full grow bg-surface-3">
        <SliderPrimitive.Range className="absolute h-full bg-action" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb className="block h-4 w-2 bg-ink hover:bg-action focus-visible:outline-2 focus-visible:outline-action" />
    </SliderPrimitive.Root>
  );
}

/* ---------- Switch ---------- */
export function Switch({ checked, onChange, ariaLabel }: { checked: boolean; onChange: (v: boolean) => void; ariaLabel?: string }) {
  return (
    <SwitchPrimitive.Root
      checked={checked}
      onCheckedChange={onChange}
      aria-label={ariaLabel}
      className={cn("relative h-5 w-9 border border-line-2 bg-surface-2 transition-colors data-[state=checked]:bg-action data-[state=checked]:border-action")}
    >
      <SwitchPrimitive.Thumb className="block h-3.5 w-3.5 translate-x-0.5 bg-ink transition-transform data-[state=checked]:translate-x-[18px] data-[state=checked]:bg-on-action" />
    </SwitchPrimitive.Root>
  );
}

/* ---------- Select ---------- */
export function Select<T extends string>({ value, onChange, options, className, ariaLabel }: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; className?: string; ariaLabel?: string }) {
  return (
    <SelectPrimitive.Root value={value} onValueChange={(v) => onChange(v as T)}>
      <SelectPrimitive.Trigger aria-label={ariaLabel} className={cn("flex h-9 items-center justify-between gap-2 border border-line-2 bg-surface-2 px-3 text-sm text-ink hover:bg-surface-hover", className)}>
        <SelectPrimitive.Value />
        <ChevronDown size={14} className="text-ink-2" />
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content position="popper" sideOffset={4} className="z-50 min-w-[var(--radix-select-trigger-width)] border border-line-2 bg-surface-1 shadow-lg">
          <SelectPrimitive.Viewport className="p-1">
            {options.map((o) => (
              <SelectPrimitive.Item key={o.value} value={o.value} className="relative flex cursor-pointer select-none items-center pl-7 pr-3 py-1.5 text-sm text-ink outline-none data-[highlighted]:bg-surface-hover data-[state=checked]:text-action-text">
                <SelectPrimitive.ItemIndicator className="absolute left-2"><Check size={12} /></SelectPrimitive.ItemIndicator>
                <SelectPrimitive.ItemText>{o.label}</SelectPrimitive.ItemText>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}

/* ---------- Input / Textarea ---------- */
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => (
  <input ref={ref} className={cn("h-9 w-full border border-line-2 bg-surface-2 px-3 text-sm text-ink placeholder:text-ink-3 focus-visible:border-action", className)} {...p} />
));
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, ref) => (
  <textarea ref={ref} className={cn("w-full resize-none border border-line-2 bg-surface-2 px-3 py-2 text-sm leading-relaxed text-ink placeholder:text-ink-3 focus-visible:border-action", className)} {...p} />
));
Textarea.displayName = "Textarea";
