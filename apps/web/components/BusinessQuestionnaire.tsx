"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { wholesaleCategories } from "../lib/wholesale";

export const profileFields = [
  ["description", "What does your business do?", 20, 3000],
  ["offerings", "Products or services, aliases and pricing", 3, 3000],
  ["customers", "Who are your customers?", 3, 1500],
  ["workflow", "Workflow: inquiry to delivery and payment", 10, 3000],
  ["hours", "Opening hours and response times", 3, 500],
  ["payments", "Payments, deposits, refunds and cancellation", 3, 1500],
  ["delivery", "Delivery areas or project delivery process", 3, 1500],
  ["service_area", "Service areas and target markets", 0, 1500],
  [
    "required_details",
    "Details your team needs before confirming work",
    0,
    1500,
  ],
  [
    "review_triggers",
    "Topics that always need human review (comma separated)",
    0,
    1500,
  ],
  ["exclusions", "Unrelated topics to flag (comma separated)", 0, 1500],
  [
    "business_examples",
    "Genuine client message examples (one per line)",
    0,
    3000,
  ],
  ["personal_examples", "Private message examples (one per line)", 0, 3000],
  ["spam_examples", "Spam message examples (one per line)", 0, 3000],
] as const;

const steps = [
  {
    label: "Your business",
    title: "Tell us about your business",
    hint: "Choose your business type and describe what you sell. Use your own words in Sinhala, English or Tamil.",
    keys: ["description", "offerings"],
  },
  {
    label: "Customers & orders",
    title: "Who buys from you, and how do orders work?",
    hint: "Describe your trade customers and the details you need before approving an order.",
    keys: ["customers", "workflow", "required_details"],
  },
  {
    label: "Payments & delivery",
    title: "How do customers pay and receive their orders?",
    hint: "Use your actual terms and delivery areas. Describe minimum order requirements here if your team needs to check them manually.",
    keys: ["payments", "delivery", "service_area"],
  },
  {
    label: "Hours & team review",
    title: "When are you available, and what needs team review?",
    hint: "Tell us your response times and which topics should always go to a person.",
    keys: ["hours", "review_triggers", "exclusions"],
  },
  {
    label: "Message examples",
    title: "Which messages belong to your business?",
    hint: "Optional: paste real-looking examples of business, private and spam messages, one per line. These help your inbox filters; leave out sensitive client details.",
    keys: ["business_examples", "personal_examples", "spam_examples"],
  },
  {
    label: "Review & save",
    title: "Review your answers",
    hint: "Check your answers before saving. You can return to any step and edit them.",
    keys: [],
  },
];
const placeholders: Record<string, string> = {
  description:
    "Example: We wholesale vehicle parts to garages and retail shops.",
  offerings:
    "Your product ranges, SKUs/part numbers, selling units and how pricing is agreed.",
  customers:
    "Example: Retail shops, garages, resellers or regional distributors.",
  workflow:
    "What happens after a WhatsApp inquiry? Who checks stock, approves the order and arranges dispatch?",
  required_details:
    "Example: SKU or exact part number, quantity, carton/piece unit and delivery location.",
  payments:
    "Your accepted payment methods, deposits, credit approval and cancellation/refund terms.",
  delivery:
    "Delivery areas, collection options and how your team agrees delivery arrangements.",
  service_area: "The towns, districts or markets you serve.",
  hours: "Your actual working days, opening hours and typical response time.",
  review_triggers: "Example: credit request, compatibility, special discount",
  exclusions: "Unrelated topics your team should review.",
  business_examples: "Example: Please send two cartons of SKU ABC to our shop.",
  personal_examples: "Example: Bring the family album tonight.",
  spam_examples: "Example: Unsolicited prize or investment offers.",
};
const businessTypes = [
  ["wholesale", "Wholesale / distributor"],
  ["retail", "Retail / shop"],
  ["services", "Service business"],
  ["software", "Software company"],
  ["agency", "Agency / consultancy"],
  ["hybrid", "Products and services"],
  ["online_store", "Online store"],
  ["restaurant", "Restaurant / bakery"],
  ["salon", "Salon / beauty services"],
  ["repair", "Repair / maintenance"],
];

