import type { Metadata } from "next";
import AuthPage from "../../components/AuthPage";
export const metadata: Metadata = {
  title: "Sign in · OrderMesh",
  robots: { index: false, follow: false },
};
export default function SignIn() {
  return <AuthPage mode="sign-in" />;
}
