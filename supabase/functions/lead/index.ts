import "jsr:@supabase/functions-js/edge-runtime.d.ts";

// ════════════════════════════════════════════════════════════
//  Edge Function "lead" — capture de contacts qualifiés (pay-per-lead)
//  et solde de cashback acheteur.
//
//  Pay-per-lead : sur une annonce "capture_lead", l'acheteur laisse son nom/
//  téléphone/message au lieu (ou en plus) du contact direct WhatsApp/appel.
//  Le contact du VENDEUR n'est jamais caché (il est déjà public sur la
//  fiche) — c'est la LIVRAISON du lead au vendeur qui est facturée, en
//  crédits pré-achetés (achat via /paiement/manuel, type "credits_contact").
//  Jamais bloquant pour l'acheteur : à crédits épuisés, le lead est capturé
//  quand même (non débité), le vendeur voit qu'il doit recharger.
//
//  Cashback : un acheteur (avec ou sans compte, identifié par son numéro de
//  téléphone) cumule 2% de ses achats protégés/produits numériques,
//  réutilisable en rabais sur son prochain achat — cf. consommer_cashback()
//  en base, appelée depuis l'edge function "paiement".
//
//  Routes :
//    POST /lead/soumettre    → { annonce_id, nom, tel, message } (public, sans compte)
//    GET  /lead/cashback?tel=… → solde cashback pour un numéro (public, lecture seule)
//    GET  /lead/mes-leads    → (vendeur connecté) mes leads reçus + solde de crédits
//    GET  /lead/tarifs       → grille de prix des packs de crédits contact
// ════════════════════════════════════════════════════════════

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

// Packs de crédits contact — dégressif : plus le vendeur en achète, moins
// chaque lead lui coûte.
const PACKS_CREDITS: Record<string, { nb: number; prix: number }> = {
  "10": { nb: 10, prix: 2000 },
  "30": { nb: 30, prix: 5000 },
  "100": { nb: 100, prix: 15000 },
};

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
  const fRes = await sb(`/rest/v1/utilisateurs?auth_id=eq.${me.id}&select=id,credits_contact`);
  const fiches = await fRes.json();
  return fiches.length ? fiches[0] : null;
}

async function routeSoumettre(req: Request) {
  const body = await req.json().catch(() => ({}));
  const annonceId = Number(body.annonce_id);
  if (!annonceId) return json({ error: "annonce_id requis" }, 400);
  const nom = String(body.nom || "").trim().slice(0, 80);
  if (nom.length < 2) return json({ error: "Nom requis" }, 400);
  const tel = String(body.tel || "").replace(/[^\d+]/g, "").slice(0, 20);
  if (tel.replace(/\D/g, "").length < 8) return json({ error: "Numéro de téléphone requis" }, 400);
  const message = String(body.message || "").trim().slice(0, 500) || null;

  const aRes = await sb(`/rest/v1/annonces?id=eq.${annonceId}&statut=eq.en-ligne&capture_lead=eq.true&select=id,vendeur_id`);
  const aRows = aRes.ok ? await aRes.json() : [];
  if (!aRows.length || !aRows[0].vendeur_id) return json({ error: "Cette annonce n'accepte pas les demandes de contact" }, 400);

  const r = await sb("/rest/v1/rpc/capturer_lead", {
    method: "POST",
    body: JSON.stringify({ p_annonce_id: annonceId, p_vendeur_id: aRows[0].vendeur_id, p_nom: nom, p_tel: tel, p_message: message }),
  });
  const lead = r.ok ? await r.json().catch(() => null) : null;
  if (!lead) return json({ error: "Échec de l'envoi de la demande" }, 500);
  return json({ ok: true, statut: lead.statut });
}

async function routeCashback(req: Request) {
  const url = new URL(req.url);
  const tel = (url.searchParams.get("tel") || "").replace(/[^\d+]/g, "");
  if (tel.replace(/\D/g, "").length < 8) return json({ error: "tel requis" }, 400);
  const r = await sb(`/rest/v1/cashback_soldes?tel=eq.${encodeURIComponent(tel)}&select=solde`);
  const rows = r.ok ? await r.json() : [];
  return json({ solde: rows.length ? Number(rows[0].solde) : 0 });
}

async function routeMesLeads(req: Request, user: any) {
  const r = await sb(`/rest/v1/leads?vendeur_id=eq.${user.id}&order=created_at.desc&limit=100&select=id,acheteur_nom,acheteur_tel,message,statut,created_at,annonces(titre)`);
  const rows = r.ok ? await r.json() : [];
  return json({ leads: rows, credits_contact: user.credits_contact || 0, tarifs: PACKS_CREDITS });
}

function routeTarifs() {
  return json({ tarifs: PACKS_CREDITS });
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  try {
    const path = new URL(req.url).pathname;

    if (req.method === "POST" && path.endsWith("/soumettre")) return await routeSoumettre(req);
    if (req.method === "GET" && path.endsWith("/cashback")) return await routeCashback(req);
    if (req.method === "GET" && path.endsWith("/tarifs")) return routeTarifs();

    const user = await identifierAppelant(req);
    if (!user) return json({ error: "Non authentifié" }, 401);
    if (req.method === "GET" && path.endsWith("/mes-leads")) return await routeMesLeads(req, user);
    return json({ error: "Route inconnue" }, 404);
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
});
