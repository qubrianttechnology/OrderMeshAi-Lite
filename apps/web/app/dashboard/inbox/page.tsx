"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  ArrowLeft,
  Check,
  ChevronRight,
  Inbox,
  MessageCircle,
  Moon,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Sun,
  UserRound,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { api, allPages, date } from "../../../lib/api";
import type {
  Customer,
  Draft,
  InboxConversation,
  InboxMessage,
  InboxPhoneNumber,
  Product,
  User,
} from "../../../lib/types";
import ConnectWhatsApp from "../../../components/ConnectWhatsApp";
import ModalView, { type Modal } from "../../../components/OrderDialog";
import { Brand, Empty } from "../../../components/ui";
import "../../dashboard.css";

type IntegrationStatus = {
  database: {
    backend: string;
    role: {
      name: string;
      superuser: boolean;
      bypasses_rls: boolean;
    };
    rls_required: boolean;
  };
  whatsapp: {
    configured: boolean;
    cloud_send_configured: boolean;
    test_mode: boolean;
    callback_path: string;
    registered_phone_numbers: number;
  };
  ai: {
    provider: string;
    configured: boolean;
    automatic_confirmation: false;
  };
};

const CATEGORY_LABELS: Record<string, string> = {
  all: "All messages",
  business: "Business messages",
  business_order: "Orders",
  business_inquiry: "Business inquiries",
  support: "Customer support",
  personal: "Private messages",
  spam: "Spam",
  needs_review: "Needs review",
};

function matchesCategory(message: InboxMessage, category: string) {
  if (category === "all" || message.direction === "outbound") return true;
  if (category === "business")
    return ["business_order", "business_inquiry", "support"].includes(
      message.category || "",
    );
  if (category === "needs_review")
    return (
      !message.category ||
      ["needs_review", "unclassified"].includes(message.category)
    );
  return message.category === category;
}

