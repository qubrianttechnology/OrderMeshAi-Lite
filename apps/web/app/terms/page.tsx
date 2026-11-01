import type { Metadata } from "next";
import PublicNotice from "../../components/PublicNotice";
export const metadata: Metadata = {
  title: "Service information | OrderMesh AI",
};
export default function TermsPage() {
  return <PublicNotice />;
}
