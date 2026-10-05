import {
  GitBranch,
  GitCommitHorizontal,
  GitPullRequest,
  Sparkles,
} from "lucide-react";
import { PanelHeading } from "./PanelHeading";
import { ActivityItem } from "./ActivityItem";

export function ActivityPanel({ userData }) {
  const latestCommit = userData.repositories
    ?.flatMap((repository) =>
      repository.branches.flatMap((branch) =>
        branch.commits.map((commit) => ({
          ...commit,
          repositoryName: repository.repositoryName,
        })),
      ),
    )
    .at(-1);

  return (
    <section className="overflow-hidden rounded-[7px] border border-[#30363d] bg-[#161b22c2]">
      <PanelHeading
        title="Recent activity"
        subtitle="Latest updates from your workspace"
        action={
          <button className="border-0 bg-transparent text-[10px] text-[#a99bff]">
            •••
          </button>
        }
      />
      <div className="px-5 pb-[11px]">
        <ActivityItem
          icon={GitCommitHorizontal}
          title={`${userData.username} committed to`}
          detail={latestCommit?.repositoryName ?? "No repositories"}
          time={latestCommit?.message ?? "No commits yet"}
          color="purple"
        />
        <ActivityItem
          icon={GitBranch}
          title={`${userData.username} owns`}
          detail={`${userData.repositories?.length ?? 0} repositories`}
          time=""
          color="blue"
        />
        <ActivityItem
          icon={Sparkles}
          title="AI generated a commit"
          detail="No AI-generated commits recorded"
          time=""
          color="amber"
        />
        <ActivityItem
          icon={GitPullRequest}
          title="Pull request opened in"
          detail="No pull requests recorded"
          time=""
          color="green"
        />
      </div>
    </section>
  );
}
