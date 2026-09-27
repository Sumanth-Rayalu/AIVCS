import { Star } from "lucide-react";
import { Button } from "./Button";
import { PanelHeading } from "./PanelHeading";

export function Profile({ userData }) {
  const repositories = userData.repositories ?? [];

  return (
    <>
      <div className="h-[110px] rounded-t-[7px] border border-[#30363d] bg-gradient-to-br from-[#222139] via-[#1a2029] to-[#202c3c]" />
      <div className="flex flex-wrap items-start gap-[17px] border-b border-[#30363d] px-[15px] pb-5 sm:px-[26px]">
        <div className="-mt-[38px] grid h-[76px] w-[76px] place-items-center rounded-full border-[5px] border-[#0d1117] bg-gradient-to-br from-[#c2b7ff] to-[#5651a5] text-[22px] font-bold text-white">
          {userData.username.charAt(0).toUpperCase()}
        </div>
        <div>
          <h1 className="mt-0.5 mb-[5px] text-lg sm:text-[22px]">
            {userData.username}
          </h1>
          <p className="my-[3px] text-[11px] text-[#8b949e]">
            @{userData.username}
          </p>
          <p className="my-[3px] text-[11px] text-[#6e7681]">
            {userData.email}
          </p>
        </div>
        {/* <Button>Edit profile</Button> */}
      </div>
      <div className="flex gap-[18px] px-[15px] py-[19px] pb-7 sm:gap-[30px] sm:px-[25px]">
        <div className="flex items-baseline gap-2 max-sm:flex-col max-sm:gap-[3px]">
          <strong className="text-[17px]">{userData.noOfRepositories}</strong>
          <span className="text-[11px] text-[#8b949e]">Repositories</span>
        </div>
        <div className="flex items-baseline gap-2 max-sm:flex-col max-sm:gap-[3px]">
          <strong className="text-[17px]">{userData.noOfCommits}</strong>
          <span className="text-[11px] text-[#8b949e]">Commits</span>
        </div>
      </div>
      <section className="overflow-hidden rounded-[7px] border border-[#30363d] bg-[#161b22c2]">
        <PanelHeading
          title="Pinned repositories"
          subtitle="Projects worth a closer look"
        />
        <div className="grid grid-cols-2 gap-[11px] p-[0_15px_15px] max-sm:grid-cols-1">
          {repositories.slice(0, 2).map((repo) => (
            <button
              className="min-w-0 rounded-[6px] border border-[#2b333c] bg-[#191f27] p-[15px] text-left text-[#f0f6fc]"
              key={repo.name}
            >
              <div className="flex items-center gap-2 text-[11px]">
                <span className="h-2 w-2 shrink-0 rounded-full bg-[#58a6ff]" />
                <strong className="overflow-hidden text-ellipsis">
                  {repo.name}
                </strong>
              </div>
              <p className="my-[14px] min-h-[30px] text-[10px] leading-[1.5] text-[#8b949e]">
                {repo.description}
              </p>
              <div className="flex items-center gap-3 text-[10px] text-[#8b949e]">
                <span>{repo.language}</span>
                <span className="flex items-center gap-1">
                  <Star size={13} />
                  {repo.branches?.length ?? 0} branches
                </span>
              </div>
            </button>
          ))}
        </div>
      </section>
    </>
  );
}
