import "jsr:@supabase/functions-js/edge-runtime.d.ts";

// ════════════════════════════════════════════════════════════
//  Edge Function "paiement-webhook" — notification CinetPay (notify_url).
//
//  verify_jwt=false : CinetPay appelle cette URL côté serveur, sans jeton
//  Supabase. C'est pourquoi on NE FAIT JAMAIS confiance au statut envoyé
//  dans la notification elle-même (un tiers pourrait la rejouer) : on
//  revient TOUJOURS interroger l'API "check" de CinetPay avec nos propres
//  identifiants serveur pour obtenir le statut définitif.
//
//  Deux API CinetPay sont prises en charge :
//    - v1 (panel.cinetpay.net) : secrets CINETPAY_API_KEY + CINETPAY_API_PASSWORD
//    - checkout v2 (ancienne)  : secrets CINETPAY_API_KEY + CINETPAY_SITE_ID
// ════════════════════════════════════════════════════════════

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const CINETPAY_API_KEY = Deno.env.get("CINETPAY_API_KEY") || "";
const CINETPAY_SITE_ID = Deno.env.get("CINETPAY_SITE_ID") || "";
const CINETPAY_API_PASSWORD = Deno.env.get("CINETPAY_API_PASSWORD") || "";
const CP_V1 = !!(CINETPAY_API_KEY && CINETPAY_API_PASSWORD);
const CP_V1_BASE = CINETPAY_API_KEY.startsWith("sk_live_") ? "https://api.cinetpay.co" : "https://api.cinetpay.net";
// Statuts définitifs d'échec de l'API v1 (SUCCESS = payé ; le reste = en cours).
const CP_V1_ECHECS = ["FAILED", "EXPIRED", "INSUFFICIENT_BALANCE", "USER_IS_BLOCKED", "NOT_ALLOWED"];

const sb = (path: string, init: RequestInit = {}) => fetch(`${SUPABASE_URL}${path}`, {
  ...init,
  headers: { Authorization: `Bearer ${SERVICE_ROLE_KEY}`, apikey: SERVICE_ROLE_KEY, "Content-Type": "application/json", ...(init.headers || {}) },
});

// Notre référence (TXN…) : "merchant_transaction_id" en v1, "cpm_trans_id" en v2.
// En v1, "transaction_id" est l'identifiant CinetPay, pas le nôtre.
async function extraireNotification(req: Request): Promise<{ reference: string; cpTransactionId: string }> {
  const url = new URL(req.url);
  const fromQuery = url.searchParams.get("cpm_trans_id") || url.searchParams.get("ref");
  if (fromQuery) return { reference: fromQuery, cpTransactionId: "" };
  try {
    const ct = req.headers.get("content-type") || "";
    const body: any = ct.includes("application/json")
      ? await req.json()
      : Object.fromEntries((await req.formData()).entries());
    if (body.merchant_transaction_id) {
      return { reference: String(body.merchant_transaction_id), cpTransactionId: String(body.transaction_id || "") };
    }
    return { reference: String(body.cpm_trans_id || body.transaction_id || body.ref || ""), cpTransactionId: "" };
  } catch {
    return { reference: "", cpTransactionId: "" };
  }
}

// Statut définitif d'un paiement via l'API CinetPay v1 : "paye", "echec" ou "attente".
async function statutV1(paiement: any, cpTransactionId: string): Promise<string> {
  const entetes = { "Content-Type": "application/json", Accept: "application/json" };
  const login = await fetch(`${CP_V1_BASE}/v1/oauth/login`, {
    method: "POST", headers: entetes,
    body: JSON.stringify({ api_key: CINETPAY_API_KEY, api_password: CINETPAY_API_PASSWORD }),
  });
  const jeton = (await login.json().catch(() => null))?.access_token;
  if (!jeton) { console.error("[paiement-webhook] connexion CinetPay v1 refusée"); return "attente"; }
  const id = paiement.metadata?.cp_transaction_id || cpTransactionId || paiement.ref;
  const r = await fetch(`${CP_V1_BASE}/v1/payment/${encodeURIComponent(id)}`, {
    headers: { ...entetes, Authorization: `Bearer ${jeton}` },
  });
  const d = await r.json().catch(() => null);
  // La transaction interrogée doit bien être la nôtre.
  if (!d || (d.merchant_transaction_id && d.merchant_transaction_id !== paiement.ref)) return "attente";
  if (d.status === "SUCCESS") return "paye";
  if (CP_V1_ECHECS.includes(d.status)) return "echec";
  return "attente";
}

