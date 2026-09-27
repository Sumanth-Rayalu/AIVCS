import { useState } from "react";
import { Topbar } from "./Components/Topbar";
import { Sidebar } from "./Components/Sidebar";
import { Dashboard } from "./Components/Dashboard";
import { Repository } from "./Components/Repository";
import { AIHistory } from "./Components/AIHistory";
import { ListView } from "./Components/ListView";
import { Profile } from "./Components/Profile";
import { Settings } from "./Components/Settings";
import { RepositoryModal } from "./Components/RepositoryModal";
// import { CommitModal } from "./Components/CommitModal";
import { userData as Data } from "./Static/repos";

function App() {
  const [userData, setUserData] = useState(Data); // Initialize user state with userData
  const [view, setView] = useState("overview"); //This is for sidebar view, default is overview
  const [modal, setModal] = useState(null); //this is for repository modal, default is null
  const [mobileOpen, setMobileOpen] = useState(false);
  const [selectedRepositoryId, setSelectedRepositoryId] = useState(null);
  const [selectedBranchName, setSelectedBranchName] = useState(null);
  const openView = (nextView) => {
    setView(nextView);
    setMobileOpen(false);
  };
  const openRepository = (repositoryId) => {
    setSelectedRepositoryId(repositoryId);
    setSelectedBranchName(null);
    openView("repository");
  };
  const createRepository = (repositoryName, description) => {
    if (!repositoryName) return "Repository name is required.";
    if (
      userData.repositories.some(
        (repository) =>
          repository.repositoryName.toLowerCase() ===
          repositoryName.toLowerCase(),
      )
    ) {
      return "A repository with this name already exists.";
    }

    const baseId =
      repositoryName
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "") || "repository";
    let repositoryId = baseId;
    let suffix = 2;
    while (
      userData.repositories.some(
        (repository) => repository.repositoryId === repositoryId,
      )
    ) {
      repositoryId = `${baseId}-${suffix}`;
      suffix += 1;
    }

    setUserData((currentUserData) => {
      const repositories = [
        ...currentUserData.repositories,
        {
          repositoryId,
          repositoryName,
          description,
          branches: [{ branchName: "main", headCommitId: null, commits: [] }],
        },
      ];
      return {
        ...currentUserData,
        repositories,
        noOfRepositories: repositories.length,
      };
    });
    openRepository(repositoryId);
    return null;
  };
  const commitFileChange = ({
    repositoryId,
    branchName,
    filename,
    fileextension,
    content,
    message,
  }) => {
    setUserData((currentUserData) => {
      const timestamp = new Date().toISOString();
      const commitId = `${currentUserData.username}-${Date.now()}`;
      const repositories = currentUserData.repositories.map((repository) => {
        if (repository.repositoryId !== repositoryId) return repository;

        return {
          ...repository,
          branches: repository.branches.map((branch) => {
            if (branch.branchName !== branchName) return branch;

            const commits = branch.commits ?? [];
            const previousCommit = commits.at(-1);

            return {
              ...branch,
              headCommitId: commitId,
              commits: [
                ...commits,
                {
                  commitId,
                  message,
                  timestamp,
                  author: currentUserData.username,
                  parent:
                    previousCommit?.commitId ?? branch.headCommitId ?? null,
                  fileDetails: [
                    {
                      filename,
                      fileextension,
                      content,
                      contentHash: `${filename}-${timestamp}`,
                    },
                  ],
                },
              ],
            };
          }),
        };
      });
      const noOfCommits = repositories.reduce(
        (total, repository) =>
          total +
          repository.branches.reduce(
            (branchTotal, branch) => branchTotal + branch.commits.length,
            0,
          ),
        0,
      );

      return {
        ...currentUserData,
        repositories,
        noOfRepositories: repositories.length,
        noOfCommits,
      };
    });
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-[#f0f6fc] antialiased">
      <Topbar
        openView={openView}
        setMobileOpen={setMobileOpen}
        name={userData.username}
      />
      <div className="mx-auto flex max-w-[1480px]">
        <Sidebar
          view={view}
          openView={openView}
          mobileOpen={mobileOpen}
          setModal={setModal}
          userData={userData}
          onRepositorySelect={openRepository}
        />
        <main className="min-w-0 max-w-[1170px] flex-1 px-4 py-[30px] pb-[50px] sm:px-[30px] sm:py-[38px] lg:px-[56px] lg:py-[49px] lg:pb-20">
          {view === "overview" && (
            <Dashboard
              userData={userData}
              onNew={() => setModal("repository")}
              onRepo={openRepository}
            />
          )}
          {view === "repository" && (
            <Repository
              userData={userData}
              selectedRepositoryId={selectedRepositoryId}
              selectedBranchName={selectedBranchName}
              onRepositorySelect={openRepository}
              onBranchSelect={setSelectedBranchName}
              onCommit={commitFileChange}
              onAI={() => setModal("commit")}
            />
          )}
          {view === "ai-history" && <AIHistory />}
          {(view === "issues" || view === "pulls") && (
            <ListView type={view} userData={userData} />
          )}
          {view === "profile" && <Profile userData={userData} />}
          {view === "settings" && <Settings />}
        </main>
      </div>
      {modal === "repository" && (
        <RepositoryModal
          onClose={() => setModal(null)}
          onCreate={createRepository}
        />
      )}
      {modal === "commit" && <CommitModal onClose={() => setModal(null)} />}
    </div>
  );
}

export default App;
