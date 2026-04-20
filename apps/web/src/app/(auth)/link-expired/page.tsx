import Link from "next/link";
import { StateCard } from "@/components/auth/StateCard";
import { Button } from "@/components/shared/Button";

export default function LinkExpiredPage() {
  return (
    <StateCard
      icon="!"
      tone="danger"
      title="Ce lien n'est plus valide"
      description="Le lien de connexion a expiré ou a déjà été utilisé. Vous pouvez en demander un nouveau en quelques secondes."
    >
      <Link href="/login" style={{ width: "100%" }}>
        <Button>Recevoir un nouveau lien</Button>
      </Link>
    </StateCard>
  );
}
