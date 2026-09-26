import "jsr:@supabase/functions-js/edge-runtime.d.ts";

// ════════════════════════════════════════════════════════════
//  Edge Function "parrainage" — réseau d'ambassadeurs rémunérés en argent.
//
//  Différence avec l'ancien "parrainage" (crédits d'annonces gratuites,
//  purement local/simulé côté frontend) : ici, un ambassadeur touche une
//  vraie commission en FCFA (calculée côté base de données par le trigger
//  commission_parrainage(), sur les 90 jours suivant l'inscription de son
//  filleul) chaque fois que ce filleul paie une commission de vente, un
//  abonnement, un boost ou une vérification.
//
//  Le code de parrainage saisi à l'inscription (colonne utilisateurs.code_parrain)
//  est résolu automatiquement en base par le trigger resoudre_code_parrainage() —
//  cette fonction n'a donc rien à faire à l'inscription elle-même.
//
//  Routes :
//    POST /parrainage/devenir        → active le statut d'ambassadeur pour
//                                       l'appelant (génère son code si besoin)
//    GET  /parrainage/mes-stats      → code, filleuls, commissions à payer / payées
//    GET  /parrainage/a-payer        → (admin) commissions en attente de règlement
//    POST /parrainage/marquer-paye   → (admin) marque une commission réglée
// ════════════════════════════════════════════════════════════

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

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
  const fRes = await sb(`/rest/v1/utilisateurs?auth_id=eq.${me.id}&select=id,prenom,nom,role`);
  const fiches = await fRes.json();
  return fiches.length ? fiches[0] : null;
}

function genererCode(prenom: string, nom: string): string {
  const initiales = ((prenom || "X")[0] + ((nom || "X")[0] || "")).toUpperCase().replace(/[^A-Z]/g, "X");
  const suffixe = Math.floor(1000 + Math.random() * 9000);
  return "AMI" + initiales + suffixe;
}

// Crée la fiche ambassadeur si elle n'existe pas déjà (idempotent) — quelques
// essais en cas de collision improbable sur le code généré.
async function devenirAmbassadeur(user: any) {
  const existant = await sb(`/rest/v1/ambassadeurs?utilisateur_id=eq.${user.id}&select=id,code,statut,taux_commission`);
  const rows = existant.ok ? await existant.json() : [];
  if (rows.length) return rows[0];

  for (let essai = 0; essai < 5; essai++) {
    const code = genererCode(user.prenom, user.nom);
    const ins = await sb(`/rest/v1/ambassadeurs`, {
      method: "POST",
      headers: { Prefer: "return=representation" },
      body: JSON.stringify({ utilisateur_id: user.id, code }),
    });
    if (ins.ok) {
      const created = await ins.json();
      if (created.length) return created[0];
    }
    // Code déjà pris (collision) : on retente avec un autre suffixe.
  }
  throw new Error("Impossible de générer un code de parrainage, réessayez");
}

async function routeDevenir(req: Request, user: any) {
  const amb = await devenirAmbassadeur(user);
  return json({ code: amb.code, statut: amb.statut, taux_commission: amb.taux_commission });
}

async function routeMesStats(req: Request, user: any) {
  const amb = await devenirAmbassadeur(user);

  const filleulsRes = await sb(`/rest/v1/utilisateurs?parraine_par=eq.${amb.id}&select=id`);
  const filleuls = filleulsRes.ok ? await filleulsRes.json() : [];

  const commRes = await sb(`/rest/v1/commissions_parrainage?ambassadeur_id=eq.${amb.id}&select=montant,statut`);
  const commissions = commRes.ok ? await commRes.json() : [];
  const aPayer = commissions.filter((c: any) => c.statut === "a_payer").reduce((s: number, c: any) => s + Number(c.montant), 0);
  const paye = commissions.filter((c: any) => c.statut === "paye").reduce((s: number, c: any) => s + Number(c.montant), 0);

  return json({
    code: amb.code,
    statut: amb.statut,
    taux_commission: amb.taux_commission,
    nb_filleuls: filleuls.length,
    commissions_a_payer: aPayer,
    commissions_payees: paye,
  });
}

async function routeAPayer(req: Request, user: any) {
  if (user.role !== "admin") return json({ error: "Réservé à l'administrateur" }, 403);
  const r = await sb(
    `/rest/v1/commissions_parrainage?statut=eq.a_payer&order=created_at.asc&select=id,montant,paiement_ref,created_at,ambassadeurs(code,utilisateur_id),utilisateurs(prenom,nom)`,
  );
  const rows = r.ok ? await r.json() : [];
  return json({ commissions: rows });
}

async function routeMarquerPaye(req: Request, user: any) {
  if (user.role !== "admin") return json({ error: "Réservé à l'administrateur" }, 403);
  const body = await req.json().catch(() => ({}));
  const id = Number(body.commission_id);
  if (!id) return json({ error: "commission_id requis" }, 400);

  const r = await sb(`/rest/v1/commissions_parrainage?id=eq.${id}&statut=eq.a_payer`, {
    method: "PATCH",
    headers: { Prefer: "return=representation" },
    body: JSON.stringify({ statut: "paye", paye_le: new Date().toISOString() }),
  });
  const rows = r.ok ? await r.json() : [];
  if (!rows.length) return json({ error: "Commission introuvable ou déjà réglée" }, 409);
  return json({ ok: true });
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  try {
    const path = new URL(req.url).pathname;
    const user = await identifierAppelant(req);
    if (!user) return json({ error: "Non authentifié" }, 401);

    if (req.method === "POST" && path.endsWith("/devenir")) return await routeDevenir(req, user);
    if (req.method === "GET" && path.endsWith("/mes-stats")) return await routeMesStats(req, user);
    if (req.method === "GET" && path.endsWith("/a-payer")) return await routeAPayer(req, user);
    if (req.method === "POST" && path.endsWith("/marquer-paye")) return await routeMarquerPaye(req, user);
    return json({ error: "Route inconnue" }, 404);
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
});
