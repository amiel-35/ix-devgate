// E09 — Lien expiré
// Référence visuelle : docs/ds/mockups/devgate-e09-link-expired.mockup.html
import Link from "next/link";

export default function LinkExpiredPage() {
  return (
    <main>
      {/* TODO: implémenter l'UI à partir du mockup E09 */}
      <h1>Ce lien n&apos;est plus valide</h1>
      <p>
        Le lien a expiré ou a déjà été utilisé.
      </p>
      <Link href="/login">Demander un nouveau lien</Link>
    </main>
  );
}
