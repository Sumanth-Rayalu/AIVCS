export function ActivityItem({ icon: Icon, title, detail, time, color }) {
  return (
    <div className="flex items-start gap-2.5 border-t border-[#30363d8c] py-3">
      <span
        className={`grid h-[25px] w-[25px] shrink-0 place-items-center rounded-md ${color === "purple" ? "bg-[#2c2648] text-[#b4a8ff]" : color === "blue" ? "bg-[#1d3047] text-[#73b7ff]" : color === "amber" ? "bg-[#3b2e1b] text-[#e7b85b]" : "bg-[#1c3725] text-[#68d47a]"}`}
      >
        <Icon size={15} />
      </span>
      <div>
        <p className="m-[2px_0_5px] overflow-hidden text-ellipsis whitespace-nowrap text-[10px] text-[#8b949e]">
          {title}{" "}
          <strong className="font-medium text-[#f0f6fc]">{detail}</strong>
        </p>
        <small className="text-[9px] text-[#6e7681]">{time}</small>
      </div>
    </div>
  );
}
