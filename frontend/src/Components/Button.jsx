export function Button({ children, primary = false, onClick }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[5px] border px-3 py-2 text-[11px] ${primary ? "border-[#7568d7] bg-[#7365d3] text-white hover:bg-[#8375e7]" : "border-[#30363d] bg-[#212832] text-[#f0f6fc] hover:border-[#657180] hover:bg-[#282f38]"}`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