async function statutV2(reference: string): Promise<string> {
  const checkRes = await fetch("https://api-checkout.cinetpay.com/v2/payment/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ apikey: CINETPAY_API_KEY, site_id: CINETPAY_SITE_ID, transaction_id: reference }),
  });
  const checkData = await checkRes.json().catch(() => null);
  const statut = checkData?.data?.status;
  return statut === "ACCEPTED" ? "paye" : statut === "REFUSED" ? "echec" : "attente";
}

async function creerAnnoncePourPaiement(paiement: any) {
  const meta = paiement.metadata || {};
  const payload = {
    titre: meta.titre || paiement.annonce_titre || "Annonce",
    cat: meta.cat || "Divers",
    valeur: paiement.valeur,
    etat: meta.etat || null,
    desc_txt: meta.desc || "",
    ville: meta.ville || "",
    lat: meta.lat || null,
    lng: meta.lng || null,
    vendeur_id: paiement.vendeur_id,
    statut: "attente",
    vues: 0,
    emoji: meta.emoji || "📦",
    type_tab: meta.targetTab || "tab-marche",
    photos: meta.photos || [],
  };
  await sb("/rest/v1/annonces", { method: "POST", headers: { Prefer: "return=minimal" }, body: JSON.stringify(payload) });

  if (meta.promoCode) {
    await sb("/rest/v1/rpc/consommer_code_promo", { method: "POST", body: JSON.stringify({ p_code: meta.promoCode }) }).catch(() => {});
  }
}

async function activerAbonnementPourPaiement(paiement: any) {
  const meta = paiement.metadata || {};
  await sb("/rest/v1/abonnements", {
    method: "POST", headers: { Prefer: "return=minimal" },
    body: JSON.stringify({
      utilisateur_id: paiement.vendeur_id, plan: paiement.plan_vendeur,
      debut: meta.debut || new Date().toISOString().slice(0, 10),
      fin: meta.fin || null, actif: false, statut: "attente", moyen: paiement.moyen, ref: paiement.ref,
    }),
  });
}

async function activerBoostPourPaiement(paiement: any) {
  const r = await sb("/rest/v1/rpc/activer_boost", { method: "POST", body: JSON.stringify({ p_ref: paiement.ref }) });
  const ok = r.ok ? await r.json().catch(() => null) : null;
  if (ok !== true) console.error("[paiement-webhook] boost non activé", paiement.ref, r.status);
}

Deno.serve(async (req: Request) => {
  // CinetPay attend un 200 rapide ; toute erreur est journalisée côté serveur
  // sans jamais faire échouer la réponse HTTP (sinon CinetPay rejoue en boucle).
  try {
    if (!CP_V1 && !(CINETPAY_API_KEY && CINETPAY_SITE_ID)) {
      console.error("[paiement-webhook] secrets CinetPay manquants");
      return new Response("ok");
    }
    const { reference, cpTransactionId } = await extraireNotification(req);
    if (!reference) return new Response("ok");

    const pRes = await sb(`/rest/v1/paiements?ref=eq.${encodeURIComponent(reference)}&select=*`);
    const rows = pRes.ok ? await pRes.json() : [];
    if (!rows.length) { console.error("[paiement-webhook] paiement introuvable", reference); return new Response("ok"); }
    const paiement = rows[0];

    // Déjà traite (webhook idempotent : CinetPay peut notifier plusieurs fois)
    if (paiement.statut === "confirme" || paiement.statut === "echoue") return new Response("ok");

    // Statut DÉFINITIF : jamais celui de la notification, toujours celui de
    // l'appel "check" fait depuis le serveur avec nos identifiants.
    const statut = CP_V1 ? await statutV1(paiement, cpTransactionId) : await statutV2(reference);

    if (statut === "paye") {
      await sb(`/rest/v1/paiements?ref=eq.${encodeURIComponent(reference)}`, {
        method: "PATCH", headers: { Prefer: "return=minimal" }, body: JSON.stringify({ statut: "confirme" }),
      });
      if (paiement.type === "abonnement") await activerAbonnementPourPaiement(paiement);
      else if (paiement.type === "boost") await activerBoostPourPaiement(paiement);
      // Produit numérique : le paiement confirmé suffit à ouvrir le
      // téléchargement (edge function "telechargement"), rien à créer.
      else if (paiement.type !== "produit") await creerAnnoncePourPaiement(paiement);
    } else if (statut === "echec") {
      await sb(`/rest/v1/paiements?ref=eq.${encodeURIComponent(reference)}`, {
        method: "PATCH", headers: { Prefer: "return=minimal" }, body: JSON.stringify({ statut: "echoue" }),
      });
    }
    // Sinon (en attente) : on ne change rien, une prochaine notification arrivera.

    return new Response("ok");
  } catch (e) {
    console.error("[paiement-webhook] erreur", e);
    return new Response("ok");
  }
});
