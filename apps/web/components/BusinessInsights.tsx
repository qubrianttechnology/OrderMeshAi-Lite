"use client";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  ArrowRight,
  BarChart3,
  Package,
  RefreshCw,
  TrendingUp,
  Users,
} from "lucide-react";
import { api, money } from "../lib/api";

type Day = {
  date: string;
  sales_minor: number;
  gross_profit_minor: number | null;
};
type Insights = {
  period: { start: string; end: string; days: number };
  summary: {
    net_sales_minor: number;
    cost_of_sales_minor: number | null;
    gross_profit_minor: number | null;
    expenses_minor: number;
    net_profit_minor: number | null;
    sales_count: number;
    missing_cost_lines: number;
    unposted_orders: number;
  };
  daily: Day[];
  low_stock_count: number;
  low_stock: {
    id: string;
    name: string;
    sku: string;
    stock: number;
    unit: string;
    reorder_level: number;
  }[];
  top_products: {
    product_id: string;
    name: string;
    quantity: number;
    net_sales_minor: number;
  }[];
  staff: {
    user_id: string;
    name: string;
    order_count: number;
    fulfilled_orders: number;
    net_sales_minor: number;
    fulfillment_percent: number | null;
  }[];
};
const shortDate = (value: string) =>
  new Date(value + "T12:00:00Z").toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "Asia/Colombo",
  });
