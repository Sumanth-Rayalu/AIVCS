import { useEffect, useState } from "react";
import {
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import { Topbar } from "./Components/Topbar";
import { AuthPage } from "./Components/AuthPage";
import { Sidebar } from "./Components/Sidebar";
import { Dashboard } from "./Components/Dashboard";
import { Repository } from "./Components/Repository";
import { AIHistory } from "./Components/AIHistory";
import { ListView } from "./Components/ListView";
import { Profile } from "./Components/Profile";
import { Settings } from "./Components/Settings";
import { RepositoryModal } from "./Components/RepositoryModal";
// import { CommitModal } from "./Components/CommitModal";
import {
  clearSession,
  getSignedInAccount,
  loadAccounts,
  persistUserData,
  saveAccounts,
  storeSession,
} from "./Static/authStorage";

function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const [auth, setAuth] = useState(() => {
    const account = getSignedInAccount();
    return account
      ? { email: account.email, userData: account.userData }
      : { email: null, userData: null };
  });
  const { email: currentEmail, userData } = auth;
  const [modal, setModal] = useState(null); //this is for repository modal, default is null
  const [mobileOpen, setMobileOpen] = useState(false);
  const [selectedBranchName, setSelectedBranchName] = useState(null);
  const setUserData = (update) => {
    setAuth((current) => ({
      ...current,
      userData:
        typeof update === "function" ? update(current.userData) : update,
    }));
  };

  useEffect(() => {
    if (currentEmail && userData) persistUserData(currentEmail, userData);
  }, [currentEmail, userData]);

  const login = ({ email, password }) => {
    const normalizedEmail = email.trim().toLowerCase();
    const account = loadAccounts().find(
      (item) =>
        item.email.toLowerCase() === normalizedEmail &&
        item.password === password,
    );
    if (!account) return "Email or password is incorrect.";

    storeSession(account);
    setAuth({ email: account.email, userData: account.userData });
    navigate("/", { replace: true });
    return null;
  };

  const register = ({ username, email, password }) => {
    const normalizedEmail = email.trim().toLowerCase();
    const accounts = loadAccounts();
    if (
      accounts.some(
        (account) => account.email.toLowerCase() === normalizedEmail,
      )
    ) {
      return "An account with this email already exists.";
    }

    const createdAt = new Date().toISOString();
    const account = {
      email: normalizedEmail,
      password,
      username: username.trim(),
      userData: {
        email: normalizedEmail,
        username: username.trim(),
        createdAt,
        noOfRepositories: 0,
        noOfCommits: 0,
        repositories: [],
      },
    };
    accounts.push(account);
    saveAccounts(accounts);
    storeSession(account);
    setAuth({ email: account.email, userData: account.userData });
    navigate("/", { replace: true });
    return null;
  };

  const logout = () => {
    clearSession();
    setAuth({ email: null, userData: null });
    setSelectedBranchName(null);
    navigate("/login", { replace: true });
  };
  const isAuthenticated = Boolean(currentEmail && userData);

  const openView = (nextView) => {
    const paths = {
      overview: "/",
      repository: "/repositories",
      "ai-history": "/ai-history",
      issues: "/issues",
      pulls: "/pulls",
      profile: "/profile",
      settings: "/settings",
    };
    navigate(paths[nextView] ?? "/");
    setMobileOpen(false);
  };
  const openRepository = (repositoryId) => {
    setSelectedBranchName(null);
    navigate(
      repositoryId
        ? `/repositories/${encodeURIComponent(repositoryId)}`
        : "/repositories",
    );
    setMobileOpen(false);
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

  const view = getViewFromPath(location.pathname);
  const protectedLayout = isAuthenticated ? (
    <WorkspaceLayout
      view={view}
      userData={userData}
      openView={openView}
      openRepository={openRepository}
      onLogout={logout}
      mobileOpen={mobileOpen}
      setMobileOpen={setMobileOpen}
      setModal={setModal}
      modal={modal}
      createRepository={createRepository}
    />
  ) : (
    <Navigate to="/login" replace />
  );

  return (
    <Routes>
      <Route
        path="/login"
        element={
          isAuthenticated ? (
            <Navigate to="/" replace />
          ) : (
            <AuthPage mode="login" onLogin={login} onRegister={register} />
          )
        }
      />
      <Route
        path="/register"
        element={
          isAuthenticated ? (
            <Navigate to="/" replace />
          ) : (
            <AuthPage mode="register" onLogin={login} onRegister={register} />
          )
        }
      />
      <Route element={protectedLayout}>
        <Route
          index
          element={
            <Dashboard
              userData={userData}
              onNew={() => setModal("repository")}
              onRepo={openRepository}
            />
          }
        />
        <Route
          path="repositories"
          element={
            <Repository
              userData={userData}
              selectedRepositoryId={null}
              selectedBranchName={selectedBranchName}
              onRepositorySelect={openRepository}
              onBranchSelect={setSelectedBranchName}
              onCommit={commitFileChange}
              onAI={() => setModal("commit")}
            />
          }
        />
        <Route
          path="repositories/:repositoryId"
          element={
            <RepositoryRoute
              userData={userData}
              selectedBranchName={selectedBranchName}
              onRepositorySelect={openRepository}
              onBranchSelect={setSelectedBranchName}
              onCommit={commitFileChange}
              onAI={() => setModal("commit")}
            />
          }
        />
        <Route path="ai-history" element={<AIHistory />} />
        <Route
          path="issues"
          element={<ListView type="issues" userData={userData} />}
        />
        <Route
          path="pulls"
          element={<ListView type="pulls" userData={userData} />}
        />
        <Route path="profile" element={<Profile userData={userData} />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

function getViewFromPath(pathname) {
  if (pathname === "/") return "overview";
  if (pathname.startsWith("/repositories")) return "repository";
  return pathname.slice(1).split("/")[0];
}

function RepositoryRoute(props) {
  const { repositoryId } = useParams();
  return <Repository {...props} selectedRepositoryId={repositoryId} />;
}

function WorkspaceLayout({
  view,
  userData,
  openView,
  openRepository,
  onLogout,
  mobileOpen,
  setMobileOpen,
  setModal,
  modal,
  createRepository,
}) {
  return (
    <div className="min-h-screen bg-[#0d1117] text-[#f0f6fc] antialiased">
      <Topbar
        openView={openView}
        setMobileOpen={setMobileOpen}
        name={userData.username}
        repositories={userData.repositories}
        onRepositorySelect={openRepository}
        onLogout={onLogout}
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
          <Outlet />
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
