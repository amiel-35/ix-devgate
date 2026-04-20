"use client";

import { useSearchParams, useRouter } from "next/navigation";

export default function MagicSentContent() {
  const params = useSearchParams();
  const router = useRouter();
  const email = params.get("email") ?? "";

  return (
    <main>
      {/* TODO: implémenter l'UI à partir du mockup E02 */}
      <p>Lien envoyé à {email}</p>
      <button onClick={() => router.push(`/otp?email=${encodeURIComponent(email)}`)}>
        Utiliser un code OTP
      </button>
      <button onClick={() => router.push("/login")}>
        Modifier l&apos;adresse
      </button>
    </main>
  );
}
