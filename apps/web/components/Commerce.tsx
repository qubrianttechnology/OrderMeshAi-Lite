"use client";
import {
  cloneElement,
  useId,
  type ReactElement,
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { api, allPages, money } from "../lib/api";
import type { Customer, Product, Order } from "../lib/types";

type Warehouse = { id: string; name: string; code: string; active: boolean };
type Supplier = { id: string; name: string; active: boolean };
type Purchase = {
  id: string;
  reference: string;
  status: string;
  total_minor: number;
  lines: { name: string; quantity: number }[];
};
type Member = { user_id: string; name: string; email: string; role: string };
type SaleOrder = Order & {
  financial_posted: boolean;
  outstanding_minor: number | null;
  days_overdue: number;
  refund_due_minor: number;
  delivery_status: string;
  assigned_to: string | null;
  delivery_reference: string;
};
type Account = Customer & {
  outstanding_minor: number;
  overdue_minor: number;
  credit_limit_minor: number;
  orders: SaleOrder[];
};
type Expense = {
  id: string;
  category: string;
  description: string;
  amount_minor: number;
  paid_on: string;
  voided: boolean;
};
type Quote = {
  subtotal_minor: number;
  discount_minor: number;
  tax_minor: number;
  total_minor: number;
  items: {
    product_id: string;
    name: string;
    quantity: number;
    available: number | null;
    price_minor: number;
  }[];
};
const minor = (v: FormDataEntryValue | null) =>
  Math.round(Number(v || 0) * 100);
const today = () =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Colombo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
const options = (list: { id: string; name: string }[]) =>
  list.map((x) => (
    <option key={x.id} value={x.id}>
      {x.name}
    </option>
  ));
function Field({
  label,
  children,
}: {
  label: string;
  children: ReactElement<{ id?: string }>;
}) {
  const id = useId();
  return (
    <div className="commerce-field">
      <label htmlFor={id}>{label}</label>
      {cloneElement(children, { id })}
    </div>
  );
}
function Action({
  title,
  children,
  submit,
  onDone,
}: {
  title: string;
  children: ReactNode;
  submit: (f: FormData, key: string) => Promise<unknown>;
  onDone: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [success, setSuccess] = useState("");
  const key = useRef("");
  async function send(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true);
    setError("");
    setSuccess("");
    if (!key.current) key.current = crypto.randomUUID();
    try {
      await submit(new FormData(form), key.current);
      key.current = "";
      form.reset();
      setSuccess("Saved successfully.");
      await onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel commerce-panel" aria-label={title}>
      <h3>{title}</h3>
      <form
        onSubmit={send}
        onChange={() => {
          key.current = "";
          setSuccess("");
        }}
      >
        <fieldset disabled={busy}>
          {children}
          <button className="button primary" type="submit">
            {busy ? "Saving…" : title}
          </button>
        </fieldset>
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        {success && <p role="status">{success}</p>}
      </form>
    </section>
  );
}
export default function Commerce({
  org,
  role,
  onChanged,
  section = "POS",
  onSectionChange,
}: {
  org: string;
  role: string;
  onChanged: () => Promise<void>;
  section?: string;
  onSectionChange?: (section: string) => void;
}) {
  const manage = role === "owner" || role === "admin";
  const [localTab, setLocalTab] = useState("POS"),
    [products, setProducts] = useState<Product[]>([]),
    [customers, setCustomers] = useState<Customer[]>([]),
    [orders, setOrders] = useState<SaleOrder[]>([]),
    [warehouses, setWarehouses] = useState<Warehouse[]>([]),
    [suppliers, setSuppliers] = useState<Supplier[]>([]),
    [purchases, setPurchases] = useState<Purchase[]>([]),
    [accounts, setAccounts] = useState<Account[]>([]),
    [expenses, setExpenses] = useState<Expense[]>([]),
    [team, setTeam] = useState<Member[]>([]),
    [error, setError] = useState("");
  const refresh = useCallback(async () => {
    const [p, c, o, w, s, po, a, t, e] = await Promise.all([
      allPages<Product>("/products", org),
      allPages<Customer>("/customers", org),
      allPages<SaleOrder>("/orders", org),
      api<Warehouse[]>("/commerce/warehouses", org),
      api<Supplier[]>("/commerce/suppliers", org),
      api<Purchase[]>("/commerce/purchases", org),
      api<Account[]>("/commerce/accounts", org),
      api<Member[]>("/commerce/team", org),
      manage ? api<Expense[]>("/commerce/expenses", org) : Promise.resolve([]),
    ]);
    setProducts(p);
    setCustomers(c);
    setOrders(o);
    setWarehouses(w);
    setSuppliers(s);
    setPurchases(po);
    setAccounts(a);
    setTeam(t);
    setExpenses(e);
  }, [org, manage]);
  useEffect(() => {
    void refresh().catch((e) => setError(e.message));
  }, [refresh]);
  async function done() {
    await refresh();
    await onChanged();
  }
  const post = (path: string, body: unknown, key?: string, method = "POST") =>
    api(`/commerce${path}`, org, {
      method,
      body: JSON.stringify(body),
      headers: key ? { "Idempotency-Key": key } : {},
    });
  const activeProducts = products.filter((p) => p.active),
    physical = activeProducts.filter((p) => p.track_stock),
    activeOrders = orders.filter((o) => o.status !== "cancelled");
  const [returnOrder, setReturnOrder] = useState(""),
    [returnLines, setReturnLines] = useState<
      { product_id: string; product_name: string; quantity: number }[]
    >([]);
  useEffect(() => {
    let alive = true;
    setReturnLines([]);
    if (returnOrder)
      void api<{ items: typeof returnLines }>(`/orders/${returnOrder}`, org)
        .then((x) => {
          if (alive) setReturnLines(x.items);
        })
        .catch((e) => {
          if (alive) setError(e.message);
        });
    return () => {
      alive = false;
    };
  }, [org, returnOrder]);
  const [stockWarehouse, setStockWarehouse] = useState(""),
    [stock, setStock] = useState<
      { product_id: string; name: string; sku: string; quantity: number }[]
    >([]),
    [stockQuery, setStockQuery] = useState("");
  useEffect(() => {
    let alive = true;
    if (stockWarehouse)
      void api<typeof stock>(
        `/commerce/stock?warehouse_id=${stockWarehouse}`,
        org,
      )
        .then((x) => {
          if (alive) setStock(x);
        })
        .catch((e) => {
          if (alive) setError(e.message);
        });
    return () => {
      alive = false;
    };
  }, [org, stockWarehouse, products]);
  const selectedSection = onSectionChange ? section : localTab;
  const tabs = [
    "POS",
    ...(manage ? ["Purchases", "Warehouses", "Returns"] : []),
    "Credit & payments",
    ...(manage ? ["Reports & expenses"] : []),
    "Delivery",
    "Team",
  ];
  const tab = tabs.includes(selectedSection) ? selectedSection : "POS";
  const setTab = onSectionChange || setLocalTab;
  return (
    <div className="commerce">
      <div className="section-heading">
        <div>
          <span className="eyebrow">SALES & DISTRIBUTION</span>
          <h2>Business operations</h2>
          <p className="muted">
            Counter sales and WhatsApp orders share the same stock ledger.
          </p>
        </div>
        <button
          className="button secondary"
          onClick={() => void done().catch((e) => setError(e.message))}
        >
          Refresh records
        </button>
      </div>
      <div
        className="commerce-tabs"
        role="tablist"
        aria-label="Business operations"
      >
        {tabs.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            className={tab === t ? "active" : ""}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {tab === "POS" && (
        <POS
          org={org}
          products={activeProducts}
          customers={customers.filter((c) => c.active)}
          warehouses={warehouses}
          onDone={done}
        />
      )}
      {tab === "Purchases" && (
        <>
          <div className="commerce-grid">
            <Action
              title="Add supplier"
              onDone={done}
              submit={(f) =>
                post("/suppliers", {
                  name: f.get("name"),
                  phone: f.get("phone"),
                  address: f.get("address"),
                })
              }
            >
              <Field label="Supplier name">
                <input name="name" required maxLength={120} />
              </Field>
              <Field label="Phone">
                <input name="phone" maxLength={40} />
              </Field>
              <Field label="Address">
                <input name="address" maxLength={500} />
              </Field>
            </Action>
            <Action
              title="Create purchase order"
              onDone={done}
              submit={(f, k) =>
                post(
                  "/purchases",
                  {
                    supplier_id: f.get("supplier"),
                    warehouse_id: f.get("warehouse"),
                    reference: f.get("reference"),
                    items: [
                      {
                        product_id: f.get("product"),
                        quantity: Number(f.get("quantity")),
                        cost_minor: minor(f.get("cost")),
                      },
                    ],
                  },
                  k,
                )
              }
            >
              <Field label="Supplier">
                <select name="supplier" required>
                  <option value="">Choose supplier</option>
                  {options(suppliers.filter((s) => s.active))}
                </select>
              </Field>
              <Field label="Warehouse">
                <select name="warehouse" required>
                  {options(warehouses)}
                </select>
              </Field>
              <ProductPicker products={physical} />
              <Field label="Quantity">
                <input
                  name="quantity"
                  type="number"
                  min={1}
                  max={100000}
                  required
                />
              </Field>
              <Field label="Unit cost (LKR)">
                <input
                  name="cost"
                  type="number"
                  min={0}
                  step="0.01"
                  max={1000000}
                  required
                />
              </Field>
              <Field label="Supplier reference">
                <input name="reference" maxLength={100} />
              </Field>
              <p className="muted small">
                Stock changes only when you receive the goods below.
              </p>
            </Action>
          </div>
          <section className="panel commerce-panel">
            <h3>Purchase orders & goods received</h3>
            {!purchases.length && <p>No purchase orders yet.</p>}
            {purchases
              .slice()
              .reverse()
              .map((p) => (
                <div className="commerce-row" key={p.id}>
                  <div>
                    <strong>{p.reference || p.id.slice(0, 8)}</strong>
                    <p>
                      {p.lines
                        .map((l) => `${l.name} × ${l.quantity}`)
                        .join(", ")}{" "}
                      · {money(p.total_minor)} · {p.status}
                    </p>
                  </div>
                  {p.status === "draft" && (
                    <>
                      <button
                        className="button primary"
                        onClick={() =>
                          void post(
                            `/purchases/${p.id}`,
                            { status: "received" },
                            undefined,
                            "PATCH",
                          )
                            .then(done)
                            .catch((e) => setError(e.message))
                        }
                      >
                        Receive goods / GRN
                      </button>
                      <button
                        className="button secondary"
                        onClick={() =>
                          void post(
                            `/purchases/${p.id}`,
                            { status: "cancelled" },
                            undefined,
                            "PATCH",
                          )
                            .then(done)
                            .catch((e) => setError(e.message))
                        }
                      >
                        Cancel purchase
                      </button>
                    </>
                  )}
                </div>
              ))}
          </section>
        </>
      )}
      {tab === "Warehouses" && (
        <>
          <div className="commerce-grid">
            <Action
              title="Add warehouse"
              onDone={done}
              submit={(f) =>
                post("/warehouses", {
                  name: f.get("name"),
                  code: String(f.get("code")).toUpperCase(),
                })
              }
            >
              <Field label="Warehouse name">
                <input name="name" maxLength={120} required />
              </Field>
              <Field label="Unique code">
                <input
                  name="code"
                  pattern="[A-Za-z0-9_-]+"
                  maxLength={32}
                  required
                />
              </Field>
            </Action>
            <Action
              title="Transfer stock"
              onDone={done}
              submit={(f, k) =>
                post(
                  "/transfers",
                  {
                    product_id: f.get("product"),
                    from_warehouse_id: f.get("from"),
                    to_warehouse_id: f.get("to"),
                    quantity: Number(f.get("quantity")),
                  },
                  k,
                )
              }
            >
              <ProductPicker products={physical} />
              <Field label="From warehouse">
                <select name="from" required>
                  {options(warehouses)}
                </select>
              </Field>
              <Field label="To warehouse">
                <select name="to" required>
                  {options(warehouses)}
                </select>
              </Field>
              <Field label="Transfer quantity">
                <input
                  name="quantity"
                  type="number"
                  min={1}
                  max={1000000}
                  required
                />
              </Field>
            </Action>
          </div>
          <section className="panel commerce-panel">
            <h3>Warehouse balances</h3>
            <Field label="View warehouse">
              <select
                value={stockWarehouse}
                onChange={(e) => setStockWarehouse(e.target.value)}
              >
                <option value="">Choose warehouse</option>
                {options(warehouses)}
              </select>
            </Field>
            <Field label="Filter stock">
              <input
                value={stockQuery}
                onChange={(e) => setStockQuery(e.target.value)}
                placeholder="Product name or SKU"
              />
            </Field>
            {stock
              .filter((p) =>
                `${p.name} ${p.sku}`
                  .toLowerCase()
                  .includes(stockQuery.toLowerCase()),
              )
              .slice(0, 100)
              .map((p) => (
                <div key={p.product_id} className="commerce-row">
                  <span>
                    {p.name} · {p.sku}
                  </span>
                  <strong>{p.quantity}</strong>
                </div>
              ))}
            <p className="muted small">Showing up to 100 matching products.</p>
          </section>
        </>
      )}
      {tab === "Returns" && (
        <Action
          title="Record return"
          onDone={done}
          submit={(f, k) =>
            post(
              `/orders/${f.get("order")}/returns`,
              {
                warehouse_id: f.get("warehouse"),
                items: [
                  {
                    product_id: f.get("product"),
                    quantity: Number(f.get("quantity")),
                    resellable: f.get("resellable") === "on",
                  },
                ],
                reason: f.get("reason"),
                refund_minor: minor(f.get("refund")),
                method: f.get("method"),
              },
              k,
            )
          }
        >
          <Field label="Original order">
            <select
              name="order"
              required
              value={returnOrder}
              onChange={(e) => setReturnOrder(e.target.value)}
            >
              <option value="">Choose order</option>
              {activeOrders.map((o) => (
                <option value={o.id} key={o.id}>
                  {o.customer_name} · {o.id.slice(0, 8)} ·{" "}
                  {money(o.total_minor)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Sold product">
            <select name="product" required>
              <option value="">Choose sold product</option>
              {returnLines.map((l) => (
                <option key={l.product_id} value={l.product_id}>
                  {l.product_name} · sold {l.quantity}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Return quantity">
            <input
              name="quantity"
              type="number"
              min={1}
              max={100000}
              required
            />
          </Field>
          <Field label="Return warehouse">
            <select name="warehouse" required>
              {options(warehouses)}
            </select>
          </Field>
          <label className="checkbox">
            <input name="resellable" type="checkbox" defaultChecked />
            Resellable: restore this stock
          </label>
          <Field label="Reason">
            <input name="reason" required minLength={3} maxLength={500} />
          </Field>
          <Field label="Refund paid now (LKR)">
            <input
              name="refund"
              type="number"
              min={0}
              step="0.01"
              defaultValue={0}
            />
          </Field>
          <Field label="Refund method">
            <select name="method">
              <option value="cash">Cash</option>
              <option value="card">Card terminal</option>
              <option value="bank_transfer">Bank transfer</option>
            </select>
          </Field>
          <p className="muted small">
            Credit is prorated from the original invoice, including its discount
            and tax. Refunds cannot exceed money paid above the remaining
            invoice value.
          </p>
        </Action>
      )}
      {tab === "Credit & payments" && (
        <>
          <Action
            title="Record customer payment"
            onDone={done}
            submit={(f, k) =>
              post(
                `/orders/${f.get("order")}/payments`,
                {
                  amount_minor: minor(f.get("amount")),
                  method: f.get("method"),
                  reference: f.get("reference"),
                },
                k,
              )
            }
          >
            <Field label="Invoice">
              <select name="order" required>
                <option value="">Choose invoice</option>
                {accounts.flatMap((c) =>
                  c.orders
                    .filter((o) => o.status !== "cancelled")
                    .map((o) => (
                      <option key={o.id} value={o.id}>
                        {c.name} · {o.id.slice(0, 8)} ·{" "}
                        {o.outstanding_minor === null
                          ? "Payment not recorded"
                          : `Due ${money(o.outstanding_minor)}`}
                      </option>
                    )),
                )}
              </select>
            </Field>
            <Field label="Amount received (LKR)">
              <input name="amount" type="number" min={0} step="0.01" required />
            </Field>
            <Field label="Payment method">
              <select name="method">
                <option value="cash">Cash</option>
                <option value="card">Card terminal</option>
                <option value="bank_transfer">Bank transfer</option>
                <option value="credit">Post remaining balance to credit</option>
              </select>
            </Field>
            <Field label="Payment reference">
              <input name="reference" maxLength={120} />
            </Field>
            <p className="muted small">
              For a credit-only posting enter zero. This records a payment
              already received; it does not charge a card or initiate a bank
              transfer.
            </p>
          </Action>
          {manage && (
            <Action
              title="Record outstanding refund"
              onDone={done}
              submit={(f, k) =>
                post(
                  `/orders/${f.get("order")}/refunds`,
                  {
                    amount_minor: minor(f.get("amount")),
                    method: f.get("method"),
                    reference: f.get("reference"),
                  },
                  k,
                )
              }
            >
              <Field label="Return with refund due">
                <select name="order" required>
                  <option value="">Choose invoice</option>
                  {accounts.flatMap((c) =>
                    c.orders
                      .filter((o) => o.refund_due_minor > 0)
                      .map((o) => (
                        <option key={o.id} value={o.id}>
                          {c.name} · {o.id.slice(0, 8)} · Refund due{" "}
                          {money(o.refund_due_minor)}
                        </option>
                      )),
                  )}
                </select>
              </Field>
              <Field label="Refund amount (LKR)">
                <input
                  name="amount"
                  type="number"
                  min="0.01"
                  step="0.01"
                  required
                />
              </Field>
              <Field label="Refund method">
                <select name="method">
                  <option value="cash">Cash</option>
                  <option value="card">Card terminal</option>
                  <option value="bank_transfer">Bank transfer</option>
                </select>
              </Field>
              <Field label="Refund reference">
                <input name="reference" maxLength={120} />
              </Field>
            </Action>
          )}
          <section className="panel commerce-panel">
            <h3>Customer credit & aging</h3>
            {accounts
              .filter((c) => c.outstanding_minor || c.credit_limit_minor)
              .map((c) => (
                <div className="commerce-row" key={c.id}>
                  <div>
                    <strong>{c.name}</strong>
                    <p>
                      Limit {money(c.credit_limit_minor)} · Outstanding{" "}
                      {money(c.outstanding_minor)} · Overdue{" "}
                      {money(c.overdue_minor)}
                    </p>
                    {c.orders
                      .filter((o) => (o.outstanding_minor || 0) > 0)
                      .map((o) => (
                        <p key={o.id} className="small">
                          {o.id.slice(0, 8)} · {money(o.outstanding_minor!)} ·{" "}
                          {o.days_overdue} days overdue
                        </p>
                      ))}
                  </div>
                </div>
              ))}
          </section>
        </>
      )}
      {tab === "Reports & expenses" && (
        <>
          <Reports org={org} />
          <div className="commerce-grid">
            <Action
              title="Record expense"
              onDone={done}
              submit={(f, k) =>
                post(
                  "/expenses",
                  {
                    category: f.get("category"),
                    description: f.get("description"),
                    amount_minor: minor(f.get("amount")),
                    paid_on: f.get("date"),
                    reference: f.get("reference"),
                  },
                  k,
                )
              }
            >
              <Field label="Category">
                <input
                  name="category"
                  required
                  maxLength={60}
                  placeholder="Rent, transport, utilities"
                />
              </Field>
              <Field label="Description">
                <input
                  name="description"
                  required
                  minLength={3}
                  maxLength={500}
                />
              </Field>
              <Field label="Expense amount (LKR)">
                <input
                  name="amount"
                  type="number"
                  min="0.01"
                  step="0.01"
                  required
                />
              </Field>
              <Field label="Paid on">
                <input
                  name="date"
                  type="date"
                  defaultValue={today()}
                  required
                />
              </Field>
              <Field label="Reference">
                <input name="reference" maxLength={120} />
              </Field>
            </Action>
            <section className="panel commerce-panel">
              <h3>Expense records</h3>
              {expenses
                .slice()
                .reverse()
                .map((e) => (
                  <div className="commerce-row" key={e.id}>
                    <div>
                      <strong>
                        {e.category} · {money(e.amount_minor)}
                      </strong>
                      <p>
                        {e.paid_on} · {e.description}{" "}
                        {e.voided ? "· Voided" : ""}
                      </p>
                    </div>
                    {!e.voided && (
                      <button
                        className="button secondary"
                        onClick={() =>
                          void api(`/commerce/expenses/${e.id}`, org, {
                            method: "DELETE",
                          })
                            .then(done)
                            .catch((e) => setError(e.message))
                        }
                      >
                        Void
                      </button>
                    )}
                  </div>
                ))}
            </section>
          </div>
        </>
      )}
      {tab === "Delivery" && (
        <Action
          title="Update delivery"
          onDone={done}
          submit={(f) =>
            post(
              `/orders/${f.get("order")}/delivery`,
              {
                status: f.get("status"),
                assigned_to: f.get("member") || null,
                reference: f.get("reference"),
              },
              undefined,
              "PUT",
            )
          }
        >
          <Field label="Order">
            <select name="order" required>
              {activeOrders.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.customer_name} · {o.id.slice(0, 8)} · {o.delivery_status}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Status">
            <select name="status">
              <option value="pending">Pending</option>
              <option value="dispatched">Dispatched</option>
              <option value="delivered">Delivered</option>
              <option value="failed">Delivery failed</option>
            </select>
          </Field>
          <Field label="Sales rep / staff member">
            <select name="member">
              <option value="">Unassigned</option>
              {team.map((t) => (
                <option key={t.user_id} value={t.user_id}>
                  {t.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Tracking reference / delivery note">
            <input name="reference" maxLength={160} />
          </Field>
          <p className="muted small">
            A delivery update never deducts stock again. Courier integration is
            manual.
          </p>
        </Action>
      )}
      {tab === "Team" && (
        <>
          <section className="panel commerce-panel">
            <h3>Workspace members</h3>
            {team.map((t) => (
              <div key={t.user_id} className="commerce-row">
                <div>
                  <strong>{t.name}</strong>
                  <p>
                    {t.email} ·{" "}
                    {t.role === "staff" ? "Staff / cashier" : t.role}
                  </p>
                </div>
                {role === "owner" && t.role !== "owner" && (
                  <button
                    className="button secondary"
                    onClick={() =>
                      void api(`/commerce/team/${t.user_id}`, org, {
                        method: "DELETE",
                      })
                        .then(done)
                        .catch((e) => setError(e.message))
                    }
                  >
                    Remove access
                  </button>
                )}
              </div>
            ))}
          </section>
          {role === "owner" && (
            <Action
              title="Add or update member"
              onDone={done}
              submit={(f) =>
                post(
                  "/team",
                  { email: f.get("email"), role: f.get("role") },
                  undefined,
                  "PUT",
                )
              }
            >
              <Field label="Registered user email">
                <input name="email" type="email" required maxLength={254} />
              </Field>
              <Field label="Role">
                <select name="role">
                  <option value="staff">
                    Staff / cashier: orders, POS, payments
                  </option>
                  <option value="admin">
                    Admin: products, stock, finance, purchases
                  </option>
                  <option value="viewer">Viewer: read-only dashboard</option>
                </select>
              </Field>
              <p className="muted small">
                The person must register first. Access is limited to this
                workspace. No invitation email is sent.
              </p>
            </Action>
          )}
        </>
      )}
    </div>
  );
}
function ProductPicker({ products }: { products: Product[] }) {
  return (
    <Field label="Product">
      <select name="product" required>
        <option value="">Choose product</option>
        {products.map((p) => (
          <option key={p.id} value={p.id}>
            {p.sku} · {p.name}
          </option>
        ))}
      </select>
    </Field>
  );
}
function POS({
  org,
  products,
  customers,
  warehouses,
  onDone,
}: {
  org: string;
  products: Product[];
  customers: Customer[];
  warehouses: Warehouse[];
  onDone: () => Promise<void>;
}) {
  const [query, setQuery] = useState(""),
    [cart, setCart] = useState<{ product_id: string; quantity: number }[]>([]),
    [customer, setCustomer] = useState(""),
    [warehouse, setWarehouse] = useState(""),
    [mode, setMode] = useState("retail"),
    [discount, setDiscount] = useState("0"),
    [tax, setTax] = useState("0"),
    [method, setMethod] = useState("cash"),
    [paid, setPaid] = useState(""),
    [quote, setQuote] = useState<Quote | null>(null),
    [quoted, setQuoted] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [sale, setSale] = useState<Order | null>(null),
    [confirmed, setConfirmed] = useState(false);
  const key = useRef("");
  const request = JSON.stringify({
    items: cart,
    warehouse_id: warehouse || null,
    price_mode: mode,
    discount_minor: Math.round(Number(discount) * 100),
    tax_basis_points: Math.round(Number(tax) * 100),
  });
  useEffect(() => {
    let active = true;
    if (!cart.length) {
      setQuote(null);
      return;
    }
    setQuoted("");
    const timer = setTimeout(() => {
      void api<Quote>("/commerce/quote", org, { method: "POST", body: request })
        .then((x) => {
          if (active) {
            setQuote(x);
            setQuoted(request);
            setError("");
          }
        })
        .catch((e) => {
          if (active) {
            setQuote(null);
            setError(e.message);
          }
        });
    }, 200);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [org, request, cart.length]);
  function add(p: Product) {
    if (busy) return;
    setCart((old) =>
      old.some((x) => x.product_id === p.id)
        ? old.map((x) =>
            x.product_id === p.id ? { ...x, quantity: x.quantity + 1 } : x,
          )
        : [...old, { product_id: p.id, quantity: p.min_order_qty || 1 }],
    );
    setQuery("");
    setConfirmed(false);
    setSale(null);
    key.current = "";
  }
  const matches = products
    .filter((p) =>
      `${p.name} ${p.sku} ${p.barcode || ""}`
        .toLowerCase()
        .includes(query.toLowerCase()),
    )
    .slice(0, 12);
  async function checkout(e: FormEvent) {
    e.preventDefault();
    if (!quote || quoted !== request || !confirmed) return;
    setBusy(true);
    setError("");
    if (!key.current) key.current = crypto.randomUUID();
    try {
      const result = await api<Order>("/commerce/sales", org, {
        method: "POST",
        headers: { "Idempotency-Key": key.current },
        body: JSON.stringify({
          ...JSON.parse(request),
          customer_id: customer || null,
          human_confirmed: true,
          expected_total_minor: quote.total_minor,
          paid_minor:
            method === "credit"
              ? 0
              : paid === ""
                ? quote.total_minor
                : Math.round(Number(paid) * 100),
          payment_method: method,
        }),
      });
      setSale(result);
      setCart([]);
      setPaid("");
      setConfirmed(false);
      key.current = "";
      await onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="commerce-grid pos-grid">
      <section className="panel commerce-panel">
        <h3>Find products</h3>
        <Field label="Scan barcode, SKU or search">
          <input
            value={query}
            disabled={busy}
            placeholder="Scan barcode and press Enter"
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                const exact = products.find(
                  (p) =>
                    (p.barcode && p.barcode === query) ||
                    p.sku.toLowerCase() === query.toLowerCase(),
                );
                if (exact) add(exact);
                else if (matches.length === 1) add(matches[0]);
              }
            }}
          />
        </Field>
        <div className="pos-products">
          {matches.map((p) => (
            <button
              key={p.id}
              className="pos-product"
              disabled={busy}
              onClick={() => add(p)}
            >
              <span>
                <strong>{p.name}</strong>
                <small>
                  {p.sku} ·{" "}
                  {p.track_stock
                    ? `${p.stock} ${p.unit} across warehouses`
                    : "Service"}
                </small>
              </span>
              <b>{money(p.price_minor)}</b>
            </button>
          ))}
        </div>
        <p className="muted small">
          Search all {products.length.toLocaleString()} active products.
          Displaying up to 12 matches.
        </p>
      </section>
      <section className="panel commerce-panel">
        <h3>Counter sale</h3>
        <form onSubmit={checkout}>
          <fieldset disabled={busy}>
            <Field label="Customer">
              <select
                value={customer}
                onChange={(e) => {
                  setCustomer(e.target.value);
                  const c = customers.find((x) => x.id === e.target.value);
                  setMode(c?.price_group || "retail");
                }}
              >
                <option value="">Walk-in customer (no credit)</option>
                {options(customers)}
              </select>
            </Field>
            <div className="commerce-grid">
              <Field label="Sale warehouse">
                <select
                  value={warehouse}
                  onChange={(e) => setWarehouse(e.target.value)}
                >
                  <option value="">Main warehouse</option>
                  {options(warehouses)}
                </select>
              </Field>
              <Field label="Price group">
                <select value={mode} onChange={(e) => setMode(e.target.value)}>
                  <option value="retail">Retail</option>
                  <option value="wholesale">Wholesale</option>
                </select>
              </Field>
            </div>
            {cart.length === 0 && (
              <p className="muted">Add a product to begin.</p>
            )}
            {cart.map((line) => {
              const p = products.find((p) => p.id === line.product_id);
              return (
                <div className="commerce-row" key={line.product_id}>
                  <div>
                    <strong>{p?.name}</strong>
                    <small>
                      Minimum {p?.min_order_qty || 1} · {p?.unit}
                    </small>
                  </div>
                  <input
                    aria-label={`Quantity for ${p?.name}`}
                    type="number"
                    min={p?.min_order_qty || 1}
                    max={100000}
                    value={line.quantity}
                    onChange={(e) => {
                      setCart(
                        cart.map((x) =>
                          x.product_id === line.product_id
                            ? { ...x, quantity: Number(e.target.value) }
                            : x,
                        ),
                      );
                      setConfirmed(false);
                    }}
                  />
                  <button
                    type="button"
                    className="button secondary"
                    aria-label={`Remove ${p?.name}`}
                    onClick={() =>
                      setCart(
                        cart.filter((x) => x.product_id !== line.product_id),
                      )
                    }
                  >
                    Remove
                  </button>
                </div>
              );
            })}
            <div className="commerce-grid">
              <Field label="Discount (LKR)">
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={discount}
                  onChange={(e) => {
                    setDiscount(e.target.value);
                    setConfirmed(false);
                  }}
                />
              </Field>
              <Field label="Configured tax (%)">
                <input
                  type="number"
                  min={0}
                  max={100}
                  step="0.01"
                  value={tax}
                  onChange={(e) => {
                    setTax(e.target.value);
                    setConfirmed(false);
                  }}
                />
              </Field>
            </div>
            <p className="muted small">
              Wholesale prices apply only above each product’s quantity
              threshold. Tax defaults to zero; use your business’s configured
              rate.
            </p>
            {quote && (
              <div className="pos-total">
                <span>
                  Subtotal {money(quote.subtotal_minor)} · Discount{" "}
                  {money(quote.discount_minor)} · Tax {money(quote.tax_minor)}
                </span>
                <strong>Total {money(quote.total_minor)}</strong>
                {quote.items
                  .filter(
                    (x) => x.available !== null && x.available < x.quantity,
                  )
                  .map((x) => (
                    <p className="form-error" key={x.product_id}>
                      {x.name}: only {x.available} available in this warehouse.
                    </p>
                  ))}
              </div>
            )}
            <Field label="Payment">
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value)}
              >
                <option value="cash">Cash</option>
                <option value="card">Card terminal (record only)</option>
                <option value="bank_transfer">
                  Bank transfer (record only)
                </option>
                <option value="credit">Customer credit</option>
              </select>
            </Field>
            {method !== "credit" && (
              <Field label="Amount received (LKR; blank = full total)">
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={paid}
                  onChange={(e) => setPaid(e.target.value)}
                />
              </Field>
            )}
            <label className="checkbox">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
                required
              />
              I reviewed quantities, prices and payment.
            </label>
            <button
              className="button primary full"
              disabled={
                busy ||
                !cart.length ||
                !quote ||
                quoted !== request ||
                !confirmed
              }
            >
              {busy ? "Posting sale…" : "Complete sale"}
            </button>
          </fieldset>
        </form>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {sale && (
          <div className="info-note" role="status">
            Sale posted. Stock and payment recorded.{" "}
            <a
              href={`/api/commerce/orders/${sale.id}/receipt?organization_id=${org}`}
              onClick={async (e) => {
                e.preventDefault();
                try {
                  const r = await fetch(
                    `/api/commerce/orders/${sale.id}/receipt`,
                    {
                      headers: { "X-Organization-ID": org },
                    },
                  );
                  if (!r.ok) throw new Error("Invoice download failed");
                  const url = URL.createObjectURL(await r.blob());
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `payment-record-${sale.id}.pdf`;
                  a.click();
                  setTimeout(() => URL.revokeObjectURL(url), 1000);
                } catch (err) {
                  setError((err as Error).message);
                }
              }}
            >
              Download payment record PDF
            </a>
          </div>
        )}
      </section>
    </div>
  );
}
function Reports({ org }: { org: string }) {
  const [start, setStart] = useState(today()),
    [end, setEnd] = useState(today()),
    [report, setReport] = useState<Record<string, number | null> | null>(null),
    [error, setError] = useState("");
  async function load(e: FormEvent) {
    e.preventDefault();
    try {
      setReport(await api(`/commerce/reports?start=${start}&end=${end}`, org));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const metrics: [[string, string], ...[string, string][]] = [
    ["net_sales_minor", "Net sales (excluding tax)"],
    ["cost_of_sales_minor", "Cost of sales"],
    ["expenses_minor", "Operating expenses"],
    ["net_profit_minor", "Net profit"],
    ["payments_received_minor", "Customer payments received"],
    ["refunds_paid_minor", "Refunds paid"],
    ["outstanding_minor", "Current customer balances"],
  ];
  return (
    <section className="panel commerce-panel">
      <h3>Sales & profit reports</h3>
      <form onSubmit={load} className="commerce-grid">
        <Field label="From">
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            required
          />
        </Field>
        <Field label="To">
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            required
          />
        </Field>
        <button className="button primary">Run report</button>
      </form>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {report && (
        <>
          <div className="commerce-metrics">
            {metrics.map(([key, label]) => (
              <div className="pos-total" key={key}>
                <span>{label}</span>
                <strong>
                  {report[key] === null
                    ? "Cost data incomplete"
                    : money(report[key] || 0)}
                </strong>
              </div>
            ))}
          </div>
          <p className="muted small">
            Posted sales: {report.sales_count}. Orders without payment/credit
            posting: {report.unposted_orders} (excluded). Missing cost lines:{" "}
            {report.missing_cost_lines}. These operational reports are not
            statutory accounts or a bank balance.
          </p>
        </>
      )}
    </section>
  );
}
