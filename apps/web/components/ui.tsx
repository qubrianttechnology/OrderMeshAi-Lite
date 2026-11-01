"use client";
import {
  Children,
  cloneElement,
  isValidElement,
  useId,
  type ReactNode,
  type ReactElement,
} from "react";
import { Layers3, Box } from "lucide-react";
import { money } from "../lib/api";
import type { Order } from "../lib/types";
export function Brand() {
  return (
    <div className="brand">
      <span className="brand-icon">
        <Layers3 size={22} />
      </span>
      <span>
        OrderMesh<span className="brand-sub">AI LITE</span>
      </span>
    </div>
  );
}
export function Badge({
  children,
  kind = "neutral",
}: {
  children: ReactNode;
  kind?: string;
}) {
  return <span className={`badge ${kind}`}>{children}</span>;
}
export function Empty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty">
      <Box size={30} />
      <h3>{title}</h3>
      <p>{detail}</p>
    </div>
  );
}
export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {Children.map(children, (child) =>
        isValidElement(child) &&
        ["input", "select", "textarea"].includes(child.type as string)
          ? cloneElement(child as ReactElement<{ id: string }>, { id })
          : child,
      )}
    </div>
  );
}

export function Metric({
  label,
  value,
  note,
  icon,
  color,
}: {
  label: string;
  value: string;
  note: string;
  icon: ReactNode;
  color: string;
}) {
  return (
    <section className="metric">
      <div>
        <span>{label}</span>
        <span className={`metric-icon ${color}`}>{icon}</span>
      </div>
      <strong>{value}</strong>
      <p>{note}</p>
    </section>
  );
}
export function SalesChart({
  data,
}: {
  data: { date: string; total_minor: number }[];
}) {
  if (!data.length)
    return (
      <div className="chart-empty" role="status">
        <Box size={22} />
        <span>Sales data for this period is not available yet.</span>
      </div>
    );
  const max = Math.max(...data.map((d) => d.total_minor), 10000);
  const formattedDate = (value: string) =>
    new Intl.DateTimeFormat("en-GB", {
      weekday: "short",
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "Asia/Colombo",
    }).format(new Date(`${value}T12:00:00+05:30`));
  const shortDate = (value: string) =>
    new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "short",
      timeZone: "Asia/Colombo",
    }).format(new Date(`${value}T12:00:00+05:30`));
  return (
    <div
      className="sales-chart"
      role="img"
      aria-label={`Sales trend over the last seven days. ${data.map((d) => `${formattedDate(d.date)}: ${money(d.total_minor)}`).join(", ")}`}
    >
      <div className="chart-y">
        <span>{money(max)}</span>
        <span>{money(max / 2)}</span>
        <span>0</span>
      </div>
      <div className="chart-bars">
        <div className="chart-grid" />
        {data.map((d) => (
          <div className="chart-column" key={d.date}>
            <div className="bar-slot">
              <div
                className={`chart-bar ${d.total_minor ? "" : "zero"}`}
                style={{
                  height: `${Math.max((d.total_minor / max) * 100, 1)}%`,
                }}
                title={`${formattedDate(d.date)}: ${money(d.total_minor)}`}
              />
            </div>
            <span title={formattedDate(d.date)}>{shortDate(d.date)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function OrderStatusChart({ orders }: { orders: Order[] }) {
  const statuses = [
    { key: "confirmed", label: "To fulfill", color: "confirmed" },
    { key: "fulfilled", label: "Fulfilled", color: "fulfilled" },
    { key: "cancelled", label: "Cancelled", color: "cancelled" },
  ] as const;
  const counts = statuses.map((status) => ({
    ...status,
    count: orders.filter((order) => order.status === status.key).length,
  }));
  const max = Math.max(...counts.map((status) => status.count), 1);
  if (!orders.length)
    return (
      <div className="chart-empty" role="status">
        <Box size={22} />
        <span>Order status will appear when orders are available.</span>
      </div>
    );
  return (
    <div
      className="order-status-chart"
      role="img"
      aria-label={`Order status breakdown from ${orders.length} orders. ${counts.map(({ label, count }) => `${label}: ${count}`).join(", ")}`}
    >
      {counts.map((status) => (
        <div className="order-status-row" key={status.key}>
          <div className="order-status-label">
            <span className={`order-status-dot ${status.color}`} />
            <span>{status.label}</span>
            <strong>{status.count}</strong>
          </div>
          <div className="order-status-track">
            <span
              className={`order-status-fill ${status.color}`}
              style={{ width: `${(status.count / max) * 100}%` }}
              title={`${status.label}: ${status.count} of ${orders.length} orders`}
            />
          </div>
        </div>
      ))}
      <p className="order-status-total">{orders.length} total orders</p>
    </div>
  );
}
