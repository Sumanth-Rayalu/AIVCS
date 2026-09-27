export function Metric({ icon: Icon, tone, label, value, note }) {
  return (
    <div className="relative rounded-[7px] border border-[#30363d] bg-gradient-to-br from-[#171d25] to-[#141a21] p-[18px_19px] max-sm:min-h-[110px]">
      <span
        className={`absolute right-[17px] top-[17px] grid h-[31px] w-[31px] place-items-center rounded-[7px] ${tone === "purple" ? "bg-[#2c2648] text-[#b2a5ff]" : tone === "blue" ? "bg-[#1e3148] text-[#79b8ff]" : "bg-[#3a2d1c] text-[#e6b85c]"}`}
      >
        <Icon size={17} />
      </span>
      <small className="block text-[11px] text-[#8b949e]">{label}</small>
      <strong className="my-[13px] block text-[26px] leading-none">
        {value}
      </strong>
      <em className="block text-[10px] not-italic text-[#3fb950]">{note}</em>
    </div>
  );
}
