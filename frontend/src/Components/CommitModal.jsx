import { Check, Sparkles } from "lucide-react";
import { Button } from "./Button";
import { Modal } from "./Modal";

export function CommitModal({ onClose }) {
  return (
    <Modal
      onClose={onClose}
      title="AI Commit"
      subtitle="A clear message for the changes in your working tree."
    >
      <div className="rounded-[6px] border border-[#30363d] bg-[#11161d] p-[14px]">
        <div className="flex justify-between text-[10px]">
          <span className="flex items-center gap-[7px] text-[#c8c0ff]">
            <Sparkles size={15} />
            Analyzing your changes
          </span>
          <strong className="text-[10px] text-[#3fb950]">100%</strong>
        </div>
        <div className="my-3 h-[5px] overflow-hidden rounded-full bg-[#2b323b]">
          <i className="block h-full w-full bg-gradient-to-r from-[#7769da] to-[#a595ff]" />
        </div>
        <small className="text-[9px] text-[#8b949e]">
          3 files changed · 2.4s
        </small>
      </div>
      <div className="rounded-[6px] border border-[#514b83] bg-[#201e31] p-[15px]">
        <small className="text-[9px] text-[#a99cff]">AI-generated commit</small>
        <h3 className="my-[11px_8px] font-mono text-[13px] font-medium">
          feat(auth): add JWT authentication
        </h3>
        <p className="m-[0_0_13px] text-[11px] leading-[1.5] text-[#8b949e]">
          Authentication was updated to use JWT with refresh-token support.
        </p>
        <div className="flex gap-3 font-mono text-[10px]">
          <span className="text-[#3fb950]">+84</span>
          <span className="text-[#f78166]">−21</span>
          <span className="text-[#8b949e]">3 files</span>
        </div>
      </div>
      <div className="flex justify-end gap-2">
        <Button onClick={onClose}>Edit</Button>
        <Button primary onClick={onClose}>
          <Check size={15} />
          Use commit
        </Button>
      </div>
    </Modal>
  );
}
