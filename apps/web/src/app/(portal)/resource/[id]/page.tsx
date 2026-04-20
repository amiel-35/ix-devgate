// E06 — Détail environnement
// Référence visuelle : docs/ds/mockups/devgate-e06-detail-env.mockup.html
interface Props {
  params: Promise<{ id: string }>;
}

export default async function ResourceDetailPage({ params }: Props) {
  const { id } = await params;
  // TODO: charger les détails de l'environnement via l'API
  // Ne jamais exposer upstream_hostname ni service_token_ref au frontend

  return (
    <main>
      {/* TODO: implémenter l'UI à partir du mockup E06 */}
      {/* Breadcrumb, meta table, statut tunnel, bouton Accéder */}
      <h1>Environnement {id}</h1>
      <a href={`/resource/${id}/interstitial`}>Accéder</a>
      <a href="..">Retour</a>
    </main>
  );
}
