import "jsr:@supabase/functions-js/edge-runtime.d.ts";

// ════════════════════════════════════════════════════════════
//  Edge Function "achat-protege" — cycle de vie du paiement séquestre.
//
//  La déclaration du paiement lui-même (l'acheteur envoie l'argent au
//  Grenier) se fait via /paiement/achat-protege (edge function "paiement"),
//  SANS compte — comme l'achat express de produit numérique. Cette fonction
//  gère ce qui vient APRÈS que l'admin a confirmé la réception de l'argent
//  (statut "attente_livraison") : suivi par jeton pour l'acheteur, listing
//  et règlement manuel du vendeur pour l'admin.
//
//  Personne (ni le vendeur, ni l'acheteur) ne touche l'argent avant que
//  l'acheteur confirme avoir reçu l'article — ou que le délai de 5 jours
//  expire sans réclamation (confirmer_achats_proteges_expires en base).
//  Le versement au vendeur reste manuel (Mobile Money direct), comme tous
//  les autres règlements de cette plateforme : aucune API de reversement
//  automatique n'est branchée.
//
//  Routes :
//    GET  /achat-protege/statut?jeton=…   → statut de l'achat (public, par jeton)
//    POST /achat-protege/confirmer        → { jeton } : "j'ai bien reçu mon article"
//    POST /achat-protege/signaler         → { jeton, motif } : litige, argent bloqué
//    GET  /achat-protege/a-verser         → (admin) achats confirmés, vendeur pas encore payé
//    POST /achat-protege/marquer-verse    → (admin) { id } : vendeur payé par Mobile Money
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
  const fRes = await sb(`/rest/v1/utilisateurs?auth_id=eq.${me.id}&select=id,role`);
  const fiches = await fRes.json();
  return fiches.length ? fiches[0] : null;
}

async function trouverParJeton(jeton: string) {
  const r = await sb(`/rest/v1/achats_proteges?jeton=eq.${encodeURIComponent(jeton)}&select=*`);
  const rows = r.ok ? await r.json() : [];
  return rows.length ? rows[0] : null;
}

async function routeStatut(req: Request) {
  await sb("/rest/v1/rpc/confirmer_achats_proteges_expires", { method: "POST" }).catch(() => {});
  const url = new URL(req.url);
  const jeton = url.searchParams.get("jeton") || "";
  if (!jeton) return json({ error: "jeton requis" }, 400);
  const achat = await trouverParJeton(jeton);
  if (!achat) return json({ error: "Achat introuvable" }, 404);
  return json({
    statut: achat.statut, montant_article: achat.montant_article, frais_protection: achat.frais_protection,
    date_limite_confirmation: achat.date_limite_confirmation, confirme_le: achat.confirme_le,
  });
}

async function routeConfirmer(req: Request) {
  const body = await req.json().catch(() => ({}));
  const jeton = String(body.jeton || "");
  if (!jeton) return json({ error: "jeton requis" }, 400);
  const r = await sb(`/rest/v1/achats_proteges?jeton=eq.${encodeURIComponent(jeton)}&statut=eq.attente_livraison`, {
    method: "PATCH", headers: { Prefer: "return=representation" },
    body: JSON.stringify({ statut: "confirme_recu", confirme_le: new Date().toISOString() }),
  });
  const rows = r.ok ? await r.json() : [];
  if (!rows.length) return json({ error: "Achat introuvable ou déjà traité" }, 409);
  return json({ ok: true, statut: "confirme_recu" });
}

async function routeSignaler(req: Request) {
  const body = await req.json().catch(() => ({}));
  const jeton = String(body.jeton || "");
  const motif = String(body.motif || "").trim().slice(0, 500);
  if (!jeton) return json({ error: "jeton requis" }, 400);
  if (motif.length < 5) return json({ error: "Décrivez le problème (5 caractères minimum)" }, 400);
  const r = await sb(`/rest/v1/achats_proteges?jeton=eq.${encodeURIComponent(jeton)}&statut=eq.attente_livraison`, {
    method: "PATCH", headers: { Prefer: "return=representation" },
    body: JSON.stringify({ statut: "dispute", motif_dispute: motif }),
  });
  const rows = r.ok ? await r.json() : [];
  if (!rows.length) return json({ error: "Achat introuvable ou déjà traité" }, 409);
  return json({ ok: true, statut: "dispute" });
}

