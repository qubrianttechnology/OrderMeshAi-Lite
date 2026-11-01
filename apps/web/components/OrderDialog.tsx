"use client";
import { wholesaleCategories } from "../lib/wholesale";
import { useRef, useState, useEffect, type FormEvent } from "react";
import { X, ShieldCheck, Plus, Check } from "lucide-react";
import { api, money } from "../lib/api";
import type { Customer, Product, Draft } from "../lib/types";
import { Field } from "./ui";
import { RequestReview } from "./ServiceRequests";
export type Modal =
  | { type: "customer"; item?: Customer }
  | { type: "product"; item?: Product }
  | { type: "stock"; item: Product }
  | { type: "order"; draft?: Draft }
  | null;
export default function ModalView({
  modal,
  serviceBusiness = false,
  org,
  products,
  customers,
  onClose,
  onSaved,
}: {
  modal: NonNullable<Modal>;
  serviceBusiness?: boolean;
  org: string;
  products: Product[];
  customers: Customer[];
  onClose: () => void;
  onSaved: (s: string) => Promise<void>;
}) {
  const ref = useRef<HTMLDialogElement>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  const title =
    modal.type === "order"
      ? modal.draft?.result.kind === "service_request"
        ? "Review service request"
        : "Review & confirm order"
      : modal.type === "stock"
        ? `Adjust stock · ${modal.item.name}`
        : modal.type === "customer"
          ? modal.item
            ? "Edit customer"
            : "Add customer"
          : modal.item
            ? "Edit product"
            : serviceBusiness
              ? "Add service"
              : "Add product";
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      if (modal.type === "customer") {
        await api(`/customers${modal.item ? `/${modal.item.id}` : ""}`, org, {
          method: modal.item ? "PUT" : "POST",
          body: JSON.stringify({
            ...data,
            active: data.active === "on",
            credit_limit_minor: Math.round(
              Number(data.credit_limit_minor) * 100,
            ),
            payment_terms_days: Number(data.payment_terms_days),
          }),
        });
      } else if (modal.type === "product") {
        await api(`/products${modal.item ? `/${modal.item.id}` : ""}`, org, {
          method: modal.item ? "PUT" : "POST",
          body: JSON.stringify({
            ...data,
            active: data.active === "on",
            track_stock: data.track_stock === "on",
            price_minor: Math.round(Number(data.price_minor) * 100),
            cost_minor:
              data.cost_minor === ""
                ? null
                : Math.round(Number(data.cost_minor) * 100),
            wholesale_price_minor:
              data.wholesale_price_minor === ""
                ? null
                : Math.round(Number(data.wholesale_price_minor) * 100),
            wholesale_min_qty: Number(data.wholesale_min_qty),
            min_order_qty: Number(data.min_order_qty),
            reorder_level: Number(data.reorder_level),
            aliases: String(data.aliases)
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean),
          }),
        });
      } else if (modal.type === "stock") {
        await api(`/products/${modal.item.id}/stock`, org, {
          method: "POST",
          body: JSON.stringify({ ...data, delta: Number(data.delta) }),
        });
      }
      await onSaved("Workspace updated.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <dialog
      ref={ref}
      className={`modal ${modal.type === "order" ? "wide" : ""}`}
      onCancel={(e) => {
        if (busy) e.preventDefault();
        else onClose();
      }}
    >
      <div className="modal-header">
        <div>
          <span className="eyebrow">ORDERMESH WORKSPACE</span>
          <h2>{title}</h2>
        </div>
        <button
          className="icon-button"
          aria-label="Close dialog"
          disabled={busy}
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      {modal.type === "order" &&
      modal.draft?.result.kind === "service_request" ? (
        <RequestReview
          draft={modal.draft}
          org={org}
          onSaved={onSaved}
          onBusy={setBusy}
        />
      ) : modal.type === "order" ? (
        <OrderForm
          draft={modal.draft}
          org={org}
          products={products}
          customers={customers}
          onSaved={onSaved}
          onBusy={setBusy}
        />
      ) : (
        <form onSubmit={save} className="modal-body">
          {modal.type === "customer" && (
            <>
              <Field label="Customer name">
                <input
                  name="name"
                  required
                  maxLength={120}
                  defaultValue={modal.item?.name}
                />
              </Field>
              <Field label="Phone">
                <input
                  name="phone"
                  maxLength={30}
                  defaultValue={modal.item?.phone}
                />
              </Field>
              <div className="form-grid">
                <Field label="Approved credit limit (LKR)">
                  <input
                    name="credit_limit_minor"
                    type="number"
                    min="0"
                    max="20000000"
                    step="0.01"
                    defaultValue={(modal.item?.credit_limit_minor || 0) / 100}
                    required
                  />
                </Field>
                <Field label="Payment terms (days)">
                  <input
                    name="payment_terms_days"
                    type="number"
                    min="0"
                    max="365"
                    defaultValue={modal.item?.payment_terms_days || 0}
                    required
                  />
                </Field>
                <Field label="Customer price group">
                  <select
                    name="price_group"
                    defaultValue={modal.item?.price_group || "retail"}
                  >
                    <option value="retail">Retail</option>
                    <option value="wholesale">Wholesale</option>
                  </select>
                </Field>
              </div>
              <Field label="Address">
                <textarea
                  name="address"
                  maxLength={500}
                  defaultValue={modal.item?.address}
                />
              </Field>
              <label className="checkbox">
                <input
                  type="checkbox"
                  name="active"
                  defaultChecked={modal.item?.active ?? true}
                />
                Active customer
              </label>
            </>
          )}
          {modal.type === "product" && (
            <>
              <div className="form-grid">
                <Field
                  label={serviceBusiness ? "Service name" : "Product name"}
                >
                  <input
                    name="name"
                    required
                    maxLength={120}
                    defaultValue={modal.item?.name}
                  />
                </Field>
                <Field label="Product category">
                  <select
                    name="category"
                    defaultValue={modal.item?.category || "other"}
                  >
                    {wholesaleCategories.map((category) => (
                      <option key={category.value} value={category.value}>
                        {category.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="SKU">
                  <input
                    name="sku"
                    pattern="[A-Za-z0-9_-]+"
                    required
                    maxLength={40}
                    defaultValue={modal.item?.sku}
                  />
                </Field>
                <Field label="Unit price (LKR)">
                  <input
                    name="price_minor"
                    type="number"
                    min="0"
                    max="1000000"
                    step="0.01"
                    required
                    defaultValue={
                      modal.item ? modal.item.price_minor / 100 : undefined
                    }
                  />
                </Field>
                <Field label="Unit">
                  <input
                    name="unit"
                    required
                    maxLength={30}
                    defaultValue={modal.item?.unit || "units"}
                  />
                </Field>
              </div>
              <div className="form-grid">
                <Field label="Barcode">
                  <input
                    name="barcode"
                    maxLength={80}
                    pattern="[A-Za-z0-9._-]*"
                    defaultValue={modal.item?.barcode || ""}
                  />
                </Field>
                <Field label="Unit cost (LKR; blank if unknown)">
                  <input
                    name="cost_minor"
                    type="number"
                    min="0"
                    max="1000000"
                    step="0.01"
                    defaultValue={
                      modal.item?.cost_minor == null
                        ? ""
                        : modal.item.cost_minor / 100
                    }
                  />
                </Field>
                <Field label="Wholesale unit price (LKR; optional)">
                  <input
                    name="wholesale_price_minor"
                    type="number"
                    min="0"
                    max="1000000"
                    step="0.01"
                    defaultValue={
                      modal.item?.wholesale_price_minor == null
                        ? ""
                        : modal.item.wholesale_price_minor / 100
                    }
                  />
                </Field>
                <Field label="Wholesale price minimum quantity">
                  <input
                    name="wholesale_min_qty"
                    type="number"
                    min="1"
                    max="100000"
                    defaultValue={modal.item?.wholesale_min_qty || 1}
                    required
                  />
                </Field>
                <Field label="Minimum order quantity">
                  <input
                    name="min_order_qty"
                    type="number"
                    min="1"
                    max="100000"
                    defaultValue={modal.item?.min_order_qty || 1}
                    required
                  />
                </Field>
              </div>
              <Field label="Product aliases / part numbers (comma separated)">
                <input
                  name="aliases"
                  maxLength={1000}
                  defaultValue={modal.item?.aliases.join(", ")}
                  placeholder="හාල්, සහල්"
                />
              </Field>
              <p className="muted small">
                Use the selling unit consistently for stock and price: piece,
                pack, carton, bag or kg. One carton is one catalog unit; pack
                conversions are not automatic. For vehicle parts, include
                brand/model and exact part or OEM numbers in the name or
                aliases, and verify compatibility before confirming.
              </p>
              <label className="checkbox">
                <input
                  type="checkbox"
                  name="track_stock"
                  defaultChecked={modal.item?.track_stock ?? !serviceBusiness}
                />
                Track inventory for this item
              </label>
              <Field label="Reorder level">
                <input
                  name="reorder_level"
                  type="number"
                  min="0"
                  max="1000000"
                  required
                  defaultValue={modal.item?.reorder_level ?? 10}
                />
              </Field>
              <label className="checkbox">
                <input
                  type="checkbox"
                  name="active"
                  defaultChecked={modal.item?.active ?? true}
                />
                Active product
              </label>
              <p className="muted small">
                Enable stock tracking for physical products. Services do not
                need opening stock.
              </p>
            </>
          )}
          {modal.type === "stock" && (
            <>
              <div className="info-note">
                Current stock: {modal.item.stock} {modal.item.unit}
              </div>
              <Field label="Quantity change (+ receive / − remove)">
                <input
                  name="delta"
                  type="number"
                  min={-modal.item.stock}
                  max="1000000"
                  step="1"
                  required
                />
              </Field>
              <Field label="Reason for adjustment">
                <input
                  name="reason"
                  required
                  minLength={3}
                  maxLength={200}
                  placeholder="Opening stock, delivery, correction…"
                />
              </Field>
              <p className="muted small">
                Every adjustment is recorded in the stock ledger. This form
                adjusts Main warehouse stock; use Operations for warehouse
                transfers and goods receipts.
              </p>
            </>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button className="button primary full" disabled={busy}>
            {busy ? "Saving…" : "Save changes"}
          </button>
        </form>
      )}
    </dialog>
  );
}

function OrderForm({
  draft,
  org,
  products,
  customers,
  onSaved,
  onBusy,
}: {
  draft?: Draft;
  org: string;
  products: Product[];
  customers: Customer[];
  onSaved: (s: string) => Promise<void>;
  onBusy: (b: boolean) => void;
}) {
  const [deliveryInstructions, setDeliveryInstructions] = useState(
    draft?.result.delivery_instructions || "",
  );
  const [lines, setLines] = useState(() =>
    draft
      ? draft.result.items.map((i) => ({
          product_id: i.product_id || "",
          quantity: String(i.quantity ?? ""),
          source: i.source,
        }))
      : [{ product_id: "", quantity: "1", source: "" }],
  );
  const [customer, setCustomer] = useState(""),
    [confirmed, setConfirmed] = useState(false),
    [ack, setAck] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [warehouses, setWarehouses] = useState<{ id: string; name: string }[]>(
    [],
  );
  const [warehouse, setWarehouse] = useState(""),
    [priceMode, setPriceMode] = useState("retail"),
    [discount, setDiscount] = useState("0"),
    [taxRate, setTaxRate] = useState("0");
  useEffect(() => {
    let active = true;
    void api<{ id: string; name: string }[]>("/commerce/warehouses", org)
      .then((x) => {
        if (active) setWarehouses(x);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [org]);
  const submission = useRef<{ body: string; key: string } | null>(null);
  const subtotal = lines.reduce(
    (sum, line) =>
      sum +
      (() => {
        const p = products.find((p) => p.id === line.product_id);
        const q = Number(line.quantity) || 0;
        return (
          (p
            ? priceMode === "wholesale" &&
              p.wholesale_price_minor != null &&
              q >= (p.wholesale_min_qty || 1)
              ? p.wholesale_price_minor
              : p.price_minor
            : 0) * q
        );
      })(),
    0,
  );
  const discountMinor = Math.round(Number(discount) * 100),
    taxBasisPoints = Math.round(Number(taxRate) * 100);
  const taxable = Math.max(0, subtotal - discountMinor),
    taxMinor = Math.floor((taxable * taxBasisPoints + 5000) / 10000),
    total = taxable + taxMinor;
  function update(
    index: number,
    key: "product_id" | "quantity",
    value: string,
  ) {
    setLines(lines.map((l, i) => (i === index ? { ...l, [key]: value } : l)));
    setConfirmed(false);
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    onBusy(true);
    setError("");
    try {
      const body = JSON.stringify({
        customer_id: customer,
        warehouse_id: warehouse || null,
        price_mode: priceMode,
        discount_minor: discountMinor,
        tax_basis_points: taxBasisPoints,
        delivery_instructions: deliveryInstructions,
        items: lines.map((l) => ({
          product_id: l.product_id,
          quantity: Number(l.quantity),
        })),
        human_confirmed: confirmed,
        expected_total_minor: total,
        flags_acknowledged: ack,
        draft_id: draft?.id || null,
      });
      if (!submission.current || submission.current.body !== body)
        submission.current = { body, key: crypto.randomUUID() };
      await api("/orders", org, {
        method: "POST",
        headers: { "Idempotency-Key": submission.current.key },
        body,
      });
      await onSaved("Order confirmed. Inventory has been updated.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
      onBusy(false);
    }
  }
  return (
    <form className="modal-body" onSubmit={submit}>
      <div className="info-note">
        <ShieldCheck size={18} />
        <span>
          {draft
            ? "Review the original message and every extracted line. Unmatched items must be resolved or explicitly removed."
            : "Orders deduct stock immediately on confirmation. Prices are verified by the server."}
        </span>
      </div>
      {draft && (
        <details open>
          <summary>Original message & review flags</summary>
          <pre>{draft.source_text}</pre>
          <p className="small muted">
            All lines require unit and intent verification. Confidence is
            heuristic. Removed lines will not be ordered.
          </p>
        </details>
      )}
      <Field label="Customer">
        <select
          required
          value={customer}
          onChange={(e) => {
            setCustomer(e.target.value);
            setPriceMode(
              customers.find((c) => c.id === e.target.value)?.price_group ||
                "retail",
            );
            setConfirmed(false);
          }}
        >
          <option value="">Select a customer</option>
          {customers
            .filter((c) => c.active)
            .map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
        </select>
      </Field>
      <details>
        <summary>Warehouse, wholesale pricing, discount & tax</summary>
        <div className="form-grid">
          <Field label="Order warehouse">
            <select
              value={warehouse}
              onChange={(e) => {
                setWarehouse(e.target.value);
                setConfirmed(false);
              }}
            >
              <option value="">Main warehouse</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Order price group">
            <select
              value={priceMode}
              onChange={(e) => {
                setPriceMode(e.target.value);
                setConfirmed(false);
              }}
            >
              <option value="retail">Retail</option>
              <option value="wholesale">Wholesale</option>
            </select>
          </Field>
          <Field label="Order discount (LKR)">
            <input
              type="number"
              min="0"
              step="0.01"
              value={discount}
              onChange={(e) => {
                setDiscount(e.target.value);
                setConfirmed(false);
              }}
            />
          </Field>
          <Field label="Configured order tax (%)">
            <input
              type="number"
              min="0"
              max="100"
              step="0.01"
              value={taxRate}
              onChange={(e) => {
                setTaxRate(e.target.value);
                setConfirmed(false);
              }}
            />
          </Field>
        </div>
        <p className="muted small">
          Subtotal {money(subtotal)} · Discount {money(discountMinor)} · Tax{" "}
          {money(taxMinor)}. Tax defaults to zero. Wholesale thresholds and
          minimum quantities are checked by the server.
        </p>
      </details>
      <Field label="Delivery instructions">
        <textarea
          maxLength={500}
          value={deliveryInstructions}
          onChange={(event) => {
            setDeliveryInstructions(event.target.value);
            setConfirmed(false);
          }}
          placeholder="Optional instructions stated by the customer"
        />
      </Field>
      <div className="order-lines">
        {lines.map((line, i) => (
          <div key={i} className="order-line">
            <div>
              <label>
                Product {i + 1}
                <select
                  aria-label={`Product ${i + 1}`}
                  value={line.product_id}
                  required
                  onChange={(e) => update(i, "product_id", e.target.value)}
                >
                  <option value="">Select product</option>
                  {products
                    .filter((p) => p.active)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} · {p.stock} {p.unit} available
                      </option>
                    ))}
                </select>
              </label>
              {line.source && (
                <small>
                  Source: {line.source}
                  {draft?.result.items[i]?.unit
                    ? ` · stated unit: ${draft.result.items[i].unit}`
                    : ""}
                </small>
              )}
            </div>
            <label>
              Quantity
              <input
                aria-label={`Quantity ${i + 1}`}
                type="number"
                min="1"
                max="100000"
                step="1"
                required
                value={line.quantity}
                onChange={(e) => update(i, "quantity", e.target.value)}
              />
            </label>
            <button
              type="button"
              className="icon-button"
              aria-label={`Remove line ${i + 1}`}
              disabled={lines.length === 1 || busy}
              onClick={() => {
                setLines(lines.filter((_, j) => i !== j));
                setConfirmed(false);
              }}
            >
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        className="text-button"
        disabled={lines.length >= 100 || busy}
        onClick={() => {
          setLines([...lines, { product_id: "", quantity: "1", source: "" }]);
          setConfirmed(false);
        }}
      >
        <Plus size={15} />
        Add line item
      </button>
      <div className="order-total">
        <span>
          Order total <small>No tax applied · LKR</small>
        </span>
        <strong>{money(total)}</strong>
      </div>
      {draft && (
        <label className="checkbox">
          <input
            type="checkbox"
            checked={ack}
            onChange={(e) => setAck(e.target.checked)}
            required
          />
          I reviewed all extraction flags, units, unmatched and removed lines.
        </label>
      )}
      <label className="checkbox confirmation">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
          required
        />
        I have checked the customer, quantities and products and confirm this
        order.
      </label>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button
        className="button primary full"
        disabled={busy || !confirmed || (!!draft && !ack)}
      >
        <Check size={17} />
        {busy ? "Confirming…" : "Confirm & create order"}
      </button>
      <p className="small muted text-center">
        Your confirmation creates the order and updates inventory.
      </p>
    </form>
  );
}
