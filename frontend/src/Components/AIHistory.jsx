import { FileCode2, Sparkles } from "lucide-react";
import { PageHeader } from "./PageHeader";
import { PanelHeading } from "./PanelHeading";

export function AIHistory() {
  return (
    <>
      <PageHeader
        eyebrow="Repository intelligence"
        title="AI History"
        description="Ask questions about your codebase and understand how it evolved."
        action={
          <div className="flex items-center gap-[7px] rounded-full border border-[#514a83] px-[11px] py-2 text-[10px] text-[#bfb5ff]">
            <span>
              <Sparkles size={14} />
            </span>
            AI Copilot ready
          </div>
        }
      />
      <div className="mb-[18px] flex h-[53px] items-center justify-between rounded-[7px] border border-[#544b8d] bg-[#191a29] px-[17px] text-[#c6bff6] shadow-[0_0_0_3px_rgba(115,101,211,0.08)]">
        <div className="flex items-center gap-[11px] text-xs">
          <Sparkles size={18} />
          <span>When was authentication changed?</span>
        </div>
        <kbd>⌘ ↵</kbd>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1.25fr_0.8fr] max-lg:grid-cols-1">
        <section className="rounded-[7px] border border-[#30363d] bg-gradient-to-br from-[rgba(32,29,56,0.85)] to-[rgba(22,27,34,0.85)] p-6">
          <div className="mb-[27px] flex items-center gap-2.5">
            <span className="grid h-[27px] w-[27px] place-items-center rounded-[7px] bg-[#3a3163] text-[#c7baff]">
              <Sparkles size={15} />
            </span>
            <div>
              <strong className="block text-[11px]">AI Analysis</strong>
              <small className="mt-0.5 block text-[9px] text-[#8b949e]">
                Generated from 248 commits
              </small>
            </div>
            <span className="ml-auto rounded-full border border-[#3b526d] px-[7px] py-1 text-[9px] text-[#7bbaff]">
              98% confident
            </span>
          </div>
          <h2 className="mb-[14px] max-w-[530px] text-lg leading-[1.45]">
            Authentication was significantly changed in{" "}
            <a className="text-[#9f91ff]">commit abc1234</a>.
          </h2>
          <p className="max-w-[560px] text-xs leading-[1.7] text-[#8b949e]">
            The project moved from session-based authentication to JWT
            authentication with access and refresh tokens. This change
            introduced a more scalable authentication flow for the API.
          </p>
          <div className="mt-7 grid gap-[7px] border-t border-[#30363dcc] pt-4">
            <small className="text-[10px] text-[#6e7681]">Relevant files</small>
            <button className="flex items-center gap-2 rounded bg-[#1a2129] p-2 text-left text-[10px] text-[#f0f6fc]">
              <FileCode2 size={14} />
              src/auth.py <span>+64 −12</span>
            </button>
            <button className="flex items-center gap-2 rounded bg-[#1a2129] p-2 text-left text-[10px] text-[#f0f6fc]">
              <FileCode2 size={14} />
              src/middleware.py <span>+20 −6</span>
            </button>
            <button className="flex items-center gap-2 rounded bg-[#1a2129] p-2 text-left text-[10px] text-[#f0f6fc]">
              <FileCode2 size={14} />
              tests/test_auth.py <span>+38</span>
            </button>
          </div>
        </section>
        <section className="overflow-hidden rounded-[7px] border border-[#30363d] bg-[#161b22c2]">
          <PanelHeading
            title="Explore your history"
            subtitle="Suggested questions"
          />
          {[
            "What changed in the last release?",
            "Why was the API refactored?",
            "Who owns the auth module?",
            "Show me recent security fixes",
          ].map((question, index) => (
            <button
              className="mx-4 mb-2 flex w-[calc(100%-32px)] items-center gap-2.5 rounded border border-[#2a323b] bg-[#1a2028] p-[12px_10px] text-left text-[10px] text-[#8b949e] hover:border-[#605795] hover:text-[#f0f6fc]"
              key={question}
            >
              <span className="font-mono text-[#756b9d]">0{index + 1}</span>
              {question}
              <span className="ml-auto text-[15px] text-[#6e7681]">→</span>
            </button>
          ))}
        </section>
      </div>
    </>
  );
}
