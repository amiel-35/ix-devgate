// E04 — Portail (accueil post-login)
// Référence visuelle : docs/ds/mockups/devgate-e04-portal.mockup.html
import { portalApi } from "@/lib/api/client";

export default async function PortalPage() {
  // Données chargées côté serveur — le backend est la source de vérité
  let environments: Awaited<ReturnType<typeof portalApi.environments>> = [];
  try {
    environments = await portalApi.environments();
  } catch {
    // Géré par les error boundaries ou les états vides
  }

  if (environments.length === 0) {
    // E08 — État vide
    return (
      <main>
        {/* TODO: EmptyState component — référence E08 */}
        <p>Aucun environnement disponible pour le moment.</p>
      </main>
    );
  }

  return (
    <main>
      {/* TODO: implémenter l'UI à partir du mockup E04 */}
      {/* WelcomeBanner + EnvironmentGrid */}
      <ul>
        {environments.map((env) => (
          <li key={env.id}>
            <a href={`/client/${env.organization_name}`}>
              {env.organization_name} — {env.environment_name}
            </a>
          </li>
        ))}
      </ul>
    </main>
  );
}
