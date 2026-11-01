"use client";
import { useEffect, useState, type FormEvent } from "react";
import { api, date, money } from "../lib/api";
import BusinessQuestionnaire, { profileFields } from "./BusinessQuestionnaire";

type Profile = {
  business_type: string;
  ready: boolean;
  document_suggestions?: Record<string, string>;
  profile: Record<string, string>;
};
type Billing = {
  amount_minor: number;
  trial_days: number;
  trial_ends_at: string | null;
  paid_until: string | null;
  status: string;
  checkout_available: boolean;
  sandbox: boolean;
  can_cancel: boolean;
  has_access: boolean;
};

export default function WorkspaceSetup({
  org,
  canManage,
  owner,
  onChanged,
  showBilling = true,
}: {
  org: string;
  canManage: boolean;
  owner: boolean;
  onChanged: () => Promise<void>;
  showBilling?: boolean;
}) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [billing, setBilling] = useState<Billing | null>(null);
  const [useSuggestions, setUseSuggestions] = useState(false);
  const [documentRevision, setDocumentRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let active = true;
    Promise.all([
      api<Profile>("/business-profile", org),
      showBilling ? api<Billing>("/billing", org) : Promise.resolve(null),
    ])
      .then(([p, b]) => {
        if (active) {
          setProfile(p);
          setBilling(b);
        }
      })
      .catch((e) => {
        if (active) setError((e as Error).message);
      });
    return () => {
      active = false;
    };
  }, [org, showBilling]);
  async function save(data: Record<string, string>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      setProfile(
        await api<Profile>("/business-profile", org, {
          method: "PUT",
          body: JSON.stringify(data),
        }),
      );
      setUseSuggestions(false);
      await onChanged();
      setNotice(
        "Business profile saved. Your dashboard and message routing now use this context.",
      );
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function upload(file: File) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (file.size > 2_000_000)
        throw new Error("Choose a document smaller than 2 MB.");
      setProfile(
        await api<Profile>("/business-profile/document", org, {
          method: "POST",
          headers: {
            "Content-Type": file.type || "application/octet-stream",
            "X-Filename": encodeURIComponent(file.name),
          },
          body: file,
        }),
      );
      setUseSuggestions(false);
      setDocumentRevision((value) => value + 1);
      setNotice("Document saved. Review and complete your business answers.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function downloadTemplate() {
    try {
      const result = await api<{ text: string }>(
        "/business-profile/document-template",
        org,
      );
      const url = URL.createObjectURL(
        new Blob([result.text], { type: "text/plain;charset=utf-8" }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = "OrderMesh-business-profile-template.txt";
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function checkout(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const result = await api<{
        action: string;
        fields: Record<string, string>;
      }>("/billing/checkout", org, {
        method: "POST",
        body: JSON.stringify({
          ...fields,
          consent_to_recurring: fields.consent_to_recurring === "on",
        }),
      });
      if (
        ![
          "https://sandbox.payhere.lk/pay/checkout",
          "https://www.payhere.lk/pay/checkout",
        ].includes(result.action)
      )
        throw new Error("Unexpected checkout destination");
      const form = document.createElement("form");
      form.method = "POST";
      form.action = result.action;
      for (const [name, value] of Object.entries(result.fields)) {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = name;
        input.value = value;
        form.appendChild(input);
      }
      document.body.appendChild(form);
      form.submit();
      form.remove();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  async function cancel() {
    if (
      !window.confirm(
        "Cancel future monthly charges? Access remains available until the end of the paid period.",
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      await api("/billing/cancel", org, { method: "POST" });
      setBilling(await api<Billing>("/billing", org));
      await onChanged();
      setNotice(
        "Future charges cancelled. Your paid access remains until its expiry date.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <section className="panel padded business-profile-panel">
        <span className="eyebrow">YOUR BUSINESS, YOUR WORKFLOW</span>
        <h2>Business profile</h2>
        <p className="muted">
          Answer a few questions here to explain your business, customers and
          order process. Your saved answers help organize business messages,
          private conversations and spam. You can edit them whenever your
          business changes.
        </p>
        {error && (
          <div className="alert" role="alert">
            {error}
          </div>
        )}
        {notice && (
          <p className="toast" role="status">
            {notice}
          </p>
        )}
        {profile ? (
          <BusinessQuestionnaire
            key={
              org +
              String(profile.profile.document_name) +
              String(documentRevision) +
              String(useSuggestions)
            }
            initial={{
              business_type: profile.business_type,
              primary_category: profile.profile.primary_category || "other",
              ...Object.fromEntries(
                profileFields.map(([key]) => [
                  key,
                  (useSuggestions
                    ? profile.document_suggestions?.[key]
                    : undefined) ??
                    profile.profile[key] ??
                    "",
                ]),
              ),
            }}
            canManage={canManage}
            busy={busy}
            onSave={save}
          />
        ) : (
          <p role="status">Loading business questions...</p>
        )}
        <details className="business-document-optional">
          <summary>Already have a document? Import it here (optional)</summary>
          <div className="profile-document-actions">
            <button
              type="button"
              className="button"
              onClick={() => void downloadTemplate()}
            >
              Download document template
            </button>
            {canManage && (
              <label className="button">
                Upload business document
                <input
                  type="file"
                  aria-label="Business document"
                  accept=".txt,.md,.pdf,.docx"
                  disabled={busy}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void upload(f);
                  }}
                />
              </label>
            )}
          </div>
          <p className="muted small">
            TXT, Markdown, text PDF or DOCX - up to 2 MB and 20 PDF pages.
            Documents are processed locally. Include offerings, customers,
            workflow, hours, payments, delivery and unrelated-message examples.
            Scanned PDFs need a text layer first; text is read without sending
            the document to an AI provider.
          </p>
          {profile?.profile.document_name && (
            <details>
              <summary>{profile.profile.document_name}</summary>
              <pre className="business-document-preview">
                {profile.profile.document_text}
              </pre>
            </details>
          )}
          {!!Object.keys(profile?.document_suggestions || {}).length && (
            <div className="info-note">
              <p>
                Document sections were recognized. Review suggestions in the
                form, then save to apply them.
              </p>
              {canManage && (
                <button
                  type="button"
                  className="button"
                  disabled={busy}
                  onClick={() => setUseSuggestions(true)}
                >
                  Review document suggestions
                </button>
              )}
            </div>
          )}
        </details>
      </section>
      {showBilling && (
        <section className="panel padded subscription-panel">
          <span className="eyebrow">ONE SIMPLE MONTHLY PLAN</span>
          <h2>OrderMesh AI Lite</h2>
          <p className="subscription-price">
            {money(740000)}
            <small> / month</small>
          </p>
          <p>15-day free trial - no card required to start</p>
          {billing && (
            <dl>
              <dt>Subscription</dt>
              <dd>{billing.status}</dd>
              <dt>Trial ends</dt>
              <dd>
                {billing.trial_ends_at ? date(billing.trial_ends_at) : "?"}
              </dd>
              <dt>Paid access until</dt>
              <dd>{billing.paid_until ? date(billing.paid_until) : "?"}</dd>
            </dl>
          )}
          {billing?.can_cancel && owner ? (
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={() => void cancel()}
            >
              Cancel future payments
            </button>
          ) : billing?.checkout_available && owner ? (
            <form onSubmit={checkout} className="profile-form">
              {(
                [
                  ["first_name", "First name"],
                  ["last_name", "Last name"],
                  ["phone", "Billing phone"],
                  ["address", "Billing address"],
                  ["city", "Billing city"],
                ] as const
              ).map(([key, label]) => (
                <label className="field" key={key}>
                  {label}
                  <input
                    name={key}
                    required
                    maxLength={key === "address" ? 300 : 80}
                  />
                </label>
              ))}
              <label className="checkbox">
                <input type="checkbox" name="consent_to_recurring" required />I
                authorize LKR 7,400 now and every month until cancelled.
              </label>
              <button className="button primary" disabled={busy}>
                {busy
                  ? "Opening checkout..."
                  : billing.sandbox
                    ? "Continue to PayHere sandbox"
                    : "Subscribe with PayHere"}
              </button>
              <p className="muted small">
                Subscribing charges the first month immediately. Access updates
                after PayHere confirms the payment.
              </p>
            </form>
          ) : (
            <p className="info-note">
              {owner
                ? "Subscription payments are being configured. Your trial is available until its expiry date."
                : "Your workspace owner manages subscriptions."}
            </p>
          )}
        </section>
      )}
    </>
  );
}
