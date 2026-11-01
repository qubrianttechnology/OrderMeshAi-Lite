import type { Metadata } from "next";
import PublicNotice from "../../components/PublicNotice";
export const metadata: Metadata = {
  title: "Privacy information | OrderMesh AI",
};
export default function PrivacyPage() {
  return <PublicNotice privacy />;
}
