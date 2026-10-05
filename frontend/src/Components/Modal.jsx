import { Sparkles, X } from "lucide-react";

export function Modal({ onClose, title, subtitle, children }) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-[rgba(4,7,11,0.7)] p-5 backdrop-blur-[5px]">
      <div className="relative w-full max-w-[500px] rounded-[9px] border border-[#47515d] bg-[#181e26] p-7 shadow-[0_20px_80px_#0008]">
        <button
          className="absolute right-[17px] top-[17px] border-0 bg-transparent text-[#8b949e]"
          onClick={onClose}
        >
          <X size={17} />
        </button>
        {/* <div className="mb-[14px] grid h-[34px] w-[34px] place-items-center rounded-lg bg-[#302957] text-[#bcb0ff]">
          <Sparkles size={19} />
        </div> */}
        <h2 className="m-0 mb-1.5 text-lg">{title}</h2>
        <p className="m-0 mb-[22px] text-[11px] text-[#8b949e]">{subtitle}</p>
        <div className="grid gap-[17px]">{children}</div>
      </div>
    </div>
  );
}