export default function BusinessQuestionnaire({
  initial,
  canManage,
  busy,
  onSave,
}: {
  initial: Record<string, string>;
  canManage: boolean;
  busy: boolean;
  onSave: (answers: Record<string, string>) => Promise<boolean>;
}) {
  const [answers, setAnswers] = useState(initial);
  const [step, setStep] = useState(0);
  const [all, setAll] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const form = useRef<HTMLFormElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
  }, [step, all]);
  function answer(key: string, value: string) {
    setAnswers((previous) => ({ ...previous, [key]: value }));
    setDirty(true);
    setError("");
  }
  function validate(keys: readonly string[]) {
    const invalid = profileFields.find(
      ([key, , min, max]) =>
        keys.includes(key) &&
        ((answers[key] || "").trim().length < min ||
          (answers[key] || "").length > max),
    );
    if (!invalid) return true;
    const [key, label, min, max] = invalid;
    setError(
      `${label}: ${min ? `enter at least ${min} characters` : "check your answer"} (maximum ${max}).`,
    );
    if (!all) setStep(steps.findIndex((item) => item.keys.includes(key)));
    requestAnimationFrame(() =>
      form.current?.querySelector<HTMLElement>(`[name="${key}"]`)?.focus(),
    );
    return false;
  }
  function next() {
    if (!canManage || validate(steps[step].keys)) {
      setError("");
      setStep((current) => Math.min(current + 1, steps.length - 1));
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canManage || busy) return;
    if (!all && step < steps.length - 1) {
      next();
      return;
    }
    if (!validate(profileFields.map(([key]) => key))) return;
    const values = Object.fromEntries(
      Object.entries(answers).map(([key, value]) => [key, value.trim()]),
    );
    if (await onSave(values)) {
      setAnswers(values);
      setDirty(false);
    }
  }
  const current = steps[step];
  const visible = all
    ? profileFields
    : profileFields.filter(([key]) => current.keys.includes(key));
  const completed = profileFields.filter(
    ([key, , min]) => min > 0 && (answers[key] || "").trim().length >= min,
  ).length;
  return (
    <form
      ref={form}
      className="profile-form business-questionnaire"
      onSubmit={submit}
      noValidate
      aria-label="Business questions"
    >
      <div className="business-questionnaire-top">
        <div>
          <strong>Answer here in your dashboard</strong>
          <p className="muted small">
            No document is needed. {completed} of 7 required answers completed.
          </p>
        </div>
        <button
          type="button"
          className="text-button"
          onClick={() => {
            setAll(!all);
            setError("");
          }}
        >
          {all ? "Use guided questions" : "Show all questions"}
        </button>
      </div>
      {!all && (
        <>
          <progress
            value={step + 1}
            max={steps.length}
            aria-label="Business setup progress"
          />
          <nav
            className="business-question-steps"
            aria-label="Business setup steps"
          >
            {steps.map((item, index) => (
              <button
                key={item.label}
                type="button"
                className={index === step ? "active" : ""}
                aria-current={index === step ? "step" : undefined}
                onClick={() => {
                  setStep(index);
                  setError("");
                }}
              >
                <span>{index + 1}</span>
                {item.label}
              </button>
            ))}
          </nav>
        </>
      )}
      <div>
        <span className="eyebrow">
          {all ? "YOUR ANSWERS" : `STEP ${step + 1} OF ${steps.length}`}
        </span>
        <h3 ref={heading} tabIndex={-1}>
          {all ? "Your business questions" : current.title}
        </h3>
        <p className="muted">
          {all
            ? "Edit all answers together, then save your business profile."
            : current.hint}
        </p>
      </div>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {(all || step === 0) && (
        <>
          <label className="field">
            Business type
            <select
              name="business_type"
              value={answers.business_type || "wholesale"}
              disabled={!canManage || busy}
              onChange={(event) => answer("business_type", event.target.value)}
            >
              {businessTypes.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Primary product category
            <select
              name="primary_category"
              value={answers.primary_category || "other"}
              disabled={!canManage || busy}
              onChange={(event) =>
                answer("primary_category", event.target.value)
              }
            >
              {wholesaleCategories.map((category) => (
                <option key={category.value} value={category.value}>
                  {category.label}
                </option>
              ))}
            </select>
            <small>
              Choose your main sector. Each catalog product can use a different
              category.
            </small>
          </label>
        </>
      )}
      {visible.map(([key, label, min, max]) => (
        <label key={key} className="field">
          {label}
          <span className="muted small">
            {min > 0 ? "Required" : "Optional"}
          </span>
          <textarea
            name={key}
            value={answers[key] || ""}
            minLength={min}
            maxLength={max}
            required={min > 0}
            rows={3}
            placeholder={placeholders[key]}
            disabled={!canManage || busy}
            onChange={(event) => answer(key, event.target.value)}
          />
        </label>
      ))}
      {!all && step === steps.length - 1 && (
        <div className="business-answer-review">
          <dl>
            <dt>Business type</dt>
            <dd>
              {businessTypes.find(
                ([value]) => value === answers.business_type,
              )?.[1] || answers.business_type}
            </dd>
            <dt>Primary product category</dt>
            <dd>
              {wholesaleCategories.find(
                (category) => category.value === answers.primary_category,
              )?.label || "Other / mixed categories"}
            </dd>
            {profileFields.map(([key, label, min]) => (
              <div key={key}>
                <dt>{label}</dt>
                <dd>
                  {answers[key]?.trim() ||
                    (min ? "Answer required" : "Not provided")}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
      <p className="muted small">
        {dirty ? "You have unsaved answers. " : ""}Answers are saved when you
        choose Save business profile. Message examples guide local filtering;
        unclear messages still need team review.
      </p>
      <div className="business-question-actions">
        {!all && step > 0 && (
          <button
            type="button"
            className="button-secondary"
            disabled={busy}
            onClick={() => {
              setStep((current) => current - 1);
              setError("");
            }}
          >
            Back
          </button>
        )}
        {!all && step < steps.length - 1 ? (
          <button
            type="button"
            className="button primary"
            disabled={busy}
            onClick={next}
          >
            Next
          </button>
        ) : (
          canManage && (
            <button className="button primary" disabled={busy}>
              {busy ? "Saving..." : "Save business profile"}
            </button>
          )
        )}
      </div>
    </form>
  );
}
