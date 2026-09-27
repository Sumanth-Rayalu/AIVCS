import { Menu, Search } from "lucide-react";

export function Topbar({ openView, setMobileOpen, name }) {
  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-[#30363d] bg-[#0d1117e0] px-4 backdrop-blur-[16px] sm:gap-[34px] sm:px-[30px]">
      <button
        className="relative border-0 bg-transparent p-[5px] text-[#8b949e] sm:hidden"
        onClick={() => setMobileOpen((open) => !open)}
      >
        <Menu size={19} />
      </button>
      <button
        className="flex items-center gap-2.5 border-0 bg-transparent text-[17px] font-bold tracking-[0.4px]"
        onClick={() => openView("overview")}
      >
        <span className="grid h-[25px] w-[25px] rotate-45 place-content-center rounded-md border-[1.5px] border-[#a393ff]">
          <span className="block h-[3px] w-[9px] -rotate-45 bg-[#9b89ff]" />
          <span className="ml-1 mt-[3px] block h-[3px] w-[9px] -rotate-45 bg-[#55a9ff]" />
        </span>
        <span>AIVCS</span>
      </button>
      <div className="flex h-[35px] w-auto flex-1 items-center gap-2.5 rounded-md border border-[#30363d] bg-[#11161d] px-[11px] text-xs text-[#8b949e] sm:w-[380px] sm:flex-none">
        <Search size={16} />
        <input
          className="min-w-0 flex-1 bg-transparent text-xs text-[#f0f6fc] outline-none placeholder:text-[#8b949e]"
          type="text"
          placeholder="Search repositories..."
        />
      </div>
      <div className="ml-auto flex items-center gap-5">
        <button
          className="grid h-[29px] w-[29px] place-items-center rounded-full border-0 bg-gradient-to-br from-[#c2b7ff] to-[#5651a5] text-[10px] font-bold text-white"
          onClick={() => openView("profile")}
        >
          {/*first letter of the user name*/}
          {name.charAt(0).toUpperCase()}
        </button>
      </div>
    </header>
  );
}
