"use client";
import Script from "next/script";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

type Config = {
  configured: boolean;
  missing: string[];
  app_id: string;
  config_id: string;
  graph_version: string;
  origin: string;
  callback_url: string;
};
type Attempt = Config & { attempt_id: string };
type Phone = {
  phone_number_id: string;
  display_phone_number: string;
  verified_name: string;
};
type MetaSDK = {
  init: (settings: {
    appId: string;
    version: string;
    cookie: boolean;
    xfbml: boolean;
  }) => void;
  login: (
    callback: (response: { authResponse?: { code?: string } }) => void,
    settings: {
      config_id: string;
      response_type: string;
      override_default_response_type: boolean;
      state: string;
      extras: { setup: Record<string, never> };
    },
  ) => void;
};
declare global {
  interface Window {
    FB?: MetaSDK;
  }
}

export default function ConnectWhatsApp({
  org,
  allowed,
  onConnected,
}: {
  org: string;
  allowed: boolean;
  onConnected?: () => void;
}) {
  const router = useRouter();
  const [number, setNumber] = useState("");
  const cleanup = useRef<(() => void) | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [sdkReady, setSdkReady] = useState(false);
  const [choices, setChoices] = useState<Phone[]>([]);
  const [selected, setSelected] = useState("");
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const generation = useRef(0);
  useEffect(() => {
    const epoch = ++generation.current;
    if (allowed)
      api<Config>("/inbox/meta-signup/status", org)
        .then((v) => {
          if (epoch === generation.current) setConfig(v);
        })
        .catch((cause) => {
          if (epoch === generation.current) setError(cause.message);
        });
    return () => {
      generation.current = epoch + 1;
      cleanup.current?.();
    };
  }, [org, allowed]);
  if (!allowed) return null;
  async function begin() {
    const epoch = generation.current;
    setBusy(true);
    setError("");
    setNotice("");
    setChoices([]);
    cleanup.current?.();
    setPin("");
    // Reserve the popup while this click still has browser user activation.
    const reserved = window.open(
      "about:blank",
      "ordermesh-whatsapp",
      "popup,width=650,height=760",
    );
    if (!reserved) {
      setError(
        "Allow popups for this dashboard, then click Connect WhatsApp again.",
      );
      setBusy(false);
      return;
    }
    reserved.document.title = "Connect WhatsApp";
    reserved.document.body.textContent =
      "Preparing your secure Meta connection...";
    try {
      const next = await api<Attempt>("/inbox/meta-signup/begin", org, {
        method: "POST",
        body: JSON.stringify({ phone_number: number }),
      });
      if (epoch !== generation.current) {
        reserved.close();
        return;
      }
      if (window.location.origin !== new URL(next.origin).origin)
        throw new Error(
          "Open the configured secure dashboard URL to connect WhatsApp.",
        );
      setAttempt(next);
      launch(next, reserved);
    } catch (cause) {
      reserved.close();
      if (epoch === generation.current) {
        setError((cause as Error).message);
        setBusy(false);
      }
    }
  }
  function launch(active = attempt, reserved?: Window | null) {
    if (!window.FB || !active) {
      reserved?.close();
      setBusy(false);
      return;
    }
    const attempt = active;
    setBusy(true);
    setError("");
    const epoch = generation.current;
    // The SDK uses an arbiter callback with a per-popup fragment. Preserve the
    // exact URI used in its OAuth request for the server-side code exchange.
    let sdkRedirectUri = "";
    let popup: Window | null = null;
    let wabaId = "";
    let finish: (() => void) | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    function receive(event: MessageEvent) {
      if (
        ![
          "https://www.facebook.com",
          "https://web.facebook.com",
          "https://business.facebook.com",
        ].includes(event.origin)
      )
        return;
      // Meta can post completion from a nested frame in its popup. Treat the
      // asset as a hint only; the API verifies grant access and requested number.
      if (!popup || !event.source) return;
      try {
        if (typeof event.data === "string" && event.data.length > 10000) return;
        const data =
          typeof event.data === "string" ? JSON.parse(event.data) : event.data;
        if (
          data?.type !== "WA_EMBEDDED_SIGNUP" ||
          ![
            "FINISH",
            "FINISH_ONLY_WABA",
            "FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING",
          ].includes(data.event)
        )
          return;
        if (!/^\d{5,128}$/.test(String(data.data?.waba_id || ""))) return;
        wabaId = String(data.data.waba_id);
        finish?.();
      } catch {
        /* Ignore unrelated popup messages. */
      }
    }
    cleanup.current?.();
    const dispose = () => {
      window.removeEventListener("message", receive);
      if (timer) clearTimeout(timer);
      finish?.();
    };
    cleanup.current = dispose;
    window.addEventListener("message", receive);
    const originalOpen = window.open;
    window.open = function (
      url?: string | URL,
      target?: string,
      features?: string,
    ) {
      try {
        const auth = new URL(String(url));
        if (
          ["www.facebook.com", "web.facebook.com", "facebook.com"].includes(
            auth.hostname,
          ) &&
          auth.pathname === `/${attempt.graph_version}/dialog/oauth` &&
          auth.searchParams.get("client_id") === attempt.app_id
        ) {
          sdkRedirectUri = auth.searchParams.get("redirect_uri") || "";
        }
      } catch {
        /* Leave unrelated popup URLs unchanged. */
      }
      let opened: Window | null;
      if (sdkRedirectUri && reserved && !reserved.closed) {
        if (target) reserved.name = target;
        reserved.location.replace(String(url));
        opened = reserved;
      } else opened = originalOpen.call(window, url, target, features);
      if (sdkRedirectUri) {
        popup = opened;
        if (!opened) throw new Error("Meta popup blocked");
      }
      return opened;
    };
    try {
      window.FB.login(
        (response) => {
          void handleResponse(response);
        },
        {
          config_id: attempt.config_id,
          response_type: "code",
          override_default_response_type: true,
          state: attempt.attempt_id,
          extras: { setup: {} },
        },
      );
    } catch {
      reserved?.close();
      dispose();
      setBusy(false);
      setError("Meta login could not open. Allow the popup and start again.");
    } finally {
      window.open = originalOpen;
    }
    async function handleResponse(response: {
      authResponse?: { code?: string };
    }) {
      if (epoch !== generation.current) return;
      const code = response.authResponse?.code;
      if (!code) {
        dispose();
        setBusy(false);
        setError(
          "Meta authorization was cancelled or did not return a code. Start again.",
        );
        return;
      }
      if (!sdkRedirectUri) {
        dispose();
        setBusy(false);
        setError(
          "Meta did not provide its authorization callback. Reload the page and start again.",
        );
        return;
      }
      if (!wabaId)
        await new Promise<void>((resolve) => {
          finish = resolve;
          timer = setTimeout(resolve, 5000);
        });
      dispose();
      if (epoch !== generation.current) return;
      void api<{ choices: Phone[] }>("/inbox/meta-signup/exchange", org, {
        method: "POST",
        body: JSON.stringify({
          attempt_id: attempt.attempt_id,
          code,
          redirect_uri: sdkRedirectUri,
          ...(wabaId ? { business_account_id: wabaId } : {}),
        }),
      })
        .then(async (result) => {
          if (epoch === generation.current) {
            setChoices(result.choices);
            setSelected(result.choices[0]?.phone_number_id || "");
            if (result.choices.length === 1)
              await connect(attempt, result.choices[0].phone_number_id);
          }
        })
        .catch((cause) => {
          if (epoch === generation.current) {
            setError(cause.message);
            setAttempt(null);
          }
        })
        .finally(() => {
          if (epoch === generation.current) setBusy(false);
        });
    }
  }
  async function connect(current = attempt, phoneId = selected) {
    if (!current) return;
    const epoch = generation.current;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ display_phone_number: string }>(
        "/inbox/meta-signup/confirm",
        org,
        {
          method: "POST",
          body: JSON.stringify({
            attempt_id: current.attempt_id,
            phone_number_id: phoneId,
            pin: pin || null,
            human_confirmed: true,
          }),
        },
      );
      if (epoch !== generation.current) return;
      setNotice(
        `${result.display_phone_number} connected. Send a real customer message to verify delivery.`,
      );
      setAttempt(null);
      setChoices([]);
      setPin("");
      onConnected?.();
      router.push("/dashboard/inbox");
    } catch (cause) {
      if (epoch === generation.current) setError((cause as Error).message);
    } finally {
      if (epoch === generation.current) setBusy(false);
    }
  }
  return (
    <section className="panel padded" aria-label="WhatsApp connection">
      <h2>Connect your WhatsApp</h2>
      <p>
        Enter your business number, then authorize it in Meta. We connect the
        verified number to this workspace and show new incoming messages in your
        inbox.
      </p>
      <p className="small muted">
        For a number already in the WhatsApp Business app, choose the Business
        App connection option inside Meta when offered. Eligibility and app
        review are controlled by Meta.
      </p>
      {!config && !error && <p>Checking connection setup...</p>}
      {config && !config.configured && (
        <div className="info-note">
          <div>
            Administrator setup is required before connecting. The dashboard
            needs a public HTTPS address and a verified Meta webhook.
            <details>
              <summary>Setup details</summary>
              <p>{config.missing.join(", ")}</p>
            </details>
          </div>
        </div>
      )}
      <div className="field">
        <label htmlFor="meta-business-number">WhatsApp business number</label>
        <input
          id="meta-business-number"
          type="tel"
          autoComplete="tel"
          placeholder="+94770001122"
          value={number}
          disabled={busy || !!choices.length}
          onChange={(event) => setNumber(event.target.value)}
        />
        <p className="small muted">
          By connecting, you authorize linking this number to this workspace.
          Existing chat history is not automatically imported.
        </p>
      </div>
      <button
        className="button primary"
        disabled={busy || !config?.configured || !number.trim() || !sdkReady}
        onClick={() => void begin()}
      >
        {busy ? "Connecting..." : attempt ? "Start again" : "Connect WhatsApp"}
      </button>
      {config?.configured && (
        <Script
          id="ordermesh-meta-sdk"
          src="https://connect.facebook.net/en_US/sdk.js"
          strategy="afterInteractive"
          onReady={() => {
            window.FB?.init({
              appId: config.app_id,
              version: config.graph_version,
              cookie: true,
              xfbml: false,
            });
            setSdkReady(true);
          }}
          onError={() =>
            setError(
              "Meta login could not load. Check your connection and browser privacy settings.",
            )
          }
        />
      )}
      {attempt && (
        <>
          {!choices.length && (
            <p>
              <button
                className="button secondary"
                disabled={!sdkReady || busy}
                onClick={() => launch()}
              >
                Continue with Meta
              </button>
            </p>
          )}
          {!!choices.length && (
            <div className="field" style={{ marginTop: 20 }}>
              <label htmlFor="meta-phone-choice">
                Choose your verified WhatsApp number
              </label>
              <select
                id="meta-phone-choice"
                value={selected}
                disabled={busy}
                onChange={(e) => setSelected(e.target.value)}
              >
                {choices.map((p) => (
                  <option key={p.phone_number_id} value={p.phone_number_id}>
                    {p.display_phone_number} {p.verified_name}
                  </option>
                ))}
              </select>
              <label htmlFor="meta-registration-pin">
                Six-digit Cloud API registration PIN
              </label>
              <input
                id="meta-registration-pin"
                type="password"
                inputMode="numeric"
                autoComplete="new-password"
                maxLength={6}
                pattern="[0-9]{6}"
                value={pin}
                onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
              />
              <p className="small muted">
                For a new Cloud API number, enter the six-digit PIN you want to
                use for registration. Existing Business App coexistence does not
                need this PIN. Never enter an SMS verification code here.
              </p>
              <button
                className="button primary"
                disabled={busy || !selected}
                onClick={() => void connect()}
              >
                Connect selected number
              </button>
            </div>
          )}
        </>
      )}
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="info-note">
          {notice}
        </p>
      )}
    </section>
  );
}
