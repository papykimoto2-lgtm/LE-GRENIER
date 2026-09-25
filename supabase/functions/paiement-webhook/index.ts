import "jsr:@supabase/functions-js/edge-runtime.d.ts";

// ════════════════════════════════════════════════════════════
//  Edge Function "paiement-webhook" — notification CinetPay (notify_url).
//
//  verify_jwt=false : CinetPay appelle cette URL côté serveur, sans jeton
//  Supabase. C'est pourquoi on NE FAIT JAMAIS confiance au statut envoyé
//  dans la notification elle-même (un tiers pourrait la rejouer) : on
//  revient TOUJOURS interroger l'API "check" de CinetPay avec nos propres
//  identifiants serveur pour obtenir le statut définitif.
// ════════════════════════════════════════════════════════════

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const CINETPAY_API_KEY = Deno.env.get("CINETPAY_API_KEY") || "";
const CINETPAY_SITE_ID = Deno.env.get("CINETPAY_SITE_ID") || "";

const sb = (path: string, init: RequestInit = {}) => fetch(`${SUPABASE_URL}${path}`, {
  ...init,
  headers: { Authorization: `Bearer ${SERVICE_ROLE_KEY}`, apikey: SERVICE_ROLE_KEY, "Content-Type": "application/json", ...(init.headers || {}) },
});

async function extraireReference(req: Request): Promise<string> {
  const url = new URL(req.url);
  const fromQuery = url.searchParams.get("cpm_trans_id") || url.searchParams.get("ref");
  if (fromQuery) return fromQuery;
  try {
    const ct = req.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      const body = await req.json();
      return body.cpm_trans_id || body.transaction_id || body.ref || "";
    }
    const form = await req.formData();
    return String(form.get("cpm_trans_id") || form.get("transaction_id") || "");
  } catch {
    return "";
  }
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
    if (!CINETPAY_API_KEY || !CINETPAY_SITE_ID) {
      console.error("[paiement-webhook] secrets CinetPay manquants");
      return new Response("ok");
    }
    const reference = await extraireReference(req);
    if (!reference) return new Response("ok");

    const pRes = await sb(`/rest/v1/paiements?ref=eq.${encodeURIComponent(reference)}&select=*`);
    const rows = pRes.ok ? await pRes.json() : [];
    if (!rows.length) { console.error("[paiement-webhook] paiement introuvable", reference); return new Response("ok"); }
    const paiement = rows[0];

    // Déjà traite (webhook idempotent : CinetPay peut notifier plusieurs fois)
    if (paiement.statut === "confirme" || paiement.statut === "echoue") return new Response("ok");

    // Statut DÉFINITIF : jamais celui de la notification, toujours celui de
    // l'appel "check" fait depuis le serveur avec nos identifiants.
    const checkRes = await fetch("https://api-checkout.cinetpay.com/v2/payment/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ apikey: CINETPAY_API_KEY, site_id: CINETPAY_SITE_ID, transaction_id: reference }),
    });
    const checkData = await checkRes.json().catch(() => null);
    const statutCinetpay = checkData?.data?.status;

    if (statutCinetpay === "ACCEPTED") {
      await sb(`/rest/v1/paiements?ref=eq.${encodeURIComponent(reference)}`, {
        method: "PATCH", headers: { Prefer: "return=minimal" }, body: JSON.stringify({ statut: "confirme" }),
      });
      if (paiement.type === "abonnement") await activerAbonnementPourPaiement(paiement);
      else if (paiement.type === "boost") await activerBoostPourPaiement(paiement);
      // Produit numérique : le paiement confirmé suffit à ouvrir le
      // téléchargement (edge function "telechargement"), rien à créer.
      else if (paiement.type !== "produit") await creerAnnoncePourPaiement(paiement);
    } else if (statutCinetpay === "REFUSED") {
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
