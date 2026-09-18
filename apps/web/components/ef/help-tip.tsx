"use client";

import * as Tooltip from "@radix-ui/react-tooltip";
import Link from "next/link";
import { HelpCircle } from "lucide-react";
import { HELP, type HelpKey } from "@/lib/help";

/** 悬浮说明:小问号图标,hover/focus 显示 what / effect / tip。 */
export function HelpTip({ k, className }: { k: HelpKey; className?: string }) {
  const h = HELP[k];
  return (
    <Tooltip.Root delayDuration={150}>
      <Tooltip.Trigger asChild>
        <button type="button" aria-label={`关于 ${k} 的说明`} className={className ?? "inline-flex text-ink-3 hover:text-action-text focus-visible:text-action-text"} onClick={(e) => e.preventDefault()}>
          <HelpCircle size={12} />
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content side="left" align="start" sideOffset={8} collisionPadding={12} className="z-50 max-w-[300px] border border-line-2 bg-surface-0 p-3 text-xs leading-relaxed text-ink shadow-[0_8px_24px_rgba(0,0,0,.5)]">
          <p>{h.what}</p>
          {"effect" in h && h.effect && <p className="mt-1.5 text-ink-2"><span className="micro mr-1 text-data">EFFECT</span>{h.effect}</p>}
          {"tip" in h && h.tip && <p className="mt-1.5 text-ink-2"><span className="micro mr-1 text-action-text">TIP</span>{h.tip}</p>}
          <Link href={`/guide#${k}`} className="micro mt-2 block hover:text-ink">完整说明 →</Link>
          <Tooltip.Arrow className="fill-line-2" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}
