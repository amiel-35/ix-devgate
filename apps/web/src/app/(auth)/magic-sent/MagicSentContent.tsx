"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { StateCard } from "@/components/auth/StateCard";
import { Button } from "@/components/shared/Button";
import { authApi } from "@/lib/api/client";

export default function MagicSentContent() {
  const params = useSearchParams();
  const router = useRouter();
  const email = params.get("email") ?? "";

  async function resend() {
    if (email) {
      await authApi.start(email).catch(() => {});
    }
  }

  return (
    <StateCard
      icon="✉️"
      tone="ok"
      title="Vérifiez vos emails"
      description={
        <>
          Un lien de connexion a été envoyé à <strong>{email || "votre email"}</strong>.
          Cliquez dessus pour accéder à votre espace.
        </>
      }
      footer="Le lien expire dans 15 minutes · Usage unique"
    >
      <Button onClick={resend}>Renvoyer le lien</Button>
      <Button
        variant="secondary"
        onClick={() => router.push(`/otp?email=${encodeURIComponent(email)}`)}
      >
        Utiliser un code OTP
      </Button>
      <Button variant="link" onClick={() => router.push("/login")}>
        Modifier l&apos;adresse
      </Button>
    </StateCard>
  );
}
