import { useEffect, useRef, useState } from "react";
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
import { CommitModal } from "./Components/CommitModal";
import { api } from "./Static/api";
import {
  clearSession,
  getSessionToken,
  storeSession,
} from "./Static/authStorage";

function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const [auth, setAuth] = useState(() => {
    const token = getSessionToken();
    return {
      status: token ? "loading" : "anonymous",
      token,
      user: null,
      userData: null,
      error: null,
    };
  });
  const { status: authStatus, token, userData } = auth;
  const [modal, setModal] = useState(null); //this is for repository modal, default is null
  const [mobileOpen, setMobileOpen] = useState(false);
  const [selectedBranchName, setSelectedBranchName] = useState(null);
  const [syncError, setSyncError] = useState("");
  const saveQueue = useRef(Promise.resolve());

  useEffect(() => {
    if (authStatus !== "loading" || !token) return undefined;

    let isCurrent = true;
    api
      .currentUser(token)
      .then((result) => {
        if (!isCurrent) return;
        setAuth({
          status: "authenticated",
          token,
          user: result.user,
          userData: result.userData,
          error: null,
        });
      })
      .catch((error) => {
        if (!isCurrent) return;
        if (error.status === 401) clearSession();
        setAuth({
          status: error.status === 401 ? "anonymous" : "unavailable",
          token: error.status === 401 ? null : token,
          user: null,
          userData: null,
          error: error.message,
        });
      });

    return () => {
      isCurrent = false;
    };
  }, [authStatus, token]);

  useEffect(() => {
    if (authStatus !== "authenticated" || !token || !userData) return undefined;

    let isCurrent = true;
    const snapshot = userData;
    setSyncError("");
    saveQueue.current = saveQueue.current
      .catch(() => {})
      .then(() => api.updateUserData(token, snapshot))
      .catch((error) => {
        if (isCurrent) setSyncError(error.message);
      });

    return () => {
      isCurrent = false;
    };
  }, [authStatus, token, userData]);

  const setUserData = (update) => {
    setAuth((current) => ({
      ...current,
      userData:
        typeof update === "function" ? update(current.userData) : update,
    }));
  };

  const login = async ({ email, password }) => {
    try {
      const result = await api.login({ email: email.trim(), password });
      storeSession(result.access_token);
      setAuth({
        status: "authenticated",
        token: result.access_token,
        user: result.user,
        userData: result.userData,
        error: null,
      });
      navigate("/", { replace: true });
      return null;
    } catch (error) {
      return error.message;
    }
  };

  const register = async (details) => {
    try {
      const result = await api.register({
        ...details,
        username: details.username.trim(),
        email: details.email.trim(),
      });
      storeSession(result.access_token);
      setAuth({
        status: "authenticated",
        token: result.access_token,
        user: result.user,
        userData: result.userData,
        error: null,
      });
      navigate("/", { replace: true });
      return null;
    } catch (error) {
      return error.message;
    }
  };

  const logout = () => {
    if (token) api.logout(token).catch(() => {});
    clearSession();
    setAuth({
      status: "anonymous",
      token: null,
      user: null,
      userData: null,
      error: null,
    });
    setSelectedBranchName(null);
    navigate("/login", { replace: true });
  };
  const isAuthenticated = authStatus === "authenticated";

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
      syncError={syncError}
    />
  ) : authStatus === "loading" ? (
    <LoadingScreen />
  ) : (
    <Navigate to="/login" replace />
  );

  return (
    <Routes>
      <Route
        path="/login"
        element={
          authStatus === "loading" ? (
            <LoadingScreen />
          ) : isAuthenticated ? (
            <Navigate to="/" replace />
          ) : (
            <AuthPage
              mode="login"
              onLogin={login}
              onRegister={register}
              initialError={auth.error}
            />
          )
        }
      />
      <Route
        path="/register"
        element={
          authStatus === "loading" ? (
            <LoadingScreen />
          ) : isAuthenticated ? (
            <Navigate to="/" replace />
          ) : (
            <AuthPage
              mode="register"
              onLogin={login}
              onRegister={register}
              initialError={auth.error}
            />
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

function LoadingScreen() {
  return (
    <main className="grid min-h-screen place-items-center bg-[#0d1117] text-xs text-[#8b949e]">
      Restoring your session...
    </main>
  );
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
  syncError,
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
          {syncError && (
            <p
              className="mb-5 rounded-[5px] border border-[#8c3b35] bg-[#321b1b] px-3 py-2 text-xs text-[#ffb4ab]"
              role="alert"
            >
              Could not save your latest changes: {syncError}
            </p>
          )}
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
