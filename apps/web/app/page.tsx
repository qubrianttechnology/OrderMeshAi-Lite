import type { Metadata } from "next";
import Landing from "../components/Landing";
import "./landing.css";
export const metadata: Metadata = {
  title: "OrderMesh AI | Your WhatsApp Business. Powered by AI.",
  description:
    "Turn Sinhala and English customer messages into reviewable order drafts. Explore OrderMesh AI for Sri Lankan businesses: customers, orders, inventory and a clearer working day.",
};
export default function Home() {
  return <Landing />;
}
