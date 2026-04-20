// E05 — Page client
// Référence visuelle : docs/ds/mockups/devgate-e05-client.mockup.html
import { portalApi } from "@/lib/api/client";

interface Props {
  params: Promise<{ slug: string }>;
}

export default async function ClientPage({ params }: Props) {
  const { slug } = await params;

  let environments: Awaited<ReturnType<typeof portalApi.environments>> = [];
  try {
    environments = await portalApi.environments();
  } catch {
    // TODO: gérer l'erreur avec un état explicite
  }

  const clientEnvs = environments.filter(
    (e) =>
      e.organization_name.toLowerCase().replace(/\s+/g, "-") === slug,
  );

  return (
    <main>
      {/* TODO: implémenter l'UI à partir du mockup E05 */}
      {/* Navigation par client + liste des ressources directes */}
      <h1>Client : {slug}</h1>
      <ul>
        {clientEnvs.map((env) => (
          <li key={env.id}>
            <a href={`/resource/${env.id}`}>{env.environment_name}</a>
          </li>
        ))}
      </ul>
    </main>
  );
}
