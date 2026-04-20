// E07 — Interstitiel double auth
// Référence visuelle : docs/ds/mockups/devgate-e07-interstitiel.mockup.html
// Affiché quand requires_app_auth = true, avant redirection vers la ressource
interface Props {
  params: Promise<{ id: string }>;
}

export default async function InterstitialPage({ params }: Props) {
  const { id } = await params;

  // Le gateway DevGate est la porte d'entrée.
  // L'application cible peut ensuite demander sa propre auth.
  // L'URL de la ressource est construite côté serveur, jamais exposée ici.

  return (
    <main>
      {/* TODO: implémenter l'UI à partir du mockup E07 */}
      <h1>La ressource va s&apos;ouvrir</h1>
      <p>
        Votre accès a été validé par DevGate. Cette ressource peut demander
        une authentification supplémentaire.
      </p>
      {/* Le lien pointe vers le gateway, pas vers un hostname Cloudflare brut */}
      <a href={`/api/gateway/${id}`}>Continuer vers la ressource</a>
      <a href={`/resource/${id}`}>Retour aux détails</a>
    </main>
  );
}
