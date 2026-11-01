"use client";
import Link from "next/link";
import { wholesaleCategories } from "../lib/wholesale";
import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  AudioLines,
  Check,
  CheckCheck,
  ChevronRight,
  CircleHelp,
  Cpu,
  FileImage,
  Globe2,
  Layers3,
  LayoutDashboard,
  LockKeyhole,
  Menu,
  MessageCircle,
  Package,
  Pause,
  Play,
  Plus,
  Send,
  ShieldCheck,
  Shirt,
  ShoppingBag,
  Sparkles,
  Users,
  X,
} from "lucide-react";

const navigation = [
  ["Home", "home"],
  ["Features", "features"],
  ["How It Works", "how-it-works"],
  ["Solutions", "solutions"],
  ["Pricing", "pricing"],
  ["FAQs", "questions"],
];
const sequence = [
  "A conversation begins",
  "Details come into focus",
  "An order draft takes shape",
  "Your team reviews the order",
  "A reply, with a human touch",
  "Less admin. More possibility.",
];
const steps = [
  [
    "A message starts the story.",
    "Your customer asks for what they need on WhatsApp. Connected inboxes keep the original conversation in view.",
  ],
  [
    "AI brings the details into focus.",
    "Text extraction identifies catalog items and quantities in Sinhala, English or Tamil. Uncertain details are flagged for your team.",
  ],
  [
    "A draft. Your team decides.",
    "Review the customer, products, quantities and prices. Nothing becomes an order until you explicitly confirm it.",
  ],
  [
    "Keep stock and fulfillment in view.",
    "Bring confirmed orders, inventory and fulfillment together in one business workspace.",
  ],
  [
    "See the business at a glance.",
    "Explore illustrative sales, order and stock insights alongside the records your team manages.",
  ],
];
const examples = [
  "Hi, I want to order 2 black T-shirts, size M.",
  "Please send 3 bags of rice.",
  "හාල් බෑග් 2ක් එවන්න.",
];
const faqs = [
  [
    "What does OrderMesh AI do?",
    "Built for wholesalers and distributors, OrderMesh brings customer information, text-to-order drafts, stock, orders and fulfillment into one workspace. It helps your team organize incoming requests while keeping order confirmation in human hands.",
  ],
  [
    "How does WhatsApp integration work?",
    "The app includes a Meta Cloud API connection flow, inbox, text-message processing and team replies. Live use requires your business number, Meta setup and approvals, and end-to-end verification. The demonstrations on this page run locally and do not connect to WhatsApp.",
  ],
  [
    "Do I need technical knowledge?",
    "Everyday work uses a visual dashboard. Initial WhatsApp and payment-provider setup still requires configuration and verification. Contact us to discuss the setup your business needs.",
  ],
  [
    "Can customers write in Sinhala, English and Tamil?",
    "Yes. Text extraction supports Sinhala, English and Tamil, with catalog matching and human review. Accuracy depends on the message and your catalog. WhatsApp voice notes can be transcribed with a configured speech provider and require review. Image text reading also requires provider setup and human review; product photos without readable order details need manual entry.",
  ],
  [
    "How do usage limits work?",
    "The configured Starter plan has a default allowance of 500 orders per month. The workspace enforces its assigned allowance. AI provider access depends on configuration; no unlimited messages or AI usage are promised. Confirm provider costs and usage policies before activating live integrations.",
  ],
  [
    "Can I review orders before they are created?",
    "Yes. Human confirmation is mandatory. You review and edit extracted details before confirming an order. An extraction or incoming message alone cannot create a confirmed order.",
  ],
  [
    "Can I upgrade to Growth or Business Pro?",
    "These are planned tiers. Prices, allowances and upgrade paths are not yet configured, so they cannot currently be purchased. Contact us about your needs; only the existing Starter plan is presented with a price.",
  ],
  [
    "How do subscriptions and support work?",
    "Starter is LKR 7,400 per month with a 15-day trial in the application. Recurring billing is implemented but requires payment-provider configuration and verification. Review the available billing options in your workspace, or contact info@ordermesh.com for assistance.",
  ],
];
function Logo() {
  return (
    <Link href="/" className="om-logo" aria-label="OrderMesh home">
      <span className="om-mark">
        <Layers3 size={23} />
      </span>
      <span>
        OrderMesh<span className="om-ai">AI</span>
      </span>
    </Link>
  );
}
function Phone({ stage = 5 }: { stage?: number }) {
  return (
    <div className="om-phone">
      <div className="om-phone-status">
        <span>9:41</span>
        <span className="om-island" />
        <span>● ▰</span>
      </div>
      <div className="om-chat-top">
        <span className="om-avatar">
          <ShoppingBag size={18} />
        </span>
        <div>
          <strong>Studio Ceylon</strong>
          <small>Example business conversation</small>
        </div>
        <MessageCircle size={18} />
      </div>
      <div className="om-chat-body">
        <span className="om-chat-date">TODAY · DEMONSTRATION</span>
        <div className="om-bubble in">
          Hi, I want to order 2 black T-shirts, size M.
          <small>
            09:41 <CheckCheck size={12} />
          </small>
        </div>
        <div className={`om-chat-product ${stage >= 1 ? "shown" : ""}`}>
          <div className="om-shirt">
            <Shirt size={52} strokeWidth={1.1} />
          </div>
          <div>
            <strong>Essential tee</strong>
            <span>Midnight black · M</span>
            <small>2 items requested</small>
          </div>
        </div>
        <div className={`om-bubble out ${stage >= 4 ? "shown" : ""}`}>
          Thanks! I’ve reviewed your order. We’ll confirm delivery details next.
          <small>
            Example team reply <CheckCheck size={12} />
          </small>
        </div>
        <div className="om-chat-note">
          <LockKeyhole size={11} /> Illustrative messages. No messages sent.
        </div>
      </div>
      <div className="om-chat-input">
        <Plus size={17} />
        <span>Message</span>
        <AudioLines size={17} />
      </div>
      <div className="om-homebar" />
    </div>
  );
}
const rows = [
  {
    name: "Nimali Perera",
    item: "Essential tee × 2",
    amount: "4,800",
    status: "To review",
    initials: "NP",
  },
  {
    name: "Kasun Silva",
    item: "Linen shirt × 1",
    amount: "3,200",
    status: "Confirmed",
    initials: "KS",
  },
  {
    name: "Amaya Fernando",
    item: "Canvas tote × 1",
    amount: "1,850",
    status: "Completed",
    initials: "AF",
  },
];
function Dashboard({ compact = false }: { compact?: boolean }) {
  const [tab, setTab] = useState("Overview");
  const [filter, setFilter] = useState("All orders");
  const visible = rows.filter(
    (row) => filter === "All orders" || row.status === filter,
  );
  return (
    <div className={`om-dashboard ${compact ? "compact" : ""}`}>
      <div className="om-windowbar">
        <div>
          <i />
          <i />
          <i />
        </div>
        <span>
          <LockKeyhole size={10} /> OrderMesh workspace
        </span>
        <small>SAMPLE DATA</small>
      </div>
      <div className="om-app">
        <aside className="om-app-sidebar">
          <Layers3 size={24} />
          <div>
            {[
              { name: "Overview", Icon: LayoutDashboard },
              { name: "Orders", Icon: Package },
              { name: "Conversations", Icon: MessageCircle },
              { name: "Customers", Icon: Users },
            ].map(({ name, Icon }) => (
              <button
                key={name}
                aria-label={`Preview ${name.toLowerCase()}`}
                aria-pressed={tab === name}
                onClick={() => setTab(name)}
                className={tab === name ? "selected" : ""}
              >
                <Icon size={17} />
                <span>{name}</span>
              </button>
            ))}
          </div>
          <span className="om-sidebar-bottom">
            <span className="om-avatar">SC</span>
            <span>
              Studio Ceylon<small>Demo workspace</small>
            </span>
          </span>
        </aside>
        <div className="om-app-main">
          <div className="om-app-heading">
            <div>
              <small>YOUR BUSINESS, AT A GLANCE</small>
              <h3>
                {tab === "Overview"
                  ? "A little clarity. A lot of possibility."
                  : tab}
              </h3>
            </div>
            <span className="om-avatar">SC</span>
          </div>
          {tab === "Overview" && (
            <>
              <div className="om-stats">
                <div>
                  <span>Sample order value</span>
                  <strong>LKR 9,850</strong>
                  <small>3 illustrative orders</small>
                </div>
                <div>
                  <span>Pending review</span>
                  <strong>
                    01
                    <span className="om-stat-dot" />
                  </strong>
                  <small>You’re in control</small>
                </div>
                <div>
                  <span>Completed</span>
                  <strong>01</strong>
                  <small>Ready for what’s next</small>
                </div>
              </div>
              <div className="om-chart">
                <div>
                  <strong>Business activity</strong>
                  <span>Illustrative week</span>
                </div>
                <div
                  className="om-bars"
                  role="img"
                  aria-label="Illustrative activity chart, not real business performance"
                >
                  {[30, 54, 43, 78, 58, 91, 70, 45, 66, 85, 62, 98, 80, 94].map(
                    (height, i) => (
                      <i
                        key={i}
                        style={
                          {
                            "--bar": `${height}%`,
                            "--delay": `${i * 40}ms`,
                          } as CSSProperties
                        }
                      />
                    ),
                  )}
                </div>
                <div className="om-chart-days">
                  <span>Mon</span>
                  <span>Tue</span>
                  <span>Wed</span>
                  <span>Thu</span>
                  <span>Fri</span>
                  <span>Sat</span>
                  <span>Sun</span>
                </div>
              </div>
            </>
          )}
          {(tab === "Overview" || tab === "Orders") && (
            <>
              <div className="om-table-title">
                <strong>
                  {tab === "Orders" ? "Manage your orders" : "Recent orders"}
                </strong>
                <span>Example records</span>
              </div>
              {tab === "Orders" && (
                <div className="om-filters">
                  {["All orders", "To review", "Confirmed", "Completed"].map(
                    (name) => (
                      <button
                        key={name}
                        aria-pressed={filter === name}
                        onClick={() => setFilter(name)}
                      >
                        {name}
                      </button>
                    ),
                  )}
                </div>
              )}
              <div className="om-order-table">
                <div className="om-table-header">
                  <span>Customer / order</span>
                  <span>Amount (LKR)</span>
                  <span>Status</span>
                </div>
                {visible.map((row) => (
                  <div className="om-table-row" key={row.name}>
                    <span>
                      <span className="om-avatar">{row.initials}</span>
                      <span>
                        <strong>{row.name}</strong>
                        <small>{row.item}</small>
                      </span>
                    </span>
                    <span>{row.amount}</span>
                    <span
                      className={`om-status ${row.status.toLowerCase().replace(" ", "-")}`}
                    >
                      {row.status}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
          {tab === "Customers" && (
            <div className="om-customer-list">
              {rows.map((row) => (
                <div key={row.name}>
                  <span className="om-avatar">{row.initials}</span>
                  <div>
                    <strong>{row.name}</strong>
                    <p>Example customer · 1 order</p>
                  </div>
                  <span>Customer record</span>
                </div>
              ))}
            </div>
          )}
          {tab === "Conversations" && (
            <div className="om-inbox">
              <div className="om-inbox-message">
                <MessageCircle />
                <div>
                  <strong>Nimali Perera</strong>
                  <p>Hi, I want to order 2 black T-shirts, size M.</p>
                  <span className="om-status to-review">
                    Draft ready for review
                  </span>
                </div>
              </div>
              <div className="om-activity">
                <Sparkles size={17} />
                <p>
                  Text details organized. Customer and catalog review needed
                  before confirmation.
                </p>
              </div>
              <p className="om-fine">
                Inbox preview only. WhatsApp requires provider setup and live
                verification.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
function Cinema({ paused }: { paused: boolean }) {
  const [stage, setStage] = useState(5);
  const [localPaused, setLocalPaused] = useState(false);
  const scene = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    let visible = true;
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
    });
    if (scene.current) observer.observe(scene.current);
    const timer = setInterval(() => {
      if (
        !paused &&
        !localPaused &&
        !media.matches &&
        visible &&
        !document.hidden
      )
        setStage((s) => (s + 1) % 6);
    }, 2200);
    return () => {
      clearInterval(timer);
      observer.disconnect();
    };
  }, [paused, localPaused]);
  return (
    <div
      className="om-cinema"
      ref={scene}
      onPointerMove={(event) => {
        if (
          event.pointerType !== "mouse" ||
          paused ||
          matchMedia("(prefers-reduced-motion: reduce)").matches
        )
          return;
        const bounds = event.currentTarget.getBoundingClientRect();
        event.currentTarget.style.setProperty(
          "--pointer-x",
          `${((event.clientX - bounds.left) / bounds.width) * 100}%`,
        );
        event.currentTarget.style.setProperty(
          "--pointer-y",
          `${((event.clientY - bounds.top) / bounds.height) * 100}%`,
        );
      }}
    >
      <div className="om-scene-grid" />
      <div className="om-orbit orbit-one" />
      <div className="om-orbit orbit-two" />
      <div className="om-phone-position">
        <Phone stage={stage} />
      </div>
      <div className={`om-ai-core ${stage === 1 ? "processing" : ""}`}>
        <span>
          <Layers3 size={30} />
        </span>
        <small>ORDERMESH AI</small>
      </div>
      <div className="om-connection connection-one" />
      <div className="om-connection connection-two" />
      <div className="om-dashboard-position">
        <Dashboard compact />
      </div>
      <div className={`om-extracted ${stage >= 2 ? "shown" : ""}`}>
        <span className="om-success-icon">
          <Check size={16} />
        </span>
        <div>
          <strong>Message → order draft</strong>
          <p>Black T-shirt · 2 items · Size M</p>
          <span>Ready for your review</span>
        </div>
        <Sparkles size={16} />
      </div>
      <div className="om-language-float">
        <Globe2 size={18} />
        <span>
          Made for your conversations<small>සිංහල & English text</small>
        </span>
      </div>
      <div className="om-cinema-controls">
        <button
          onClick={() => setLocalPaused(!localPaused)}
          aria-label={
            localPaused ? "Play product sequence" : "Pause product sequence"
          }
        >
          {localPaused ? <Play size={14} /> : <Pause size={14} />}
        </button>
        <span>
          PRODUCT FILM <b>0{stage + 1} / 06</b>
        </span>
        <div className="om-film-dots">
          {sequence.map((label, i) => (
            <button
              key={label}
              aria-label={`Show scene ${i + 1}: ${label}`}
              aria-pressed={i === stage}
              onClick={() => {
                setStage(i);
                setLocalPaused(true);
              }}
            />
          ))}
        </div>
        <span className="om-scene-caption">{sequence[stage]}</span>
      </div>
    </div>
  );
}
function Workflow() {
  const [step, setStep] = useState(0);
  const region = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries)
          if (entry.isIntersecting)
            setStep(Number((entry.target as HTMLElement).dataset.step));
      },
      { rootMargin: "-32% 0px -42% 0px", threshold: 0 },
    );
    region.current
      ?.querySelectorAll("[data-step]")
      .forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);
  return (
    <div className="om-workflow" ref={region}>
      <div className="om-workflow-sticky">
        <div className="om-workflow-tabs">
          {steps.map((s, i) => (
            <button
              key={s[0]}
              aria-label={`Workflow step ${i + 1}`}
              aria-pressed={step === i}
              onClick={() => setStep(i)}
            >
              0{i + 1}
            </button>
          ))}
        </div>
        <div className="om-transform-panel" key={step}>
          <span className="om-eyebrow">
            {
              [
                "INCOMING MESSAGE",
                "TEXT UNDERSTANDING",
                "DRAFT FOR HUMAN REVIEW",
                "ONE CONNECTED WORKSPACE",
              ][step]
            }
          </span>
          {step === 0 ? (
            <>
              <MessageCircle className="om-large-icon" />
              <div className="om-bubble in">
                Hi, I want to order 2 black T-shirts, size M.
                <small>Example customer message</small>
              </div>
              <p>One conversation. All the context.</p>
            </>
          ) : step === 1 ? (
            <>
              <Cpu className="om-large-icon" />
              <div className="om-token-message">
                Hi, I want to order <mark>2</mark> <mark>black T-shirts</mark>,
                size <mark>M</mark>.
              </div>
              <div className="om-extraction-fields">
                <span>
                  Product <b>Black T-shirt</b>
                </span>
                <span>
                  Quantity <b>2</b>
                </span>
                <span>
                  Size <b>M</b>
                </span>
              </div>
            </>
          ) : step === 2 ? (
            <>
              <div className="om-review-title">
                <Shirt size={42} />
                <span>
                  Order draft<strong>Essential black tee</strong>
                </span>
              </div>
              <div className="om-extraction-fields">
                <span>
                  Quantity <b>2</b>
                </span>
                <span>
                  Variant <b>Size M</b>
                </span>
                <span>
                  Example total <b>LKR 4,800</b>
                </span>
              </div>
              <div className="om-review-notice">
                <ShieldCheck size={19} /> Your confirmation is required.
              </div>
            </>
          ) : step === 3 ? (
            <>
              <LayoutDashboard className="om-large-icon" />
              <div className="om-complete-order">
                <Check size={22} />
                <div>
                  <strong>Stock and fulfillment, in view.</strong>
                  <p>Confirmed order → Inventory → Dispatch</p>
                </div>
              </div>
              <div className="om-extraction-fields">
                <span>
                  Catalog <b>In view</b>
                </span>
                <span>
                  Stock <b>Trackable</b>
                </span>
                <span>
                  Fulfillment <b>Organized</b>
                </span>
              </div>
            </>
          ) : (
            <>
              <LayoutDashboard className="om-large-icon" />
              <div className="om-complete-order">
                <Check size={22} />
                <div>
                  <strong>Your business, at a glance.</strong>
                  <p>Illustrative workspace overview</p>
                </div>
              </div>
              <div className="om-extraction-fields">
                <span>
                  Orders <b>In view</b>
                </span>
                <span>
                  Sales <b>Illustrative</b>
                </span>
                <span>
                  Stock <b>Trackable</b>
                </span>
              </div>
            </>
          )}
          <small className="om-fine">
            Illustrative workflow · no real order is created
          </small>
        </div>
      </div>
      <div className="om-workflow-steps">
        {steps.map(([title, description], i) => (
          <article
            key={title}
            data-step={i}
            className={step === i ? "active" : ""}
          >
            <span>0{i + 1}</span>
            <h3>{title}</h3>
            <p>{description}</p>
            <button onClick={() => setStep(i)}>
              Explore this step <ArrowUpRight size={17} />
            </button>
          </article>
        ))}
      </div>
    </div>
  );
}
function LiveDemo() {
  const [text, setText] = useState(examples[0]);
  const [result, setResult] = useState<{
    product: string;
    quantity: string;
    size: string;
    matched: boolean;
  } | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  function interpret() {
    const shirt =
      /\bblack\b/i.test(text) && /\b(t[ -]?shirts?|tees?)\b/i.test(text);
    const rice = /\brice\b|හාල්/i.test(text);
    const quantity =
      text
        .match(/\b(\d{1,3})\b|([0-9]{1,3})(?=ක්)/)?.[0]
        ?.replace(/[^0-9]/g, "") || "Needs review";
    setResult({
      product: shirt
        ? "Black T-shirt"
        : rice
          ? "Rice bag"
          : "No sample catalog match",
      quantity: Number(quantity) > 0 ? quantity : "Needs review",
      size: shirt
        ? text.match(/size\s+(XS|XL|S|M|L)\b/i)?.[1]?.toUpperCase() ||
          "Needs review"
        : "—",
      matched: shirt || rice,
    });
    setConfirmed(false);
  }
  return (
    <div className="om-live-demo">
      <div className="om-demo-chat">
        <div className="om-demo-panel-title">
          <MessageCircle size={20} />
          <span>Start with a message</span>
          <small>LOCAL SIMULATOR</small>
        </div>
        <div className="om-example-choices">
          {examples.map((example, i) => (
            <button
              key={example}
              lang={i === 2 ? "si" : "en"}
              onClick={() => {
                setText(example);
                setResult(null);
                setConfirmed(false);
              }}
              aria-pressed={text === example}
            >
              {["Clothing order", "Grocery order", "සිංහල උදාහරණය"][i]}
            </button>
          ))}
        </div>
        <label htmlFor="demo-message">Your example customer message</label>
        <textarea
          id="demo-message"
          maxLength={400}
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            setResult(null);
            setConfirmed(false);
          }}
        />
        <div className="om-demo-input-footer">
          <span>{text.length}/400 · Use fictional details</span>
          <button
            className="om-button primary"
            onClick={interpret}
            disabled={!text.trim()}
          >
            Organize message <Send size={16} />
          </button>
        </div>
        <p className="om-fine">
          Runs only in your browser using sample rules and a two-item catalog.
          No AI service, WhatsApp connection, storage or message sending.
        </p>
      </div>
      <div className="om-demo-result" aria-live="polite">
        <div className="om-demo-panel-title">
          <Layers3 size={20} />
          <span>Your order workspace</span>
          <span className="om-status to-review">DEMO</span>
        </div>
        {result ? (
          <>
            <div className="om-result-heading">
              <span className="om-success-icon">
                {result.matched ? (
                  <Check size={22} />
                ) : (
                  <CircleHelp size={22} />
                )}
              </span>
              <h3>
                {confirmed
                  ? "Example order confirmed"
                  : result.matched
                    ? "A draft, ready for your review."
                    : "This needs a human look."}
              </h3>
            </div>
            <div className="om-extraction-fields">
              <span>
                Product <b>{result.product}</b>
              </span>
              <span>
                Quantity <b>{result.quantity}</b>
              </span>
              <span>
                Size <b>{result.size}</b>
              </span>
            </div>
            <p className="om-fine">
              {confirmed
                ? "Simulation complete. No order was saved and no reply was sent."
                : "Sample matching only. Review the original message; colors, prices, customers and delivery details are not inferred."}
            </p>
            {!confirmed && result.matched && (
              <button
                className="om-button secondary"
                onClick={() => setConfirmed(true)}
                disabled={
                  result.quantity === "Needs review" ||
                  result.size === "Needs review"
                }
              >
                Confirm example only <Check size={16} />
              </button>
            )}
            <button
              className="om-text-button"
              onClick={() => {
                setResult(null);
                setConfirmed(false);
              }}
            >
              Reset demo
            </button>
          </>
        ) : (
          <div className="om-demo-empty">
            <span>
              <Sparkles size={34} />
            </span>
            <h3>
              A little message.
              <br />A clearer next step.
            </h3>
            <p>
              Choose an example or try your own.
              <br />
              Your sample draft will appear here.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
function FutureFeature({ voice = false }: { voice?: boolean }) {
  const [playing, setPlaying] = useState(false);
  return (
    <article className={`om-future-feature ${playing ? "playing" : ""}`}>
      <div className="om-future-visual">
        {voice ? (
          <>
            <span className="om-voice-icon">
              <AudioLines size={25} />
            </span>
            <div className="om-wave" aria-hidden="true">
              {[
                16, 24, 38, 20, 45, 31, 54, 28, 41, 19, 34, 50, 27, 40, 22, 13,
                31, 18,
              ].map((h, i) => (
                <i
                  key={i}
                  style={
                    { height: h, "--delay": `${i * 70}ms` } as CSSProperties
                  }
                />
              ))}
            </div>
            <span>0:12</span>
          </>
        ) : (
          <>
            <div className="om-photo-card">
              <Shirt size={62} strokeWidth={1.1} />
              <span>Customer product image</span>
              <div className="om-scan" />
            </div>
            <ArrowRight size={22} />
            <div className="om-image-result">
              <FileImage size={22} />
              <span>Product details</span>
              <i />
              <i />
              <i />
            </div>
          </>
        )}
      </div>
      <div className="om-future-copy">
        <span className="om-status planned">
          {voice
            ? "VOICE TRANSCRIPTION · PROVIDER SETUP REQUIRED"
            : "IMAGE TEXT READING · PROVIDER SETUP REQUIRED"}
        </span>
        <h3>
          {voice
            ? "From voice notes to reviewable details."
            : "Read an order from a picture."}
        </h3>
        <p>
          {voice
            ? "Connected WhatsApp voice notes can be transcribed in their original language when speech processing is configured. Review names, quantities and prices before confirming."
            : "Read visible typed or handwritten order text with a configured AI provider. Check unclear details before confirming; photographed objects alone do not establish products or quantities."}
        </p>
        <button
          className="om-text-button"
          aria-pressed={playing}
          onClick={() => setPlaying(!playing)}
        >
          {playing ? <Pause size={14} /> : <Play size={14} />}
          {playing ? "Pause concept animation" : "Play concept animation"}
        </button>
      </div>
    </article>
  );
}
export default function Landing() {
  const [menu, setMenu] = useState(false);
  const [active, setActive] = useState("home");
  const [paused, setPaused] = useState(false);
  const [solution, setSolution] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const solutions = wholesaleCategories
    .filter((category) => category.value !== "other")
    .map(
      (category) =>
        [
          category.label,
          `${category.label} wholesale, organized.`,
          `${category.examples}. Keep trade customer requests, catalog SKUs, quantities, stock and fulfillment together. Review every order before confirmation.`,
          category.value === "electronics"
            ? Cpu
            : category.value === "fashion"
              ? Shirt
              : category.value === "beauty"
                ? Sparkles
                : Package,
        ] as const,
    );
  const SolutionIcon = solutions[solution][3];
  useEffect(() => {
    const reveal = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("revealed");
            reveal.unobserve(entry.target);
          }
        }),
      { threshold: 0.08 },
    );
    root.current
      ?.querySelectorAll(".om-reveal")
      .forEach((el) => reveal.observe(el));
    const nav = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => {
          if (entry.isIntersecting) setActive(entry.target.id);
        }),
      { rootMargin: "-15% 0px -65% 0px" },
    );
    navigation.forEach(([, id]) => {
      const section = document.getElementById(id);
      if (section) nav.observe(section);
    });
    const escape = (event: KeyboardEvent) => {
      if (
        event.key === "Escape" &&
        document
          .getElementById("om-menu-toggle")
          ?.getAttribute("aria-expanded") === "true"
      ) {
        setMenu(false);
        document.getElementById("om-menu-toggle")?.focus();
      }
    };
    document.addEventListener("keydown", escape);
    return () => {
      reveal.disconnect();
      nav.disconnect();
      document.removeEventListener("keydown", escape);
    };
  }, []);
  return (
    <div ref={root} className={`om ${paused ? "om-paused" : ""}`}>
      <a className="om-skip" href="#main">
        Skip to content
      </a>
      <header className="om-header">
        <div className="om-container om-nav-wrap">
          <Logo />
          <nav
            id="om-navigation"
            aria-label="Main navigation"
            className={menu ? "open" : ""}
          >
            {navigation.map(([label, id]) => (
              <a
                key={id}
                href={`#${id}`}
                aria-current={active === id ? "location" : undefined}
                onClick={() => setMenu(false)}
              >
                {label}
              </a>
            ))}
            <Link className="om-mobile-login" href="/sign-in">
              Login
            </Link>
          </nav>
          <div className="om-nav-actions">
            <Link className="om-login" href="/sign-in">
              Login <ArrowUpRight size={13} />
            </Link>
            <Link className="om-button primary small" href="/sign-up">
              Get Started <ArrowUpRight size={15} />
            </Link>
            <button
              id="om-menu-toggle"
              className="om-menu-toggle"
              aria-label={menu ? "Close navigation" : "Open navigation"}
              aria-expanded={menu}
              aria-controls="om-navigation"
              onClick={() => setMenu(!menu)}
            >
              {menu ? <X /> : <Menu />}
            </button>
          </div>
        </div>
      </header>
      <main id="main">
        <section id="home" className="om-hero">
          <div className="om-hero-glow" />
          <div className="om-container om-hero-copy">
            <div className="om-pill">
              <span /> BUILT FOR THE WAY SRI LANKA DOES BUSINESS{" "}
              <ArrowUpRight size={12} />
            </div>
            <h1>
              Your Business.
              <br />
              <span>One Intelligent Platform.</span>
            </h1>
            <h2>Built for wholesalers and distributors.</h2>
            <p>
              Transform WhatsApp conversations, orders, inventory, sales, and
              business operations into one connected experience.
            </p>
            <div className="om-actions">
              <a className="om-button primary" href="#features">
                Explore Features <ArrowRight size={17} />
              </a>
              <Link className="om-button secondary" href="/sign-up">
                Get Started <ArrowUpRight size={17} />
              </Link>
            </div>
            <div className="om-hero-points">
              <span>
                <Check size={13} /> 15-day trial
              </span>
              <span>
                <Check size={13} /> Sinhala, English & Tamil text
              </span>
              <span>
                <Check size={13} /> Human-reviewed orders
              </span>
            </div>
          </div>
          <div className="om-container">
            <Cinema paused={paused} />
            <div className="om-hero-footnote">
              <span>
                <span className="om-dot" /> A PRODUCT VISION, GROUNDED IN YOUR
                WORKFLOW
              </span>
              <p>
                Simulated product story. WhatsApp requires setup and live
                verification. Every order requires human confirmation.
              </p>
              <a href="#problem" aria-label="Explore the OrderMesh experience">
                <ArrowDown size={19} />
              </a>
            </div>
          </div>
        </section>
        <section className="om-business-strip">
          <div className="om-container">
            <span>
              FOR BUSINESSES BUILT
              <br />
              <strong>one conversation at a time.</strong>
            </span>
            <span>
              <Shirt /> Fashion wholesalers
            </span>
            <span>
              <ShoppingBag /> Vehicle parts
            </span>
            <span>
              <Sparkles /> Beauty distributors
            </span>
            <span>
              <Package /> Grocery & household
            </span>
          </div>
        </section>
        <section id="problem" className="om-section om-problem">
          <div className="om-container">
            <div className="om-section-heading om-reveal">
              <span className="om-eyebrow">LESS CHAOS. MORE CLARITY.</span>
              <h2>
                Less Chaos.
                <br />
                <span>More Control.</span>
              </h2>
              <p>One connected view instead of another disconnected workflow.</p>
            </div>
            <div className="om-before-after om-reveal">
              <article className="om-before">
                <span className="om-eyebrow">THE EVERYDAY JUGGLE</span>
                <div className="om-scattered">
                  <div>
                    “Is this still available?” <small>Unread message</small>
                  </div>
                  <div>
                    2 black tees, M?{" "}
                    <small>Notes · Customer name missing</small>
                  </div>
                  <div>
                    Order-list-final-v3.xlsx{" "}
                    <small>Last updated… yesterday</small>
                  </div>
                </div>
                <p>
                  Repeated questions. Scattered details.
                  <br />
                  Manual entry. Orders that are hard to track.
                </p>
              </article>
              <div className="om-compare-arrow">
                <ArrowRight size={23} />
              </div>
              <article className="om-after">
                <span className="om-eyebrow">THE ORDERMESH WAY</span>
                <div className="om-organized">
                  <div>
                    <span className="om-mark">
                      <Layers3 size={22} />
                    </span>
                    <strong>Everything has its place.</strong>
                    <Check size={18} />
                  </div>
                  {[
                    "Conversations, connected",
                    "Order details, organized",
                    "Human decisions, supported",
                    "Your business, in view",
                  ].map((text) => (
                    <p key={text}>
                      <CheckCheck size={17} />
                      {text}
                    </p>
                  ))}
                </div>
                <p>
                  One workspace. A clear next step.
                  <br />
                  More attention for the people behind every order.
                </p>
              </article>
            </div>
          </div>
        </section>
        <section id="how-it-works" className="om-section om-workflow-section">
          <div className="om-container">
            <div className="om-section-heading om-reveal">
              <span className="om-eyebrow">FROM MESSAGE TO MOMENTUM</span>
              <h2>
                From a Simple Message
                <br />
                <span>to a Smarter Business.</span>
              </h2>
              <p>
                Follow the details from a customer message to a clearer business
                view.
              </p>
            </div>
            <Workflow />
          </div>
        </section>
        <section id="features" className="om-section">
          <div className="om-container">
            <div className="om-section-heading om-heading-split om-reveal">
              <div>
                <span className="om-eyebrow">INTELLIGENCE, WITH INTENTION</span>
                <h2>
                  Less busywork.
                  <br />
                  <span>More business.</span>
                </h2>
              </div>
              <p>
                Useful tools for real working days.
                <br />
                Built around your catalog, your customers,
                <br />
                and your team’s judgment.
              </p>
            </div>
            <article className="om-feature-main om-reveal">
              <div className="om-feature-copy">
                <span className="om-feature-number">
                  01 / TEXT INTELLIGENCE
                </span>
                <h3>
                  Understands the message.
                  <br />
                  Keeps you in control.
                </h3>
                <p>
                  Turn Sinhala, English and Tamil text into structured order
                  drafts. Check product matches, fill in the gaps, and approve
                  when it’s right.
                </p>
                <div className="om-feature-list">
                  <span>
                    <Check /> Catalog-aware text extraction
                  </span>
                  <span>
                    <Check /> Editable drafts & review flags
                  </span>
                  <span>
                    <Check /> Customer and conversation context
                  </span>
                </div>
                <a href="#demo" className="om-text-button">
                  See it in action <ArrowUpRight size={17} />
                </a>
              </div>
              <div className="om-feature-conversation">
                <div className="om-bubble in" lang="si">
                  හාල් බෑග් 2ක් එවන්න.<small>EXAMPLE SINHALA MESSAGE</small>
                </div>
                <div className="om-understanding-line">
                  <span />
                  <Sparkles size={22} />
                  <span />
                </div>
                <div className="om-translation">
                  <span className="om-eyebrow">
                    A LITTLE STRUCTURE GOES A LONG WAY
                  </span>
                  <h4>
                    Rice bags <span>× 2</span>
                  </h4>
                  <p>Catalog match → Review → Confirm</p>
                  <span className="om-status to-review">
                    Human review required
                  </span>
                </div>
              </div>
            </article>
            <div className="om-secondary-features om-reveal">
              <article>
                <span className="om-feature-number">
                  02 / CONNECTED OPERATIONS
                </span>
                <Package size={31} />
                <h3>POS, orders and stock in one flow.</h3>
                <p>
                  Keep counter sales, inventory, customers, confirmed orders
                  and fulfillment together with a clear activity history.
                </p>
                <div className="om-status-track">
                  <span>Review</span>
                  <ChevronRight size={13} />
                  <span>Confirmed</span>
                  <ChevronRight size={13} />
                  <span>Fulfilled</span>
                </div>
              </article>
              <article>
                <span className="om-feature-number">
                  03 / CUSTOMER CONVERSATIONS
                </span>
                <MessageCircle size={31} />
                <h3>Keep customer context close.</h3>
                <p>
                  A connected inbox and team replies, subject to Meta setup and
                  verification. Fully automated customer responses are not
                  available in this release.
                </p>
                <span className="om-status planned">
                  WHATSAPP · SETUP REQUIRED
                </span>
              </article>
            </div>
            <div className="om-future-grid om-reveal">
              <FutureFeature />
              <FutureFeature voice />
            </div>
          </div>
        </section>
        <section id="demo" className="om-section om-demo-section">
          <div className="om-container">
            <div className="om-section-heading om-reveal">
              <span className="om-eyebrow">DON’T JUST IMAGINE IT. TRY IT.</span>
              <h2>
                Your message.
                <br />
                <span>A more organized next step.</span>
              </h2>
              <p>
                A hands-on, local simulation. Fictional messages. Real clarity.
              </p>
            </div>
            <LiveDemo />
          </div>
        </section>
        <section id="solutions" className="om-section om-solutions">
          <div className="om-container">
            <div className="om-section-heading om-reveal">
              <span className="om-eyebrow">
                BUILT FOR THE WAY BUSINESS MOVES
              </span>
              <h2>
                Built for the Way
                <br />
                Business Moves.
              </h2>
              <p>From electronics and grocery to hardware and vehicle parts.</p>
            </div>
            <div className="om-solutions-layout">
              <div className="om-solution-options" aria-label="Business types">
                {solutions.map(([name, , , Icon], i) => (
                  <button
                    key={name}
                    aria-pressed={solution === i}
                    onClick={() => setSolution(i)}
                  >
                    <Icon size={19} />
                    {name}
                    <ArrowUpRight size={17} />
                  </button>
                ))}
              </div>
              <article className="om-solution-detail" key={solution}>
                <div className="om-solution-art">
                  <div className="om-art-ring" />
                  <SolutionIcon size={90} strokeWidth={0.8} />
                  <span className="om-art-tag">
                    <CheckCheck size={15} /> A clearer next step
                  </span>
                </div>
                <span className="om-eyebrow">{solutions[solution][0]}</span>
                <h3>{solutions[solution][1]}</h3>
                <p>{solutions[solution][2]}</p>
                <Link href="/sign-up" className="om-text-button">
                  Explore your workspace <ArrowUpRight size={16} />
                </Link>
              </article>
            </div>
          </div>
        </section>
        <section
          id="dashboard-preview"
          className="om-section om-dashboard-section"
        >
          <div className="om-container">
            <div className="om-section-heading om-reveal">
              <span className="om-eyebrow">
                YOUR BUSINESS, BEAUTIFULLY IN VIEW
              </span>
              <h2>
                Your Entire Business.
                <br />
                <span>One View.</span>
              </h2>
              <p>
                Orders, customers, conversations and activity.
                <br />
                Explore the tabs below. Every record is illustrative.
              </p>
            </div>
            <div className="om-desktop-device om-reveal">
              <Dashboard />
              <div className="om-device-base" />
            </div>
            <div className="om-device-notes">
              <span>
                <LayoutDashboard size={16} /> Clear on desktop
              </span>
              <span>
                <Package size={16} /> Focused on tablet
              </span>
              <span>
                <MessageCircle size={16} /> Ready for your phone
              </span>
            </div>
          </div>
        </section>
        <section id="pricing" className="om-section om-pricing">
          <div className="om-container">
            <div className="om-section-heading om-reveal">
              <span className="om-eyebrow">YOUR NEXT CHAPTER STARTS HERE</span>
              <h2>
                Small beginnings.
                <br />
                Space to grow.
              </h2>
              <p>Start with the available plan. Build at your own pace.</p>
              <span className="om-billing-period">Monthly billing · LKR</span>
            </div>
            <div className="om-pricing-grid om-reveal">
              {["Starter", "Growth", "Business"].map((plan, i) => (
                <article key={plan} className={i === 1 ? "featured" : ""}>
                  {i === 1 && (
                    <span className="om-plan-banner">
                      LOOKING AHEAD · PLANNED TIER
                    </span>
                  )}
                  <span className="om-plan-icon">
                    {i === 0 ? (
                      <Package />
                    ) : i === 1 ? (
                      <Sparkles />
                    ) : (
                      <Layers3 />
                    )}
                  </span>
                  <h3>{plan}</h3>
                  <p>
                    {
                      [
                        "A clear foundation for everyday operations.",
                        "A future step for growing businesses.",
                        "A future tier for more complex operations.",
                      ][i]
                    }
                  </p>
                  <div className="om-price">
                    {i === 0 ? (
                      <>
                        <small>LKR</small> 7,400<span>/ month</span>
                      </>
                    ) : (
                      <>
                        Coming later<span>Price not yet announced</span>
                      </>
                    )}
                  </div>
                  <Link
                    className={`om-button ${i === 0 ? "primary" : "secondary"}`}
                    href={
                      i === 0
                        ? "/sign-up"
                        : "mailto:info@ordermesh.com?subject=OrderMesh%20plan%20enquiry"
                    }
                  >
                    {i === 0 ? "Get Started" : "Discuss your needs"}
                    <ArrowUpRight size={16} />
                  </Link>
                  <ul>
                    {(i === 0
                      ? [
                          "15-day application trial",
                          "500 orders / month by default",
                          "Sinhala, English & Tamil text drafts",
                          "Customers, inventory & fulfillment",
                          "Business dashboard & order activity",
                          "Human review before confirmation",
                        ]
                      : [
                          "Not currently available to purchase",
                          "Allowances not yet configured",
                          "Feature limits to be confirmed",
                          "Contact us about your requirements",
                        ]
                    ).map((item) => (
                      <li key={item}>
                        {i === 0 ? (
                          <Check size={15} />
                        ) : (
                          <span className="om-list-dash">—</span>
                        )}
                        {item}
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
            <p className="om-pricing-note">
              Starter reflects the existing Lite subscription.
              Workspace-specific order limits apply. AI and WhatsApp depend on
              provider setup; unlimited usage is not included. Payment
              activation requires gateway configuration and verification. Growth
              and Business have no published entitlements or self-service
              upgrades yet.
            </p>
          </div>
        </section>
        <section className="om-section om-trust">
          <div className="om-container om-trust-layout">
            <div>
              <span className="om-eyebrow">THOUGHTFUL BY DESIGN</span>
              <h2>
                Work Smarter.
                <br />
                <span>Grow Further.</span>
              </h2>
              <p>
                Your business deserves more than a black box. Keep the context,
                review the details, and make the final decision.
              </p>
              <div className="om-trust-seal">
                <ShieldCheck size={36} />
                <span>
                  Designed around
                  <br />
                  <strong>accountability.</strong>
                </span>
              </div>
            </div>
            <div className="om-trust-points">
              {[
                {
                  Icon: LockKeyhole,
                  title: "Account access with boundaries",
                  text: "Password hashing, server-managed sessions and organization-scoped access are implemented in the application.",
                },
                {
                  Icon: ShieldCheck,
                  title: "Your team has the final say",
                  text: "Extracted information is a draft. Human confirmation is required before an order is created.",
                },
                {
                  Icon: Users,
                  title: "Data with a clear purpose",
                  text: "Customer and order records support your workflows. Configured AI providers may process extraction text; review provider settings before using real customer data.",
                },
                {
                  Icon: CircleHelp,
                  title: "Know what you’re using",
                  text: "Visible order allowances and honest integration status. No invented certifications, uptime guarantees or unlimited AI claims.",
                },
              ].map(({ Icon, title, text }) => (
                <article key={title}>
                  <Icon size={21} />
                  <div>
                    <h3>{title}</h3>
                    <p>{text}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>
        <section id="questions" className="om-section om-faq">
          <div className="om-container om-faq-layout">
            <div>
              <span className="om-eyebrow">A LITTLE MORE CLARITY</span>
              <h2>
                Good questions.
                <br />
                <span>Straight answers.</span>
              </h2>
              <p>Have something else in mind?</p>
              <a href="mailto:info@ordermesh.com" className="om-text-button">
                Let’s talk <ArrowUpRight size={16} />
              </a>
            </div>
            <div>
              {faqs.map(([q, a], i) => (
                <details key={q}>
                  <summary>
                    <span className="om-faq-number">0{i + 1}</span>
                    {q}
                    <Plus size={18} />
                  </summary>
                  <p>{a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>
        <section className="om-final">
          <div className="om-final-orbit" />
          <div className="om-container">
            <span className="om-mark">
              <Layers3 size={30} />
            </span>
            <span className="om-eyebrow">LET’S MAKE ROOM FOR WHAT’S NEXT</span>
            <h2>
              Build the Future
              <br />
              <span>of Your Business.</span>
            </h2>
            <p>
              Bring conversations, orders and everyday operations into clearer
              view.
            </p>
            <div className="om-actions">
              <Link href="/sign-up" className="om-button primary">
                Get Started <ArrowUpRight size={17} />
              </Link>
              <a href="mailto:info@ordermesh.com" className="om-button secondary">
                Contact Us <ArrowUpRight size={16} />
              </a>
            </div>
            <div className="om-final-preview">
              <MessageCircle size={18} />
              <span>A new message</span>
              <ArrowRight size={15} />
              <Layers3 size={18} />
              <span>A clearer next step</span>
              <CheckCheck size={18} />
            </div>
          </div>
        </section>
      </main>
      <footer className="om-footer">
        <div className="om-container">
          <div className="om-footer-grid">
            <div>
              <Logo />
              <p>
                Less admin. More possibility.
                <br />
                Built for the way Sri Lanka does business.
              </p>
              <span className="om-footer-company">
                A product of Qubriant Technologies
              </span>
            </div>
            <div>
              <h3>Product</h3>
              <a href="#features">Features</a>
              <a href="#how-it-works">How it works</a>
              <a href="#demo">Interactive demo</a>
              <a href="#pricing">Pricing</a>
            </div>
            <div>
              <h3>Explore</h3>
              <a href="#solutions">Business solutions</a>
              <a href="#questions">FAQs</a>
              <Link href="/sign-in">Login</Link>
              <Link href="/sign-up">Get Started</Link>
            </div>
            <div>
              <h3>Let’s connect</h3>
              <a href="mailto:info@ordermesh.com">
                info@ordermesh.com <ArrowUpRight size={13} />
              </a>
              <a href="tel:+94722616616">0722 616 616</a>
              <span>Made for Sri Lankan businesses.</span>
            </div>
          </div>
          <div className="om-footer-bottom">
            <span>© 2026 OrderMesh AI. Qubriant Technologies.</span>
            <div>
              <Link href="/privacy">Privacy Policy</Link>
              <Link href="/terms">Terms of Service</Link>
              <button onClick={() => setPaused(!paused)} aria-pressed={paused}>
                {paused ? <Play size={12} /> : <Pause size={12} />}
                {paused ? "Resume motion" : "Pause motion"}
              </button>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
