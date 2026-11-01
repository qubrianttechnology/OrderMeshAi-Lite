"use client";
import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Mail,
  Phone,
  ShieldCheck,
  ClipboardList,
  CheckCircle2,
} from "lucide-react";
import { api } from "../lib/api";
import { Brand, Badge, Field } from "./ui";
export default function Auth({
  onLogin,
  mode = "sign-in",
}: {
  onLogin: () => Promise<void>;
  mode?: "sign-in" | "sign-up";
}) {
  const register = mode === "sign-up";
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [googleSetup, setGoogleSetup] = useState(false);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setGoogleSetup(register && params.get("google") === "1");
    const errors: Record<string, string> = {
      google_not_configured: "Google sign-in is not configured yet.",
      invalid_oauth_state:
        "Your Google sign-in session expired. Please try again.",
      google_cancelled: "Google sign-in was cancelled.",
      google_verification_failed:
        "We could not verify your Google account. Please try again.",
      google_account_not_found:
        "No OrderMesh account uses this Google email. Create a workspace first.",
      google_account_conflict:
        "This email is linked to a different Google account. Use email and password instead.",
    };
    const message = errors[params.get("oauth_error") || ""];
    if (message) setError(message);
  }, [register]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await api(
        googleSetup
          ? "/auth/google/complete-registration"
          : `/auth/${register ? "register" : "login"}`,
        undefined,
        {
          method: "POST",
          body: JSON.stringify(data),
        },
      );
      await onLogin();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-shell">
      <section className="auth-story">
        <Link href="/" aria-label="OrderMesh home">
          <Brand />
        </Link>
        <div>
          <Badge kind="mint">FOR WHOLESALERS AND DISTRIBUTORS</Badge>
          <h1>
            Less paperwork.
            <br />
            More possibility.
          </h1>
          <p>
            Your conversations, orders and services.
            <br />
            One connected workspace.
          </p>
          <div className="auth-illustration">
            <div className="mock-order">
              <span className="icon-tile">
                <ClipboardList />
              </span>
              <div>
                <strong>From conversation to action</strong>
                <p>Extract. Review. Confirm.</p>
              </div>
              <CheckCircle2 className="green" />
            </div>
            <div className="connection-line" />
            <div className="mock-order smaller">
              <ShieldCheck />
              <span>You stay in control.</span>
            </div>
          </div>
        </div>
        <footer>
          QUBRIANT TECHNOLOGIES{" "}
          <span>Thoughtfully built. Locally focused.</span>
        </footer>
      </section>
      <section className="auth-form">
        <div>
          <Link href="/" className="auth-home">
            ← Back to OrderMesh
          </Link>
          <span className="eyebrow">YOUR OPERATIONS, CONNECTED</span>
          <h2>
            {googleSetup
              ? "Complete your workspace"
              : register
                ? "Create your workspace"
                : "Welcome back"}
          </h2>
          <p>
            {googleSetup
              ? "Add your business name to finish Google sign-in."
              : register
                ? "Create a private wholesale or distribution workspace."
                : "Sign in to your OrderMesh workspace."}
          </p>
          <form onSubmit={submit}>
            {register && !googleSetup && (
              <>
                <Field label="Your name">
                  <input
                    name="name"
                    autoComplete="name"
                    required
                    maxLength={120}
                  />
                </Field>
                <Field label="Business name">
                  <input
                    name="organization_name"
                    autoComplete="organization"
                    required
                    maxLength={120}
                  />
                </Field>
              </>
            )}
            {googleSetup && (
              <Field label="Business name">
                <input
                  name="organization_name"
                  autoComplete="organization"
                  required
                  maxLength={120}
                />
              </Field>
            )}
            {!googleSetup && (
              <Field label="Email address">
                <input
                  name="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@yourbusiness.lk"
                  required
                />
              </Field>
            )}
            {!googleSetup && (
              <Field label="Password">
                <input
                  name="password"
                  type="password"
                  minLength={register ? 12 : 1}
                  maxLength={128}
                  autoComplete={register ? "new-password" : "current-password"}
                  required
                />
                {register && <small>Use at least 12 characters.</small>}
              </Field>
            )}
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <button className="button primary full" disabled={busy}>
              {busy
                ? "Please wait…"
                : googleSetup
                  ? "Create workspace"
                  : register
                    ? "Create workspace"
                    : "Sign in"}
              <ArrowRight size={17} />
            </button>
          </form>
          {!googleSetup && (
            <>
              <div className="oauth-divider">or</div>
              <a
                className="google-sign-in"
                href={`/api/auth/google/start?intent=${register ? "sign-up" : "sign-in"}`}
              >
                <span aria-hidden="true">G</span> Continue with Google
              </a>
            </>
          )}
          <p className="auth-switch">
            {register ? "Already have a workspace?" : "New to OrderMesh?"}{" "}
            <Link href={register ? "/sign-in" : "/sign-up"}>
              {register ? "Sign in" : "Create an account"}
            </Link>
          </p>
          <div className="secure-note">
            <ShieldCheck size={16} /> Secure sessions · Private organization
            data
          </div>
          <div className="auth-support">
            <span>Need a hand?</span>
            <a href="tel:+94722616616">
              <Phone size={14} />
              0722 616 616
            </a>
            <a href="mailto:info@ordermesh.com">
              <Mail size={14} />
              info@ordermesh.com
            </a>
          </div>
        </div>
      </section>
    </main>
  );
}
