import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, GitBranch, LockKeyhole, Mail } from "lucide-react";

export function AuthPage({ mode, onLogin, onRegister, initialError = "" }) {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(initialError);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isRegistering = mode === "register";
  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      const result = isRegistering
        ? await onRegister({ username, email, password })
        : await onLogin({ email, password });
      if (result) setError(result);
    } catch (requestError) {
      setError(requestError.message || "Authentication failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="relative grid min-h-screen overflow-hidden bg-[#0d1117] text-[#f0f6fc] lg:grid-cols-[1fr_440px]">
      <section className="relative flex min-h-[34vh] flex-col justify-between overflow-hidden border-b border-[#30363d] px-7 py-8 sm:px-12 sm:py-10 lg:min-h-screen lg:border-r lg:border-b-0 lg:px-[9vw] lg:py-[9vh]">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_18%_22%,rgba(65,108,125,0.2),transparent_42%),linear-gradient(145deg,#111b20_0%,#0d1117_58%,#151725_100%)]" />
        <div className="relative flex items-center gap-3">
          <span className="grid h-9 w-9 rotate-45 place-content-center rounded-lg border border-[#86c6bd]">
            <GitBranch size={16} className="-rotate-45 text-[#86c6bd]" />
          </span>
          <span className="text-sm font-bold">AIVCS</span>
        </div>
        <div className="relative mt-12 max-w-[520px] lg:mt-0">
          <p className="mb-4 text-[10px] font-semibold uppercase tracking-[2px] text-[#86c6bd]">
            Your development workspace
          </p>
          <h1 className="m-0 max-w-[500px] text-[34px] leading-[1.12] font-semibold sm:text-[46px]">
            Keep your work moving forward.
          </h1>
          <p className="mt-5 max-w-[390px] text-sm leading-6 text-[#9aa7b3]">
            Repositories, branches, and commit history, together in one place.
          </p>
        </div>
        <div className="relative mt-10 flex items-center gap-2 text-[10px] text-[#6e7b85] lg:mt-0">
          <span className="h-1.5 w-1.5 rounded-full bg-[#79c5a7]" />
          Local demo workspace
        </div>
      </section>

      <section className="flex items-center justify-center px-5 py-10 sm:px-10 lg:min-h-screen">
        <div className="w-full max-w-[360px]">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[1.6px] text-[#86c6bd]">
            {isRegistering ? "Create your workspace" : "Welcome back"}
          </p>
          <h2 className="m-0 text-[25px] font-semibold">
            {isRegistering ? "Create an account" : "Sign in to AIVCS"}
          </h2>
          <p className="mt-2 text-xs text-[#8b949e]">
            {isRegistering
              ? "Your repositories will be saved to this account."
              : "Use a demo account or register to get started."}
          </p>

          <form className="mt-7 grid gap-4" onSubmit={submit}>
            {isRegistering && (
              <label className="grid gap-1.5 text-[11px] text-[#c9d1d9]">
                Username
                <input
                  className="h-10 rounded-[5px] border border-[#30363d] bg-[#11161d] px-3 text-xs text-[#f0f6fc] outline-none focus:border-[#86c6bd]"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="username"
                  required
                />
              </label>
            )}
            <label className="grid gap-1.5 text-[11px] text-[#c9d1d9]">
              Email
              <span className="flex h-10 items-center gap-2 rounded-[5px] border border-[#30363d] bg-[#11161d] px-3 focus-within:border-[#86c6bd]">
                <Mail size={15} className="text-[#71808c]" />
                <input
                  className="min-w-0 flex-1 bg-transparent text-xs text-[#f0f6fc] outline-none"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  required
                />
              </span>
            </label>
            <label className="grid gap-1.5 text-[11px] text-[#c9d1d9]">
              Password
              <span className="flex h-10 items-center gap-2 rounded-[5px] border border-[#30363d] bg-[#11161d] px-3 focus-within:border-[#86c6bd]">
                <LockKeyhole size={15} className="text-[#71808c]" />
                <input
                  className="min-w-0 flex-1 bg-transparent text-xs text-[#f0f6fc] outline-none"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete={
                    isRegistering ? "new-password" : "current-password"
                  }
                  minLength={isRegistering ? 6 : undefined}
                  required
                />
              </span>
            </label>

            {error && (
              <p className="m-0 text-[11px] text-[#ff7b72]" role="alert">
                {error}
              </p>
            )}

            <button
              className="mt-1 flex h-10 items-center justify-center gap-2 rounded-[5px] border border-[#628f86] bg-[#47756d] text-xs font-semibold text-white hover:bg-[#54867c]"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting
                ? "Please wait..."
                : isRegistering
                  ? "Create account"
                  : "Sign in"}
              <ArrowRight size={15} />
            </button>
          </form>

          {!isRegistering && (
            <div className="mt-6 border-t border-[#30363d] pt-4 text-[10px] leading-5 text-[#8b949e]">
              <p className="m-0 font-semibold text-[#c9d1d9]">Demo accounts</p>
              <p className="m-0">bob@example.com / bob-password</p>
              <p className="m-0">alice@example.com / alice-password</p>
            </div>
          )}

          <p className="mt-6 text-center text-[11px] text-[#8b949e]">
            {isRegistering ? "Already have an account?" : "New to AIVCS?"}{" "}
            <Link
              className="border-0 bg-transparent p-0 font-semibold text-[#86c6bd] hover:text-[#a1ddd3]"
              to={isRegistering ? "/login" : "/register"}
            >
              {isRegistering ? "Sign in" : "Create an account"}
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
