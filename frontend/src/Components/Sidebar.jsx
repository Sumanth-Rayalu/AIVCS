import {
  CircleDot,
  Code2,
  GitPullRequest,
  LayoutDashboard,
  Plus,
  Settings2,
  Sparkles,
  Zap,
} from "lucide-react";

export function Sidebar({
  view,
  openView,
  mobileOpen,
  setModal,
  userData,
  onRepositorySelect,
}) {
  const navItems = [
    ["overview", "Overview", LayoutDashboard],
    ["repository", "Repositories", Code2],
    // ["ai-history", "AI History", Sparkles],
    // ["issues", "Issues", CircleDot],
    // ["pulls", "Pull requests", GitPullRequest],
  ];
  return (
    <aside
      className={`fixed inset-y-0 left-0 top-16 z-[15] flex w-[240px] shrink-0 flex-col border-r border-[#30363d] bg-[#10151b] px-4 py-5 transition-transform duration-200 sm:static sm:min-h-[calc(100vh-64px)] sm:translate-x-0 sm:bg-transparent sm:py-[25px] ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}
    >
      <div className="mb-6 flex items-center gap-2.5 border-b border-[#30363d99] px-2 pb-6">
        <div className="grid h-[29px] w-[29px] place-items-center rounded-lg bg-[#2c253c] text-xs font-bold text-[#bdadff]">
          {userData.username.charAt(0).toUpperCase()}
        </div>
        <div className="flex-1">
          <strong className="block text-xs">{userData.username}</strong>
          <small className="mt-0.5 block text-[10px] text-[#8b949e]">
            Personal workspace
          </small>
        </div>
        {/*<ChevronDown size={15} />*/}
      </div>
      <div className="px-[9px] pb-[9px] text-[9px] font-bold uppercase tracking-[1px] text-[#6e7681]">
        Workspace
      </div>
      <nav className="grid gap-[3px]">
        {navItems.map(([id, label, Icon]) => (
          <button
            key={id}
            className={`flex w-full items-center gap-[11px] rounded-[5px] border-0 p-[9px] text-left text-xs ${view === id ? "bg-[#29253b] text-[#d6d0ff]" : "bg-transparent text-[#8b949e] hover:bg-[#1b222b] hover:text-[#f0f6fc]"}`}
            onClick={() => openView(id)}
          >
            <Icon size={17} />
            <span>{label}</span>
            {/* {count && (
              <em className="ml-auto text-[10px] not-italic text-[#6e7681]">
                {count}
              </em>
            )} */}
          </button>
        ))}
      </nav>
      <div className="mt-7 flex justify-between px-[9px] pb-[9px] text-[9px] font-bold uppercase tracking-[1px] text-[#6e7681]">
        Your repositories{" "}
        <button
          className="border-0 bg-transparent p-0 text-[#6e7681]"
          onClick={() => setModal("repository")}
        >
          <Plus size={15} />
        </button>
      </div>
      <div className="grid gap-0.5">
        {/*Repository list*/}
        {userData.repositories.map((repository) => (
          <button
            className="flex w-full items-center gap-[11px] border-0 bg-transparent p-[9px] text-left text-[11px] text-[#8b949e] hover:bg-[#1b222b] hover:text-[#f0f6fc]"
            key={repository.repositoryId}
            onClick={() => onRepositorySelect(repository.repositoryId)}
          >
            <span className="h-2 w-2 shrink-0 rounded-full bg-[#58a6ff]" />
            {repository.repositoryName}
          </button>
        ))}
      </div>
    </aside>
  );
}
