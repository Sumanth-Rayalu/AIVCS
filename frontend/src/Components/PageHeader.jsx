export function PageHeader({ eyebrow, title, description, action }) {
  return (
    <div className="mb-6 flex flex-col items-start justify-between gap-5 sm:mb-9 sm:flex-row sm:items-end">
      <div>
        <div className="mb-[11px] text-[10px] font-bold uppercase tracking-[1.2px] text-[#6e7681]">
          {eyebrow}
        </div>
        <h1 className="m-0 mb-2 text-2xl leading-[1.15] tracking-[-0.7px] sm:text-[28px]">
          {title}
        </h1>
        <p className="m-0 text-[13px] text-[#8b949e]">{description}</p>
      </div>
      {action}
    </div>
  );
}
