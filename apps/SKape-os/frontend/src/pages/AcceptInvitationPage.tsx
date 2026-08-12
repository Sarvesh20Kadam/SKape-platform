import {
    useMemo,
    useState,
    type FormEvent,
  } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  LockKeyhole,
  Mail,
  UserRound,
} from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { acceptInvitation } from "../features/organization/services/organization.service";

function AcceptInvitationPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const token = useMemo(
    () => searchParams.get("token")?.trim() || "",
    [searchParams],
  );

  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] =
    useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] =
    useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();

    setError(null);

    if (!token) {
      setError(
        "This invitation link is invalid or incomplete.",
      );
      return;
    }

    const trimmedName = name.trim();

    if (!trimmedName) {
      setError("Please enter your name.");
      return;
    }

    if (password.length < 8) {
      setError(
        "Password must contain at least 8 characters.",
      );
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      setLoading(true);

      await acceptInvitation({
        token,
        name: trimmedName,
        password,
      });

      setSuccess(true);
    } catch (err: any) {
      console.error(
        "Failed to accept invitation:",
        err,
      );

      const detail =
        err?.response?.data?.detail;

      setError(
        detail ||
          "Unable to accept this invitation. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-zinc-950 px-4 text-zinc-100">
        <div className="mx-auto flex min-h-screen w-full max-w-md items-center justify-center">
          <div className="w-full rounded-2xl border border-zinc-800 bg-zinc-900/50 p-8 text-center shadow-2xl">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-emerald-500/20 bg-emerald-500/10">
              <CheckCircle2
                size={26}
                className="text-emerald-400"
              />
            </div>

            <h1 className="mt-6 text-2xl font-semibold tracking-tight">
              Invitation accepted
            </h1>

            <p className="mt-3 text-sm leading-6 text-zinc-500">
              Your SKape account has been created
              successfully. You can now sign in to
              your workspace.
            </p>

            <button
              type="button"
              onClick={() => navigate("/login")}
              className="mt-7 h-11 w-full rounded-lg bg-emerald-500 px-4 text-sm font-semibold text-zinc-950 transition hover:bg-emerald-400"
            >
              Continue to login
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 px-4 text-zinc-100">
      <div className="mx-auto flex min-h-screen w-full max-w-md items-center justify-center py-10">
        <div className="w-full">
          <div className="mb-8 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-900">
              <LockKeyhole
                size={20}
                className="text-emerald-400"
              />
            </div>

            <p className="mt-5 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-400">
              SKape Workspace
            </p>

            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-100">
              Accept invitation
            </h1>

            <p className="mt-2 text-sm leading-6 text-zinc-500">
              Create your account to join the
              organization.
            </p>
          </div>

          <form
            onSubmit={handleSubmit}
            className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 shadow-2xl"
          >
            {!token && (
              <div className="mb-5 flex gap-3 rounded-lg border border-red-500/20 bg-red-500/5 p-3.5 text-sm text-red-400">
                <AlertCircle
                  size={17}
                  className="mt-0.5 shrink-0"
                />

                <p>
                  This invitation link is invalid.
                  Please request a new invitation.
                </p>
              </div>
            )}

            {error && (
              <div className="mb-5 flex gap-3 rounded-lg border border-red-500/20 bg-red-500/5 p-3.5 text-sm text-red-400">
                <AlertCircle
                  size={17}
                  className="mt-0.5 shrink-0"
                />

                <p>{error}</p>
              </div>
            )}

            <div className="space-y-5">
              <div>
                <label
                  htmlFor="name"
                  className="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-zinc-500"
                >
                  Full name
                </label>

                <div className="relative">
                  <UserRound
                    size={16}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600"
                  />

                  <input
                    id="name"
                    type="text"
                    autoComplete="name"
                    value={name}
                    onChange={(event) =>
                      setName(event.target.value)
                    }
                    placeholder="Your name"
                    disabled={loading || !token}
                    className="h-11 w-full rounded-lg border border-zinc-800 bg-zinc-950 pl-10 pr-3 text-sm text-zinc-200 outline-none transition placeholder:text-zinc-700 focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/10 disabled:opacity-50"
                  />
                </div>
              </div>

              <div>
                <label
                  htmlFor="password"
                  className="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-zinc-500"
                >
                  Password
                </label>

                <div className="relative">
                  <LockKeyhole
                    size={16}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600"
                  />

                  <input
                    id="password"
                    type="password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(event) =>
                      setPassword(event.target.value)
                    }
                    placeholder="Minimum 8 characters"
                    disabled={loading || !token}
                    className="h-11 w-full rounded-lg border border-zinc-800 bg-zinc-950 pl-10 pr-3 text-sm text-zinc-200 outline-none transition placeholder:text-zinc-700 focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/10 disabled:opacity-50"
                  />
                </div>
              </div>

              <div>
                <label
                  htmlFor="confirm-password"
                  className="mb-2 block text-xs font-semibold uppercase tracking-[0.12em] text-zinc-500"
                >
                  Confirm password
                </label>

                <div className="relative">
                  <LockKeyhole
                    size={16}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600"
                  />

                  <input
                    id="confirm-password"
                    type="password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(event) =>
                      setConfirmPassword(
                        event.target.value,
                      )
                    }
                    placeholder="Repeat your password"
                    disabled={loading || !token}
                    className="h-11 w-full rounded-lg border border-zinc-800 bg-zinc-950 pl-10 pr-3 text-sm text-zinc-200 outline-none transition placeholder:text-zinc-700 focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/10 disabled:opacity-50"
                  />
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !token}
              className="mt-6 flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 text-sm font-semibold text-zinc-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading && (
                <Loader2
                  size={16}
                  className="animate-spin"
                />
              )}

              {loading
                ? "Creating account..."
                : "Accept invitation"}
            </button>

            <div className="mt-5 flex items-center justify-center gap-2 text-xs text-zinc-600">
              <Mail size={13} />

              <span>
                Already have an account?
              </span>

              <Link
                to="/login"
                className="text-zinc-400 transition hover:text-zinc-200"
              >
                Sign in
              </Link>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default AcceptInvitationPage;