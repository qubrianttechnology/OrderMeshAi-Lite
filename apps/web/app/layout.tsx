import type { Metadata } from "next";
import SiteLanguage from "../components/SiteLanguage";
import "./globals.css";
import "./design-system.css";
import "./site-language.css";
export const metadata: Metadata = {
  title: "OrderMesh AI Lite · Qubriant",
  description:
    "WhatsApp order drafts, stock, customers and invoices for wholesalers and distributors.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        {children}
        <SiteLanguage />
      </body>
    </html>
  );
}
