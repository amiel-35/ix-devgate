"use client";

import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { authApi } from "@/lib/api/client";

export default function OtpContent() {
  const params = useSearchParams();
  const router = useRouter();
  const email = params.get("email") ?? "";
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
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
    <main>
      {/* TODO: implémenter l'UI à partir du mockup E03 */}
      <p>Code envoyé à {email}</p>
      <form onSubmit={handleSubmit}>
        <label htmlFor="otp">Code à 6 chiffres</label>
        <input
          id="otp"
          type="text"
          inputMode="numeric"
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          required
        />
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={loading || code.length !== 6}>
          {loading ? "Vérification…" : "Valider"}
        </button>
      </form>
    </main>
  );
}