async function routeAVerser(req: Request, user: any) {
  if (user.role !== "admin") return json({ error: "Réservé à l'administrateur" }, 403);
  await sb("/rest/v1/rpc/confirmer_achats_proteges_expires", { method: "POST" }).catch(() => {});
  const r = await sb(
    `/rest/v1/achats_proteges?statut=eq.confirme_recu&order=confirme_le.asc&select=id,paiement_ref,acheteur_nom,acheteur_tel,montant_article,frais_protection,confirme_le,utilisateurs(prenom,nom,tel)`,
  );
  const rows = r.ok ? await r.json() : [];
  const rDispute = await sb(
    `/rest/v1/achats_proteges?statut=eq.dispute&order=created_at.asc&select=id,paiement_ref,acheteur_nom,acheteur_tel,montant_article,motif_dispute,created_at,utilisateurs(prenom,nom,tel)`,
  );
  const disputes = rDispute.ok ? await rDispute.json() : [];
  return json({ a_verser: rows, disputes });
}

async function routeMarquerVerse(req: Request, user: any) {
  if (user.role !== "admin") return json({ error: "Réservé à l'administrateur" }, 403);
  const body = await req.json().catch(() => ({}));
  const id = Number(body.id);
  if (!id) return json({ error: "id requis" }, 400);
  const r = await sb(`/rest/v1/achats_proteges?id=eq.${id}&statut=eq.confirme_recu`, {
    method: "PATCH", headers: { Prefer: "return=representation" },
    body: JSON.stringify({ statut: "vendeur_paye" }),
  });
  const rows = r.ok ? await r.json() : [];
  if (!rows.length) return json({ error: "Achat introuvable ou déjà réglé" }, 409);
  return json({ ok: true });
}

// Décision admin sur un litige : rembourser l'acheteur ou finalement libérer
// les fonds au vendeur (litige non fondé).
async function routeTrancherLitige(req: Request, user: any) {
  if (user.role !== "admin") return json({ error: "Réservé à l'administrateur" }, 403);
  const body = await req.json().catch(() => ({}));
  const id = Number(body.id);
  const decision = body.decision === "rembourser" ? "rembourse" : body.decision === "verser" ? "confirme_recu" : "";
  if (!id || !decision) return json({ error: "id et decision requis" }, 400);
  const r = await sb(`/rest/v1/achats_proteges?id=eq.${id}&statut=eq.dispute`, {
    method: "PATCH", headers: { Prefer: "return=representation" },
    body: JSON.stringify({ statut: decision, decision_admin: String(body.note || "").slice(0, 300) }),
  });
  const rows = r.ok ? await r.json() : [];
  if (!rows.length) return json({ error: "Litige introuvable ou déjà tranché" }, 409);
  return json({ ok: true, statut: decision });
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  try {
    const path = new URL(req.url).pathname;

    // Routes publiques (sans compte), identifiées par le jeton secret.
    if (req.method === "GET" && path.endsWith("/statut")) return await routeStatut(req);
    if (req.method === "POST" && path.endsWith("/confirmer")) return await routeConfirmer(req);
    if (req.method === "POST" && path.endsWith("/signaler")) return await routeSignaler(req);

    // Routes admin : authentification requise.
    const user = await identifierAppelant(req);
    if (!user) return json({ error: "Non authentifié" }, 401);

    if (req.method === "GET" && path.endsWith("/a-verser")) return await routeAVerser(req, user);
    if (req.method === "POST" && path.endsWith("/marquer-verse")) return await routeMarquerVerse(req, user);
    if (req.method === "POST" && path.endsWith("/trancher")) return await routeTrancherLitige(req, user);
    return json({ error: "Route inconnue" }, 404);
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
});
