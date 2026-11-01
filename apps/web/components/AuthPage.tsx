"use client";
import { useRouter } from "next/navigation";
import Auth from "./Auth";
export default function AuthPage({ mode }: { mode: "sign-in" | "sign-up" }) {
  const router = useRouter();
  return (
    <Auth
      mode={mode}
      onLogin={async () => {
        router.replace("/dashboard");
        router.refresh();
      }}
    />
  );
}
