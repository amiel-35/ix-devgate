"use client";

import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { authApi } from "@/lib/api/client";
import { AuthCard } from "@/components/auth/AuthCard";
import { OtpInput } from "@/components/auth/OtpInput";
import { Button } from "@/components/shared/Button";

export default function OtpContent() {
  const params = useSearchParams();
  const router = useRouter();
  const email = params.get("email") ?? "";
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await authApi.verify(code);
      router.push(res.redirect_to);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Code invalide");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthCard footer="Code à usage unique · Valable 10 minutes">
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 6 }}>Entrez votre code</h1>
      <p style={{ fontSize: 14, color: "var(--color-text-muted)", marginBottom: 20 }}>
        Un code à 6 chiffres a été envoyé à <strong>{email}</strong>.
      </p>
      <form onSubmit={submit} noValidate>
        <OtpInput value={code} onChange={setCode} />
        {error && <p role="alert" style={{ color: "var(--color-danger)", fontSize: 13, marginBottom: 12 }}>{error}</p>}
        <Button type="submit" disabled={loading || code.length !== 6}>
          {loading ? "Vérification…" : "Valider"}
        </Button>
      </form>
    </AuthCard>
  );
}
