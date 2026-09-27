export function PanelHeading({ title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between gap-[15px] p-[19px_20px]">
      <div>
        <h2 className="m-0 mb-[5px] text-sm">{title}</h2>
        <p className="m-0 text-[11px] text-[#8b949e]">{subtitle}</p>
      </div>
      {action}
    </div>
  );
}
