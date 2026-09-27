import {
  GitBranch,
  GitCommitHorizontal,
  GitPullRequest,
  Plus,
  Sparkles,
} from "lucide-react";
import { PageHeader } from "./PageHeader";
import { Button } from "./Button";
import { Metric } from "./Metric";
import { PanelHeading } from "./PanelHeading";
import { ActivityPanel } from "./ActivityPanel";
import { ActivityChart } from "./ActivityChart";

export function Dashboard({ userData, onNew, onRepo }) {
  const repositories = userData.repositories ?? [];
  const currentDate = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  return (
    <>
      <PageHeader
        eyebrow={currentDate}
        title={`Good morning, ${userData.username}`}
        description="Here's what's happening across your workspace."
        action={
          <Button primary onClick={onNew}>
            <Plus size={16} />
            New repository
          </Button>
        }
      />
      <section className="mb-[23px] grid gap-[14px] sm:grid-cols-3 max-sm:grid-cols-1">
        <Metric
          icon={GitCommitHorizontal}
          tone="purple"
          label="Commits this week"
          value={userData.noOfCommits}
          note="Commits recorded in your workspace"
        />
        {/* <Metric
          icon={GitPullRequest}
          tone="blue"
          label="Open pull requests"
          value="—"
          note=""
        /> */}
        <Metric
          icon={Sparkles}
          tone="amber"
          label="AI insights generated"
          value="—"
          note=""
        />
      </section>
      <div className="grid gap-4 lg:grid-cols-[1.35fr_0.9fr] max-lg:grid-cols-1">
        <section className="overflow-hidden rounded-[7px] border border-[#30363d] bg-[#161b22c2]">
          <PanelHeading
            title="Your repositories"
            subtitle="Active projects in your workspace"
            action={
              <button
                className="border-0 bg-transparent text-[10px] text-[#a99bff]"
                onClick={onRepo}
              >
                View all <span>→</span>
              </button>
            }
          />
          <div className="grid gap-[11px] p-[0_15px_15px] max-lg:grid-cols-1 lg:grid-cols-3">
            {repositories.map((repo) => (
              <button
                className="min-w-0 rounded-[6px] border border-[#2b333c] bg-[#191f27] p-[15px] text-left text-[#f0f6fc] hover:-translate-y-px hover:border-[#5d5b8f]"
                key={repo.repositoryId}
                onClick={() => onRepo(repo.repositoryId)}
              >
                <div className="flex items-center gap-2 text-[11px]">
                  <span
                    className={`h-2 w-2 shrink-0 rounded-full ${repo.language === "Python" ? "bg-[#58a6ff]" : "bg-[#e3b341]"}`}
                  />
                  <strong className="overflow-hidden text-ellipsis">
                    {repo.repositoryName}
                  </strong>
                  <span className="ml-auto rounded-full border border-[#3b4650] px-1.5 py-0.5 text-[9px] text-[#8b949e]">
                    Public
                  </span>
                </div>
                <p className="my-[14px] min-h-[30px] text-[10px] leading-[1.5] text-[#8b949e]">
                  {repo.description}
                </p>
                <div className="flex items-center gap-3 text-[10px] text-[#8b949e]">
                  <span className="flex items-center gap-1">
                    <GitBranch size={13} />
                    {repo.branches?.length ?? 0} branches
                  </span>
                  <span className="flex items-center gap-1">
                    <GitCommitHorizontal size={13} />
                    {repo.branches?.reduce(
                      (total, branch) => total + (branch.commits?.length ?? 0),
                      0,
                    ) ?? 0}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </section>
        <ActivityPanel userData={userData} />
      </div>
      {/* <ActivityChart /> */}
    </>
  );
}
