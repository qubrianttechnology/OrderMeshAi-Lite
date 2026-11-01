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
      <body>
        {children}
        <SiteLanguage />
      </body>
    </html>
  );
}
