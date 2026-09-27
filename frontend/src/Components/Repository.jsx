import { useEffect, useState } from "react";
import {
  BookOpen,
  Check,
  ChevronDown,
  CircleDot,
  Code2,
  FileCode2,
  Folder,
  GitBranch,
  GitPullRequest,
  Layers3,
  Pencil,
  Plus,
  Save,
  Settings2,
  Sparkles,
  Star,
  Zap,
} from "lucide-react";
import { Button } from "./Button";

export function Repository({
  userData,
  selectedRepositoryId,
  selectedBranchName,
  onRepositorySelect,
  onBranchSelect,
  onCommit,
  onAI,
}) {
  const repositories = userData.repositories ?? [];
  const repository = repositories.find(
    (item) => item.repositoryId === selectedRepositoryId,
  );
  const [isBranchMenuOpen, setIsBranchMenuOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isEditingFile, setIsEditingFile] = useState(false);
  const [editedContent, setEditedContent] = useState("");
  const [commitMessage, setCommitMessage] = useState("");
  const [isAddingFile, setIsAddingFile] = useState(false);
  const [newFileName, setNewFileName] = useState("");
  const [newFileExtension, setNewFileExtension] = useState("");
  const [newFileContent, setNewFileContent] = useState("");
  const [newFileCommitMessage, setNewFileCommitMessage] = useState("");
  const branch =
    repository?.branches?.find(
      (item) => item.branchName === selectedBranchName,
    ) ?? repository?.branches?.[0];
  const files = branch?.commits
    ? Array.from(
        branch.commits
          .reduce((fileMap, commit) => {
            (commit.fileDetails ?? []).forEach((file) => {
              const name = `${file.filename}${file.fileextension}`;
              fileMap.set(name, {
                name,
                filename: file.filename,
                fileextension: file.fileextension,
                commit: commit.message,
                time: new Date(commit.timestamp).toLocaleDateString(),
                icon: FileCode2,
                content: file.content,
              });
            });
            return fileMap;
          }, new Map())
          .values(),
      )
    : [];
  useEffect(() => {
    setSelectedFile(null);
    setIsEditingFile(false);
    setEditedContent("");
    setCommitMessage("");
    setIsAddingFile(false);
    setNewFileName("");
    setNewFileExtension("");
    setNewFileContent("");
    setNewFileCommitMessage("");
  }, [selectedRepositoryId, branch?.branchName]);
  const readme = [...(branch?.commits ?? [])]
    .reverse()
    .flatMap((commit) => commit.fileDetails ?? [])
    .find((file) => file.fileextension === ".md");

  const selectFile = (file) => {
    setSelectedFile(file);
    setIsEditingFile(false);
    setEditedContent(file.content ?? "");
    setCommitMessage("");
  };

  const commitFile = () => {
    if (!selectedFile || !commitMessage.trim()) return;

    onCommit({
      repositoryId: repository.repositoryId,
      branchName: branch.branchName,
      filename: selectedFile.filename,
      fileextension: selectedFile.fileextension,
      content: editedContent,
      message: commitMessage.trim(),
    });
    setSelectedFile({
      ...selectedFile,
      content: editedContent,
      commit: commitMessage.trim(),
      time: new Date().toLocaleDateString(),
    });
    setIsEditingFile(false);
    setCommitMessage("");
  };

  const addFile = () => {
    const filename = newFileName.trim();
    const extension = newFileExtension.trim();
    const fileextension = extension
      ? extension.startsWith(".")
        ? extension
        : `.${extension}`
      : "";
    const name = `${filename}${fileextension}`;

    if (
      !filename ||
      !newFileCommitMessage.trim() ||
      files.some((file) => file.name === name)
    ) {
      return;
    }

    onCommit({
      repositoryId: repository.repositoryId,
      branchName: branch.branchName,
      filename,
      fileextension,
      content: newFileContent,
      message: newFileCommitMessage.trim(),
    });
    setSelectedFile({
      name,
      filename,
      fileextension,
      content: newFileContent,
      commit: newFileCommitMessage.trim(),
      time: new Date().toLocaleDateString(),
    });
    setIsAddingFile(false);
    setNewFileName("");
    setNewFileExtension("");
    setNewFileContent("");
    setNewFileCommitMessage("");
  };

  return (
    <>
      <section className="mb-6 overflow-hidden rounded-[7px] border border-[#30363d] bg-[#161b22c2]">
        <div className="border-b border-[#30363d] px-4 py-[13px]">
          <h1 className="m-0 text-lg">Your repositories</h1>
          <p className="m-0 mt-1 text-[11px] text-[#8b949e]">
            Select a repository to view its files and history.
          </p>
        </div>
        <div className="grid gap-2 p-3">
          {repositories.map((item) => {
            const commitCount =
              item.branches?.reduce(
                (total, itemBranch) =>
                  total + (itemBranch.commits?.length ?? 0),
                0,
              ) ?? 0;
            const isSelected = item.repositoryId === selectedRepositoryId;

            return (
              <button
                className={`flex w-full items-center gap-3 rounded-[6px] border p-3 text-left ${isSelected ? "border-[#8b7cff] bg-[#29253b]" : "border-[#2b333c] bg-[#191f27] hover:border-[#5d5b8f]"}`}
                key={item.repositoryId}
                onClick={() =>
                  onRepositorySelect(isSelected ? null : item.repositoryId)
                }
                aria-expanded={isSelected}
              >
                <span className="h-2 w-2 shrink-0 rounded-full bg-[#58a6ff]" />
                <span className="min-w-0 flex-1">
                  <strong className="block overflow-hidden text-ellipsis text-[11px]">
                    {item.repositoryName}
                  </strong>
                  <span className="block overflow-hidden text-ellipsis text-[10px] text-[#8b949e]">
                    {item.description}
                  </span>
                </span>
                <span className="shrink-0 text-[10px] text-[#8b949e]">
                  {commitCount} commits
                </span>
                <ChevronDown
                  size={15}
                  className={isSelected ? "rotate-180" : ""}
                />
              </button>
            );
          })}
        </div>
      </section>
      {repository && (
        <>
          <div className="relative mb-6">
            <div className="flex flex-wrap items-center gap-[9px]">
              <span className="h-2 w-2 shrink-0 rounded-full bg-[#58a6ff]" />
              <h1 className="m-0 text-[21px]">
                {userData.username} /{" "}
                <strong>{repository?.repositoryName}</strong>
              </h1>
              {/* <span className="ml-auto rounded-full border border-[#3b4650] px-1.5 py-0.5 text-[9px] text-[#8b949e]">
                Public
              </span> */}
            </div>
            <p className="ml-0 mt-2.5 text-[13px] text-[#8b949e] sm:ml-[17px]">
              {repository?.description}
            </p>
            {/* <div className="mt-[17px] flex gap-[7px] sm:absolute sm:bottom-0 sm:right-0 sm:mt-0">
              <Button>
                <Star size={15} />
                Star <span className="button-count">24</span>
              </Button>
              <Button>
                <GitBranch size={15} />
                Fork <span className="button-count">5</span>
              </Button>
            </div> */}
          </div>
          {/* <div className="-mx-4 flex gap-[18px] overflow-auto border-b border-[#30363d] px-4 sm:mx-[-30px] sm:px-[30px] lg:mx-[-56px] lg:gap-[23px] lg:px-[56px]">
            <button className="flex shrink-0 items-center gap-[7px] border-0 border-b-2 border-[#a594ff] bg-transparent px-px py-[13px] text-[11px] text-[#f0f6fc]">
              <Code2 size={16} />
              Code
            </button>
            <button className="flex shrink-0 items-center gap-[7px] border-0 border-b-2 border-transparent bg-transparent px-px py-[13px] text-[11px] text-[#8b949e]">
              <CircleDot size={16} />
              Issues <span>12</span>
            </button>
            <button className="flex shrink-0 items-center gap-[7px] border-0 border-b-2 border-transparent bg-transparent px-px py-[13px] text-[11px] text-[#8b949e]">
              <GitPullRequest size={16} />
              Pull Requests <span>4</span>
            </button>
            <button
              className="flex shrink-0 items-center gap-[7px] border-0 border-b-2 border-transparent bg-transparent px-px py-[13px] text-[11px] text-[#8b949e]"
              onClick={onAI}
            >
              <Sparkles size={16} />
              AI History
            </button>
            <button className="flex shrink-0 items-center gap-[7px] border-0 border-b-2 border-transparent bg-transparent px-px py-[13px] text-[11px] text-[#8b949e]">
              <Settings2 size={16} />
              Settings
            </button>
          </div> */}
          <div className="flex justify-between gap-2 pt-[22px] pb-[15px]">
            <div className="relative">
              <button
                type="button"
                className="inline-flex items-center gap-[7px] rounded-[5px] border border-[#30363d] bg-[#1c232b] px-[9px] py-[7px] text-[10px] text-[#f0f6fc] hover:border-[#5d5b8f]"
                onClick={() => setIsBranchMenuOpen((open) => !open)}
                aria-expanded={isBranchMenuOpen}
                aria-haspopup="listbox"
              >
                <GitBranch size={15} className="text-[#8b949e]" />
                {branch?.branchName ?? "Select branch"}
                <ChevronDown
                  size={14}
                  className={isBranchMenuOpen ? "rotate-180" : ""}
                />
              </button>
              {isBranchMenuOpen && (
                <div
                  className="absolute left-0 top-full z-10 mt-1 min-w-full overflow-hidden rounded-[5px] border border-[#30363d] bg-[#161b22] p-1 shadow-[0_8px_24px_rgba(0,0,0,0.35)]"
                  role="listbox"
                  aria-label="Branches"
                >
                  {repository?.branches?.map((item) => {
                    const isSelected = item.branchName === branch?.branchName;

                    return (
                      <button
                        type="button"
                        className={`block w-full whitespace-nowrap rounded-[3px] px-2.5 py-1.5 text-left text-[10px] ${isSelected ? "bg-[#29253b] text-[#d6d0ff]" : "text-[#8b949e] hover:bg-[#1c232b] hover:text-[#f0f6fc]"}`}
                        key={item.branchName}
                        onClick={() => {
                          onBranchSelect(item.branchName);
                          setIsBranchMenuOpen(false);
                        }}
                        role="option"
                        aria-selected={isSelected}
                      >
                        {item.branchName}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            <div className="flex gap-2">
              <Button onClick={() => setIsAddingFile((adding) => !adding)}>
                <Plus size={15} />
                Add file <ChevronDown size={14} />
              </Button>
              <Button primary onClick={onAI}>
                <Sparkles size={15} />
                AI commit
              </Button>
            </div>
          </div>
          {isAddingFile && (
            <section className="mb-[18px] grid gap-3 rounded-[7px] border border-[#30363d] bg-[#161b22c2] p-4">
              <div className="flex gap-2">
                <input
                  className="min-w-0 flex-1 rounded-[5px] border border-[#30363d] bg-[#11161d] px-3 py-2 text-[11px] text-[#f0f6fc] outline-none placeholder:text-[#6e7681] focus:border-[#8b7cff]"
                  placeholder="File name"
                  value={newFileName}
                  onChange={(event) => setNewFileName(event.target.value)}
                  aria-label="File name"
                />
                <input
                  className="w-24 rounded-[5px] border border-[#30363d] bg-[#11161d] px-3 py-2 text-[11px] text-[#f0f6fc] outline-none placeholder:text-[#6e7681] focus:border-[#8b7cff]"
                  placeholder=".js"
                  value={newFileExtension}
                  onChange={(event) => setNewFileExtension(event.target.value)}
                  aria-label="File extension"
                />
              </div>
              <textarea
                className="min-h-[180px] w-full resize-y rounded-[5px] border border-[#30363d] bg-[#11161d] p-3 font-mono text-[11px] leading-[1.8] text-[#f0f6fc] outline-none placeholder:text-[#6e7681] focus:border-[#8b7cff]"
                placeholder="File content"
                value={newFileContent}
                onChange={(event) => setNewFileContent(event.target.value)}
                aria-label="File content"
              />
              <input
                className="w-full rounded-[5px] border border-[#30363d] bg-[#11161d] px-3 py-2 text-[11px] text-[#f0f6fc] outline-none placeholder:text-[#6e7681] focus:border-[#8b7cff]"
                placeholder="Commit message"
                value={newFileCommitMessage}
                onChange={(event) =>
                  setNewFileCommitMessage(event.target.value)
                }
                aria-label="Commit message"
              />
              <div className="flex justify-end gap-2">
                <Button onClick={() => setIsAddingFile(false)}>Cancel</Button>
                <button
                  type="button"
                  className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[5px] border border-[#7568d7] bg-[#7365d3] px-3 py-2 text-[11px] text-white hover:bg-[#8375e7] disabled:cursor-not-allowed disabled:opacity-50"
                  onClick={addFile}
                  disabled={!newFileName.trim() || !newFileCommitMessage.trim()}
                >
                  <Save size={14} />
                  Add and commit file
                </button>
              </div>
            </section>
          )}
          <section className="overflow-hidden rounded-[7px] border border-[#30363d] bg-[#161b22c2]">
            <div className="flex items-center gap-[7px] border-b border-[#30363d] px-4 py-[13px] text-[10px] text-[#8b949e]">
              <Folder size={15} /> {repository?.repositoryName} <span>/</span>{" "}
              <strong>{branch?.branchName ?? "root"}</strong>
              <span className="ml-auto flex items-center gap-[5px] text-[#3fb950] max-sm:hidden">
                <Check size={13} /> Working tree clean
              </span>
            </div>
            {files.map((file) => {
              return (
                <button
                  className="flex w-full items-center gap-3 border-0 border-b border-[#30363d99] bg-transparent p-[14px_16px] text-left hover:bg-[#1c232b] max-sm:gap-2 max-sm:p-[13px_10px]"
                  key={file.name}
                  onClick={() => selectFile(file)}
                >
                  {/* <FileCode2
                    size={16}
                    className={
                      file.name.endsWith("/")
                        ? "text-[#d8aa4a]"
                        : "text-[#8b949e]"
                    }
                  /> */}
                  <strong className="w-[180px] text-[11px] font-medium max-sm:min-w-[90px] max-sm:w-auto">
                    {file.name}
                  </strong>
                  <span className="flex-1 text-[10px] text-[#8b949e] max-sm:hidden">
                    {file.commit}
                  </span>
                  <small className="text-[10px] text-[#6e7681] max-sm:hidden">
                    {file.time}
                  </small>
                  <ChevronDown
                    size={14}
                    className="-rotate-90 text-[#6e7681]"
                  />
                </button>
              );
            })}
          </section>
          {selectedFile && (
            <section className="mt-[18px] overflow-hidden rounded-[7px] border border-[#30363d] bg-[#161b22c2]">
              <div className="flex flex-wrap items-center gap-2 border-b border-[#30363d] px-[17px] py-[13px] text-[11px] text-[#8b949e]">
                <FileCode2 size={16} />
                <strong className="text-[#f0f6fc]">{selectedFile.name}</strong>
                {!isEditingFile && (
                  <>
                    <span className="ml-auto text-[10px] text-[#6e7681]">
                      {selectedFile.commit}
                    </span>
                    <Button
                      onClick={() => {
                        setEditedContent(selectedFile.content ?? "");
                        setIsEditingFile(true);
                      }}
                    >
                      <Pencil size={13} />
                      Edit
                    </Button>
                  </>
                )}
              </div>
              {isEditingFile ? (
                <div className="grid gap-3 bg-[#0d1117] p-4">
                  <textarea
                    className="min-h-[220px] w-full resize-y rounded-[5px] border border-[#30363d] bg-[#11161d] p-3 font-mono text-[11px] leading-[1.8] text-[#f0f6fc] outline-none focus:border-[#8b7cff]"
                    value={editedContent}
                    onChange={(event) => setEditedContent(event.target.value)}
                    aria-label={`Edit ${selectedFile.name}`}
                  />
                  <input
                    className="w-full rounded-[5px] border border-[#30363d] bg-[#11161d] px-3 py-2 text-[11px] text-[#f0f6fc] outline-none placeholder:text-[#6e7681] focus:border-[#8b7cff]"
                    placeholder="Commit message"
                    value={commitMessage}
                    onChange={(event) => setCommitMessage(event.target.value)}
                    aria-label="Commit message"
                  />
                  <div className="flex justify-end gap-2">
                    <Button
                      onClick={() => {
                        setIsEditingFile(false);
                        setEditedContent(selectedFile.content ?? "");
                        setCommitMessage("");
                      }}
                    >
                      Cancel
                    </Button>
                    <button
                      className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[5px] border border-[#7568d7] bg-[#7365d3] px-3 py-2 text-[11px] text-white hover:bg-[#8375e7] disabled:cursor-not-allowed disabled:opacity-50"
                      onClick={commitFile}
                      disabled={!commitMessage.trim()}
                    >
                      <Save size={14} />
                      Commit changes
                    </button>
                  </div>
                </div>
              ) : (
                <pre className="m-0 overflow-auto bg-[#0d1117] p-5 text-[11px] leading-[1.8] text-[#c9d1d9]">
                  <code>
                    {selectedFile.content || "This file has no content."}
                  </code>
                </pre>
              )}
            </section>
          )}
          {/* <section className="mt-[18px] overflow-hidden rounded-[7px] border border-[#30363d] bg-[#161b22c2]">
            <div className="flex items-center gap-2 border-b border-[#30363d] px-[17px] py-[13px] text-[11px] text-[#8b949e]">
              <BookOpen size={16} />
              README.md{" "}
              <span className="ml-auto text-[10px] text-[#6e7681]">
                Preview
              </span>
            </div>
            <div className="max-w-[750px] px-5 py-6 sm:p-[30px_40px_38px]">
              <h2 className="m-0 mb-2.5 text-[25px]">
                <span className="text-[#9d90fa]">#</span> AIVCS
              </h2>
              <p className="text-[13px] text-[#8b949e]">
                AI-native version control system.
              </p>
              <hr className="my-[26px] border-0 border-t border-[#30363d]" />
              <h3 className="my-[24px_15px] text-base">
                <span className="text-[#9d90fa]">#</span># Features
              </h3>
              <ul className="grid list-none grid-cols-2 gap-[9px] p-0 text-xs text-[#8b949e] max-sm:grid-cols-1">
                <li>
                  <Sparkles className="text-[#b09eff]" size={14} />
                  AI-generated commits
                </li>
                <li>
                  <Zap className="text-[#b09eff]" size={14} />
                  Intelligent diffs
                </li>
                <li>
                  <Layers3 className="text-[#b09eff]" size={14} />
                  Semantic history
                </li>
                <li>
                  <Code2 className="text-[#b09eff]" size={14} />
                  Developer-first workflow
                </li>
              </ul>
              <h3 className="my-[24px_15px] text-base">
                <span className="text-[#9d90fa]">#</span># Installation
              </h3>
              <pre className="overflow-auto rounded-[5px] border border-[#30363d] bg-[#0d1117] p-[15px]">
                <code className="font-mono text-[11px] leading-[1.8] text-[#c9d1d9]">
                  <span className="text-[#79c0ff]">$</span> git clone
                  https://aivcs.dev/{userData.username}/
                  {repository?.repositoryName}
                  {`\n`}
                  <span className="text-[#79c0ff]">$</span> cd{" "}
                  {repository?.repositoryName}
                  {`\n`}
                  <span className="text-[#9d90fa]">#</span>{" "}
                  {readme?.content ?? repository?.repositoryName}
                  <span className="text-[#79c0ff]">$</span> pip install -r
                  requirements.txt
                </code>
              </pre>
            </div>
          </section> */}
        </>
      )}
    </>
  );
}
