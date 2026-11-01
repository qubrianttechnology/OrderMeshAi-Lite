import type { Metadata } from "next";
import AuthPage from "../../components/AuthPage";
export const metadata: Metadata = {
  title: "Create your workspace · OrderMesh",
  robots: { index: false, follow: false },
};
export default function SignUp() {
  return <AuthPage mode="sign-up" />;
}
