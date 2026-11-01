"use client";
import AccountSettings from "../../components/AccountSettings";
import BusinessInsights from "../../components/BusinessInsights";
import Commerce from "../../components/Commerce";
import NotificationCentre from "../../components/NotificationCentre";
import WhatsAppChatbot from "../../components/WhatsAppChatbot";
import PendingWhatsAppOrders from "../../components/PendingWhatsAppOrders";
import type { PendingWhatsAppOrder } from "../../lib/types";
import { wholesaleCategories, categoryLabel } from "../../lib/wholesale";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  ClipboardList,
  CreditCard,
  ShoppingCart,
  Truck,
  Warehouse,
  RotateCcw,
  Download,
  LayoutDashboard,
  LogOut,
  Mail,
  Menu,
  MessageSquareText,
  Moon,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  Phone,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Sun,
  TrendingUp,
  Users,
  WandSparkles,
  X,
} from "lucide-react";
import { api, allPages, money, date } from "../../lib/api";
import type {
  Analytics,
  ServiceSummary,
  Audit,
  Customer,
  Order,
  Product,
  User,
} from "../../lib/types";

type Tab =
  | "Operations"
  | "Overview"
  | "Orders"
  | "Customers"
  | "Inventory"
  | "Service requests"
  | "Order assistant"
  | "Settings"
  | "Business Intelligence";
const nav = [
  { label: "Overview" as Tab, icon: LayoutDashboard },
  { label: "Orders" as Tab, icon: ClipboardList },
  { label: "Operations" as Tab, icon: TrendingUp },
  { label: "Service requests" as Tab, icon: MessageSquareText },
  { label: "Customers" as Tab, icon: Users },
  { label: "Inventory" as Tab, icon: Package },
  { label: "Business Intelligence" as Tab, icon: ShieldCheck },
];

