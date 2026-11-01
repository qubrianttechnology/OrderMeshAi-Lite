"use client";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api } from "../lib/api";
import type { Draft, ServiceFields } from "../lib/types";
import { Field, Badge } from "./ui";

export function RequestReview({
  draft,
  org,
  onSaved,
  onBusy,
  readOnly = false,
}: {
  draft: Draft;
  org: string;
  onSaved: (message: string) => Promise<void>;
  onBusy?: (busy: boolean) => void;
  readOnly?: boolean;
}) {
  const initial = draft.result.review?.fields || draft.result.service_request!;
  const [fields, setFields] = useState<ServiceFields>(initial);
  const [requirements, setRequirements] = useState(
    initial.requirements.join("\n"),
  );
  const [notes, setNotes] = useState(draft.result.review?.notes || "");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const status = draft.result.review?.status || "pending_review";
  const closed = ["completed", "rejected"].includes(status);
  async function save(next: string) {
    setBusy(true);
    onBusy?.(true);
    setError("");
    try {
      await api(`/service-requests/${draft.id}/review`, org, {
        method: "PUT",
        body: JSON.stringify({
          revision: draft.result.review?.revision || 0,
          status: next,
          fields: {
            ...fields,
            requirements: requirements
              .split("\n")
              .map((v) => v.trim())
              .filter(Boolean),
          },
          notes,
          human_confirmed: confirmed,
        }),
      });
      await onSaved(
        "Service request saved. No appointment, invoice or order was created.",
      );
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
      onBusy?.(false);
    }
  }
  return (
    <div className="modal-body">
      <Badge kind="mint">{status.replaceAll("_", " ")}</Badge>
      <p className="small muted">
        Provider: {draft.result.provider}. Relative dates stay as written;
        confirm the date, time zone and budget with the customer.
      </p>
      <details open>
        <summary>Original customer message</summary>
        <pre style={{ whiteSpace: "pre-wrap" }}>{draft.source_text}</pre>
      </details>
      <p className="small muted">
        {draft.result.flags.map((v) => v.replaceAll("_", " ")).join(" / ")}
      </p>
      {!!draft.result.missing_fields?.length && (
        <p className="info-note">
          Not stated in message: {draft.result.missing_fields.join(", ")}. Ask
          the customer if needed.
        </p>
      )}
      <fieldset
        disabled={readOnly || closed || busy}
        style={{ border: 0, padding: 0 }}
      >
        <Field label="Request type">
          <select
            value={fields.request_type}
            onChange={(e) =>
              setFields({
                ...fields,
                request_type: e.target.value as ServiceFields["request_type"],
              })
            }
          >
            {["project", "quotation", "appointment", "support", "service"].map(
              (v) => (
                <option key={v}>{v}</option>
              ),
            )}
          </select>
        </Field>
        <Field label="Requirements (one per line)">
          <textarea
            rows={5}
            maxLength={10000}
            value={requirements}
            onChange={(e) => setRequirements(e.target.value)}
          />
        </Field>
        {(["budget", "deadline", "appointment", "contact"] as const).map(
          (key) => (
            <Field key={key} label={key[0].toUpperCase() + key.slice(1)}>
              <input
                maxLength={500}
                value={fields[key] || ""}
                placeholder="Not stated - confirm with customer"
                onChange={(e) =>
                  setFields({ ...fields, [key]: e.target.value || null })
                }
              />
            </Field>
          ),
        )}
        <Field label="Team notes">
          <textarea
            rows={3}
            maxLength={3000}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </Field>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
          I reviewed the message, requirements, budget and dates.
        </label>
        <div className="heading-actions" style={{ marginTop: 16 }}>
          <button
            type="button"
            className="button primary"
            disabled={!confirmed || busy}
            onClick={() => void save("accepted")}
          >
            {status === "accepted" ? "Save changes" : "Accept request"}
          </button>
          {status === "accepted" && (
            <button
              type="button"
              className="button secondary"
              disabled={!confirmed || busy}
              onClick={() => void save("completed")}
            >
              Mark completed
            </button>
          )}
          <button
            type="button"
            className="button secondary"
            disabled={!confirmed || busy}
            onClick={() => void save("rejected")}
          >
            Reject request
          </button>
        </div>
      </fieldset>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export default function ServiceRequests({
  org,
  allowed,
}: {
  org: string;
  allowed: boolean;
}) {
  const [rows, setRows] = useState<Draft[]>([]);
  const [selected, setSelected] = useState<Draft | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const load = useCallback(async () => {
    try {
      setRows(
        await api<Draft[]>(`/service-requests?limit=50&offset=${offset}`, org),
      );
      setError("");
    } catch (cause) {
      setError((cause as Error).message);
    }
  }, [org, offset]);
  useEffect(() => {
    void load();
  }, [load]);
  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const draft = await api<Draft>("/service-requests", org, {
        method: "POST",
        body: JSON.stringify({ text, language: "auto" }),
      });
      setSelected(draft);
      setText("");
      await load();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="settings-grid">
      <section className="panel padded">
        <h2>Service request inbox</h2>
        <p>
          Review project inquiries, quotations, appointments and support
          requests. Accepting a request does not book a calendar slot or send a
          quote.
        </p>
        <button className="button secondary" onClick={() => void load()}>
          Refresh requests
        </button>
        {allowed && (
          <form onSubmit={create} style={{ marginTop: 20 }}>
            <Field label="Customer service message">
              <textarea
                rows={5}
                required
                maxLength={10000}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="We need a website with online booking. Budget: LKR 150,000. Deadline: 30 November."
              />
            </Field>
            <p className="small muted">
              If OpenAI is configured, this message and business type are sent
              for extraction. Business documents stay local. Local fallback is
              identified on each draft.
            </p>
            <button className="button primary" disabled={busy}>
              {busy ? "Extracting..." : "Extract service request"}
            </button>
          </form>
        )}
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        <div className="extraction-list">
          {rows.map((d) => (
            <div key={d.id}>
              <strong>
                {d.result.review?.fields?.request_type ||
                  d.result.service_request?.request_type}
              </strong>
              <p>{d.source_text.slice(0, 180)}</p>
              <Badge kind="neutral">
                {d.result.review?.status.replaceAll("_", " ")}
              </Badge>
              <button
                className="button secondary"
                onClick={() => setSelected(d)}
              >
                Review request
              </button>
            </div>
          ))}
        </div>
        {!rows.length && (
          <p>
            No service requests on this page yet. Eligible WhatsApp inquiries
            will appear here after processing.
          </p>
        )}
        <div className="heading-actions">
          <button
            className="button secondary"
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - 50))}
          >
            Previous
          </button>
          <button
            className="button secondary"
            disabled={rows.length < 50}
            onClick={() => setOffset(offset + 50)}
          >
            Next
          </button>
        </div>
      </section>
      {selected && (
        <section className="panel padded">
          <h2>Review service request</h2>
          <RequestReview
            key={selected.id + ":" + selected.result.review?.revision}
            org={org}
            draft={selected}
            readOnly={!allowed}
            onSaved={async () => {
              setSelected(await api<Draft>(`/extractions/${selected.id}`, org));
              await load();
            }}
          />
        </section>
      )}
    </div>
  );
}
