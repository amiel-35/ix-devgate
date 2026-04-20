// E10 — Session expirée
// Référence visuelle : docs/ds/mockups/devgate-e10-session-expired.mockup.html
import Link from "next/link";

export default function SessionExpiredPage() {
  return (
    <main>
      {/* TODO: implémenter l'UI à partir du mockup E10 */}
      <h1>Votre session a expiré</h1>
      <p>Vous avez été déconnecté automatiquement après 7 jours.</p>
      <Link href="/login">Se reconnecter</Link>
    </main>
  );
}
