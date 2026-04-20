// E11 — Accès refusé 403
// Référence visuelle : docs/ds/mockups/devgate-e11-access-denied.mockup.html
import Link from "next/link";

export default function AccessDeniedPage() {
  return (
    <main>
      {/* TODO: implémenter l'UI à partir du mockup E11 */}
      <h1>Accès non autorisé</h1>
      <p>
        Votre compte ne dispose pas d&apos;un accès actif à cette ressource.
      </p>
      <Link href="/portal">Retour à mon portail</Link>
    </main>
  );
}
