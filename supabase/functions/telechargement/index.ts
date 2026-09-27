import "jsr:@supabase/functions-js/edge-runtime.d.ts";

// ════════════════════════════════════════════════════════════
//  Edge Function "telechargement" — délivre un lien temporaire vers le
//  fichier d'un produit numérique (bucket privé "produits-fichiers").
//
//  POST { produit_id } → { url } (valable 10 minutes)
//  POST { jeton }      → { url } pour un achat express sans compte, une fois
//                        le paiement confirmé ; { statut: "attente" } avant.
//  Accès accordé si l'appelant :
//    - a un paiement confirmé de ce produit, ou
//    - a un abonnement Business actif (formations incluses), ou
//    - est admin.
// ════════════════════════════════════════════════════════════

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const BUCKET = "produits-fichiers";
const DUREE_LIEN_S = 600;

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });
}

const sb = (path: string, init: RequestInit = {}) => fetch(`${SUPABASE_URL}${path}`, {
  ...init,
  headers: { Authorization: `Bearer ${SERVICE_ROLE_KEY}`, apikey: SERVICE_ROLE_KEY, "Content-Type": "application/json", ...(init.headers || {}) },
});

async function identifierAppelant(req: Request) {
  const token = (req.headers.get("Authorization") || "").replace("Bearer ", "");
  if (!token) return null;
  const meRes = await fetch(`${SUPABASE_URL}/auth/v1/user`, { headers: { Authorization: `Bearer ${token}`, apikey: SERVICE_ROLE_KEY } });
  if (!meRes.ok) return null;
  const me = await meRes.json();
  const r = await sb(`/rest/v1/utilisateurs?auth_id=eq.${me.id}&select=id,role`);
  const rows = r.ok ? await r.json() : [];
  return rows[0] || null;
}

async function aAcces(user: any, produitId: number): Promise<boolean> {
  if (user.role === "admin") return true;
  const achat = await sb(`/rest/v1/paiements?vendeur_id=eq.${user.id}&type=eq.produit&statut=eq.confirme&metadata->>produit_id=eq.${produitId}&select=id&limit=1`);
  if (achat.ok && (await achat.json()).length) return true;
  const today = new Date().toISOString().slice(0, 10);
  const abo = await sb(`/rest/v1/abonnements?utilisateur_id=eq.${user.id}&plan=eq.Business&statut=eq.actif&fin=gte.${today}&select=id&limit=1`);
  return abo.ok && (await abo.json()).length > 0;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  try {
    if (req.method !== "POST") return json({ error: "Route inconnue" }, 404);
    const body = await req.json().catch(() => ({}));
    let produitId: number;

    const jeton = String(body.jeton || "");
    if (jeton) {
      // Achat express sans compte : le jeton secret remplace la connexion.
      if (!/^[a-f0-9]{48}$/.test(jeton)) return json({ error: "Lien invalide" }, 400);
      const r = await sb(`/rest/v1/paiements?type=eq.produit&metadata->>jeton=eq.${jeton}&select=statut,metadata&limit=1`);
      const achat = r.ok ? (await r.json())[0] : null;
      if (!achat) return json({ error: "Lien invalide" }, 404);
      if (achat.statut === "attente") return json({ statut: "attente" });
      if (achat.statut !== "confirme") return json({ error: "Paiement refusé" }, 403);
      produitId = Math.trunc(Number(achat.metadata?.produit_id) || 0);
    } else {
      const user = await identifierAppelant(req);
      if (!user) return json({ error: "Non authentifié" }, 401);
      produitId = Math.trunc(Number(body.produit_id) || 0);
      if (!produitId) return json({ error: "produit_id requis" }, 400);
      if (!(await aAcces(user, produitId))) return json({ error: "Achat requis pour télécharger ce produit" }, 403);
    }

    const pr = await sb(`/rest/v1/produits_numeriques?id=eq.${produitId}&select=id,slug,titre,fichier_path`);
    const produit = pr.ok ? (await pr.json())[0] : null;
    if (!produit || !produit.fichier_path) return json({ error: "Fichier indisponible" }, 404);

    const nomFichier = `${produit.slug}.pdf`;
    const s = await sb(`/storage/v1/object/sign/${BUCKET}/${produit.fichier_path}`, {
      method: "POST", body: JSON.stringify({ expiresIn: DUREE_LIEN_S }),
    });
    const signe = s.ok ? await s.json() : null;
    if (!signe || !signe.signedURL) return json({ error: "Lien de téléchargement indisponible" }, 500);
    return json({ url: `${SUPABASE_URL}/storage/v1${signe.signedURL}&download=${encodeURIComponent(nomFichier)}`, expire_dans: DUREE_LIEN_S, titre: produit.titre, produit_id: produit.id });
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
});
