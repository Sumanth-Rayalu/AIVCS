import { useState } from "react";
import { LogOut, Menu, Search } from "lucide-react";

export function Topbar({
  openView,
  setMobileOpen,
  name,
  repositories,
  onRepositorySelect,
  onLogout,
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const matchingRepositories = repositories.filter((repository) => {
    const query = searchQuery.trim().toLowerCase();
    return (
      query &&
      `${repository.repositoryName} ${repository.description ?? ""}`
        .toLowerCase()
        .includes(query)
    );
  });

  const selectRepository = (repositoryId) => {
    onRepositorySelect(repositoryId);
    setSearchQuery("");
    setIsSearchOpen(false);
  };

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
      <div className="relative flex h-[35px] w-auto flex-1 items-center gap-2.5 rounded-md border border-[#30363d] bg-[#11161d] px-[11px] text-xs text-[#8b949e] sm:w-[380px] sm:flex-none">
        <Search size={16} />
        <input
          className="min-w-0 flex-1 bg-transparent text-xs text-[#f0f6fc] outline-none placeholder:text-[#8b949e]"
          type="text"
          placeholder="Search repositories..."
          value={searchQuery}
          onChange={(event) => {
            setSearchQuery(event.target.value);
            setIsSearchOpen(true);
          }}
          onFocus={() => setIsSearchOpen(true)}
          onBlur={(event) => {
            if (
              !event.currentTarget.parentElement.contains(event.relatedTarget)
            ) {
              setIsSearchOpen(false);
            }
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") setIsSearchOpen(false);
          }}
          aria-label="Search repositories"
          aria-expanded={isSearchOpen && Boolean(searchQuery.trim())}
          aria-controls="repository-search-results"
        />
        {isSearchOpen && searchQuery.trim() && (
          <div
            id="repository-search-results"
            className="absolute left-0 right-0 top-[calc(100%+8px)] z-30 overflow-hidden rounded-[6px] border border-[#30363d] bg-[#161b22] py-1 shadow-[0_12px_30px_rgba(0,0,0,0.45)]"
            role="listbox"
            aria-label="Repository search results"
          >
            {matchingRepositories.length > 0 ? (
              matchingRepositories.map((repository) => (
                <button
                  key={repository.repositoryId}
                  type="button"
                  className="flex w-full items-start gap-2.5 border-0 bg-transparent px-3 py-2.5 text-left hover:bg-[#1c232b] focus:bg-[#1c232b] focus:outline-none"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => selectRepository(repository.repositoryId)}
                  role="option"
                  aria-selected="false"
                >
                  <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-[#58a6ff]" />
                  <span className="min-w-0">
                    <strong className="block truncate text-[11px] text-[#f0f6fc]">
                      {repository.repositoryName}
                    </strong>
                    <span className="mt-0.5 block truncate text-[10px] text-[#8b949e]">
                      {repository.description || "No description"}
                    </span>
                  </span>
                </button>
              ))
            ) : (
              <p className="m-0 px-3 py-3 text-[11px] text-[#8b949e]">
                No repositories found.
              </p>
            )}
          </div>
        )}
      </div>
      <div className="ml-auto flex items-center gap-3">
        <button
          type="button"
          title="Sign out"
          aria-label="Sign out"
          className="grid h-[29px] w-[29px] place-items-center rounded-[5px] border-0 bg-transparent text-[#8b949e] hover:bg-[#1b222b] hover:text-[#f0f6fc]"
          onClick={onLogout}
        >
          <LogOut size={16} />
        </button>
        <button
          type="button"
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
