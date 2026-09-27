import { CircleDot, GitBranch, Plus, Search } from "lucide-react";
import { Button } from "./Button";
import { PageHeader } from "./PageHeader";

export function ListView({ type, userData }) {
  const issue = type === "issues";
  const rows = issue
    ? [
        [
          "Authentication fails after token expiry",
          "#42",
          "bug",
          "authentication",
          "opened 2 hours ago",
        ],
        [
          "Improve repository search experience",
          "#41",
          "enhancement",
          "",
          "opened yesterday",
        ],
        [
          "Add rate limiting to public API",
          "#39",
          "security",
          "api",
          "opened 4 days ago",
        ],
        [
          "Update Python dependencies",
          "#37",
          "maintenance",
          "",
          "opened 1 week ago",
        ],
      ]
    : [
        [
          "Add JWT authentication",
          "#18",
          "feature/auth",
          "main",
          "updated 2 hours ago",
        ],
        [
          "Improve API validation",
          "#17",
          "feature/api",
          "main",
          "updated yesterday",
        ],
        [
          "Refactor repository indexing",
          "#15",
          "refactor/search",
          "develop",
          "updated 3 days ago",
        ],
        [
          "Add onboarding flow",
          "#12",
          "feature/onboarding",
          "main",
          "updated 1 week ago",
        ],
      ];
  return (
    <>
      <PageHeader
        eyebrow={userData.repositories?.[0]?.repositoryName ?? "Repositories"}
        title={issue ? "Issues" : "Pull requests"}
        description={
          issue
            ? "Track ideas, bugs, and tasks for this repository."
            : "Review code changes and ship with confidence."
        }
        action={
          <Button primary>
            <Plus size={16} />
            New {issue ? "issue" : "pull request"}
          </Button>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-2 border-b border-[#30363d]">
        <button className="border-0 border-b-2 border-[#9c8dff] bg-transparent px-[14px] py-3 text-[11px] text-[#f0f6fc]">
          Open <span>{issue ? "12" : "4"}</span>
        </button>
        <button className="border-0 border-b-2 border-transparent bg-transparent px-[14px] py-3 text-[11px] text-[#8b949e]">
          Closed <span>{issue ? "38" : "21"}</span>
        </button>
        <div className="ml-auto flex items-center gap-2 rounded border border-[#30363d] p-[7px_10px] text-[10px] text-[#8b949e] max-sm:mb-2.5 max-sm:w-full">
          <Search size={15} />
          Filter {issue ? "issues" : "pull requests"}
        </div>
      </div>
      <section className="overflow-hidden rounded-[7px] border border-[#30363d] bg-[#161b22c2]">
        {rows.map((row, index) => (
          <div
            className="flex items-center gap-[13px] border-b border-[#30363db3] p-[17px_20px] max-sm:p-[15px_12px]"
            key={row[1]}
          >
            <span
              className={
                issue && index === 0 ? "text-[#f78166]" : "text-[#3fb950]"
              }
            >
              <CircleDot size={17} />
            </span>
            <div className="flex-1">
              <strong className="text-xs font-medium">{row[0]}</strong>
              <p className="m-[6px_0_0] flex items-center gap-1.5 text-[10px] text-[#8b949e]">
                {row[1]} ·{" "}
                {issue ? (
                  <>
                    <span
                      className={`rounded-xl px-1.5 py-0.5 text-[9px] ${row[2] === "bug" ? "bg-[#452b2b] text-[#ff9b8b]" : row[2] === "enhancement" ? "bg-[#342f55] text-[#b7aaff]" : row[2] === "security" ? "bg-[#42331e] text-[#dfb65a]" : "bg-[#2c343d] text-[#9da7b2]"}`}
                    >
                      {row[2]}
                    </span>
                    {row[3] && (
                      <span className="rounded-xl bg-[#2c343d] px-1.5 py-0.5 text-[9px] text-[#9da7b2]">
                        {row[3]}
                      </span>
                    )}
                  </>
                ) : (
                  <>
                    <GitBranch size={12} />
                    {row[2]} → {row[3]}
                  </>
                )}
              </p>
            </div>
            <small className="text-[10px] text-[#6e7681] max-sm:hidden">
              {row[4]}
            </small>
          </div>
        ))}
      </section>
    </>
  );
}
