// E06 — Détail environnement
// Référence visuelle : docs/ds/mockups/devgate-e06-detail-env.mockup.html
// Note : upstream_hostname et service_token_ref ne sont JAMAIS renvoyés par l'API portal.
import Link from "next/link";
import { redirect, notFound } from "next/navigation";
import { serverPortalApi, ServerApiError } from "@/lib/api/server";
import { KindBadge, StatusBadge } from "@/components/portal/Badge";
import styles from "./resource.module.css";

function toSlug(name: string) {
  return name.toLowerCase().replace(/\s+/g, "-");
}

interface Props {
  params: Promise<{ id: string }>;
}

export default async function ResourceDetailPage({ params }: Props) {
  const { id } = await params;

  let environments;
  try {
    environments = await serverPortalApi.environments();
  } catch (err) {
    if (err instanceof ServerApiError && err.status === 401) {
      redirect("/login");
    }
    redirect("/session-expired");
  }

  const env = environments.find((e) => e.id === id);
  if (!env) notFound();

  const hostname = env.url.replace(/^https?:\/\//, "");
  const orgSlug = toSlug(env.organization_name);
  const isOnline = env.status === "online";

  return (
    <main className={styles.main}>
      <nav className={styles.breadcrumb}>
        <Link href="/portal">Portail</Link>
        <span>›</span>
        <Link href={`/client/${orgSlug}`}>{env.organization_name}</Link>
        <span>›</span>
        <span style={{ color: "var(--color-text)", fontWeight: 500 }}>
          {env.environment_name}
        </span>
      </nav>

      <div className={styles.layout}>
        {/* Colonne principale */}
        <div>
          <h1 className={styles.title}>{env.environment_name}</h1>
          <p className={styles.desc}>{env.project_name}</p>

          {isOnline ? (
            <div className={styles.noticeOk}>
              ✅ Tunnel actif — environnement accessible.
            </div>
          ) : (
            <div className={styles.noticeWarn}>
              ⚠️ Cet environnement est actuellement hors ligne.
            </div>
          )}

          {env.requires_app_auth && (
            <div className={styles.noticeWarn}>
              ⚠️ Cette ressource demande une authentification applicative après
              l&apos;ouverture via DevGate.
            </div>
          )}

          <div className={styles.metaTable}>
            <div className={styles.metaRow}>
              <div className={styles.metaKey}>Projet</div>
              <div className={styles.metaVal}>{env.project_name}</div>
            </div>
            <div className={styles.metaRow}>
              <div className={styles.metaKey}>Type</div>
              <div className={styles.metaVal}>
                <KindBadge kind={env.kind} />
              </div>
            </div>
            <div className={styles.metaRow}>
              <div className={styles.metaKey}>URL publique</div>
              <div className={`${styles.metaVal} ${styles.metaMono}`}>{hostname}</div>
            </div>
            <div className={styles.metaRow}>
              <div className={styles.metaKey}>Statut</div>
              <div className={styles.metaVal}>
                <StatusBadge status={env.status} />
              </div>
            </div>
            <div className={styles.metaRow}>
              <div className={styles.metaKey}>Auth applicative</div>
              <div className={styles.metaVal}>
                {env.requires_app_auth ? "Requise" : "Non requise"}
              </div>
            </div>
          </div>

          <div className={styles.actions}>
            {isOnline && (
              <Link
                href={env.requires_app_auth ? `/resource/${id}/interstitial` : env.url}
                className={styles.btnPrimary}
                {...(!env.requires_app_auth
                  ? { target: "_blank", rel: "noopener noreferrer" }
                  : {})}
              >
                Ouvrir la ressource ↗
              </Link>
            )}
            <Link href={`/client/${orgSlug}`} className={styles.btnSecondary}>
              ← Retour aux ressources
            </Link>
          </div>
        </div>

        {/* Panneau de statut */}
        <div className={styles.statusPanel}>
          <div className={styles.tile}>
            <div className={styles.tileLabel}>Tunnel</div>
            <div className={`${styles.tileValue} ${isOnline ? styles.colorOk : styles.colorWarn}`}>
              {isOnline ? "🟢 Actif" : "🔴 Inactif"}
            </div>
            <div className={styles.tileSub}>{isOnline ? "Accessible" : "Hors ligne"}</div>
          </div>
          <div className={styles.tile}>
            <div className={styles.tileLabel}>Auth DevGate</div>
            <div className={`${styles.tileValue} ${styles.colorOk}`}>✅ Validée</div>
            <div className={styles.tileSub}>Accès accordé</div>
          </div>
          <div className={styles.tile}>
            <div className={styles.tileLabel}>Auth applicative</div>
            {env.requires_app_auth ? (
              <>
                <div className={`${styles.tileValue} ${styles.colorWarn}`}>⚠️ Requise</div>
                <div className={styles.tileSub}>Login après ouverture</div>
              </>
            ) : (
              <>
                <div className={`${styles.tileValue} ${styles.colorOk}`}>✅ Non requise</div>
                <div className={styles.tileSub}>Accès direct</div>
              </>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
