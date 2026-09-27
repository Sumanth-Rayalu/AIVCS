import { useState } from "react";
import { Button } from "./Button";
import { Modal } from "./Modal";

export function RepositoryModal({ onClose, onCreate }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

  const submitRepository = (event) => {
    event.preventDefault();
    const result = onCreate(name.trim(), description.trim());
    if (result) {
      setError(result);
      return;
    }
    onClose();
  };

  return (
    <Modal
      onClose={onClose}
      title="Create a new repository"
      subtitle="A home for your code, ideas, and AI-assisted history."
    >
      <form className="grid gap-[17px]" onSubmit={submitRepository}>
        <label className="grid gap-[7px] text-[10px] text-[#8b949e]">
          Repository name
          <input
            autoFocus
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="w-full rounded border border-[#30363d] bg-[#11161d] p-[9px] text-[11px] text-[#f0f6fc] outline-none"
            placeholder="Repository name"
          />
        </label>
        <label className="grid gap-[7px] text-[10px] text-[#8b949e]">
          Description <span className="text-[#6e7681]">(optional)</span>
          <input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="w-full rounded border border-[#30363d] bg-[#11161d] p-[9px] text-[11px] text-[#f0f6fc] outline-none"
            placeholder="What is this repository about?"
          />
        </label>
        {error && (
          <p role="alert" className="m-0 text-[10px] text-[#ff7b72]">
            {error}
          </p>
        )}
        <Button primary>Create repository</Button>
      </form>
    </Modal>
  );
}
