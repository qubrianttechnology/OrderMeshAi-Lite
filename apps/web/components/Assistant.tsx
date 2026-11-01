"use client";
import { useState, useEffect } from "react";
import { Sparkles, WandSparkles, ShieldCheck, ArrowRight } from "lucide-react";
import { api } from "../lib/api";
import type { Draft } from "../lib/types";
import { RequestReview } from "./ServiceRequests";
import { Field, Badge } from "./ui";
import type { Integrations } from "./IntegrationPanel";
export default function Assistant({
  org,
  allowed,
  onReview,
  serviceBusiness = false,
}: {
  org: string;
  allowed: boolean;
  serviceBusiness?: boolean;
  onReview: (d: Draft) => void;
}) {
  const [text, setText] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [draft, setDraft] = useState<Draft | null>(null);
  const [provider, setProvider] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imageEnabled, setImageEnabled] = useState(false);
  const [imagePreview, setImagePreview] = useState("");
  useEffect(() => {
    if (!imageFile) {
      setImagePreview("");
      return;
    }
    const url = URL.createObjectURL(imageFile);
    setImagePreview(url);
    return () => URL.revokeObjectURL(url);
  }, [imageFile]);
  useEffect(() => {
    let active = true;
    api<Integrations>("/integrations", org)
      .then((data) => {
        if (active) {
          setProvider(data.text.provider || "");
          setImageEnabled(data.images?.status === "configured");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [org]);
  return (
    <div className="assistant-layout">
      <section className="panel padded">
        <div className="section-icon">
          <Sparkles />
          <div>
            <h2>Start with a customer message</h2>
            <p>Sinhala, English, Tamil, or a mix</p>
          </div>
        </div>
        <p className="small muted">
          {provider === "openai-structured-v1"
            ? "Configured model: this message and your product catalog will be sent to OpenAI for extraction."
            : provider
              ? "Local rules mode: messages stay within this application."
              : "Checking extraction configuration…"}
        </p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            setDraft(null);
            try {
              setDraft(
                await api<Draft>("/extractions", org, {
                  method: "POST",
                  body: JSON.stringify({ text, language: "auto" }),
                }),
              );
            } catch (err) {
              setError((err as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <Field label={serviceBusiness ? "Service message" : "Order message"}>
            <textarea
              rows={9}
              required
              maxLength={10000}
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                setDraft(null);
              }}
              placeholder={"Rice 10\nසීනි 5\nDhal 3"}
            />
          </Field>
          <p className="muted small">
            {serviceBusiness
              ? "Describe the requested service, requirements, budget, deadline and meeting preferences. Missing values stay blank."
              : "Use one product per line with a numeric quantity. Product names or Sinhala/Tamil aliases must exist in your catalog."}
          </p>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button
            className="button primary"
            disabled={busy || !allowed || !provider}
          >
            <WandSparkles size={17} />
            {busy
              ? "Reading message…"
              : serviceBusiness
                ? "Extract service details"
                : "Extract order details"}
          </button>
        </form>
        <form
          aria-label="Read order image"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!imageFile) return;
            setBusy(true);
            setError("");
            setDraft(null);
            try {
              setDraft(
                await api<Draft>("/extractions/image", org, {
                  method: "POST",
                  headers: { "Content-Type": imageFile.type },
                  body: imageFile,
                }),
              );
            } catch (error) {
              setError((error as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <Field label="Order image">
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              disabled={busy || !allowed}
              onChange={(event) => {
                setError("");
                setDraft(null);
                const file = event.target.files?.[0] || null;
                if (
                  file &&
                  (file.size > 8 * 1024 * 1024 ||
                    !["image/jpeg", "image/png", "image/webp"].includes(
                      file.type,
                    ))
                ) {
                  setImageFile(null);
                  setError("Choose a JPEG, PNG or WebP image up to 8 MB.");
                } else {
                  setImageFile(file);
                }
              }}
            />
          </Field>
          <p className="muted small">
            Upload a typed or handwritten order in Sinhala, English or Tamil.
            The image is sent to OpenAI to read its visible text. Unclear
            details need review; prices continue to come from your catalog.
          </p>
          {imagePreview && (
            <img
              src={imagePreview}
              alt="Selected order image"
              style={{ maxHeight: 280, maxWidth: "100%", objectFit: "contain" }}
            />
          )}
          {!imageEnabled && (
            <p className="muted small">
              Image reading needs a configured AI provider.
            </p>
          )}
          <button
            className="button secondary"
            disabled={busy || !allowed || !imageEnabled || !imageFile}
          >
            {busy ? "Reading…" : "Read order image"}
          </button>
        </form>
        <div className="info-note">
          <ShieldCheck size={17} />
          <span>
            Extraction does not create an order or change stock. You must review
            and confirm the result.
          </span>
        </div>
      </section>
      <section className="panel padded">
        <h2>
          {draft ? "Your extraction is ready" : "Built to keep you in control"}
        </h2>
        {draft ? (
          <>
            <Badge kind="mint">Draft only · no order created</Badge>
            <p className="muted small">Provider: {draft.result.provider}</p>
            {draft.result.source_type === "image_text" && (
              <div className="info-note">
                <div>
                  <strong>
                    Text read from image - verify against your original
                  </strong>
                  <p style={{ whiteSpace: "pre-wrap" }}>{draft.source_text}</p>
                </div>
              </div>
            )}
            {draft.result.kind === "service_request" && (
              <RequestReview
                key={draft.id}
                draft={draft}
                org={org}
                readOnly={!allowed}
                onSaved={async () =>
                  setDraft(await api<Draft>(`/extractions/${draft.id}`, org))
                }
              />
            )}
            <div className="extraction-list">
              {draft.result.items.map((item, i) => (
                <div key={i}>
                  <strong>{item.product_name || "Unmatched product"}</strong>
                  <span>Quantity: {item.quantity ?? "Needs review"}</span>
                  <small>Source: {item.source}</small>
                  <Badge kind={item.confidence > 0.8 ? "mint" : "amber"}>
                    {Math.round(item.confidence * 100)}% review confidence
                  </Badge>
                  {item.flags.map((flag) => (
                    <small className="flag" key={flag}>
                      {flag.replaceAll("_", " ")}
                    </small>
                  ))}
                </div>
              ))}
            </div>
            {draft.result.kind !== "service_request" && (
              <button
                className="button primary full"
                onClick={() => onReview(draft)}
              >
                Review & confirm <ArrowRight size={17} />
              </button>
            )}
          </>
        ) : (
          <>
            <div className="steps">
              <div>
                <span>1</span>
                <section>
                  <h3>Paste the message</h3>
                  <p>Start with Sinhala, English or Tamil text.</p>
                </section>
              </div>
              <div>
                <span>2</span>
                <section>
                  <h3>Review every detail</h3>
                  <p>Resolve products, quantities and flagged lines.</p>
                </section>
              </div>
              <div>
                <span>3</span>
                <section>
                  <h3>You make it an order</h3>
                  <p>Confirm the customer and items before stock changes.</p>
                </section>
              </div>
            </div>
            <div className="info-note">
              Local rules are the default. A configured model is identified on
              each extraction. Confidence scores are review hints, not accuracy
              guarantees.
            </div>
            <p className="muted small">
              Sinhala, English and Tamil text are supported. Connected WhatsApp
              voice notes are transcribed when speech processing is configured;
              always review the transcript.
            </p>
          </>
        )}
      </section>
    </div>
  );
}