export default function InboxPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [orgId, setOrgId] = useState("");
  const [boot, setBoot] = useState(true);
  const [phones, setPhones] = useState<InboxPhoneNumber[]>([]);
  const [conversations, setConversations] = useState<InboxConversation[]>([]);
  const [integrationStatus, setIntegrationStatus] =
    useState<IntegrationStatus | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [messages, setMessages] = useState<InboxMessage[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [query, setQuery] = useState("");
  const [inboxView, setInboxView] = useState("active");
  const [selectedSnapshot, setSelectedSnapshot] =
    useState<InboxConversation | null>(null);
  const autoSelect = useRef(true);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [theme, setTheme] = useState<"dark" | "light">("light");
  const [modal, setModal] = useState<Modal>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [streamStatus, setStreamStatus] = useState<
    "connecting" | "connected" | "disconnected" | "polling"
  >("connecting");
  const [phoneNumberId, setPhoneNumberId] = useState("");
  const [displayPhone, setDisplayPhone] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerName, setCustomerName] = useState("Test customer");
  const [linkCustomerId, setLinkCustomerId] = useState("");
  const [messageText, setMessageText] = useState("");
  const [busy, setBusy] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [replyBusy, setReplyBusy] = useState(false);
  const [replyError, setReplyError] = useState("");
  const replyRequestId = useRef<{ conversationId: string; id: string } | null>(
    null,
  );
  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;
  const organization = user?.organizations.find((item) => item.id === orgId);
  const canManage =
    organization?.role === "owner" || organization?.role === "admin";
  const canOrder = !!organization && organization.role !== "viewer";
  const selected = useMemo(
    () =>
      conversations.find((item) => item.id === selectedId) ??
      (selectedSnapshot?.id === selectedId ? selectedSnapshot : null),
    [conversations, selectedId, selectedSnapshot],
  );

  const refreshInbox = useCallback(async () => {
    if (!orgId) return;
    const [items, registered] = await Promise.all([
      api<InboxConversation[]>(
        `/inbox/conversations?search=${encodeURIComponent(query)}&category=${encodeURIComponent(categoryFilter)}&view=${encodeURIComponent(inboxView)}`,
        orgId,
      ),
      api<InboxPhoneNumber[]>("/inbox/phone-numbers", orgId),
    ]);
    setConversations(items);
    setPhones(registered);
    const role = user?.organizations.find((item) => item.id === orgId)?.role;
    if (role === "owner" || role === "admin") {
      setIntegrationStatus(
        await api<IntegrationStatus>("/inbox/integration-status", orgId),
      );
    } else {
      setIntegrationStatus(null);
    }
    if (
      selectedIdRef.current &&
      !items.some((item) => item.id === selectedIdRef.current) &&
      inboxView !== "unread"
    ) {
      setSelectedId("");
      setSelectedSnapshot(null);
      setMessages([]);
    }
    if (!selectedIdRef.current && items.length && autoSelect.current) {
      autoSelect.current = false;
      setSelectedSnapshot(items[0]);
      setSelectedId(items[0].id);
    }
  }, [orgId, query, user, categoryFilter, inboxView]);

  async function manageConversation(change: {
    pinned?: boolean;
    archived?: boolean;
    read_state?: "read" | "unread";
  }) {
    if (!selected || !canOrder) return;
    setBusy(true);
    setError("");
    try {
      await api(`/inbox/conversations/${selected.id}/management`, orgId, {
        method: "PATCH",
        body: JSON.stringify(change),
      });
      if (change.read_state === "unread" || change.archived !== undefined) {
        autoSelect.current = false;
        selectedIdRef.current = "";
        setSelectedId("");
        setSelectedSnapshot(null);
        setMessages([]);
      }
      await refreshInbox();
      setNotice("Conversation updated.");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const loadMessages = useCallback(
    async (conversationId: string, markRead = false) => {
      if (!orgId || !conversationId) return;
      const data = await api<InboxMessage[]>(
        `/inbox/conversations/${conversationId}/messages?mark_read=${markRead}`,
        orgId,
      );
      if (selectedIdRef.current !== conversationId) return;
      setMessages(data);
      if (markRead)
        setConversations((items) =>
          items.map((item) =>
            item.id === conversationId ? { ...item, unread_count: 0 } : item,
          ),
        );
    },
    [orgId],
  );

  useEffect(() => {
    setTheme(
      localStorage.getItem("ordermesh-theme") === "dark" ? "dark" : "light",
    );
    api<User>("/auth/me")
      .then((data) => {
        setUser(data);
        const saved = localStorage.getItem("ordermesh-org");
        setOrgId(
          data.organizations.some((item) => item.id === saved)
            ? saved!
            : data.organizations[0]?.id || "",
        );
      })
      .catch(() => {
        router.replace("/sign-in");
      })
      .finally(() => setBoot(false));
  }, [router]);

  useEffect(() => {
    if (!orgId) return;
    let live = true;
    setLoading(true);
    setError("");
    Promise.all([
      refreshInbox(),
      allPages<Product>("/products", orgId),
      allPages<Customer>("/customers", orgId),
    ])
      .then(([, productRows, customerRows]) => {
        if (!live) return;
        setProducts(productRows);
        setCustomers(customerRows);
      })
      .catch((cause: Error) => {
        if (live) setError(cause.message);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [orgId, refreshInbox]);

  useEffect(() => {
    if (selectedId)
      void loadMessages(selectedId, true).catch((cause: Error) =>
        setError(cause.message),
      );
    else setMessages([]);
  }, [selectedId, loadMessages]);

  useEffect(() => {
    if (!orgId) return;
    if (window.location.hostname.endsWith(".trycloudflare.com")) {
      // Quick Tunnels do not support SSE; use bounded polling during HTTPS tests.
      setStreamStatus("polling");
      let pending = false;
      const timer = setInterval(async () => {
        if (pending || document.hidden) return;
        pending = true;
        try {
          await refreshInbox();
          if (selectedId) await loadMessages(selectedId);
        } catch {
          /* Keep the last successful inbox; the refresh control can retry. */
        } finally {
          pending = false;
        }
      }, 5000);
      return () => clearInterval(timer);
    }
    setStreamStatus("connecting");
    const controller = new AbortController();
    async function listen() {
      try {
        const response = await fetch("/api/inbox/events", {
          credentials: "same-origin",
          cache: "no-store",
          headers: {
            "X-OrderMesh": "1",
            "X-Organization-ID": orgId,
          },
          signal: controller.signal,
        });
        if (!response.ok || !response.body) {
          throw new Error("Live inbox updates could not be started.");
        }
        setStreamStatus("connected");
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!controller.signal.aborted) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const blocks = buffer.split("\n\n");
          buffer = blocks.pop() ?? "";
          for (const block of blocks) {
            if (!block.startsWith("event: messages")) continue;
            await refreshInbox();
            if (selectedId) await loadMessages(selectedId);
          }
        }
      } catch (cause) {
        if (!controller.signal.aborted) {
          setStreamStatus("disconnected");
          setError((cause as Error).message);
        }
      }
    }
    void listen();
    return () => {
      controller.abort();
      setStreamStatus("disconnected");
    };
  }, [orgId, refreshInbox, loadMessages, selectedId]);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 4500);
    return () => clearTimeout(timer);
  }, [notice]);

  async function registerPhone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/inbox/phone-numbers", orgId, {
        method: "POST",
        body: JSON.stringify({
          phone_number_id: phoneNumberId,
          display_phone_number: displayPhone,
          business_account_id: "",
        }),
      });
      setPhoneNumberId("");
      setDisplayPhone("");
      setNotice("WhatsApp phone number registered.");
      await refreshInbox();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function simulateMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api<{ status: string }>("/inbox/simulator", orgId, {
        method: "POST",
        body: JSON.stringify({
          phone_number_id: phoneNumberId,
          customer_phone: customerPhone,
          customer_name: customerName,
          text: messageText,
        }),
      });
      setMessageText("");
      setNotice(
        result.status === "processed"
          ? "Test message processed. Review its AI order draft before confirming."
          : "Test message queued for processing.",
      );
      await refreshInbox();
      const matching = await api<InboxConversation[]>(
        `/inbox/conversations?search=${encodeURIComponent(customerPhone.replace(/\D/g, ""))}`,
        orgId,
      );
      if (matching[0]) {
        setSelectedId(matching[0].id);
        await loadMessages(matching[0].id);
      }
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function sendReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !replyText.trim() || replyBusy) return;
    setReplyBusy(true);
    setReplyError("");
    if (replyRequestId.current?.conversationId !== selected.id) {
      replyRequestId.current = {
        conversationId: selected.id,
        id: crypto.randomUUID(),
      };
    }
    try {
      await api(`/inbox/conversations/${selected.id}/reply`, orgId, {
        method: "POST",
        body: JSON.stringify({
          text: replyText.trim(),
          client_request_id: replyRequestId.current.id,
        }),
      });
      replyRequestId.current = null;
      setReplyText("");
      await Promise.all([loadMessages(selected.id), refreshInbox()]);
    } catch (cause) {
      setReplyError((cause as Error).message);
    } finally {
      setReplyBusy(false);
    }
  }

  async function reviewDraft(draftId: string) {
    try {
      const draft = await api<Draft>(`/extractions/${draftId}`, orgId);
      setModal({ type: "order", draft });
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  async function linkCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !linkCustomerId || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{
        customer_id: string;
        customer_name: string;
        customer_match_source: InboxConversation["customer_match_source"];
      }>(`/inbox/conversations/${selected.id}/customer`, orgId, {
        method: "PUT",
        body: JSON.stringify({ customer_id: linkCustomerId }),
      });
      setConversations((items) =>
        items.map((item) =>
          item.id === selected.id
            ? {
                ...item,
                customer_id: result.customer_id,
                customer_name: result.customer_name,
                customer_match_source: result.customer_match_source,
              }
            : item,
        ),
      );
      setLinkCustomerId("");
      setNotice(
        "Customer linked. Future messages from this WhatsApp number will route here.",
      );
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function saved(message: string) {
    setModal(null);
    setNotice(message);
    await Promise.all([refreshInbox(), loadMessages(selectedId)]);
  }

  if (boot) {
    return (
      <div className="boot">
        <Brand />
        <p>Opening your workspace…</p>
      </div>
    );
  }
  if (!user) {
    return (
      <div className="boot">
        <Brand />
        <p>Redirecting to sign in…</p>
      </div>
    );
  }

  return (
    <div className="app-shell inbox-shell" data-theme={theme}>
      <main className="main-shell inbox-main">
        <header className="topbar inbox-topbar">
          <button
            className="icon-button"
            aria-label="Back to dashboard"
            onClick={() => router.push("/dashboard")}
          >
            <ArrowLeft size={18} />
          </button>
          <div className="inbox-brand">
            <Brand />
            <span>/</span>
            <span>Inbox</span>
          </div>
          <div className="topbar-right">
            <label className="inbox-org-select">
              <span className="sr-only">Organization</span>
              <select
                aria-label="Organization"
                value={orgId}
                onChange={(event) => {
                  localStorage.setItem("ordermesh-org", event.target.value);
                  setOrgId(event.target.value);
                  autoSelect.current = true;
                  setSelectedSnapshot(null);
                  setSelectedId("");
                  setMessages([]);
                }}
              >
                {user.organizations.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <span className="connection">
              <span className="dot" />
              {organization?.name}
            </span>
            <button
              className="icon-button"
              title="Refresh inbox"
              aria-label="Refresh inbox"
              onClick={() =>
                void refreshInbox().catch((cause: Error) =>
                  setError(cause.message),
                )
              }
            >
              <RefreshCw size={17} />
            </button>
            <button
              className="icon-button theme-toggle"
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              onClick={() => {
                const next = theme === "dark" ? "light" : "dark";
                setTheme(next);
                localStorage.setItem("ordermesh-theme", next);
              }}
            >
              {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
          </div>
        </header>

        <section className="main-content inbox-content">
          <div className="breadcrumb">
            <button onClick={() => router.push("/dashboard")}>Workspace</button>
            <ChevronRight size={14} />
            <strong>WhatsApp inbox</strong>
          </div>
          <div className="page-heading inbox-heading">
            <div>
              <span className="eyebrow">CUSTOMER MESSAGES</span>
              <h1>WhatsApp inbox</h1>
              <label className="field">
                Chat view
                <select
                  aria-label="Chat view"
                  value={inboxView}
                  onChange={(event) => {
                    setInboxView(event.target.value);
                    setSelectedId("");
                    setSelectedSnapshot(null);
                    setMessages([]);
                    autoSelect.current = false;
                  }}
                >
                  <option value="active">Active chats</option>
                  <option value="unread">Unread chats</option>
                  <option value="archived">Archived chats</option>
                  <option value="all">All chats</option>
                </select>
              </label>
              <label className="field">
                Filter messages
                <select
                  aria-label="Filter messages"
                  value={categoryFilter}
                  onChange={(event) => {
                    autoSelect.current = true;
                    setSelectedId("");
                    selectedIdRef.current = "";
                    setSelectedSnapshot(null);
                    setMessages([]);
                    setCategoryFilter(event.target.value);
                  }}
                >
                  {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <p>
                Filter chats by incoming message category. Replies stay visible
                for context. Private and spam messages are kept for review.
              </p>
            </div>
            <span className="inbox-live">
              <span className={`dot ${streamStatus}`} />
              {streamStatus === "connected"
                ? "Live updates connected"
                : streamStatus === "polling"
                  ? "Updates every 5 seconds"
                  : streamStatus === "connecting"
                    ? "Connecting to live updates"
                    : "Live updates disconnected"}
            </span>
          </div>
          {integrationStatus && (
            <section
              className="integration-diagnostics"
              aria-label="Integration diagnostics"
            >
              <strong>Connection diagnostics</strong>
              <span>
                Database: {integrationStatus.database.backend}
                {integrationStatus.database.role.name !== "local" &&
                  ` · ${integrationStatus.database.role.name}`}
                {integrationStatus.database.rls_required
                  ? integrationStatus.database.role.superuser ||
                    integrationStatus.database.role.bypasses_rls
                    ? " · RLS role check failed"
                    : " · non-bypass role"
                  : ""}
              </span>
              <span>
                WhatsApp webhook:{" "}
                {integrationStatus.whatsapp.configured
                  ? `secrets configured · ${integrationStatus.whatsapp.registered_phone_numbers} phone number(s)`
                  : "secrets not configured"}
                {" · "}
                {integrationStatus.whatsapp.callback_path}
              </span>
              <span>
                AI: {integrationStatus.ai.provider}
                {integrationStatus.ai.configured
                  ? " configured"
                  : " not configured"}
                {" · human approval required"}
              </span>
              <small>
                Configuration only; this does not contact Meta or the AI
                provider.
              </small>
            </section>
          )}

          {error && (
            <div className="error-banner" role="alert">
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="success-banner" role="status">
              <Check size={16} />
              {notice}
            </div>
          )}

          <div className="inbox-grid">
            <section
              className="panel inbox-list-panel"
              aria-label="Conversations"
            >
              <div className="inbox-list-header">
                <div>
                  <h2>Conversations</h2>
                  <p>{conversations.length} customer threads</p>
                </div>
                <span className="inbox-count">{conversations.length}</span>
              </div>
              <label className="inbox-search">
                <Search size={16} />
                <input
                  aria-label="Search conversations"
                  placeholder="Search messages or phone"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
              <div className="inbox-conversation-list">
                {conversations.length ? (
                  conversations.map((conversation) => (
                    <button
                      className={`inbox-conversation${selectedId === conversation.id ? " selected" : ""}`}
                      key={conversation.id}
                      onClick={() => {
                        setSelectedSnapshot(conversation);
                        setSelectedId(conversation.id);
                        void loadMessages(conversation.id, true).catch(
                          (cause: Error) => setError(cause.message),
                        );
                      }}
                    >
                      <span className="inbox-avatar">
                        <UserRound size={18} />
                      </span>
                      <span className="inbox-conversation-copy">
                        <span className="inbox-conversation-top">
                          <strong>
                            {conversation.customer_name ||
                              conversation.customer_phone}
                          </strong>
                          <time>{date(conversation.last_message_at)}</time>
                        </span>
                        <span className="inbox-phone">
                          {conversation.customer_phone}
                          {conversation.pinned && <small> � Pinned</small>}
                          {conversation.archived && <small> � Archived</small>}
                        </span>
                        {!conversation.customer_id && (
                          <span className="inbox-unassigned">
                            Needs customer link
                          </span>
                        )}
                        <span className="inbox-preview">
                          {conversation.last_message_preview}
                        </span>
                      </span>
                      {conversation.unread_count > 0 && (
                        <span
                          className="inbox-unread"
                          aria-label={`${conversation.unread_count} unread`}
                        >
                          {conversation.unread_count}
                        </span>
                      )}
                    </button>
                  ))
                ) : (
                  <Empty
                    title={
                      categoryFilter !== "all" || query
                        ? "No matching conversations"
                        : "No conversations yet"
                    }
                    detail={
                      categoryFilter !== "all" || query
                        ? "Try another category or clear your search."
                        : "Incoming customer messages will appear here."
                    }
                  />
                )}
              </div>
            </section>

            <section
              className="panel inbox-thread-panel"
              aria-label="Message thread"
            >
              {selected ? (
                <>
                  <div className="inbox-thread-header">
                    <span className="inbox-avatar large">
                      <UserRound size={20} />
                    </span>
                    <div>
                      <h2>{selected.customer_name || "Customer"}</h2>
                      <p>{selected.customer_phone}</p>
                    </div>
                    {selected.customer_id ? (
                      <span className="inbox-customer-status matched">
                        <Check size={13} /> Customer linked
                      </span>
                    ) : canOrder ? (
                      <form
                        className="inbox-customer-link"
                        onSubmit={linkCustomer}
                      >
                        <label htmlFor="inbox-link-customer">
                          Link this WhatsApp number
                        </label>
                        <div>
                          <select
                            id="inbox-link-customer"
                            required
                            value={linkCustomerId}
                            onChange={(event) =>
                              setLinkCustomerId(event.target.value)
                            }
                          >
                            <option value="">Choose customer</option>
                            {customers
                              .filter((customer) => customer.active)
                              .map((customer) => (
                                <option key={customer.id} value={customer.id}>
                                  {customer.name}
                                </option>
                              ))}
                          </select>
                          <button
                            className="button-secondary"
                            disabled={!linkCustomerId || busy}
                          >
                            Link
                          </button>
                        </div>
                      </form>
                    ) : (
                      <span className="inbox-customer-status unmatched">
                        Needs customer link
                      </span>
                    )}
                    <span className="inbox-thread-channel">
                      <MessageCircle size={15} />
                      WhatsApp
                    </span>
                  </div>
                  {canOrder && (
                    <div
                      className="inbox-management-actions"
                      aria-label="Manage conversation"
                    >
                      <button
                        className="button"
                        disabled={busy}
                        onClick={() =>
                          void manageConversation({ pinned: !selected.pinned })
                        }
                      >
                        {selected.pinned ? "Unpin chat" : "Pin chat"}
                      </button>
                      <button
                        className="button"
                        disabled={busy}
                        onClick={() =>
                          void manageConversation({
                            archived: !selected.archived,
                          })
                        }
                      >
                        {selected.archived ? "Unarchive chat" : "Archive chat"}
                      </button>
                      <button
                        className="button"
                        disabled={busy}
                        onClick={() =>
                          void manageConversation({ read_state: "unread" })
                        }
                      >
                        Mark unread
                      </button>
                      <button
                        className="button"
                        disabled={busy}
                        onClick={() =>
                          void manageConversation({ read_state: "read" })
                        }
                      >
                        Mark read
                      </button>
                    </div>
                  )}
                  <div className="inbox-messages">
                    {messages
                      .filter((message) =>
                        matchesCategory(message, categoryFilter),
                      )
                      .map((message) => (
                        <article
                          className={`inbox-message${message.direction === "outbound" ? " outbound" : ""}`}
                          key={message.id}
                        >
                          <div className="inbox-bubble">
                            <p>
                              {message.text ||
                                `${message.message_type} message`}
                            </p>
                            {["audio", "image"].includes(
                              message.message_type,
                            ) && (
                              <div
                                className="inbox-category-note"
                                role="status"
                              >
                                {message.transcription_status === "transcribed"
                                  ? `${message.message_type === "image" ? "Image text" : "Voice transcript"} - check names, quantities and prices before confirming.`
                                  : message.transcription_status === "failed"
                                    ? message.transcription_error ||
                                      "Media reading needs attention."
                                    : `${message.message_type === "image" ? "Image" : "Voice note"} received. Reading is queued.`}
                                {message.transcription_status === "failed" &&
                                  canOrder && (
                                    <button
                                      className="text-button"
                                      disabled={busy}
                                      onClick={async () => {
                                        setBusy(true);
                                        setError("");
                                        try {
                                          await api(
                                            `/inbox/messages/${message.id}/transcription/retry`,
                                            orgId,
                                            { method: "POST" },
                                          );
                                          await loadMessages(selectedId);
                                        } catch (error) {
                                          setError((error as Error).message);
                                        } finally {
                                          setBusy(false);
                                        }
                                      }}
                                    >
                                      {message.message_type === "image"
                                        ? "Retry image reading"
                                        : "Retry transcription"}
                                    </button>
                                  )}
                              </div>
                            )}
                            {message.is_simulated && (
                              <span className="inbox-message-label">
                                Synthetic demo
                              </span>
                            )}
                            <time>
                              {new Date(message.sent_at).toLocaleString()}
                            </time>
                            {message.direction === "inbound" && (
                              <div className="inbox-category">
                                <select
                                  aria-label="Message category"
                                  value={message.category || "needs_review"}
                                  disabled={!canOrder || busy}
                                  onChange={async (event) => {
                                    setBusy(true);
                                    setError("");
                                    try {
                                      await api(
                                        `/inbox/messages/${message.id}/category`,
                                        orgId,
                                        {
                                          method: "PUT",
                                          body: JSON.stringify({
                                            category: event.target.value,
                                          }),
                                        },
                                      );
                                      await loadMessages(selectedId);
                                      await refreshInbox();
                                    } catch (error) {
                                      setError((error as Error).message);
                                    } finally {
                                      setBusy(false);
                                    }
                                  }}
                                >
                                  {[
                                    "business_order",
                                    "business_inquiry",
                                    "support",
                                    "personal",
                                    "spam",
                                    "needs_review",
                                  ].map((category) => (
                                    <option key={category} value={category}>
                                      {CATEGORY_LABELS[category] || category}
                                    </option>
                                  ))}
                                </select>
                                <span className="inbox-category-note">
                                  {message.category_reason}
                                </span>
                              </div>
                            )}
                            {message.direction === "outbound" &&
                              message.delivery_status && (
                                <span
                                  className={`inbox-delivery-status ${message.delivery_status}`}
                                >
                                  {message.delivery_status}
                                  {message.delivery_status === "failed" &&
                                  message.delivery_error_code
                                    ? ` · ${message.delivery_error_code}`
                                    : ""}
                                </span>
                              )}
                          </div>
                          {message.extraction_draft_id &&
                            [
                              "business_order",
                              "business_inquiry",
                              "support",
                            ].includes(message.category) && (
                              <div className="inbox-draft-card">
                                <div className="inbox-draft-icon">
                                  <Sparkles size={17} />
                                </div>
                                <div>
                                  <strong>Message extraction ready</strong>
                                  <p>
                                    Review the extracted business details before
                                    accepting a request or creating an order.
                                  </p>
                                </div>
                                <button
                                  className="text-button"
                                  disabled={!canOrder}
                                  onClick={() =>
                                    void reviewDraft(
                                      message.extraction_draft_id!,
                                    )
                                  }
                                >
                                  Review draft <ChevronRight size={15} />
                                </button>
                              </div>
                            )}
                        </article>
                      ))}
                  </div>
                  {canOrder && (
                    <form className="inbox-reply" onSubmit={sendReply}>
                      <label htmlFor="inbox-reply-text">
                        Reply to customer
                      </label>
                      <div className="inbox-reply-row">
                        <textarea
                          id="inbox-reply-text"
                          required
                          maxLength={4096}
                          value={replyText}
                          onChange={(event) => setReplyText(event.target.value)}
                          placeholder="Write a WhatsApp reply…"
                          disabled={replyBusy}
                        />
                        <button
                          className="button-primary"
                          disabled={replyBusy || !replyText.trim()}
                        >
                          <Send size={15} />
                          {replyBusy ? "Sending…" : "Send reply"}
                        </button>
                      </div>
                      {replyError && (
                        <p className="inbox-reply-error" role="alert">
                          {replyError}
                        </p>
                      )}
                      <small>
                        Free-text replies are available within 24 hours of the
                        customer’s latest message. Outside that window, an
                        approved template is required.
                      </small>
                    </form>
                  )}
                  <div className="inbox-thread-note">
                    <ShieldCheck size={16} />
                    Orders are never created automatically. A team member must
                    review and confirm.
                  </div>
                </>
              ) : (
                <div className="inbox-empty-thread">
                  <span className="inbox-empty-icon">
                    <Inbox size={24} />
                  </span>
                  <h2>Select a conversation</h2>
                  <p>
                    Choose a customer thread to review their messages and order
                    drafts.
                  </p>
                </div>
              )}
            </section>
          </div>

          <ConnectWhatsApp
            key={"meta-" + orgId}
            org={orgId}
            allowed={canManage}
            onConnected={() =>
              void refreshInbox().catch((cause: Error) =>
                setError(cause.message),
              )
            }
          />
          {canManage && (
            <details className="panel inbox-developer-tools">
              <summary>Developer testing tools</summary>
              <section className="inbox-setup">
                <div className="inbox-setup-intro">
                  <span className="inbox-setup-icon">
                    <MessageCircle size={19} />
                  </span>
                  <div>
                    <h2>Connect and test WhatsApp</h2>
                    <p>
                      Register a Meta phone number ID for routing, or send a
                      synthetic test message. Simulator messages are clearly
                      marked and are not sent to WhatsApp.
                    </p>
                  </div>
                </div>
                {phones.length > 0 && (
                  <div className="inbox-registered">
                    <span>Registered phone numbers</span>
                    {phones.map((phone) => (
                      <button
                        key={phone.id}
                        className={
                          phoneNumberId === phone.phone_number_id
                            ? "active"
                            : ""
                        }
                        onClick={() => {
                          setPhoneNumberId(phone.phone_number_id);
                          setDisplayPhone(phone.display_phone_number);
                        }}
                      >
                        {phone.display_phone_number}
                        <small>ID {phone.phone_number_id}</small>
                      </button>
                    ))}
                  </div>
                )}
                <div className="inbox-setup-forms">
                  {canManage && (
                    <form className="inbox-form" onSubmit={registerPhone}>
                      <h3>Register phone number</h3>
                      <label>
                        Meta phone number ID
                        <input
                          required
                          inputMode="numeric"
                          pattern="[0-9]+"
                          value={phoneNumberId}
                          onChange={(event) =>
                            setPhoneNumberId(event.target.value)
                          }
                          placeholder="Phone number ID"
                        />
                      </label>
                      <label>
                        Display number
                        <input
                          required
                          value={displayPhone}
                          onChange={(event) =>
                            setDisplayPhone(event.target.value)
                          }
                          placeholder="+94 72 261 6616"
                        />
                      </label>
                      <button className="button-secondary" disabled={busy}>
                        Register number
                      </button>
                    </form>
                  )}
                  <form className="inbox-form" onSubmit={simulateMessage}>
                    <h3>Send a synthetic test message</h3>
                    <label>
                      Registered phone number
                      <select
                        required
                        value={phoneNumberId}
                        onChange={(event) =>
                          setPhoneNumberId(event.target.value)
                        }
                      >
                        <option value="">Select phone number</option>
                        {phones.map((phone) => (
                          <option key={phone.id} value={phone.phone_number_id}>
                            {phone.display_phone_number}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="inbox-form-row">
                      <label>
                        Customer phone
                        <input
                          required
                          pattern="\+?[0-9]{5,40}"
                          value={customerPhone}
                          onChange={(event) =>
                            setCustomerPhone(event.target.value)
                          }
                          placeholder="+94770001122"
                        />
                      </label>
                      <label>
                        Customer name
                        <input
                          value={customerName}
                          onChange={(event) =>
                            setCustomerName(event.target.value)
                          }
                          placeholder="Customer"
                        />
                      </label>
                    </div>
                    <label>
                      Message
                      <textarea
                        required
                        maxLength={10000}
                        value={messageText}
                        onChange={(event) => setMessageText(event.target.value)}
                        placeholder="Rice 2, coconut oil 1..."
                      />
                    </label>
                    <button
                      className="button-primary"
                      disabled={busy || !phones.length || !canOrder}
                    >
                      <Send size={15} />
                      {busy ? "Processing…" : "Send test message"}
                    </button>
                  </form>
                </div>
                {!canManage && !phones.length && (
                  <p className="inbox-permission-note">
                    Ask an owner or admin to register a WhatsApp phone number
                    before testing the inbox.
                  </p>
                )}
                {loading && (
                  <span className="inbox-loading">
                    Refreshing workspace data…
                  </span>
                )}
              </section>
            </details>
          )}
          <footer className="inbox-footer">
            <span>OrderMesh AI · Secure team inbox</span>
            <span>
              Meta webhook connection is not live until configured and verified.
            </span>
          </footer>
        </section>
      </main>

      {modal && orgId && (
        <ModalView
          modal={modal}
          serviceBusiness={["services", "software", "agency"].includes(
            organization?.business_type || "",
          )}
          org={orgId}
          products={products}
          customers={customers}
          onClose={() => setModal(null)}
          onSaved={saved}
        />
      )}
    </div>
  );
}
