"use client";
import { useEffect, useState } from "react";
import Image from "next/image";
import { api } from "../lib/api";

type Profile = {
  name: string;
  email: string;
  phone: string;
  has_photo: boolean;
  google_linked: boolean;
};
type Basics = {
  name: string;
  contact_phone: string;
  contact_email: string;
  address: string;
  currency: string;
  report_timezone: string;
  business_type: string;
};
export default function AccountSettings({
  org,
  canManage,
  onChanged,
}: {
  org: string;
  canManage: boolean;
  onChanged: () => Promise<void>;
}) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [basics, setBasics] = useState<Basics | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [photoVersion, setPhotoVersion] = useState(0);
  useEffect(() => {
    let active = true;
    Promise.all([
      api<Profile>("/auth/profile"),
      api<Basics>("/workspace/basic-settings", org),
    ])
      .then(([account, workspace]) => {
        if (active) {
          setProfile(account);
          setBasics(workspace);
        }
      })
      .catch((cause: Error) => {
        if (active) setError(cause.message);
      });
    return () => {
      active = false;
    };
  }, [org]);
  async function action(work: () => Promise<void>, message: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
      await onChanged();
      setNotice(message);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function upload(file: File) {
    if (file.size > 5 * 1024 * 1024) {
      setError("Choose a photo under 5 MB.");
      return;
    }
    await action(async () => {
      const updated = await api<Profile>("/auth/profile/photo", undefined, {
        method: "PUT",
        headers: { "Content-Type": file.type },
        body: file,
      });
      setProfile(updated);
      setPhotoVersion(Date.now());
    }, "Profile photo updated.");
  }
  return (
    <section
      className="panel padded account-settings"
      aria-label="Profile and basic settings"
    >
      <span className="eyebrow">YOUR ACCOUNT</span>
      <h2>Profile & basic setup</h2>
      <p className="muted">
        Your profile follows your account. Business details apply only to the
        selected workspace.
      </p>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="info-note" role="status">
          {notice}
        </p>
      )}
      {profile && basics ? (
        <div className="account-settings-columns">
          <form
            className="profile-form"
            onSubmit={(event) => {
              event.preventDefault();
              void action(async () => {
                setProfile(
                  await api<Profile>("/auth/profile", undefined, {
                    method: "PUT",
                    body: JSON.stringify({
                      name: profile.name,
                      phone: profile.phone,
                    }),
                  }),
                );
              }, "Profile saved.");
            }}
          >
            <h3>Personal profile</h3>
            <div className="profile-photo-row">
              {profile.has_photo ? (
                <Image
                  unoptimized
                  src={`/api/auth/profile/photo?v=${photoVersion}`}
                  alt="Your profile photo"
                  width={88}
                  height={88}
                  className="profile-photo"
                />
              ) : (
                <span
                  className="profile-photo profile-photo-placeholder"
                  aria-label="No profile photo"
                >
                  {profile.name.slice(0, 1).toUpperCase()}
                </span>
              )}
              <div>
                <label className="field">
                  Profile photo
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    disabled={busy}
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void upload(file);
                      event.target.value = "";
                    }}
                  />
                </label>
                <small className="muted">JPG, PNG or WebP, under 5 MB.</small>
                {profile.has_photo && (
                  <button
                    className="button"
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      void action(async () => {
                        await api("/auth/profile/photo", undefined, {
                          method: "DELETE",
                        });
                        setProfile({ ...profile, has_photo: false });
                      }, "Profile photo removed.")
                    }
                  >
                    Remove photo
                  </button>
                )}
              </div>
            </div>
            <label className="field">
              Full name
              <input
                required
                maxLength={120}
                autoComplete="name"
                value={profile.name}
                onChange={(event) =>
                  setProfile({ ...profile, name: event.target.value })
                }
              />
            </label>
            <label className="field">
              Phone number
              <input
                type="tel"
                maxLength={40}
                autoComplete="tel"
                value={profile.phone}
                onChange={(event) =>
                  setProfile({ ...profile, phone: event.target.value })
                }
              />
            </label>
            <label className="field">
              Sign-in email
              <input type="email" readOnly value={profile.email} />
            </label>
            <p className="small muted">
              {profile.google_linked
                ? "Google sign-in is connected."
                : "Email and password sign-in account."}
            </p>
            <button className="button primary" disabled={busy}>
              Save profile
            </button>
          </form>
          <form
            className="profile-form"
            onSubmit={(event) => {
              event.preventDefault();
              void action(async () => {
                const { name, contact_phone, contact_email, address } = basics;
                setBasics(
                  await api<Basics>("/workspace/basic-settings", org, {
                    method: "PUT",
                    body: JSON.stringify({
                      name,
                      contact_phone,
                      contact_email,
                      address,
                    }),
                  }),
                );
              }, "Business basics saved.");
            }}
          >
            <h3>Business basics</h3>
            <fieldset
              disabled={!canManage || busy}
              className="basic-settings-fields"
            >
              <label className="field">
                Business name
                <input
                  required
                  maxLength={120}
                  value={basics.name}
                  onChange={(event) =>
                    setBasics({ ...basics, name: event.target.value })
                  }
                />
              </label>
              <label className="field">
                Business phone
                <input
                  type="tel"
                  maxLength={40}
                  value={basics.contact_phone}
                  onChange={(event) =>
                    setBasics({ ...basics, contact_phone: event.target.value })
                  }
                />
              </label>
              <label className="field">
                Business email
                <input
                  type="email"
                  maxLength={254}
                  value={basics.contact_email}
                  onChange={(event) =>
                    setBasics({ ...basics, contact_email: event.target.value })
                  }
                />
              </label>
              <label className="field">
                Business address
                <textarea
                  rows={3}
                  maxLength={500}
                  value={basics.address}
                  onChange={(event) =>
                    setBasics({ ...basics, address: event.target.value })
                  }
                />
              </label>
            </fieldset>
            <p className="small muted">
              Business type: {basics.business_type} · Currency:{" "}
              {basics.currency} · Reports: {basics.report_timezone}
            </p>
            {canManage ? (
              <button className="button primary" disabled={busy}>
                Save business basics
              </button>
            ) : (
              <p className="muted">
                An owner or admin can update business details.
              </p>
            )}
          </form>
        </div>
      ) : (
        <p role="status">Loading account settings...</p>
      )}
    </section>
  );
}
