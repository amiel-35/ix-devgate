"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api/client";
import { AuthCard } from "@/components/auth/AuthCard";
import { Button } from "@/components/shared/Button";
import styles from "./page.module.css";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submitMagicLink(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await authApi.start(email);
      router.push(`/magic-sent?email=${encodeURIComponent(email)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue");
    } finally {
      setLoading(false);
    }
  }

  function useOtp() {
    router.push(`/otp?email=${encodeURIComponent(email)}`);
  }

  return (
    <AuthCard footer="Accès sécurisé · Aucun mot de passe · DevGate">
      <h1 className={styles.title}>Accéder à votre espace</h1>
      <p className={styles.sub}>
        Saisissez votre email professionnel pour recevoir un lien de connexion sécurisé.
      </p>
      <form onSubmit={submitMagicLink} noValidate>
        <label htmlFor="email" className={styles.label}>Adresse email</label>
        <input
          id="email"
          type="email"
          className={styles.input}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="vous@example.com"
          autoComplete="email"
          required
        />
        {error && <p role="alert" className={styles.error}>{error}</p>}
        <Button type="submit" disabled={loading}>
          {loading ? "Envoi…" : "Recevoir mon lien sécurisé"}
        </Button>
      </form>
      <div className={styles.divider}>ou</div>
      <Button type="button" variant="secondary" onClick={useOtp}>
        Utiliser un code OTP
      </Button>
    </AuthCard>
  );
}
