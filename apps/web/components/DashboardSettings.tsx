"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { DashboardPreferences } from "../lib/types";

const modules = [
  ["orders", "Orders and invoices"],
  ["service_requests", "Service and project requests"],
  ["customers", "Customer directory"],
  ["catalog", "Product or service catalog"],
] as const;

export default function DashboardSettings({
  org,
  canManage,
  onChanged,
}: {
  org: string;
  canManage: boolean;
  onChanged: () => Promise<void>;
}) {
  const [preferences, setPreferences] = useState<DashboardPreferences | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let active = true;
    api<DashboardPreferences>("/dashboard-preferences", org)
      .then((value) => {
        if (active) setPreferences(value);
      })
      .catch((cause) => {
        if (active) setError((cause as Error).message);
      });
    return () => {
      active = false;
    };
  }, [org]);
  async function save(recommended = false) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const value = await api<DashboardPreferences>(
        "/dashboard-preferences",
        org,
        {
          method: "PUT",
          body: JSON.stringify({
            modules: recommended ? null : preferences?.modules,
            layout: recommended
              ? "recommended"
              : preferences?.layout || "recommended",
          }),
        },
      );
      setPreferences(value);
      await onChanged();
      setNotice("Dashboard layout saved for this business.");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel padded" aria-label="Dashboard customization">
      <h2>Your dashboard</h2>
      <p className="muted">
        Choose the sections your team uses. Recommended sections follow your
        business type. WhatsApp, AI assistant and Settings stay available.
      </p>
      <p className="small muted">
        Hiding a section preserves its records and does not change staff
        permissions. Service requests record appointment preferences; they do
        not reserve calendar bookings.
      </p>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="info-note">
          {notice}
        </p>
      )}
      {preferences ? (
        <form
          className="profile-form"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <fieldset
            className="dashboard-module-options"
            disabled={!canManage || busy}
          >
            <legend>Dashboard layout and sections</legend>
            <label className="field">
              Layout
              <select
                aria-label="Layout"
                value={preferences.layout || "recommended"}
                onChange={(event) =>
                  setPreferences({
                    ...preferences,
                    layout: event.target.value as "recommended" | "full",
                    modules:
                      event.target.value === "full"
                        ? modules.map(([key]) => key)
                        : preferences.service_business
                          ? ["service_requests", "customers", "catalog"]
                          : ["orders", "customers", "catalog"],
                  })
                }
              >
                <option value="recommended">
                  Recommended for this business
                </option>
                <option value="full">Full business dashboard</option>
              </select>
            </label>
            <p className="muted">
              Full layout includes sales, profit charts, inventory and
              operations alongside service requests. Your business type and AI
              workflow stay the same.
            </p>
            <p className="small">Visible dashboard sections</p>
            {modules.map(([key, label]) => (
              <label key={key} className="field">
                <span>
                  <input
                    type="checkbox"
                    checked={preferences.modules.includes(key)}
                    onChange={(event) => {
                      setPreferences({
                        ...preferences,
                        modules: event.target.checked
                          ? [...preferences.modules, key]
                          : preferences.modules.filter((item) => item !== key),
                      });
                    }}
                  />{" "}
                  {label}
                </span>
              </label>
            ))}
          </fieldset>
          {canManage && (
            <div className="heading-actions">
              <button className="button primary" disabled={busy}>
                Save dashboard layout
              </button>
              <button
                className="button"
                type="button"
                disabled={busy}
                onClick={() => void save(true)}
              >
                Use business recommendations
              </button>
            </div>
          )}
        </form>
      ) : (
        <p role="status">Loading dashboard preferences...</p>
      )}
    </section>
  );
}
