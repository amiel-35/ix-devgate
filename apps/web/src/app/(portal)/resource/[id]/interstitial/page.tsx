// E07 — Interstitiel double auth
// Référence visuelle : docs/ds/mockups/devgate-e07-interstitiel.mockup.html
// Affiché uniquement quand requires_app_auth=true, avant ouverture de la ressource.
// "Continuer" ouvre le gateway DevGate — jamais directement le hostname Cloudflare.
import Link from "next/link";
import { redirect, notFound } from "next/navigation";
import { serverPortalApi, ServerApiError } from "@/lib/api/server";
import styles from "./interstitial.module.css";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function InterstitialPage({ params }: Props) {
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

  // URL de navigation : gateway DevGate (jamais le public_hostname directement)
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
  const gatewayUrl = `${apiBase}${env.gateway_url}`;

  return (
    <div className={styles.wrap}>
      <div className={styles.card}>
        <div className={styles.icon}>↗</div>
        <h1 className={styles.title}>La ressource va s&apos;ouvrir</h1>
        <p className={styles.sub}>
          Votre accès à <strong>{env.environment_name}</strong> a été validé par DevGate.
          Cette ressource va maintenant vous demander son propre login.
        </p>
        <div className={styles.notice}>
          ℹ️ C&apos;est normal. DevGate contrôle l&apos;accès à l&apos;environnement.
          L&apos;application peut ensuite avoir sa propre authentification — par exemple
          WordPress ou votre outil métier.
        </div>
        <a
          href={gatewayUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.btnPrimary}
        >
          Continuer vers la ressource ↗
        </a>
        <Link href={`/resource/${id}`} className={styles.btnSecondary}>
          ← Retour aux détails
        </Link>
        <p className={styles.note}>
          Si vous n&apos;avez pas les identifiants de l&apos;application, contactez l&apos;agence.
        </p>
      </div>
    </div>
  );
}
