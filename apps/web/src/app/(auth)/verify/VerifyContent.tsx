"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { authApi, ApiError } from "@/lib/api/client";
import { StateCard } from "@/components/auth/StateCard";

export default function VerifyContent() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token");
  const [status, setStatus] = useState<"pending" | "error">("pending");

  useEffect(() => {
    if (!token) {
      router.replace("/link-expired");
      return;
    }
    authApi
      .verify(token)
      .then((res) => {
        router.replace(res.redirect_to ?? "/portal");
      })
      .catch((err) => {
        if (err instanceof ApiError && (err.status === 404 || err.status === 410)) {
          router.replace("/link-expired");
        } else {
          setStatus("error");
        }
      });
  }, [token, router]);

  if (status === "error") {
    return (
      <StateCard
        icon="!"
        tone="danger"
        title="Une erreur est survenue"
        description="Impossible de vérifier votre lien. Réessayez dans quelques instants."
      />
    );
  }

  return (
    <StateCard
      icon="⏳"
      tone="info"
      title="Vérification en cours…"
      description="Nous confirmons votre identité, un instant."
    />
  );
}