import { useRouter } from "next/navigation";
import ServiceRequests from "../../components/ServiceRequests";
import Assistant from "../../components/Assistant";
import ConnectWhatsApp from "../../components/ConnectWhatsApp";
import IntegrationPanel from "../../components/IntegrationPanel";
import DashboardSettings from "../../components/DashboardSettings";
import BusinessFilterPreview from "../../components/BusinessFilterPreview";
import WorkspaceSetup from "../../components/WorkspaceSetup";
import ModalView, { type Modal } from "../../components/OrderDialog";
import {
  Brand,
  Badge,
  Empty,
  Metric,
  OrderStatusChart,
  SalesChart,
} from "../../components/ui";
import "../dashboard.css";
export default function Dashboard() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null),
    [orgId, setOrgId] = useState(""),
    [boot, setBoot] = useState(true),
    [selectedTab, setTab] = useState<Tab>("Overview"),
    [mobile, setMobile] = useState(false),
    [collapsed, setCollapsed] = useState(false),
    [theme, setTheme] = useState<"dark" | "light">("light");
  const [productCategory, setProductCategory] = useState("all");
  const [productPage, setProductPage] = useState(1);
  const [operationSection, setOperationSection] = useState("POS");
  const operationLinks = [
    { label: "POS", icon: ShoppingCart, manager: false },
    { label: "Purchases", icon: Package, manager: true },
    { label: "Warehouses", icon: Warehouse, manager: true },
    { label: "Returns", icon: RotateCcw, manager: true },
    { label: "Credit & payments", icon: CreditCard, manager: false },
    { label: "Reports & expenses", icon: TrendingUp, manager: true },
    { label: "Delivery", icon: Truck, manager: false },
    { label: "Team", icon: Users, manager: false },
  ];
  const [pendingRequests, setPendingRequests] = useState<
    PendingWhatsAppOrder[]
  >([]);
  const [products, setProducts] = useState<Product[]>([]),
    [customers, setCustomers] = useState<Customer[]>([]),
    [orders, setOrders] = useState<Order[]>([]),
    [analytics, setAnalytics] = useState<Analytics | null>(null),
    [serviceSummary, setServiceSummary] = useState<ServiceSummary | null>(null),
    [audits, setAudits] = useState<Audit[]>([]);
  const [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [query, setQuery] = useState(""),
    [modal, setModal] = useState<Modal>(null),
    [actionBusy, setActionBusy] = useState(false);
  const generation = useRef(0);
  const org = user?.organizations.find((o) => o.id === orgId),
    canManage = org?.role === "owner" || org?.role === "admin",
    canOrder = !!org && org.role !== "viewer";
  const serviceBusiness =
    org?.dashboard?.service_business ??
    ["services", "software", "agency", "salon", "repair"].includes(
      org?.business_type || "",
    );
  const fullBusinessTools = !!org?.dashboard?.full_business_tools;
  const overviewService = serviceBusiness && !fullBusinessTools;
  const moduleForTab: Partial<Record<Tab, string>> = {
    Orders: "orders",
    "Service requests": "service_requests",
    Customers: "customers",
    Inventory: "catalog",
  };
  const enabled = (value: Tab) =>
    value === "Operations"
      ? canOrder && (!serviceBusiness || fullBusinessTools)
      : !moduleForTab[value] ||
        !org?.dashboard ||
        org.dashboard.modules.includes(moduleForTab[value]!);
  const tab = enabled(selectedTab) ? selectedTab : "Overview";
  const tabLabel = (value: Tab) =>
    (
      ({
        Customers: org?.dashboard?.customer_label || "Customers",
        Inventory: serviceBusiness
          ? org?.dashboard?.catalog_label || "Services"
          : "Products & inventory",
        "Service requests": org?.dashboard?.request_label || "Service requests",
        "Order assistant": serviceBusiness ? "AI assistant" : "Order assistant",
      }) as Partial<Record<Tab, string>>
    )[value] || value;
  const loadUser = useCallback(async () => {
    const data = await api<User>("/auth/me");
    setUser(data);
    const saved = localStorage.getItem("ordermesh-org");
    setOrgId(
      data.organizations.some((o) => o.id === saved)
        ? saved!
        : data.organizations[0]?.id || "",
    );
  }, []);
  useEffect(() => {
    setCollapsed(
      localStorage.getItem("ordermesh-sidebar-collapsed") === "true",
    );
    setTheme(
      localStorage.getItem("ordermesh-theme") === "dark" ? "dark" : "light",
    );
  }, []);
  useEffect(() => {
    loadUser()
      .catch(() => {
        setUser(null);
        router.replace("/sign-in");
      })
      .finally(() => setBoot(false));
  }, [loadUser, router]);
  const refresh = useCallback(async () => {
    if (!orgId) return;
    const request = ++generation.current;
    setLoading(true);
    setError("");
    try {
      const results = await Promise.allSettled([
        allPages<Product>("/products", orgId),
        allPages<Customer>("/customers", orgId),
        allPages<Order>("/orders", orgId),
        api<Analytics>("/analytics", orgId),
        api<ServiceSummary>("/dashboard-service-summary", orgId),
        api<PendingWhatsAppOrder[]>("/inbox/order-requests", orgId),
      ] as const);
      if (request !== generation.current) return;
      if (results[0].status === "fulfilled") setProducts(results[0].value);
      if (results[1].status === "fulfilled") setCustomers(results[1].value);
      if (results[2].status === "fulfilled") setOrders(results[2].value);
      if (results[3].status === "fulfilled") setAnalytics(results[3].value);
      if (results[4].status === "fulfilled")
        setServiceSummary(results[4].value);
      if (results[5].status === "fulfilled")
        setPendingRequests(results[5].value);
      const names = [
        "Products",
        "Customers",
        "Orders",
        "Analytics",
        "Service summary",
        "WhatsApp approvals",
      ];
      const failures = results.flatMap((r, i) =>
        r.status === "rejected"
          ? [
              names[i] +
                ": " +
                (r.reason instanceof Error
                  ? r.reason.message
                  : "Could not load"),
            ]
          : [],
      );
      if (failures.length) setError(failures.join(" · "));
      if (canManage) {
        const events = await api<Audit[]>("/audit", orgId);
        if (request === generation.current) setAudits(events);
      }
    } catch (e) {
      if (request === generation.current) setError((e as Error).message);
    } finally {
      if (request === generation.current) setLoading(false);
    }
  }, [orgId, canManage]);
  useEffect(() => {
    setProducts([]);
    setProductCategory("all");
    setProductPage(1);
    setQuery("");
    setCustomers([]);
    setOrders([]);
    setAnalytics(null);
    setServiceSummary(null);
    setPendingRequests([]);
    setAudits([]);
    setModal(null);
    void refresh();
    return () => {
      // Advance the request epoch so results from the previous organization are ignored.
      // eslint-disable-next-line react-hooks/exhaustive-deps
      generation.current++;
    };
  }, [refresh]);
  useEffect(() => {
    if (!orgId) return;
    const timer = setInterval(() => {
      if (!document.hidden && !modal) void refresh();
    }, 15000);
    return () => clearInterval(timer);
  }, [orgId, refresh, modal]);
  useEffect(() => {
    if (notice) {
      const timeout = setTimeout(() => setNotice(""), 5000);
      return () => clearTimeout(timeout);
    }
  }, [notice]);
  function navigate(next: Tab) {
    setTab(next);
    window.history.replaceState(null, "", `#${encodeURIComponent(next)}`);
    if (next === "Overview") void refresh();
    setQuery("");
    setProductPage(1);
    setProductCategory("all");
    setMobile(false);
  }
  function openOperation(section: string) {
    setOperationSection(section);
    setTab("Operations");
    setMobile(false);
    setQuery("");
    window.history.replaceState(
      null,
      "",
      `#Operations/${encodeURIComponent(section)}`,
    );
  }
  async function openProducts() {
    if (!enabled("Inventory") && canManage && org) {
      try {
        await api("/dashboard-preferences", orgId, {
          method: "PUT",
          body: JSON.stringify({
            layout: org.dashboard?.layout || "recommended",
            modules: [
              ...new Set([...(org.dashboard?.modules || []), "catalog"]),
            ],
          }),
        });
        await loadUser();
      } catch (e) {
        setError((e as Error).message);
        return;
      }
    }
    navigate("Inventory");
  }
  useEffect(() => {
    const restore = () => {
      const [name, section] = window.location.hash
        .slice(1)
        .split("/")
        .map((x) => {
          try {
            return decodeURIComponent(x);
          } catch {
            return "";
          }
        });
      if (
        [
          "Overview",
          "Orders",
          "Operations",
          "Customers",
          "Inventory",
          "Service requests",
          "Order assistant",
          "Settings",
          "Business Intelligence",
        ].includes(name)
      ) {
        setTab(name as Tab);
        if (name === "Operations" && section) setOperationSection(section);
      }
    };
    restore();
    window.addEventListener("hashchange", restore);
    return () => window.removeEventListener("hashchange", restore);
  }, []);
  useEffect(() => setProductPage(1), [query, productCategory]);
  async function saved(message: string) {
    setModal(null);
    setNotice(message);
    await refresh();
  }
  async function transition(order: Order, status: "fulfilled" | "cancelled") {
    if (
      status === "cancelled" &&
      !window.confirm("Cancel this order and restore its inventory?")
    )
      return;
    setActionBusy(true);
    try {
      await api(`/orders/${order.id}`, orgId, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await saved(
        status === "fulfilled"
          ? "Order marked as fulfilled."
          : "Order cancelled. Stock restored.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setActionBusy(false);
    }
  }
  async function invoice(order: Order) {
    setActionBusy(true);
    try {
      const res = await fetch(`/api/orders/${order.id}/invoice`, {
        headers: { "X-Organization-ID": orgId },
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail);
      }
      const url = URL.createObjectURL(await res.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = `invoice-${order.id}.pdf`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setActionBusy(false);
    }
  }
  if (boot)
    return (
      <div className="boot">
        <Brand />
        <p>Opening your workspace…</p>
      </div>
    );
  if (!user)
    return (
      <div className="boot">
        <Brand />
        <p>Opening sign in?</p>
      </div>
    );
  const matchingOrders = orders.filter((o) =>
    `${o.id} ${o.customer_name} ${o.status}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const matchingProducts = products.filter(
    (p) =>
      (productCategory === "all" ||
        (p.category || "other") === productCategory) &&
      `${p.name} ${p.sku} ${p.barcode || ""} ${p.aliases.join(" ")} ${categoryLabel(p.category)}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const productPages = Math.max(1, Math.ceil(matchingProducts.length / 50));
  const currentProductPage = Math.min(productPage, productPages);
  const visibleProducts = matchingProducts.slice(
    (currentProductPage - 1) * 50,
    currentProductPage * 50,
  );
  const matchingCustomers = customers.filter((c) =>
    `${c.name} ${c.phone}`.toLowerCase().includes(query.toLowerCase()),
  );
  const lowStock = products.filter(
    (p) => p.active && p.track_stock && p.stock <= p.reorder_level,
  );
  const today = new Date().toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Asia/Colombo",
  });
  function OrderTable({
    rows,
    compact = false,
  }: {
    rows: Order[];
    compact?: boolean;
  }) {
    return rows.length ? (
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Order</th>
              <th>Customer</th>
              <th>Status</th>
              <th>Amount</th>
              {!compact && <th>Date</th>}
              <th>
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((o) => (
              <tr key={o.id}>
                <td>
                  <span className="order-id">
                    #{o.id.slice(0, 8).toUpperCase()}
                  </span>
                  <small>
                    {o.draft_id ? "Assisted order" : "Manual order"}
                  </small>
                </td>
                <td>{o.customer_name}</td>
                <td>
                  <Badge
                    kind={
                      o.status === "fulfilled"
                        ? "mint"
                        : o.status === "confirmed"
                          ? "amber"
                          : "neutral"
                    }
                  >
                    <span className="dot" />
                    {o.status === "confirmed"
                      ? "To fulfill"
                      : o.status === "fulfilled"
                        ? "Fulfilled"
                        : "Cancelled"}
                  </Badge>
                </td>
                <td className="number">{money(o.total_minor)}</td>
                {!compact && <td className="muted">{date(o.created_at)}</td>}
                <td>
                  <div className="row-actions">
                    <button
                      className="icon-button"
                      title="Download invoice"
                      aria-label={`Download invoice ${o.id.slice(0, 8)}`}
                      disabled={actionBusy}
                      onClick={() => invoice(o)}
                    >
                      <Download size={16} />
                    </button>
                    {!compact && canOrder && o.status === "confirmed" && (
                      <>
                        <button
                          className="text-button"
                          disabled={actionBusy}
                          onClick={() => transition(o, "fulfilled")}
                        >
                          Fulfill
                        </button>
                        <button
                          className="icon-button"
                          title="Cancel order"
                          aria-label={`Cancel order ${o.id.slice(0, 8)}`}
                          disabled={actionBusy}
                          onClick={() => transition(o, "cancelled")}
                        >
                          <X size={16} />
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    ) : (
      <Empty
        title="Your next order starts here"
        detail="Create an order or review a customer message to get started."
      />
    );
  }
  return (
    <div
      className={`app-shell${collapsed ? " sidebar-collapsed" : ""}`}
      data-theme={theme}
    >
      <aside className={`sidebar ${mobile ? "mobile-open" : ""}`}>
        <div className="sidebar-brand-row">
          <Brand />
          <button
            className="icon-button sidebar-collapse"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={() => {
              const next = !collapsed;
              setCollapsed(next);
              localStorage.setItem("ordermesh-sidebar-collapsed", String(next));
            }}
          >
            {collapsed ? (
              <PanelLeftOpen size={17} />
            ) : (
              <PanelLeftClose size={17} />
            )}
          </button>
        </div>
        <span className="nav-caption">WORKSPACE</span>
        <nav>
          {nav
            .filter(
              (n) =>
                enabled(n.label) ||
                (n.label === "Inventory" && canManage && !serviceBusiness),
            )
            .map((n) => (
              <button
                key={n.label}
                className={tab === n.label ? "active" : ""}
                aria-label={tabLabel(n.label)}
                title={tabLabel(n.label)}
                onClick={() =>
                  n.label === "Inventory"
                    ? void openProducts()
                    : navigate(n.label)
                }
              >
                <n.icon size={19} />
                <span className="nav-label">{tabLabel(n.label)}</span>
                {n.label === "Orders" &&
                  !!(
                    (analytics?.pending_orders || 0) +
                    (analytics?.pending_approvals || 0)
                  ) && (
                    <span className="nav-count">
                      {(analytics?.pending_orders || 0) +
                        (analytics?.pending_approvals || 0)}
                    </span>
                  )}
              </button>
            ))}
          {enabled("Operations") && (
            <>
              <span className="nav-caption">SALES & OPERATIONS</span>
              {operationLinks
                .filter((item) => !item.manager || canManage)
                .map((item) => (
                  <button
                    key={item.label}
                    className={
                      tab === "Operations" && operationSection === item.label
                        ? "active"
                        : ""
                    }
                    aria-label={`Open ${item.label}`}
                    title={item.label}
                    onClick={() => openOperation(item.label)}
                  >
                    <item.icon size={18} />
                    <span className="nav-label">{item.label}</span>
                  </button>
                ))}
            </>
          )}
          <span className="nav-caption assistant-caption">INTELLIGENCE</span>
          <button
            aria-label="WhatsApp inbox"
            title="WhatsApp inbox"
            onClick={() => router.push("/dashboard/inbox")}
          >
            <MessageSquareText size={19} />
            <span className="nav-label">WhatsApp inbox</span>
          </button>
          <button
            className={tab === "Order assistant" ? "active" : ""}
            aria-label={tabLabel("Order assistant")}
            title={tabLabel("Order assistant")}
            onClick={() => navigate("Order assistant")}
          >
            <Sparkles size={19} />
            <span className="nav-label">{tabLabel("Order assistant")}</span>
            <Badge kind="mint">BETA</Badge>
          </button>
        </nav>
        <div className="sidebar-bottom">
          <div className="plan-card">
            <div>
              <span className="plan-dot" />
              OrderMesh AI Lite
            </div>
            <p>LKR 7,400 / month - 15-day free trial</p>
            <button onClick={() => navigate("Settings")}>
              View workspace plan <ArrowUpRight size={15} />
            </button>
          </div>
          <button
            className={`settings-link ${tab === "Settings" ? "active" : ""}`}
            aria-label="Settings"
            title="Settings"
            onClick={() => navigate("Settings")}
          >
            <Settings2 size={18} />
            <span className="nav-label">Settings</span>
          </button>
          <div className="sidebar-credit">
            <span className="qubriant-mark">Q</span>
            <span>
              by <strong>Qubriant</strong>
              <small>TECHNOLOGIES</small>
            </span>
          </div>
        </div>
      </aside>
      {mobile && (
        <button
          className="sidebar-backdrop"
          aria-label="Close menu"
          onClick={() => setMobile(false)}
        />
      )}
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Open menu"
              onClick={() => setMobile(true)}
            >
              <Menu size={21} />
            </button>
            <span>Workspace</span>
            <span className="slash">/</span>
            <strong>{tab}</strong>
          </div>
          <div className="workspace-picker topbar-workspace-picker">
            <span className="workspace-avatar">
              {org?.name.slice(0, 1) || "O"}
            </span>
            <div>
              <small>YOUR WORKSPACE</small>
              <select
                aria-label="Organization"
                value={orgId}
                onChange={(e) => {
                  localStorage.setItem("ordermesh-org", e.target.value);
                  setOrgId(e.target.value);
                }}
              >
                {user.organizations.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </select>
            </div>
            <ChevronDown size={14} />
          </div>
          <div className="topbar-right">
            <label className="topbar-search">
              <Search size={16} />
              <input
                aria-label="Search orders"
                placeholder="Search orders…"
                value={tab === "Orders" ? query : ""}
                onFocus={() => {
                  if (tab !== "Orders") setTab("Orders");
                }}
                onChange={(event) => {
                  setTab("Orders");
                  setQuery(event.target.value);
                }}
              />
              <kbd>/</kbd>
            </label>
            {tab !== "Overview" && (
              <span className="connection">
                <span />
                Workspace connected
              </span>
            )}
            <NotificationCentre
              key={`alerts-${orgId}`}
              org={orgId}
              userId={user.id}
              onNavigate={(target) => {
                if (target === "WhatsApp inbox")
                  router.push("/dashboard/inbox");
                else if (enabled(target as Tab)) navigate(target as Tab);
                else {
                  navigate("Settings");
                  setNotice(
                    "Enable this section in your dashboard layout to open the alert record.",
                  );
                }
              }}
            />
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
            <button
              className="icon-button"
              aria-label="Workspace help"
              onClick={() => navigate("Settings")}
            >
              <CircleHelp size={18} />
            </button>
            {tab !== "Overview" && (
              <div className="profile">
                <span className="avatar">
                  {user.name
                    .split(" ")
                    .map((n) => n[0])
                    .slice(0, 2)
                    .join("")}
                </span>
                <div>
                  <strong>{user.name}</strong>
                  <small>{org?.role || "Member"}</small>
                </div>
              </div>
            )}
            <button
              className="icon-button"
              aria-label="Sign out"
              onClick={async () => {
                try {
                  await api("/auth/logout", undefined, { method: "POST" });
                  generation.current++;
                  setUser(null);
                  setOrgId("");
                  router.replace("/sign-in");
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              <LogOut size={17} />
            </button>
          </div>
        </header>
        <main className="main-content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                {tab === "Overview"
                  ? "A LITTLE CLARITY FOR YOUR EVERYDAY"
                  : "YOUR BUSINESS, IN SYNC"}
              </span>
              <h1>
                {tab === "Overview" ? "Business at a glance" : tabLabel(tab)}
              </h1>
              <p>
                {
                  {
                    Overview:
                      "Here’s what’s happening with your business today.",
                    Operations: "Sales, stock and distribution",
                    Orders: "Every order, from confirmation to fulfillment.",
                    Customers:
                      "Better relationships start with a connected customer list.",
                    Inventory: overviewService
                      ? "Your services, pricing and customer offerings."
                      : org?.business_type === "restaurant"
                        ? "Manage menu items, pricing and availability."
                        : "Know what’s on hand. Stay ahead of what’s running low.",
                    "Order assistant":
                      "Turn customer messages into orders you can trust.",
                    "Service requests":
                      "Project requirements, budgets, deadlines and appointments for team review.",
                    Settings: "Your workspace, access and connected services.",
                    "Business Intelligence":
                      "Your business context, target clients and message filtering examples.",
                  }[tab]
                }
              </p>
            </div>
            <div className="heading-actions">
              {tab === "Overview" && (
                <span className="date-label">{today}</span>
              )}
              {canOrder &&
                enabled("Orders") &&
                (tab === "Overview" || tab === "Orders") && (
                  <button
                    className="button primary"
                    onClick={() => setModal({ type: "order" })}
                  >
                    <Plus size={17} />
                    New order
                  </button>
                )}
              {canOrder &&
                overviewService &&
                enabled("Service requests") &&
                tab === "Overview" && (
                  <button
                    className="button primary"
                    onClick={() => navigate("Service requests")}
                  >
                    Review {tabLabel("Service requests").toLowerCase()}
                  </button>
                )}
              {canManage && tab === "Customers" && (
                <button
                  className="button primary"
                  onClick={() => setModal({ type: "customer" })}
                >
                  <Plus size={17} />
                  Add customer
                </button>
              )}
              {canManage && tab === "Inventory" && (
                <button
                  className="button primary"
                  onClick={() => setModal({ type: "product" })}
                >
                  <Plus size={17} />
                  {overviewService ? "Add service" : "Add product"}
                </button>
              )}
            </div>
          </div>
          {org &&
            (org.subscription_status === "trial"
              ? org.trial_ends_at
              : org.paid_until) &&
            new Date(
              (org.subscription_status === "trial"
                ? org.trial_ends_at
                : org.paid_until)!,
            ).getTime() <= Date.now() && (
              <div className="business-onboarding-note">
                <div>
                  <strong>Your subscription period has ended</strong>
                  <p>
                    Your existing records remain available. Renew to create or
                    update business records.
                  </p>
                </div>
                <button className="button" onClick={() => navigate("Settings")}>
                  Manage subscription
                </button>
              </div>
            )}
          {error && (
            <div className="alert" role="alert">
              {error}
              <button onClick={() => void refresh()}>Retry</button>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="toast" role="status">
              <CheckCircle2 size={18} />
              {notice}
            </div>
          )}
          {loading && (
            <div className="loading-line" role="status">
              Updating workspace…
            </div>
          )}
          {tab === "Operations" && org && (
            <Commerce
              key={orgId}
              org={orgId}
              role={org.role}
              section={operationSection}
              onSectionChange={openOperation}
              onChanged={async () => {
                await refresh();
              }}
            />
          )}
          {tab === "Inventory" && (
            <div className="catalog-context">
              <div>
                <strong>
                  {products.length.toLocaleString()} catalog items in{" "}
                  {org?.name}
                </strong>
                <p>
                  Products and stock are specific to this workspace. Search by
                  name, SKU, barcode or part number.
                </p>
              </div>
              {!enabled("Inventory") && (
                <span>Catalog is disabled in workspace preferences.</span>
              )}
            </div>
          )}
          {tab === "Overview" && !org?.business_profile?.description && (
            <div className="business-onboarding-note">
              <div>
                <strong>Make this workspace fit your business</strong>
                <p>
                  Add your business profile to tailor the dashboard and help
                  route WhatsApp messages.
                </p>
              </div>
              <button
                className="button"
                onClick={() => navigate("Business Intelligence")}
              >
                Set up my business
              </button>
            </div>
          )}
          {tab === "Overview" && (
            <>
              <div className="metrics">
                {enabled(overviewService ? "Service requests" : "Orders") && (
                  <Metric
                    label={
                      overviewService
                        ? "Service requests received"
                        : "Total order value"
                    }
                    value={
                      overviewService
                        ? String(serviceSummary?.total ?? 0)
                        : analytics
                          ? money(analytics.sales_minor)
                          : "—"
                    }
                    note={
                      analytics
                        ? overviewService
                          ? "Customer requests, including closed requests"
                          : "Excludes cancelled orders"
                        : "Waiting for workspace data"
                    }
                    icon={<TrendingUp />}
                    color="green"
                  />
                )}
                {enabled(overviewService ? "Service requests" : "Orders") && (
                  <Metric
                    label={
                      overviewService ? "Awaiting review" : "Orders received"
                    }
                    value={
                      overviewService
                        ? String(serviceSummary?.pending_review ?? 0)
                        : analytics
                          ? String(analytics.order_count)
                          : "—"
                    }
                    note={
                      analytics
                        ? overviewService
                          ? `${serviceSummary?.accepted ?? 0} accepted requests`
                          : `${analytics.pending_orders} orders ready to fulfill`
                        : "Waiting for workspace data"
                    }
                    icon={<ClipboardList />}
                    color="blue"
                  />
                )}
                {enabled("Customers") && (
                  <Metric
                    label={`Active ${tabLabel("Customers").toLowerCase()}`}
                    value={analytics ? String(analytics.customer_count) : "—"}
                    note={
                      analytics
                        ? "Across your organization"
                        : "Waiting for workspace data"
                    }
                    icon={<Users />}
                    color="purple"
                  />
                )}
                {enabled("Inventory") && (
                  <Metric
                    label={
                      overviewService
                        ? "Service offerings"
                        : "Low-stock products"
                    }
                    value={
                      overviewService
                        ? String(products.filter((p) => p.active).length)
                        : analytics
                          ? String(analytics.low_stock_count)
                          : "—"
                    }
                    note={
                      analytics
                        ? overviewService
                          ? "Active services in your catalog"
                          : "At or below reorder level"
                        : "Waiting for workspace data"
                    }
                    icon={<Package />}
                    color="orange"
                  />
                )}
              </div>
              {canManage && !overviewService && (
                <BusinessInsights
                  key={orgId}
                  org={orgId}
                  onProducts={() => void openProducts()}
                  onReports={() => openOperation("Reports & expenses")}
                />
              )}
              <div className="overview-middle">
                <div className="overview-primary">
                  {enabled(overviewService ? "Service requests" : "Orders") &&
                    (overviewService ? (
                      <section className="panel padded">
                        <h2>{tabLabel("Service requests")} overview</h2>
                        <p className="muted">
                          Review requirements, budget, deadlines and appointment
                          preferences before accepting work.
                        </p>
                        <dl>
                          <dt>Accepted requests</dt>
                          <dd>{serviceSummary?.accepted ?? 0}</dd>
                          <dt>Completed requests</dt>
                          <dd>{serviceSummary?.completed ?? 0}</dd>
                        </dl>
                        {enabled("Service requests") && (
                          <button
                            className="button"
                            onClick={() => navigate("Service requests")}
                          >
                            Open {tabLabel("Service requests").toLowerCase()}
                          </button>
                        )}
                      </section>
                    ) : (
                      <section className="panel sales-panel">
                        <div className="panel-heading">
                          <div>
                            <h2>Sales trend</h2>
                            <p>Daily sales over the last 7 days</p>
                          </div>
                          <Badge>
                            Last 7 days <ChevronDown size={12} />
                          </Badge>
                        </div>
                        <div className="chart-total">
                          {analytics
                            ? money(
                                analytics.daily_sales.reduce(
                                  (s, d) => s + d.total_minor,
                                  0,
                                ),
                              )
                            : "—"}
                          <span>
                            <span className="legend-dot" />
                            Confirmed and fulfilled sales
                          </span>
                        </div>
                        <SalesChart data={analytics?.daily_sales || []} />
                      </section>
                    ))}
                </div>
                <aside
                  className="overview-side"
                  aria-label="Quick business actions"
                >
                  {!overviewService && enabled("Orders") && (
                    <section className="panel overview-approval-card">
                      <div className="panel-heading">
                        <div>
                          <h2>WhatsApp approvals</h2>
                          <p>
                            {pendingRequests.length
                              ? `${pendingRequests.length} customer ${
                                  pendingRequests.length === 1
                                    ? "request needs"
                                    : "requests need"
                                } review`
                              : "No requests waiting for approval"}
                          </p>
                        </div>
                        <span className="count-circle">
                          {pendingRequests.length}
                        </span>
                      </div>
                      <button
                        className="button primary"
                        onClick={() => navigate("Orders")}
                      >
                        Review WhatsApp orders <ArrowRight size={16} />
                      </button>
                    </section>
                  )}
                  <section className="panel overview-quick-actions">
                    <div className="panel-heading">
                      <div>
                        <h2>Quick actions</h2>
                        <p>Common tasks for your workspace</p>
                      </div>
                    </div>
                    <div className="overview-action-list">
                      {canOrder && enabled("Orders") && (
                        <button
                          className="button primary"
                          onClick={() => setModal({ type: "order" })}
                        >
                          <Plus size={16} />
                          New order
                        </button>
                      )}
                      {canOrder && !overviewService && (
                        <button
                          className="button"
                          onClick={() => openOperation("POS")}
                        >
                          <ClipboardList size={16} />
                          Open POS
                        </button>
                      )}
                      {canOrder &&
                        overviewService &&
                        enabled("Service requests") && (
                          <button
                            className="button"
                            onClick={() => navigate("Service requests")}
                          >
                            <ClipboardList size={16} />
                            Review requests
                          </button>
                        )}
                    </div>
                  </section>
                </aside>
              </div>
              {tab === "Overview" && (
                <section
                  className="panel workspace-tools"
                  aria-label="Workspace tools"
                >
                  <div className="section-heading">
                    <div>
                      <h2>Your workspace tools</h2>
                      <p className="muted">
                        Open the feature you need. Records belong to the
                        workspace selected above.
                      </p>
                    </div>
                    <span className="workspace-context">{org?.name}</span>
                  </div>
                  <div className="workspace-tool-grid">
                    {(enabled("Inventory") ||
                      (canManage && !overviewService)) && (
                      <button
                        className="workspace-tool"
                        onClick={() => void openProducts()}
                      >
                        <Package size={21} />
                        <strong>
                          {overviewService
                            ? "Services"
                            : "Products & inventory"}
                        </strong>
                        <span>
                          {products.length.toLocaleString()} catalog items ·
                          prices, barcodes and stock
                        </span>
                      </button>
                    )}
                    {enabled("Orders") && (
                      <button
                        className="workspace-tool"
                        onClick={() => navigate("Orders")}
                      >
                        <ClipboardList size={21} />
                        <strong>Orders & invoices</strong>
                        <span>
                          {orders.length} orders · review WhatsApp requests and
                          download invoices
                        </span>
                      </button>
                    )}
                    {enabled("Customers") && (
                      <button
                        className="workspace-tool"
                        onClick={() => navigate("Customers")}
                      >
                        <Users size={21} />
                        <strong>{tabLabel("Customers")}</strong>
                        <span>
                          {customers.length} records · contacts, credit limits
                          and terms
                        </span>
                      </button>
                    )}
                    {enabled("Operations") &&
                      operationLinks
                        .filter((item) => !item.manager || canManage)
                        .map((item) => (
                          <button
                            className="workspace-tool"
                            key={item.label}
                            onClick={() => openOperation(item.label)}
                          >
                            <item.icon size={21} />
                            <strong>{item.label}</strong>
                            <span>
                              {
                                {
                                  POS: "Counter sales and payment records",
                                  Purchases:
                                    "Suppliers, purchase orders and goods received",
                                  Warehouses: "Balances and stock transfers",
                                  Returns: "Return stock and customer refunds",
                                  "Credit & payments":
                                    "Balances, payment records and aging",
                                  "Reports & expenses":
                                    "Sales, costs, profit and operating expenses",
                                  Delivery:
                                    "Delivery status and staff assignment",
                                  Team: "Workspace members and access",
                                }[item.label]
                              }
                            </span>
                          </button>
                        ))}
                    <button
                      className="workspace-tool"
                      onClick={() => router.push("/dashboard/inbox")}
                    >
                      <MessageSquareText size={21} />
                      <strong>WhatsApp inbox</strong>
                      <span>
                        Incoming messages, category filters and replies
                      </span>
                    </button>
                    <button
                      className="workspace-tool"
                      onClick={() => navigate("Business Intelligence")}
                    >
                      <ShieldCheck size={21} />
                      <strong>Business Intelligence</strong>
                      <span>
                        Business questions and private/spam filtering context
                      </span>
                    </button>
                    <button
                      className="workspace-tool"
                      onClick={() => navigate("Settings")}
                    >
                      <Settings2 size={21} />
                      <strong>WhatsApp & workspace settings</strong>
                      <span>
                        Number connection, chatbot, billing and dashboard
                        preferences
                      </span>
                    </button>
                    <button
                      className="workspace-tool"
                      onClick={() => navigate("Order assistant")}
                    >
                      <WandSparkles size={21} />
                      <strong>{tabLabel("Order assistant")}</strong>
                      <span>
                        Text, voice and image extraction for human review
                      </span>
                    </button>
                  </div>
                </section>
              )}

              <div className="overview-bottom">
                {enabled(overviewService ? "Service requests" : "Orders") && (
                  <section className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2>
                          {overviewService
                            ? "Your client workflow"
                            : "Recent orders"}
                        </h2>
                        <p>Your latest customer activity</p>
                      </div>
                      <button
                        className="text-button"
                        onClick={() =>
                          navigate(
                            overviewService ? "Service requests" : "Orders",
                          )
                        }
                        disabled={
                          !enabled(
                            overviewService ? "Service requests" : "Orders",
                          )
                        }
                      >
                        {overviewService ? "View requests" : "View all orders"}{" "}
                        <ArrowRight size={14} />
                      </button>
                    </div>
                    {overviewService ? (
                      <Empty
                        title="Keep every request in context"
                        detail="Client requirements, budget and deadline stay with the original message. Accepting a request does not create an order or calendar booking."
                      />
                    ) : (
                      <OrderTable rows={orders.slice(0, 5)} compact />
                    )}
                  </section>
                )}
                <aside className="overview-lower-side">
                  {enabled("Inventory") && (
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h2>
                            {overviewService
                              ? "Service catalog"
                              : "Stock watch"}
                          </h2>
                          <p>A little attention goes a long way</p>
                        </div>
                        <span className="count-circle">
                          {
                            (overviewService
                              ? products.filter((p) => p.active)
                              : lowStock
                            ).length
                          }
                        </span>
                      </div>
                      {(overviewService
                        ? products.filter((p) => p.active)
                        : lowStock
                      ).length ? (
                        <div className="stock-list">
                          {(overviewService
                            ? products.filter((p) => p.active)
                            : lowStock
                          )
                            .slice(0, 4)
                            .map((p) => (
                              <div className="stock-item" key={p.id}>
                                <span className="product-icon">
                                  <Package size={18} />
                                </span>
                                <div>
                                  <strong>{p.name}</strong>
                                  <small>{p.sku}</small>
                                </div>
                                <span className="stock-qty">
                                  {overviewService
                                    ? money(p.price_minor)
                                    : p.stock}{" "}
                                  <small>
                                    {overviewService
                                      ? `per ${p.unit}`
                                      : `${p.unit} left`}
                                  </small>
                                </span>
                              </div>
                            ))}
                        </div>
                      ) : (
                        <Empty
                          title={
                            overviewService
                              ? "Ready for your next client"
                              : "Stock is looking good"
                          }
                          detail={
                            overviewService
                              ? "Add services to your catalog, then review client inquiries in the WhatsApp inbox."
                              : "Products at their reorder level will appear here."
                          }
                        />
                      )}
                      <button
                        className="panel-footer"
                        onClick={() => navigate("Inventory")}
                        disabled={!enabled("Inventory")}
                      >
                        {overviewService
                          ? "Manage services"
                          : "Manage inventory"}{" "}
                        <ArrowRight size={15} />
                      </button>
                    </section>
                  )}
                  {!overviewService && enabled("Orders") && (
                    <section className="panel order-status-panel">
                      <div className="panel-heading">
                        <div>
                          <h2>Order status</h2>
                          <p>Orders by their current status</p>
                        </div>
                      </div>
                      <OrderStatusChart orders={orders} />
                    </section>
                  )}
                </aside>
              </div>
            </>
          )}
          {(tab === "Orders" || tab === "Inventory" || tab === "Customers") && (
            <section className="panel">
              <div className="list-toolbar">
                <div>
                  <h2>
                    {tab === "Orders"
                      ? "All orders"
                      : tab === "Inventory"
                        ? `${tabLabel("Inventory")} catalog`
                        : `${tabLabel("Customers")} directory`}{" "}
                    <span className="light-count">
                      {tab === "Orders"
                        ? orders.length
                        : tab === "Inventory"
                          ? products.length
                          : customers.length}
                    </span>
                  </h2>
                  <p>
                    {tab === "Inventory"
                      ? "Stock is updated automatically when orders are confirmed."
                      : "Only records in your current workspace are shown."}
                  </p>
                </div>
                <div className="toolbar-actions">
                  {tab === "Inventory" && (
                    <label className="field">
                      Product category
                      <select
                        aria-label="Filter product category"
                        value={productCategory}
                        onChange={(event) =>
                          setProductCategory(event.target.value)
                        }
                      >
                        <option value="all">All categories</option>
                        {wholesaleCategories.map((category) => (
                          <option key={category.value} value={category.value}>
                            {category.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  <label className="search">
                    <Search size={17} />
                    <input
                      aria-label={`Search ${tab.toLowerCase()}`}
                      placeholder={`Search ${tab.toLowerCase()}…`}
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </label>
                  <button
                    className="icon-button"
                    aria-label="Refresh records"
                    onClick={() => void refresh()}
                  >
                    <RefreshCw size={17} />
                  </button>
                </div>
              </div>
              {tab === "Orders" && (
                <>
                  <PendingWhatsAppOrders
                    org={orgId}
                    rows={pendingRequests}
                    canApprove={canManage}
                    onReview={(draft) => setModal({ type: "order", draft })}
                    onChanged={refresh}
                  />
                  <OrderTable rows={matchingOrders} />
                </>
              )}
              {tab === "Inventory" &&
                (matchingProducts.length ? (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Product</th>
                          <th>SKU</th>
                          <th>Category</th>
                          <th>Unit price</th>
                          <th>On hand</th>
                          <th>Status</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visibleProducts.map((p) => (
                          <tr key={p.id}>
                            <td>
                              <strong>{p.name}</strong>
                              <small>{p.aliases.join(" · ") || p.unit}</small>
                            </td>
                            <td className="muted">{p.sku}</td>
                            <td>{categoryLabel(p.category)}</td>
                            <td>
                              {money(p.price_minor)} / {p.unit}
                            </td>
                            <td>
                              <strong>
                                {p.track_stock ? p.stock : "Not tracked"}
                              </strong>{" "}
                              <span className="muted">{p.unit}</span>
                            </td>
                            <td>
                              <Badge
                                kind={
                                  !p.active
                                    ? "neutral"
                                    : p.stock <= p.reorder_level
                                      ? "amber"
                                      : "mint"
                                }
                              >
                                {!p.active
                                  ? "Archived"
                                  : !p.track_stock
                                    ? "Service"
                                    : p.stock <= p.reorder_level
                                      ? "Low stock"
                                      : "In stock"}
                              </Badge>
                            </td>
                            <td>
                              {canManage && (
                                <div className="row-actions">
                                  {p.track_stock && (
                                    <button
                                      className="text-button"
                                      onClick={() =>
                                        setModal({ type: "stock", item: p })
                                      }
                                    >
                                      Adjust stock
                                    </button>
                                  )}
                                  <button
                                    className="text-button muted"
                                    onClick={() =>
                                      setModal({ type: "product", item: p })
                                    }
                                  >
                                    Edit
                                  </button>
                                </div>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <div
                      className="catalog-pagination"
                      aria-label="Product pages"
                    >
                      <span>
                        Showing {(currentProductPage - 1) * 50 + 1}–
                        {Math.min(
                          currentProductPage * 50,
                          matchingProducts.length,
                        )}{" "}
                        of {matchingProducts.length.toLocaleString()} matching
                        products
                      </span>
                      <div>
                        <button
                          className="button secondary"
                          disabled={currentProductPage === 1}
                          onClick={() => setProductPage(currentProductPage - 1)}
                        >
                          Previous products
                        </button>
                        <span>
                          Page {currentProductPage} / {productPages}
                        </span>
                        <button
                          className="button secondary"
                          disabled={currentProductPage === productPages}
                          onClick={() => setProductPage(currentProductPage + 1)}
                        >
                          Next products
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <Empty
                    title={
                      products.length
                        ? "No matching products"
                        : "No products yet"
                    }
                    detail={
                      products.length
                        ? "Choose another category or clear your search."
                        : "Add your catalog, then record opening stock to start taking orders."
                    }
                  />
                ))}
              {tab === "Customers" &&
                (matchingCustomers.length ? (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Customer</th>
                          <th>Phone</th>
                          <th>Address</th>
                          <th>Status</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {matchingCustomers.map((c) => (
                          <tr key={c.id}>
                            <td>
                              <div className="customer-name">
                                <span className="customer-avatar">
                                  {c.name[0]}
                                </span>
                                <strong>{c.name}</strong>
                              </div>
                            </td>
                            <td>{c.phone || "—"}</td>
                            <td className="address-cell">{c.address || "—"}</td>
                            <td>
                              <Badge kind={c.active ? "mint" : "neutral"}>
                                {c.active ? "Active" : "Archived"}
                              </Badge>
                            </td>
                            <td>
                              {canManage && (
                                <button
                                  className="text-button"
                                  onClick={() =>
                                    setModal({ type: "customer", item: c })
                                  }
                                >
                                  Edit customer
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <Empty
                    title="Make room for your customers"
                    detail="Add your first customer to create an order for their business."
                  />
                ))}
            </section>
          )}
          {tab === "Order assistant" && (
            <Assistant
              serviceBusiness={serviceBusiness}
              key={orgId}
              org={orgId}
              allowed={canOrder}
              onReview={(draft) => setModal({ type: "order", draft })}
            />
          )}
          {tab === "Service requests" && (
            <ServiceRequests key={orgId} org={orgId} allowed={canOrder} />
          )}
          {tab === "Business Intelligence" && (
            <>
              <WorkspaceSetup
                key={`intelligence-${orgId}`}
                org={orgId}
                canManage={canManage}
                owner={org?.role === "owner"}
                onChanged={loadUser}
                showBilling={false}
              />
              <BusinessFilterPreview key={`preview-${orgId}`} org={orgId} />
            </>
          )}
          {tab === "Settings" && (
            <div className="settings-grid">
              <AccountSettings
                key={`account-${orgId}`}
                org={orgId}
                canManage={canManage}
                onChanged={loadUser}
              />
              {canManage && (
                <WhatsAppChatbot key={`bot-${orgId}`} org={orgId} />
              )}
              <ConnectWhatsApp
                key={"meta-" + orgId}
                org={orgId}
                allowed={canManage}
              />
              <section className="panel padded">
                <span className="icon-tile">
                  <ShieldCheck />
                </span>
                <h2>Workspace & access</h2>
                <dl>
                  <dt>Organization</dt>
                  <dd>{org?.name}</dd>
                  <dt>Your role</dt>
                  <dd className="capitalize">{org?.role}</dd>
                  <dt>Email</dt>
                  <dd>{user.email}</dd>
                  <dt>Currency / time zone</dt>
                  <dd>LKR · Asia/Colombo</dd>
                </dl>
                <p className="muted">
                  Membership is checked on every request. Owner and admin roles
                  manage catalog and stock. Staff can process orders; viewers
                  have read-only access.
                </p>
              </section>
              <section className="panel padded">
                <h2>Business Intelligence</h2>
                <p className="muted">
                  Manage business details, target customers and message
                  classification in the dedicated Business Intelligence section.
                </p>
                <button
                  className="button"
                  onClick={() => navigate("Business Intelligence")}
                >
                  Open Business Intelligence
                </button>
                <a className="button" href="/dashboard/inbox">
                  Manage WhatsApp inbox
                </a>
              </section>
              <DashboardSettings
                key={`dashboard-${orgId}-${org?.business_type}`}
                org={orgId}
                canManage={canManage}
                onChanged={loadUser}
              />
              <details className="panel padded">
                <summary>Business workflow & subscription</summary>
                <WorkspaceSetup
                  key={`advanced-setup-${orgId}`}
                  org={orgId}
                  canManage={canManage}
                  owner={org?.role === "owner"}
                  onChanged={loadUser}
                />
              </details>
              <IntegrationPanel key={orgId} org={orgId} />
              <section className="panel padded">
                <h2>Recent audit activity</h2>
                <p className="muted">
                  {canManage
                    ? "Latest 100 workspace events."
                    : "Audit events are available to owners and admins."}
                </p>
                {canManage &&
                  (audits.length ? (
                    <div className="audit-list">
                      {audits.slice(0, 8).map((a) => (
                        <div key={a.id}>
                          <Activity size={15} />
                          <span>
                            <strong>{a.action.replaceAll(".", " · ")}</strong>
                            <small>
                              {a.entity_id.slice(0, 8)} · {date(a.created_at)}
                            </small>
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p>No recorded activity yet.</p>
                  ))}
              </section>
            </div>
          )}
          <footer className="main-footer">
            <span>
              OrderMesh AI Lite <span>by Qubriant Technologies</span>
            </span>
            <span>
              <ShieldCheck size={13} /> Your workspace. Your data.
            </span>
            <span className="dashboard-support">
              <a href="tel:+94722616616">
                <Phone size={13} />
                0722 616 616
              </a>
              <a href="mailto:info@ordermesh.com">
                <Mail size={13} />
                info@ordermesh.com
              </a>
            </span>
          </footer>
        </main>
      </div>
      {modal && (
        <ModalView
          modal={modal}
          serviceBusiness={serviceBusiness}
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
