// E05 — Page client
// Référence visuelle : docs/ds/mockups/devgate-e05-client.mockup.html
import Link from "next/link";
import { redirect, notFound } from "next/navigation";
import { serverPortalApi, ServerApiError } from "@/lib/api/server";
import { KindBadge, StatusBadge, AuthBadge } from "@/components/portal/Badge";
import styles from "./client.module.css";

// Normalise un nom d'organisation en slug URL (même logique côté portail E04)
function toSlug(name: string) {
  return name.toLowerCase().replace(/\s+/g, "-");
}

interface Props {
  params: Promise<{ slug: string }>;
}

export default async function ClientPage({ params }: Props) {
  const { slug } = await params;

  let environments;
  try {
    environments = await serverPortalApi.environments();
  } catch (err) {
    if (err instanceof ServerApiError && err.status === 401) {
      redirect("/login");
    }
    redirect("/session-expired");
  }

  // Grouper les environnements par organisation
  const orgMap = new Map<string, { name: string; slug: string; envs: typeof environments }>();
  for (const env of environments) {
    const orgSlug = toSlug(env.organization_name);
    if (!orgMap.has(orgSlug)) {
      orgMap.set(orgSlug, { name: env.organization_name, slug: orgSlug, envs: [] });
    }
    orgMap.get(orgSlug)!.envs.push(env);
  }

  const currentOrg = orgMap.get(slug);
  if (!currentOrg && orgMap.size > 0) {
    // slug inconnu → rediriger vers le premier client connu
    const firstSlug = orgMap.keys().next().value!;
    redirect(`/client/${firstSlug}`);
  }
  if (!currentOrg) notFound();

  const clientEnvs = currentOrg.envs;

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <div className={styles.sbLabel}>Mes clients</div>
        {Array.from(orgMap.values()).map((org) => (
          <Link
            key={org.slug}
            href={`/client/${org.slug}`}
            className={`${styles.clientItem} ${org.slug === slug ? styles.clientItemActive : ""}`}
          >
            <div className={styles.clientName}>{org.name}</div>
            <div className={styles.clientCount}>
              {org.envs.length} ressource{org.envs.length !== 1 ? "s" : ""}
            </div>
          </Link>
        ))}
      </aside>

      <main className={styles.main}>
        <div className={styles.pageTitle}>{currentOrg.name}</div>
        <div className={styles.pageSub}>
          Ressources de validation disponibles pour votre compte
        </div>

        {clientEnvs.some((e) => e.requires_app_auth) && (
          <div className={styles.notice}>
            ℹ️ Certaines ressources peuvent demander une authentification
            supplémentaire propre à l&apos;application une fois ouvertes.
          </div>
        )}

        <div className={styles.cards}>
          {clientEnvs.map((env) => {
            const hostname = env.url.replace(/^https?:\/\//, "");
            const offline = env.status === "offline";
            return (
              <div key={env.id} className={styles.card}>
                <div className={styles.top}>
                  <div>
                    <div className={styles.org}>{env.project_name}</div>
                    <div className={styles.project}>{env.environment_name}</div>
                  </div>
                  <KindBadge kind={env.kind} />
                </div>
                <div className={styles.meta}>
                  <StatusBadge status={env.status} />
                  {env.requires_app_auth && <AuthBadge />}
                </div>
                <div className={styles.footer}>
                  <span className={styles.hostname}>{hostname}</span>
                  <div className={styles.actions}>
                    <Link href={`/resource/${env.id}`} className={styles.btnSecondary}>
                      Détails
                    </Link>
                    {offline ? (
                      <span className={styles.btnDisabled}>Indisponible</span>
                    ) : (
                      <Link
                        href={
                          env.requires_app_auth
                            ? `/resource/${env.id}/interstitial`
                            : `/resource/${env.id}`
                        }
                        className={styles.btnPrimary}
                      >
                        Ouvrir ↗
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </main>
    </div>
  );
}
