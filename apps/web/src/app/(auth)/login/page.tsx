// E01 — Login
// Référence visuelle : docs/ds/mockups/devgate-e01-login.mockup.html
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api/client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await authApi.start(email);
      if (res.method === "magic_link") {
        router.push(`/magic-sent?email=${encodeURIComponent(email)}`);
      } else {
        router.push(`/otp?email=${encodeURIComponent(email)}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      {/* TODO: implémenter l'UI à partir du mockup E01 */}
      <form onSubmit={handleSubmit}>
        <label htmlFor="email">Adresse email</label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
          placeholder="vous@example.com"
        />
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? "Envoi…" : "Recevoir mon lien sécurisé"}
        </button>
        <button
          type="button"
          onClick={() =>
            router.push(`/otp?email=${encodeURIComponent(email)}`)
          }
        >
          Utiliser un code OTP
        </button>
      </form>
    </main>
  );
}
