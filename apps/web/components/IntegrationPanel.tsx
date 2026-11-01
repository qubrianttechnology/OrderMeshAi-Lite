"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Badge } from "./ui";

export type Integrations = Record<
  string,
  { status: string; provider?: string }
>;

export default function IntegrationPanel({ org }: { org: string }) {
  const [state, setState] = useState<Integrations | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<Integrations>("/integrations", org)
      .then((data) => {
        if (active) setState(data);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [org]);
  return (
    <section className="panel padded">
      <h2>Integration readiness</h2>
      {error && <p role="alert">{error}</p>}
      {!state && !error && <p>Checking configuration…</p>}
      {state && (
        <>
          {[
            ["text", "Sinhala / English / Tamil text"],
            ["llm", "External AI model"],
            ["whatsapp", "Official WhatsApp Business API"],
            ["billing", "Payment provider"],
            ["tamil", "Tamil extraction"],
            ["voice", "Voice notes"],
            ["images", "Order images"],
          ].map(([key, label]) => (
            <div className="integration" key={key}>
              <span>
                {label}
                {key === "text" && (
                  <small>{state.text.provider} · human review required</small>
                )}
              </span>
              <Badge
                kind={
                  state[key].status === "available" ||
                  state[key].status === "configured"
                    ? "mint"
                    : "neutral"
                }
              >
                {state[key].status.replaceAll("_", " ")}
              </Badge>
            </div>
          ))}
        </>
      )}
    </section>
  );
}
