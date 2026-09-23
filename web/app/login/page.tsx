import type { Metadata } from "next";
import { AuthForm } from "@/components/auth-form";

export const metadata: Metadata = {
  title: "Log in — Sabi",
  description: "Log in to Sabi to pick your notebook and progress back up.",
};

export default function LoginPage() {
  return <AuthForm mode="login" />;
}
