import Link from "next/link";
import "../app/landing.css";
export default function PublicNotice({
  privacy = false,
}: {
  privacy?: boolean;
}) {
  return (
    <main className="om om-notice">
      <div className="om-container">
        <Link href="/" className="om-text-button">
          ← Back to OrderMesh
        </Link>
        <span className="om-eyebrow">ORDERMESH AI · PUBLIC INFORMATION</span>
        <h1>{privacy ? "Privacy Policy" : "Terms of Service"}</h1>
        <p className="om-notice-banner">
          {privacy
            ? "A complete privacy policy has not yet been supplied for publication. The information below describes the current product; it does not replace the final policy."
            : "Final commercial terms have not yet been supplied for publication. The following product and subscription information is provided for clarity; it is not a complete service agreement."}
        </p>
        {privacy ? (
          <>
            <h2>The website demonstration</h2>
            <p>
              The interactive message demonstration uses local sample rules in
              your browser. It does not send your entered text to an AI service
              or WhatsApp, and it does not save an order. Please use fictional
              details.
            </p>
            <h2>The business application</h2>
            <p>
              The application stores account and business information, customer
              records, conversations, products and orders for business
              operations. Authentication uses server-managed sessions. Access is
              scoped to the signed-in organization and assigned role.
            </p>
            <h2>Connected services</h2>
            <p>
              When configured, AI extraction can send message text to an AI
              provider. WhatsApp integration uses Meta services, and billing
              uses PayHere. These integrations require configuration and may be
              subject to their providers’ policies.
            </p>
            <h2>Information still to be published</h2>
            <p>
              The final policy must specify the responsible legal entity,
              retention periods, processing locations, applicable privacy rights
              and request procedures. These details are not asserted here.
              Contact the team before submitting sensitive customer information.
            </p>
          </>
        ) : (
          <>
            <h2>Current product scope</h2>
            <p>
              OrderMesh provides customer, catalog, stock and order management
              with Sinhala, English and Tamil text extraction. Drafts require
              human review and confirmation. WhatsApp voice transcription
              requires a configured speech provider. Image extraction is not
              supported. Live WhatsApp and payment integrations require provider
              setup and verification.
            </p>
            <h2>Subscription information</h2>
            <p>
              The existing Starter / Lite plan is LKR 7,400 per month, with a
              15-day application trial and a default allowance of 500 orders per
              month. Workspace-specific allowances apply. Growth and Business
              Pro are planned tiers without published prices or entitlements.
            </p>
            <h2>Demonstrations and decisions</h2>
            <p>
              Website examples are fictional simulations, not customer
              transactions or performance claims. Check extracted information
              against the original customer request and your catalog before
              confirming an order.
            </p>
            <h2>Information still to be published</h2>
            <p>
              Final terms must define the contracting entity, payment and refund
              conditions, support commitments and other commercial conditions.
              Contact the team for these details before subscribing. No
              unlimited usage or guaranteed uptime is offered on this page.
            </p>
          </>
        )}
        <h2>Contact</h2>
        <p>
          <a href="mailto:info@ordermesh.com">info@ordermesh.com</a> ·{" "}
          <a href="tel:+94722616616">0722 616 616</a>
        </p>
      </div>
    </main>
  );
}
