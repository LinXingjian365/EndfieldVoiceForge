"use client";

import Link from "next/link";
import { HELP, GUIDE_SECTIONS } from "@/lib/help";
import { Panel, ScanDivider, GhostWord, Chip } from "@/components/ef";

export default function GuidePage() {
  return (
    <div className="grid h-full grid-cols-[220px_minmax(0,1fr)] gap-2 p-2">
      <Panel title="目录" en="CONTENTS">
        <nav className="flex flex-col gap-0.5 p-2">
          {GUIDE_SECTIONS.map((s) => (
            <a key={s.en} href={`#sec-${s.en}`} className="flex items-baseline gap-2 px-2 py-1.5 text-xs text-ink-2 hover:bg-surface-hover hover:text-ink">
              <span className="micro w-16 shrink-0">{s.en}</span>
              <span className="truncate">{s.title}</span>
            </a>
          ))}
        </nav>
        <div className="mx-3 mt-4 border-t border-line-1 pt-3">
          <p className="micro normal-case tracking-normal leading-relaxed">每个参数旁边的 <span className="text-ink">?</span> 图标悬浮就能看到同样的说明。这里是完整版,可以从头读一遍。</p>
        </div>
      </Panel>

      <Panel title="使用指南" en="GUIDE" action={<Chip>{Object.keys(HELP).length} 项</Chip>}>
        <div className="relative h-full overflow-auto px-8 py-6">
          <GhostWord size={120} className="right-6 top-4">MANUAL</GhostWord>
          <article className="relative max-w-[720px]">
            <p className="mb-8 text-sm leading-relaxed text-ink-2">
              这个工作台把 <span className="text-ink">GPT-SoVITS</span>(文字 → 提弗洛斯说话)和 <span className="text-ink">RVC</span>(任意人声 → 提弗洛斯音色)放在一起。
              前者已经训练好可以直接用;后者 DeepSeek 只训到第 20 轮,训练页可以续训。
              合成出来的每一条都自动存在 <span className="font-mono text-ink">outputs/generated/</span>,合成页输出列表里有下载按钮。
            </p>
            {GUIDE_SECTIONS.map((s) => (
              <section key={s.en} id={`sec-${s.en}`} className="mb-10 scroll-mt-4">
                <ScanDivider label={s.en} className="mb-3" />
                <h2 className="mb-2 text-lg font-bold text-ink">{s.title}</h2>
                <p className="mb-4 text-sm leading-relaxed text-ink-2">{s.intro}</p>
                <dl className="flex flex-col gap-3">
                  {s.keys.map((k) => {
                    const h = HELP[k];
                    return (
                      <div key={k} id={k} className="scroll-mt-4 border-l-2 border-line-1 pl-3 target:border-action">
                        <dt className="font-mono text-sm text-ink">{k}</dt>
                        <dd className="mt-1 text-sm leading-relaxed text-ink-2">
                          {h.what}
                          {"effect" in h && h.effect && <><br /><span className="micro mr-1 text-data">EFFECT</span>{h.effect}</>}
                          {"tip" in h && h.tip && <><br /><span className="micro mr-1 text-action-text">TIP</span>{h.tip}</>}
                        </dd>
                      </div>
                    );
                  })}
                </dl>
              </section>
            ))}
            <ScanDivider label="FAQ" className="mb-3" />
            <h2 className="mb-2 text-lg font-bold text-ink">常见问题</h2>
            <dl className="flex flex-col gap-3 text-sm leading-relaxed">
              <div className="border-l-2 border-line-1 pl-3"><dt className="text-ink">合成出来有杂音 / 电音?</dt><dd className="text-ink-2">先换一条更干净的参考音频(3–10 秒,无 BGM)。再把 temperature 降到 0.7、top_k 降到 8。</dd></div>
              <div className="border-l-2 border-line-1 pl-3"><dt className="text-ink">尾音一直拖 / 复读?</dt><dd className="text-ink-2">repetition_penalty 调到 1.5,或换「按标点切」让句子短一点。</dd></div>
              <div className="border-l-2 border-line-1 pl-3"><dt className="text-ink">情绪不对?</dt><dd className="text-ink-2">情绪主要来自参考音频。在合成页左侧「数据集」里挑一条情绪匹配的台词当参考。</dd></div>
              <div className="border-l-2 border-line-1 pl-3"><dt className="text-ink">能不能生成呻吟、喘息?</dt><dd className="text-ink-2">TTS 不能。用工具页「RVC 音色转换」:上传任意人声呻吟音频,index_rate 0.3、protect 0.2,转成提弗洛斯音色。或直接用解包出的游戏原声音效。</dd></div>
              <div className="border-l-2 border-line-1 pl-3"><dt className="text-ink">训练报显存 / 内存错误?</dt><dd className="text-ink-2">关掉浏览器里其他标签和大程序,主机可用内存要 ≥ 4 GB。训练期间不要合成。</dd></div>
              <div className="border-l-2 border-line-1 pl-3"><dt className="text-ink">哪个 epoch 最好?</dt><dd className="text-ink-2">模型页「A/B 试听」,同一句话固定 seed 比 e12 / e16 / e20 / e22。一般越大越像但越僵,选听感最自然的。</dd></div>
            </dl>
            <p className="mt-8 micro normal-case tracking-normal">回到 <Link href="/synth" className="text-ink hover:text-action-text">合成页</Link> 试试。</p>
          </article>
        </div>
      </Panel>
    </div>
  );
}
