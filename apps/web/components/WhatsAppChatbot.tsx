"use client";
import { useEffect, useState, type FormEvent } from "react";
import { api, date } from "../lib/api";

type Config = { enabled: boolean; answer_business_questions: boolean };
type Reply = {
  id: string;
  kind: string;
  status: string;
  last_error: string;
  created_at: string;
};

export default function WhatsAppChatbot({ org }: { org: string }) {
  const [config, setConfig] = useState<Config>({
    enabled: false,
    answer_business_questions: true,
  });
  const [replies, setReplies] = useState<Reply[]>([]);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let active = true;
    api<Config>("/inbox/chatbot-settings", org)
      .then((value) => {
        if (active) {
          setConfig({
            enabled: value.enabled,
            answer_business_questions: value.answer_business_questions,
          });
          setReady(true);
        }
      })
      .catch((cause: Error) => {
        if (active) setError(cause.message);
      });
    const load = () =>
      api<Reply[]>("/inbox/chatbot-replies", org)
        .then((rows) => {
          if (active) setReplies(rows);
        })
        .catch((cause: Error) => {
          if (active) setError(cause.message);
        });
    void load();
    const timer = setInterval(() => {
      if (!document.hidden) void load();
    }, 15000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [org]);
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api("/inbox/chatbot-settings", org, {
        method: "PUT",
        body: JSON.stringify(config),
      });
      setNotice(
        config.enabled
          ? "WhatsApp chatbot activated. Owner approval is still required for orders."
          : "WhatsApp chatbot deactivated.",
      );
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel padded">
      <span className="eyebrow">WHATSAPP AUTOMATION</span>
      <h2>Local WhatsApp chatbot</h2>
      <p className="muted">
        Check catalog availability and acknowledge order requests automatically.
        Stock is not reserved or reduced until an owner or admin reviews and
        approves the order. Business replies use saved details; unknown requests
        stay with your team. This mode uses local rules rather than an AI
        conversation model.
      </p>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="toast" role="status">
          {notice}
        </p>
      )}
      <form onSubmit={save}>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={config.enabled}
            disabled={!ready || busy}
            onChange={(event) =>
              setConfig({ ...config, enabled: event.target.checked })
            }
          />
          Activate WhatsApp chatbot
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={config.answer_business_questions}
            disabled={!ready || busy}
            onChange={(event) =>
              setConfig({
                ...config,
                answer_business_questions: event.target.checked,
              })
            }
          />
          Answer greetings, opening hours, delivery and payment questions from
          business details
        </label>
        <p className="muted small">
          Private/spam messages and simulator events do not receive automated
          replies. Replies require a connected number and an open 24-hour
          customer service window. Test mode also requires the recipient
          allowlist. Availability and confirmation replies support Sinhala,
          English and Tamil. Business information uses your saved wording. While
          this chatbot is active, WhatsApp text extraction stays local and
          audio/images require manual review.
        </p>
        <button className="button" disabled={!ready || busy}>
          {busy ? "Saving..." : "Save chatbot settings"}
        </button>
      </form>
      {!!replies.length && (
        <details>
          <summary>Recent bot replies</summary>
          <ul>
            {replies.map((reply) => (
              <li key={reply.id}>
                <strong>{reply.kind.replaceAll("_", " ")}</strong> -{" "}
                {reply.status} - {date(reply.created_at)}
                {reply.last_error && (
                  <p className="muted small">{reply.last_error}</p>
                )}
                {reply.status === "blocked" && (
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      setError("");
                      try {
                        await api(
                          `/inbox/chatbot-replies/${reply.id}/retry`,
                          org,
                          { method: "POST" },
                        );
                        setReplies(
                          await api<Reply[]>("/inbox/chatbot-replies", org),
                        );
                      } catch (cause) {
                        setError((cause as Error).message);
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Retry after fixing the connection or recipient settings
                  </button>
                )}
              </li>
            ))}
          </ul>
          <p className="muted small">
            Accepted means Meta accepted the send request; final delivery is
            shown in the inbox. Unknown delivery is never automatically resent.
          </p>
        </details>
      )}
    </section>
  );
}
