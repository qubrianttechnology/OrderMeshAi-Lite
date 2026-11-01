"use client";
import { useState } from "react";
import { api } from "../lib/api";
export default function BusinessFilterPreview({ org }: { org: string }) {
  const [text, setText] = useState("");
  const [result, setResult] = useState<{
    category: string;
    reason: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <section className="panel padded">
      <h2>Test message filtering</h2>
      <p className="muted">
        Try a sample against your saved business profile. This preview does not
        create an inbox message, order or reply.
      </p>
      <form
        className="profile-form"
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setError("");
          setResult(null);
          try {
            setResult(
              await api("/business-profile/classify-preview", org, {
                method: "POST",
                body: JSON.stringify({ text }),
              }),
            );
          } catch (cause) {
            setError((cause as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label className="field">
          Sample WhatsApp message
          <textarea
            required
            maxLength={10000}
            value={text}
            rows={3}
            onChange={(event) => {
              setText(event.target.value);
              setResult(null);
            }}
          />
        </label>
        <button className="button primary" disabled={busy || !text.trim()}>
          {busy ? "Checking..." : "Preview classification"}
        </button>
      </form>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {result && (
        <div role="status" className="info-note">
          <strong>{result.category.replaceAll("_", " ")}</strong>
          <p>{result.reason}</p>
        </div>
      )}
      <p className="small muted">
        Private, spam and uncertain messages remain available in the inbox
        category filter. A team member can correct a category. Example matching
        is a local rule, not a guarantee of AI understanding.
      </p>
    </section>
  );
}