const compact = (minor: number) =>
  new Intl.NumberFormat("en-LK", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(minor / 100);
function Trend({ daily }: { daily: Day[] }) {
  const title = useId();
  const stride = Math.ceil(daily.length / 10);
  const points = Array.from(
    { length: Math.ceil(daily.length / stride) },
    (_, i) => {
      const group = daily.slice(i * stride, (i + 1) * stride);
      return {
        label:
          group.length === 1
            ? shortDate(group[0].date)
            : `${shortDate(group[0].date)}–${shortDate(group[group.length - 1].date)}`,
        sales_minor: group.reduce((n, d) => n + d.sales_minor, 0),
        gross_profit_minor: group.some((d) => d.gross_profit_minor === null)
          ? null
          : group.reduce((n, d) => n + (d.gross_profit_minor || 0), 0),
      };
    },
  );
  const values = points.flatMap((p) => [
    p.sales_minor,
    ...(p.gross_profit_minor === null ? [] : [p.gross_profit_minor]),
  ]);
  const max = Math.max(1, ...values),
    min = Math.min(0, ...values),
    range = max - min;
  const y = (v: number) => 190 - ((v - min) / range) * 155;
  const zero = y(0);
  const step = 500 / Math.max(points.length, 1);
  const segments: { x: number; y: number }[][] = [];
  let current: { x: number; y: number }[] = [];
  points.forEach((p, i) => {
    if (p.gross_profit_minor === null) {
      if (current.length) segments.push(current);
      current = [];
    } else
      current.push({ x: 65 + i * step + step / 2, y: y(p.gross_profit_minor) });
  });
  if (current.length) segments.push(current);
  return (
    <>
      <div className="insight-chart-scroll">
        <svg
          className="insight-chart"
          viewBox="0 0 600 255"
          role="img"
          aria-labelledby={title}
        >
          <title id={title}>
            Posted sales versus gross profit in LKR. Missing costs leave gaps in
            the profit line.
          </title>
          {Array.from({ length: 5 }, (_, i) => {
            const v = min + (range * i) / 4;
            return (
              <g key={i}>
                <line
                  x1={60}
                  x2={570}
                  y1={y(v)}
                  y2={y(v)}
                  stroke="currentColor"
                  opacity=".1"
                  strokeDasharray="3 4"
                />
                <text
                  x={53}
                  y={y(v) + 4}
                  textAnchor="end"
                  fill="currentColor"
                  fontSize={10}
                >
                  {compact(v)}
                </text>
              </g>
            );
          })}
          <text x={18} y={18} fontSize={10} fill="currentColor">
            LKR
          </text>
          <line
            x1={60}
            x2={570}
            y1={zero}
            y2={zero}
            stroke="currentColor"
            opacity=".25"
          />
          {points.map((p, i) => {
            const x = 65 + i * step + step / 2;
            return (
              <g
                key={p.label}
                tabIndex={0}
                aria-label={`${p.label}: sales ${money(p.sales_minor)}, gross profit ${p.gross_profit_minor === null ? "cost data incomplete" : money(p.gross_profit_minor)}`}
              >
                <title>
                  {p.label}: Sales {money(p.sales_minor)}; gross profit{" "}
                  {p.gross_profit_minor === null
                    ? "cost data incomplete"
                    : money(p.gross_profit_minor)}
                </title>
                <rect
                  x={x - step * 0.23}
                  width={step * 0.46}
                  y={Math.min(y(p.sales_minor), zero)}
                  height={Math.max(Math.abs(y(p.sales_minor) - zero), 1)}
                  rx={3}
                  fill="#244c72"
                />
                <text
                  x={x}
                  y={214}
                  textAnchor="middle"
                  fontSize={8}
                  fill="currentColor"
                >
                  {p.label}
                </text>
                {p.gross_profit_minor !== null && (
                  <circle
                    cx={x}
                    cy={y(p.gross_profit_minor)}
                    r={4}
                    fill="#ec733b"
                  />
                )}
              </g>
            );
          })}
          {segments.map((segment, i) => (
            <polyline
              key={i}
              points={segment.map((p) => `${p.x},${p.y}`).join(" ")}
              fill="none"
              stroke="#ec733b"
              strokeWidth={2.5}
            />
          ))}
        </svg>
      </div>
      <details className="insight-data">
        <summary>View chart data</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Period</th>
                <th>Posted sales</th>
                <th>Gross profit</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.label}>
                  <td>{p.label}</td>
                  <td>{money(p.sales_minor)}</td>
                  <td>
                    {p.gross_profit_minor === null
                      ? "Cost data incomplete"
                      : money(p.gross_profit_minor)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
export default function BusinessInsights({
  org,
  onProducts,
  onReports,
}: {
  org: string;
  onProducts: () => void;
  onReports: () => void;
}) {
  const [days, setDays] = useState(30),
    [data, setData] = useState<Insights | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false);
  const sequence = useRef(0);
  const invalidate = useCallback(() => {
    sequence.current++;
  }, []);
  const load = useCallback(
    async (signal?: AbortSignal) => {
      const version = ++sequence.current;
      setLoading(true);
      try {
        const value = await api<Insights>(
          `/commerce/dashboard-insights?days=${days}`,
          org,
          { signal },
        );
        if (version === sequence.current) {
          setData(value);
          setError("");
        }
      } catch (e) {
        if (!signal?.aborted && version === sequence.current)
          setError((e as Error).message);
      } finally {
        if (!signal?.aborted && version === sequence.current) setLoading(false);
      }
    },
    [org, days],
  );
  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    void load(controller.signal);
    const timer = setInterval(() => {
      if (!document.hidden) void load(controller.signal);
    }, 30000);
    return () => {
      invalidate();
      controller.abort();
      clearInterval(timer);
    };
  }, [load, invalidate]);
  const summary = data?.summary;
  const bars = summary
    ? [
        { name: "Posted sales", value: summary.net_sales_minor },
        { name: "Cost of sales", value: summary.cost_of_sales_minor },
        { name: "Gross profit", value: summary.gross_profit_minor },
        { name: "Expenses", value: summary.expenses_minor },
        { name: "Net profit", value: summary.net_profit_minor },
      ]
    : [];
  const scale = Math.max(1, ...bars.map((b) => Math.abs(b.value || 0)));
  return (
    <section
      className="business-insights"
      aria-label="Business performance charts"
    >
      <div className="insight-toolbar">
        <div>
          <span className="eyebrow">BUSINESS PERFORMANCE</span>
          <h2>Sales, stock & team</h2>
          <p className="muted">
            Posted sales exclude tax and return credits. Costs use the values
            recorded at sale.
          </p>
        </div>
        <div className="insight-controls">
          <label>
            Chart period
            <select
              aria-label="Chart period"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
          </label>
          <button
            className="icon-button"
            aria-label="Refresh business charts"
            disabled={loading}
            onClick={() => void load()}
          >
            <RefreshCw size={17} />
          </button>
        </div>
      </div>
      {error && (
        <p role="alert" className="alert">
          Charts: {error}{" "}
          <button onClick={() => void load()}>Retry charts</button>
        </p>
      )}
      {!data ? (
        <p role="status" className="insight-loading">
          {error
            ? "Business charts are currently unavailable."
            : "Loading business charts…"}
        </p>
      ) : (
        <>
          <div className="insight-layout">
            <div className="insight-main">
              <section
                className="panel insight-panel insight-trend"
                aria-label="Profit and sales"
              >
                <div className="insight-panel-heading">
                  <div>
                    <h3>Profit vs sales</h3>
                    <p>
                      {shortDate(data.period.start)} –{" "}
                      {shortDate(data.period.end)}
                    </p>
                  </div>
                  <BarChart3 size={21} />
                </div>
                <div className="insight-legend">
                  <span>
                    <i className="sales" />
                    Posted sales
                  </span>
                  <span>
                    <i className="profit" />
                    Gross profit
                  </span>
                </div>
                <Trend daily={data.daily} />
                {summary?.missing_cost_lines !== 0 && (
                  <p className="insight-note">
                    Profit is incomplete for {summary?.missing_cost_lines} lines
                    with no recorded cost.
                  </p>
                )}
                {summary?.sales_count === 0 && (
                  <p className="insight-note">
                    No posted sales in this period. Orders appear here after
                    payment or credit is recorded.
                  </p>
                )}
              </section>
              <section
                className="panel insight-panel"
                aria-label="Low stock items"
              >
                <div className="insight-panel-heading">
                  <div>
                    <h3>Low stock items</h3>
                    <p>
                      {data.low_stock_count} products at or below reorder level
                      · current stock
                    </p>
                  </div>
                  <Package size={20} />
                </div>
                <div className="insight-stock-list">
                  {data.low_stock.length ? (
                    data.low_stock.map((p) => (
                      <div className="insight-stock-item" key={p.id}>
                        <div>
                          <strong>{p.name}</strong>
                          <span>
                            {p.sku} · Reorder at {p.reorder_level} {p.unit}
                          </span>
                        </div>
                        <div className="insight-stock-value">
                          <strong className={p.stock === 0 ? "negative" : ""}>
                            {p.stock} {p.unit}
                          </strong>
                          <div className="insight-track">
                            <i
                              style={{
                                width: `${p.reorder_level ? Math.min(100, (p.stock / p.reorder_level) * 100) : 0}%`,
                              }}
                            />
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="insight-empty">
                      Stock is above its reorder levels.
                    </p>
                  )}
                </div>
                <button className="insight-link" onClick={onProducts}>
                  View products & stock <ArrowRight size={14} />
                </button>
              </section>
              <section
                className="panel insight-panel"
                aria-label="Staff performance"
              >
                <div className="insight-panel-heading">
                  <div>
                    <h3>Staff performance</h3>
                    <p>Sales credited to the account that recorded the order</p>
                  </div>
                  <Users size={20} />
                </div>
                {data.staff.length ? (
                  <>
                    <div className="insight-staff-highlight">
                      <span className="staff-avatar">
                        {data.staff[0].name
                          .split(" ")
                          .map((x) => x[0])
                          .slice(0, 2)
                          .join("")}
                      </span>
                      <strong>{data.staff[0].name}</strong>
                      <span>Highest net posted sales in this period</span>
                      <b>{money(data.staff[0].net_sales_minor)}</b>
                    </div>
                    <div className="insight-staff-list">
                      {data.staff.map((s) => (
                        <div key={s.user_id}>
                          <span>
                            <strong>{s.name}</strong>
                            <small>
                              {s.fulfilled_orders}/{s.order_count} orders
                              fulfilled
                              {s.fulfillment_percent === null
                                ? ""
                                : ` · ${s.fulfillment_percent}%`}
                            </small>
                          </span>
                          <b>{money(s.net_sales_minor)}</b>
                        </div>
                      ))}
                    </div>
                    <p className="insight-note">
                      Fulfillment uses current status of non-cancelled orders
                      created in this period.
                    </p>
                  </>
                ) : (
                  <p className="insight-empty">
                    Staff activity will appear when workspace members record
                    orders.
                  </p>
                )}
              </section>
            </div>
            <aside className="insight-side">
              <section
                className="panel insight-panel"
                aria-label="Gross profit"
              >
                <div className="insight-panel-heading">
                  <div>
                    <h3>Gross profit</h3>
                    <p>Sales less recorded cost of goods</p>
                  </div>
                  <TrendingUp size={20} />
                </div>
                <strong className="insight-profit-total">
                  {summary?.gross_profit_minor == null
                    ? "Cost data incomplete"
                    : money(summary.gross_profit_minor)}
                </strong>
                <div className="insight-profit-bars">
                  {bars.map((b) => (
                    <div key={b.name}>
                      <div>
                        <span>{b.name}</span>
                        <strong>
                          {b.value === null ? "Unknown cost" : money(b.value)}
                        </strong>
                      </div>
                      <div className="insight-track">
                        <i
                          className={(b.value || 0) < 0 ? "negative-bar" : ""}
                          style={{
                            width:
                              b.value === null
                                ? "0%"
                                : `${(Math.abs(b.value) / scale) * 100}%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <button className="insight-link" onClick={onReports}>
                  Open financial report <ArrowRight size={14} />
                </button>
              </section>
              <section
                className="panel insight-panel"
                aria-label="Top selling products"
              >
                <div className="insight-panel-heading">
                  <div>
                    <h3>Top selling products</h3>
                    <p>Net quantities sold after returns</p>
                  </div>
                  <Package size={20} />
                </div>
                {data.top_products.length ? (
                  data.top_products.map((p, i) => (
                    <div className="insight-top-product" key={p.product_id}>
                      <span className="insight-rank">{i + 1}</span>
                      <div>
                        <strong>{p.name}</strong>
                        <span>
                          {p.quantity.toLocaleString()} catalog units ·{" "}
                          {money(p.net_sales_minor)}
                        </span>
                        <div className="insight-track">
                          <i
                            style={{
                              width: `${(p.quantity / data.top_products[0].quantity) * 100}%`,
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="insight-empty">
                    No net product sales in this period.
                  </p>
                )}
                <p className="insight-note">
                  Quantities use each SKU’s selling unit; packs and pieces are
                  not converted.
                </p>
              </section>
            </aside>
          </div>
          {!!summary?.unposted_orders && (
            <p className="insight-note">
              {summary.unposted_orders} orders have no payment/credit posting
              and are excluded from financial charts.
            </p>
          )}
        </>
      )}
    </section>
  );
}
