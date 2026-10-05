import { PageHeader } from "./PageHeader";
import { Button } from "./Button";

function Toggle({ title, copy }) {
  return (
    <div className="flex items-center justify-between border-t border-[#30363da6] pt-[18px]">
      <div>
        <strong className="mb-1 block text-[11px]">{title}</strong>
        <p className="m-0 text-[11px] text-[#8b949e]">{copy}</p>
      </div>
      <span className="h-[17px] w-[30px] rounded-full bg-[#7163d1] p-0.5">
        <i className="ml-[13px] block h-[13px] w-[13px] rounded-full bg-white" />
      </span>
    </div>
  );
}

export function Settings() {
  return (
    <>
      <PageHeader
        eyebrow="Workspace preferences"
        title="Settings"
        description="Manage your profile, workspace, and AI experience."
      />
      <div className="grid items-start gap-[25px] lg:grid-cols-[190px_1fr] max-lg:grid-cols-1">
        <nav className="grid gap-[3px] max-sm:flex max-sm:overflow-auto">
          {[
            "Account",
            "Profile",
            "Security",
            "Appearance",
            "AI Settings",
            "Repositories",
          ].map((item, index) => (
            <button
              className={`whitespace-nowrap rounded border-0 px-3 py-2.5 text-left text-[11px] ${index === 4 ? "bg-[#29253b] text-[#d5ceff]" : "bg-transparent text-[#8b949e]"}`}
              key={item}
            >
              {item}
            </button>
          ))}
        </nav>
        <section className="grid gap-5 rounded-[7px] border border-[#30363d] bg-[#161b22c2] p-[18px] sm:p-[25px]">
          <div className="border-b border-[#30363d] pb-[7px]">
            <h2 className="m-0 mb-[5px] text-base">AI Settings</h2>
            <p className="m-0 text-[11px] text-[#8b949e]">
              Customize how AIVCS intelligence works for you.
            </p>
          </div>
          <label className="grid gap-[7px] text-[10px] text-[#8b949e]">
            AI Provider
            <select className="w-full rounded border border-[#30363d] bg-[#11161d] p-[9px] text-[11px] text-[#f0f6fc] outline-none">
              <option>OpenAI</option>
              <option>Anthropic</option>
            </select>
          </label>
          <label className="grid gap-[7px] text-[10px] text-[#8b949e]">
            Model
            <select className="w-full rounded border border-[#30363d] bg-[#11161d] p-[9px] text-[11px] text-[#f0f6fc] outline-none">
              <option>GPT-4.1</option>
              <option>Claude Sonnet</option>
            </select>
          </label>
          <Toggle
            title="AI-generated commits"
            copy="Suggest commit messages based on your changes."
          />
          <Toggle
            title="Inline code explanations"
            copy="Show context when reviewing unfamiliar code."
          />
          <Button primary>Save changes</Button>
        </section>
      </div>
    </>
  );
}
