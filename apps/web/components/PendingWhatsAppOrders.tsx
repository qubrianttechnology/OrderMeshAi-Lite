"use client";
import { useState } from "react";
import { api, date } from "../lib/api";
import type { Draft, PendingWhatsAppOrder } from "../lib/types";

export default function PendingWhatsAppOrders({
  org,
  rows,
  canApprove,
  onReview,
  onChanged,
}: {
  org: string;
  rows: PendingWhatsAppOrder[];
  canApprove: boolean;
  onReview: (draft: Draft) => void;
  onChanged: () => Promise<void>;
}) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  if (!rows.length) return null;
  return (
    <section
      className="panel padded"
      aria-label="WhatsApp orders awaiting approval"
    >
      <span className="eyebrow">OWNER REVIEW</span>
      <h2>
        Awaiting owner approval{" "}
        <span className="light-count">{rows.length}</span>
      </h2>
      <p className="muted">
        These WhatsApp requests have not changed stock. Review the customer,
        selling unit, prices and quantities before confirming. Availability can
        change until approval.
      </p>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {rows.map((row) => (
        <article className="panel padded" key={row.draft.id}>
          <strong>{row.customer_name || row.customer_phone}</strong>
          {row.is_simulated && (
            <p className="muted small">
              Simulator request - no WhatsApp reply will be sent.
            </p>
          )}
          <p className="muted small">
            {row.customer_phone} - {date(row.created_at)}
          </p>
          <p style={{ whiteSpace: "pre-wrap" }}>{row.draft.source_text}</p>
          <ul>
            {row.availability.map((item, index) => (
              <li key={index}>
                {item.product_name}
                {item.quantity != null &&
                  ` - ${item.quantity} ${item.unit || ""}`}{" "}
                - <strong>{item.status.replaceAll("_", " ")}</strong>
              </li>
            ))}
          </ul>
          {canApprove ? (
            <div className="row-actions">
              <button className="button" onClick={() => onReview(row.draft)}>
                Review and approve
              </button>
              <button
                className="button-secondary"
                disabled={busy === row.draft.id}
                onClick={async () => {
                  if (
                    !window.confirm(
                      "Reject this WhatsApp order request? Stock will stay unchanged.",
                    )
                  )
                    return;
                  setBusy(row.draft.id);
                  setError("");
                  try {
                    await api(
                      `/inbox/order-requests/${row.draft.id}/reject`,
                      org,
                      { method: "POST" },
                    );
                    await onChanged();
                  } catch (cause) {
                    setError((cause as Error).message);
                  } finally {
                    setBusy("");
                  }
                }}
              >
                Reject request
              </button>
            </div>
          ) : (
            <p className="muted small">
              An owner or admin must approve this request.
            </p>
          )}
        </article>
      ))}
    </section>
  );
}
