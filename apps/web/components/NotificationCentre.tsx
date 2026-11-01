"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Bell, CheckCheck, Volume2, VolumeX, X } from "lucide-react";
import { api } from "../lib/api";

type Alert = {
  id: string;
  title: string;
  detail: string;
  target: string;
  severity: string;
  created_at: string;
  read: boolean;
};
type Feed = { items: Alert[]; unread_count: number; total: number };
export default function NotificationCentre({
  org,
  userId,
  onNavigate,
}: {
  org: string;
  userId: string;
  onNavigate: (target: string) => void;
}) {
  const [feed, setFeed] = useState<Feed>({
    items: [],
    unread_count: 0,
    total: 0,
  });
  const [open, setOpen] = useState(false),
    [error, setError] = useState(""),
    [toast, setToast] = useState("");
  const [sound, setSound] = useState(false),
    [desktop, setDesktop] = useState(false);
  const previous = useRef<Set<string> | null>(null),
    soundRef = useRef(false),
    desktopRef = useRef(false),
    audio = useRef<AudioContext | null>(null);
  const onNavigateRef = useRef(onNavigate);
  onNavigateRef.current = onNavigate;
  const preferenceKey = `ordermesh-alerts:${userId}:${org}`;
  function tone() {
    try {
      const context = audio.current;
      if (!context) return;
      void context.resume();
      const oscillator = context.createOscillator(),
        gain = context.createGain();
      gain.gain.value = 0.025;
      oscillator.frequency.value = 660;
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start();
      oscillator.stop(context.currentTime + 0.14);
    } catch {
      /* Audio is optional. */
    }
  }
  useEffect(() => {
    let active = true;
    previous.current = null;
    let preference: { sound?: boolean; desktop?: boolean } = {};
    try {
      preference = JSON.parse(localStorage.getItem(preferenceKey) || "{}");
    } catch {
      /* Ignore damaged local preferences. */
    }
    setSound(!!preference.sound);
    soundRef.current = !!preference.sound;
    setDesktop(!!preference.desktop);
    desktopRef.current = !!preference.desktop;
    async function load() {
      try {
        const value = await api<Feed>("/notifications", org);
        if (!active) return;
        const unread = value.items.filter((item) => !item.read);
        const fresh =
          previous.current === null
            ? []
            : unread.filter((item) => !previous.current!.has(item.id));
        previous.current = new Set(unread.map((item) => item.id));
        setFeed(value);
        setError("");
        if (fresh.length) {
          setToast(fresh[0].title);
          if (soundRef.current) tone();
          if (
            desktopRef.current &&
            "Notification" in window &&
            Notification.permission === "granted"
          )
            new Notification("OrderMesh: " + fresh[0].title, {
              body: "Open your workspace to review this alert.",
              tag: org + fresh[0].id,
            });
        }
      } catch (cause) {
        if (active) setError((cause as Error).message);
      }
    }
    void load();
    const timer = setInterval(() => {
      if (!document.hidden) void load();
    }, 10000);
    const visible = () => {
      if (!document.hidden) void load();
    };
    document.addEventListener("visibilitychange", visible);
    const unlock = () => {
      if (soundRef.current && "AudioContext" in window) {
        audio.current ||= new AudioContext();
        void audio.current.resume();
      }
    };
    window.addEventListener("pointerdown", unlock, { once: true });
    return () => {
      active = false;
      if (audio.current) {
        void audio.current.close();
        audio.current = null;
      }
      window.removeEventListener("pointerdown", unlock);
      clearInterval(timer);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [org, preferenceKey]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 6000);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    if (!open) return;
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [open]);
  const mark = useCallback(
    async (keys?: string[]) => {
      await api("/notifications/read", org, {
        method: "POST",
        body: JSON.stringify(keys ? { keys } : { all: true }),
      });
      const value = await api<Feed>("/notifications", org);
      setFeed(value);
      previous.current = new Set(
        value.items.filter((item) => !item.read).map((item) => item.id),
      );
    },
    [org],
  );
  function savePreferences(nextSound: boolean, nextDesktop: boolean) {
    localStorage.setItem(
      preferenceKey,
      JSON.stringify({ sound: nextSound, desktop: nextDesktop }),
    );
    setSound(nextSound);
    setDesktop(nextDesktop);
    soundRef.current = nextSound;
    desktopRef.current = nextDesktop;
  }
  return (
    <div className="notification-control">
      <button
        className="icon-button attention-button"
        aria-label="Notifications"
        aria-expanded={open}
        title="Notifications and alerts"
        onClick={() => setOpen(!open)}
      >
        <Bell size={18} />
        {feed.unread_count > 0 && (
          <span
            className="notification-count"
            aria-label={`${feed.unread_count} unread alerts`}
          >
            {feed.unread_count > 99 ? "99+" : feed.unread_count}
          </span>
        )}
      </button>
      {toast && (
        <div className="notification-toast" role="status">
          {toast}
          <button className="text-button" onClick={() => setOpen(true)}>
            View alerts
          </button>
        </div>
      )}
      {open && (
        <section
          className="notification-popover"
          role="dialog"
          aria-label="Notification centre"
        >
          <div className="notification-heading">
            <div>
              <h2>Notifications</h2>
              <p className="muted small">
                {feed.unread_count} unread · {feed.total} active alerts
              </p>
            </div>
            <button
              className="icon-button"
              aria-label="Close notifications"
              onClick={() => setOpen(false)}
            >
              <X size={18} />
            </button>
          </div>
          <div className="notification-options">
            <button
              className="text-button"
              disabled={!feed.unread_count}
              onClick={() =>
                void mark().catch((cause: Error) => setError(cause.message))
              }
            >
              <CheckCheck size={14} /> Mark all read
            </button>
            <button
              className="text-button"
              onClick={() => {
                if (!sound && "AudioContext" in window) {
                  audio.current ||= new AudioContext();
                  void audio.current.resume();
                  tone();
                }
                savePreferences(!sound, desktop);
              }}
            >
              {sound ? <Volume2 size={14} /> : <VolumeX size={14} />}
              {sound ? "Sound on" : "Enable sound"}
            </button>
            <button
              className="text-button"
              onClick={async () => {
                if (!("Notification" in window)) {
                  setError("Desktop notifications are not supported here.");
                  return;
                }
                if (desktop) {
                  savePreferences(sound, false);
                  return;
                }
                const permission = await Notification.requestPermission();
                savePreferences(sound, permission === "granted");
                if (permission !== "granted")
                  setError(
                    "Allow notifications in your browser to enable desktop alerts.",
                  );
              }}
            >
              {desktop ? "Desktop alerts on" : "Enable desktop alerts"}
            </button>
          </div>
          <p className="muted small">
            Alerts refresh while this dashboard is open. Sound requires a click
            after reopening your browser.
          </p>
          {error && (
            <p className="alert" role="alert">
              {error}
            </p>
          )}
          <div className="notification-list">
            {feed.items.length ? (
              feed.items.map((item) => (
                <article
                  key={item.id}
                  className={`notification-item ${item.severity}${item.read ? " read" : ""}`}
                >
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                  <div className="row-actions">
                    <button
                      className="text-button"
                      onClick={() => {
                        setOpen(false);
                        onNavigateRef.current(item.target);
                        void mark([item.id]).catch(() => {});
                      }}
                    >
                      Open {item.target}
                    </button>
                    {!item.read && (
                      <button
                        className="text-button"
                        onClick={() =>
                          void mark([item.id]).catch((cause: Error) =>
                            setError(cause.message),
                          )
                        }
                      >
                        Mark read
                      </button>
                    )}
                  </div>
                </article>
              ))
            ) : (
              <p className="muted">
                No active notifications. New messages, review requests and low
                stock will appear here.
              </p>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
