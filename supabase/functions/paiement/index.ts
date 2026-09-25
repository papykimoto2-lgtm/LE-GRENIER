import "jsr:@supabase/functions-js/edge-runtime.d.ts";

// ════════════════════════════════════════════════════════════
//  Edge Function "paiement" — initiation + statut d'un paiement réel.
//
//  Sécurité : le frontend n'envoie JAMAIS de clé secrète de prestataire.
//  Cette fonction détient ses propres identifiants (secrets Supabase :
//  CINETPAY_API_KEY + CINETPAY_API_PASSWORD pour la nouvelle API CinetPay
//  v1 (panel.cinetpay.net), ou CINETPAY_API_KEY + CINETPAY_SITE_ID pour
//  l'ancienne API checkout v2) et calcule elle-même la commission
//  due (plan actif de l'utilisateur), au lieu de faire confiance à une
//  valeur envoyée par le client.
//
//  Routes :
//    POST /paiement           → paiement CinetPay (redirection)
//    GET  /paiement/statut    → statut d'un paiement du client connecté
//    POST /paiement/manuel    → le client déclare un transfert Mobile Money
//                               direct (Wave/Orange/MTN/Moov) vers le numéro
//                               du Grenier, avec l'ID de transaction reçu par SMS
//    POST /paiement/invite    → achat express d'un produit numérique SANS compte
//                               (QR code, lien partagé) : transfert Mobile Money
//                               direct + nom et WhatsApp du client ; renvoie un
//                               jeton secret qui ouvrira le téléchargement une
//                               fois le paiement confirmé par l'admin
//    POST /paiement/valider   → (admin) confirme ou refuse un paiement manuel
//                               après l'avoir vu arriver sur son téléphone ;
//                               la confirmation active le service acheté.
// ════════════════════════════════════════════════════════════

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const CINETPAY_API_KEY = Deno.env.get("CINETPAY_API_KEY") || "";
const CINETPAY_SITE_ID = Deno.env.get("CINETPAY_SITE_ID") || "";
const CINETPAY_API_PASSWORD = Deno.env.get("CINETPAY_API_PASSWORD") || "";
// Nouvelle API v1 : clé sk_test_ → bac à sable, sk_live_ → production.
const CP_V1 = !!(CINETPAY_API_KEY && CINETPAY_API_PASSWORD);
const CP_V1_BASE = CINETPAY_API_KEY.startsWith("sk_live_") ? "https://api.cinetpay.co" : "https://api.cinetpay.net";

const PASSERELLE_MANUELLE = "Mobile Money direct";
const CANAUX_MANUELS = ["wave", "orange", "mtn", "moov"];
const TYPES_MANUELS = ["commission", "abonnement", "boost", "verification", "livraison", "formation", "pub", "produit", "autre"];

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
  const authHeader = req.headers.get("Authorization") || "";
  const token = authHeader.replace("Bearer ", "");
  if (!token) return null;
  const meRes = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
    headers: { Authorization: `Bearer ${token}`, apikey: SERVICE_ROLE_KEY },
  });
  if (!meRes.ok) return null;
  const me = await meRes.json();
  const fRes = await sb(`/rest/v1/utilisateurs?auth_id=eq.${me.id}&select=id,prenom,nom,email,tel,role`);
  const fiches = await fRes.json();
  if (!fiches.length) return null;
  return fiches[0];
}

// Commission réelle = celle du plan actif de l'utilisateur, jamais celle
// envoyée par le client.
async function commissionPourUtilisateur(utilisateurId: number): Promise<{ pct: number; planNom: string }> {
  const today = new Date().toISOString().slice(0, 10);
  const aboRes = await sb(`/rest/v1/abonnements?utilisateur_id=eq.${utilisateurId}&statut=eq.actif&fin=gte.${today}&select=plan&limit=1`);
  const abos = aboRes.ok ? await aboRes.json() : [];
  const planNom = abos.length ? abos[0].plan : null;

  const plansRes = await sb(`/rest/v1/plans?select=nom,commission&order=id.asc`);
  const plans = plansRes.ok ? await plansRes.json() : [];
  if (!plans.length) return { pct: 10, planNom: "Gratuit" };
  const plan = (planNom && plans.find((p: any) => p.nom === planNom)) || plans[0];
  return { pct: Number(plan.commission) || 0, planNom: plan.nom };
}

// Pour un abonnement, le plan acheté (et non le plan actuel du client) —
// validé contre la table plans, avec un montant au moins égal au prix.
async function planAchete(metadata: any, montant: number): Promise<string | null> {
  const nom = metadata && typeof metadata.plan === "string" ? metadata.plan : "";
  if (!nom) return null;
  const r = await sb(`/rest/v1/plans?nom=eq.${encodeURIComponent(nom)}&select=nom,prix`);
  const rows = r.ok ? await r.json() : [];
  if (!rows.length || Number(rows[0].prix) <= 0 || montant < Number(rows[0].prix)) return null;
  return rows[0].nom;
}

// Achat d'un produit numérique : le produit doit être en vente et le montant
// au moins égal à son prix (jamais le prix envoyé par le client).
async function produitAchete(metadata: any, montant: number): Promise<any | null> {
  const id = Number(metadata && metadata.produit_id);
  if (!id) return null;
  const r = await sb(`/rest/v1/produits_numeriques?id=eq.${id}&actif=eq.true&select=id,titre,prix`);
  const rows = r.ok ? await r.json() : [];
  if (!rows.length || montant < Number(rows[0].prix)) return null;
  return rows[0];
}

// Appel à l'API CinetPay v1 : connexion (clé + mot de passe API) → jeton
// JWT, puis requête authentifiée. Renvoie le JSON de la réponse.
async function cinetpayV1(method: string, path: string, body?: unknown): Promise<any> {
  const entetes = { "Content-Type": "application/json", Accept: "application/json" };
  const login = await fetch(`${CP_V1_BASE}/v1/oauth/login`, {
    method: "POST", headers: entetes,
    body: JSON.stringify({ api_key: CINETPAY_API_KEY, api_password: CINETPAY_API_PASSWORD }),
  });
  const jeton = (await login.json().catch(() => null))?.access_token;
  if (!jeton) throw new Error("Connexion CinetPay refusée (vérifiez la clé et le mot de passe API)");
  const r = await fetch(`${CP_V1_BASE}${path}`, {
    method, headers: { ...entetes, Authorization: `Bearer ${jeton}` },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return await r.json().catch(() => null);
}

function genererReference(): string {
  return "TXN" + Date.now().toString().slice(-10) + Math.floor(Math.random() * 900 + 100);
}

async function initierPaiement(req: Request, user: any) {
  if (!CP_V1 && !(CINETPAY_API_KEY && CINETPAY_SITE_ID)) {
    return json({ error: "Passerelle non configurée côté serveur (secrets CINETPAY_API_KEY / CINETPAY_API_PASSWORD manquants)", manuel_possible: true }, 503);
  }
  const body = await req.json().catch(() => ({}));
  const montant = Math.max(0, Math.round(Number(body.montant) || 0));
  if (!montant || montant < 100) return json({ error: "Montant invalide" }, 400);
  if (montant > 5_000_000) return json({ error: "Montant trop élevé" }, 400);

  const canal = String(body.canal || "").toLowerCase();
  const channels = canal === "carte" ? "CREDIT_CARD" : "MOBILE_MONEY";
  const description = String(body.description || "Paiement Le Grenier CI").slice(0, 255);
  const type = ["commission", "abonnement", "boost", "produit"].includes(body.type) ? body.type : "commission";
  const reference = genererReference();

  const { pct, planNom } = await commissionPourUtilisateur(user.id);
  const commission = type === "commission" ? Math.round(montant * pct / 100) : 0;

  // Métadonnées nécessaires pour créer l'annonce/l'abonnement UNE FOIS le
  // paiement confirmé par le webhook — jamais avant. `annonce` n'est que
  // du contenu (titre/description/photos...), aucune valeur financière
  // n'y est relue.
  const metadata = body.annonce && typeof body.annonce === "object" ? body.annonce : null;
  const planVendeur = type === "abonnement" ? (await planAchete(metadata, montant)) : planNom;
  if (type === "abonnement" && !planVendeur) return json({ error: "Plan d'abonnement invalide" }, 400);
  if (type === "produit" && !(await produitAchete(metadata, montant))) return json({ error: "Produit indisponible ou montant invalide" }, 400);

  const insertRes = await sb(`/rest/v1/paiements`, {
    method: "POST",
    headers: { Prefer: "return=representation" },
    body: JSON.stringify({
      vendeur_id: user.id, annonce_titre: description, valeur: montant, commission,
      ref: reference, passerelle: "CinetPay", moyen: canal || "mobile_money",
      statut: "attente", plan_vendeur: planVendeur, type, metadata,
    }),
  });
  if (!insertRes.ok) {
    return json({ error: "Échec d'enregistrement du paiement" }, 500);
  }

  const notifyUrl = `${SUPABASE_URL}/functions/v1/paiement-webhook`;
  const baseReturn = typeof body.return_url === "string" && /^https?:\/\//.test(body.return_url)
    ? body.return_url : notifyUrl;
  const returnUrl = baseReturn + (baseReturn.includes("?") ? "&" : "?") + "paiement_ref=" + encodeURIComponent(reference);

  const echec = async (message?: string) => {
    await sb(`/rest/v1/paiements?ref=eq.${reference}`, {
      method: "PATCH",
      headers: { Prefer: "return=minimal" },
      body: JSON.stringify({ statut: "echoue" }),
    });
    return json({ error: message || "Initialisation du paiement refusée par la passerelle", manuel_possible: true }, 502);
  };

  if (CP_V1) {
    let cp: any = null;
    try {
      cp = await cinetpayV1("POST", "/v1/payment", {
        currency: "XOF",
        merchant_transaction_id: reference,
        amount: montant,
        lang: "fr",
        designation: description,
        client_email: user.email || "client@legrenier.ci",
        client_first_name: (user.prenom || "Client").slice(0, 60),
        client_last_name: (user.nom || "Le Grenier").slice(0, 60),
        success_url: returnUrl,
        failed_url: returnUrl,
        notify_url: notifyUrl,
        channel: "PUSH",
      });
    } catch (e) {
      return await echec(String((e as Error).message || e));
    }
    if (!cp || !cp.payment_url) return await echec(cp && (cp.description || cp.message));
    // Identifiants CinetPay gardés pour vérifier la notification du webhook.
    await sb(`/rest/v1/paiements?ref=eq.${reference}`, {
      method: "PATCH",
      headers: { Prefer: "return=minimal" },
      body: JSON.stringify({ metadata: { ...(metadata || {}), cp_transaction_id: cp.transaction_id || null, cp_notify_token: cp.notify_token || null } }),
    });
    return json({ payment_url: cp.payment_url, reference });
  }

  const cpRes = await fetch("https://api-checkout.cinetpay.com/v2/payment", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      apikey: CINETPAY_API_KEY,
      site_id: CINETPAY_SITE_ID,
      transaction_id: reference,
      amount: montant,
      currency: "XOF",
      description,
      notify_url: notifyUrl,
      return_url: returnUrl,
      channels,
      customer_name: (user.nom || "Client").slice(0, 60),
      customer_surname: (user.prenom || "").slice(0, 60),
      customer_email: user.email || "client@legrenier.ci",
      customer_phone_number: (body.tel || user.tel || "").toString().slice(0, 20),
    }),
  });
  const cpData = await cpRes.json().catch(() => null);
  if (!cpRes.ok || !cpData || cpData.code !== "201" || !cpData.data?.payment_url) {
    return await echec(cpData && cpData.message);
  }

  return json({ payment_url: cpData.data.payment_url, reference });
}

async function statutPaiement(req: Request, user: any) {
  const url = new URL(req.url);
  const ref = url.searchParams.get("ref") || "";
  if (!ref) return json({ error: "ref requis" }, 400);
  const r = await sb(`/rest/v1/paiements?ref=eq.${encodeURIComponent(ref)}&vendeur_id=eq.${user.id}&select=statut,valeur,commission,type,annonce_titre`);
  const rows = r.ok ? await r.json() : [];
  if (!rows.length) return json({ error: "Paiement introuvable" }, 404);
  const p = rows[0];
  const statut = p.statut === "confirme" ? "paye" : p.statut === "echoue" ? "echec" : "en_attente";
  return json({ statut, valeur: p.valeur, commission: p.commission, type: p.type, annonce_titre: p.annonce_titre });
}

// ── Paiement Mobile Money direct : le client a déjà envoyé l'argent sur le
// numéro du Grenier et déclare l'ID de transaction. Rien n'est activé ici :
// le paiement reste "attente" jusqu'à ce qu'un admin le confirme.
async function declarerPaiementManuel(req: Request, user: any) {
  const body = await req.json().catch(() => ({}));
  const montant = Math.max(0, Math.round(Number(body.montant) || 0));
  if (!montant || montant < 100) return json({ error: "Montant invalide" }, 400);
  if (montant > 5_000_000) return json({ error: "Montant trop élevé" }, 400);

  const canal = String(body.canal || "").toLowerCase();
  if (!CANAUX_MANUELS.includes(canal)) return json({ error: "Moyen de paiement invalide" }, 400);

  const txnId = String(body.txn_id || "").trim().toUpperCase().replace(/\s+/g, "");
  if (!/^[A-Z0-9.\-_]{4,40}$/.test(txnId)) return json({ error: "ID de transaction invalide" }, 400);

  const dejaRes = await sb(`/rest/v1/paiements?metadata->>txn_id=eq.${encodeURIComponent(txnId)}&select=id&limit=1`);
  const deja = dejaRes.ok ? await dejaRes.json() : [];
  if (deja.length) return json({ error: "Cet ID de transaction a déjà été déclaré" }, 409);

  const type = TYPES_MANUELS.includes(body.type) ? body.type : "autre";
  const description = String(body.description || "Paiement Le Grenier CI").slice(0, 255);
  const contenu = body.annonce && typeof body.annonce === "object" ? body.annonce : {};
  const telPayeur = String(body.tel || "").replace(/[^\d+]/g, "").slice(0, 20);
  const metadata = { ...contenu, txn_id: txnId, tel_payeur: telPayeur };

  if (type === "produit" && !(await produitAchete(contenu, montant))) {
    return json({ error: "Produit indisponible ou montant invalide" }, 400);
  }

  let planVendeur: string | null;
  if (type === "abonnement") {
    planVendeur = await planAchete(contenu, montant);
    if (!planVendeur) return json({ error: "Plan d'abonnement invalide" }, 400);
  } else {
    planVendeur = (await commissionPourUtilisateur(user.id)).planNom;
  }

  const reference = "MM" + Date.now().toString().slice(-10) + Math.floor(Math.random() * 900 + 100);
  const insertRes = await sb(`/rest/v1/paiements`, {
    method: "POST",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify({
      vendeur_id: user.id, annonce_titre: description, valeur: montant,
      commission: type === "commission" ? montant : 0,
      ref: reference, passerelle: PASSERELLE_MANUELLE, moyen: canal,
      statut: "attente", plan_vendeur: planVendeur, type, metadata,
    }),
  });
  if (!insertRes.ok) return json({ error: "Échec d'enregistrement du paiement" }, 500);
  return json({ reference });
}

function nouveauJeton(): string {
  const octets = new Uint8Array(24);
  crypto.getRandomValues(octets);
  return Array.from(octets, (o) => o.toString(16).padStart(2, "0")).join("");
}

// Achat express sans compte : uniquement pour un produit numérique en vente,
// au prix du catalogue. Rien n'est délivré avant la confirmation admin.
async function declarerAchatInvite(req: Request) {
  const body = await req.json().catch(() => ({}));
  const montant = Math.max(0, Math.round(Number(body.montant) || 0));
  const canal = String(body.canal || "").toLowerCase();
  if (!CANAUX_MANUELS.includes(canal)) return json({ error: "Moyen de paiement invalide" }, 400);

  const txnId = String(body.txn_id || "").trim().toUpperCase().replace(/\s+/g, "");
  if (!/^[A-Z0-9.\-_]{4,40}$/.test(txnId)) return json({ error: "ID de transaction invalide" }, 400);
  const nom = String(body.nom || "").trim().slice(0, 80);
  if (nom.length < 2) return json({ error: "Nom requis" }, 400);
  const tel = String(body.tel || "").replace(/[^\d+]/g, "").slice(0, 20);
  if (tel.replace(/\D/g, "").length < 8) return json({ error: "Numéro WhatsApp requis" }, 400);

  const produit = await produitAchete({ produit_id: body.produit_id }, montant);
  if (!produit) return json({ error: "Produit indisponible ou montant invalide" }, 400);

  const dejaRes = await sb(`/rest/v1/paiements?metadata->>txn_id=eq.${encodeURIComponent(txnId)}&select=id&limit=1`);
  if (dejaRes.ok && (await dejaRes.json()).length) return json({ error: "Cet ID de transaction a déjà été déclaré" }, 409);

  const jeton = nouveauJeton();
  const source = String(body.source || "").replace(/[^a-z0-9_-]/gi, "").slice(0, 30) || null;
  const reference = "MM" + Date.now().toString().slice(-10) + Math.floor(Math.random() * 900 + 100);
  const insertRes = await sb(`/rest/v1/paiements`, {
    method: "POST",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify({
      vendeur_id: null, annonce_titre: "Guide : " + produit.titre, valeur: montant, commission: 0,
      ref: reference, passerelle: PASSERELLE_MANUELLE, moyen: canal, statut: "attente",
      plan_vendeur: null, type: "produit",
      metadata: { produit_id: produit.id, source, txn_id: txnId, tel_payeur: tel, nom_client: nom, jeton, invite: true },
    }),
  });
  if (!insertRes.ok) return json({ error: "Échec d'enregistrement du paiement" }, 500);
  return json({ reference, jeton });
}

async function creerAnnoncePourPaiement(paiement: any) {
  const meta = paiement.metadata || {};
  if (!meta.titre) return; // commission sans contenu d'annonce (ex. vente déjà en ligne)
  const payload = {
    titre: meta.titre,
    cat: meta.cat || "Divers",
    valeur: Number(meta.valeur) || paiement.valeur,
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

// L'admin a vu l'argent arriver : l'abonnement est actif immédiatement.
async function activerAbonnementManuel(paiement: any) {
  const debut = new Date().toISOString().slice(0, 10);
  const fin = new Date(Date.now() + 30 * 24 * 3600 * 1000).toISOString().slice(0, 10);
  await sb("/rest/v1/abonnements", {
    method: "POST", headers: { Prefer: "return=minimal" },
    body: JSON.stringify({
      utilisateur_id: paiement.vendeur_id, plan: paiement.plan_vendeur, debut, fin,
      actif: true, statut: "actif", moyen: paiement.moyen, ref: paiement.ref,
    }),
  });
}

async function validerPaiementManuel(req: Request, user: any) {
  if (user.role !== "admin") return json({ error: "Réservé à l'administrateur" }, 403);
  const body = await req.json().catch(() => ({}));
  const ref = String(body.ref || "");
  const decision = body.decision === "refuser" ? "refuser" : body.decision === "confirmer" ? "confirmer" : "";
  if (!ref || !decision) return json({ error: "ref et decision requis" }, 400);

  // Passage attente → confirme/echoue conditionnel : un double clic ou deux
  // admins en même temps ne peuvent pas activer deux fois le même achat.
  const r = await sb(
    `/rest/v1/paiements?ref=eq.${encodeURIComponent(ref)}&statut=eq.attente&passerelle=eq.${encodeURIComponent(PASSERELLE_MANUELLE)}`,
    { method: "PATCH", headers: { Prefer: "return=representation" }, body: JSON.stringify({ statut: decision === "confirmer" ? "confirme" : "echoue" }) },
  );
  const rows = r.ok ? await r.json() : [];
  if (!rows.length) return json({ error: "Paiement introuvable ou déjà traité" }, 409);
  if (decision === "refuser") return json({ ok: true, statut: "echoue" });

  const paiement = rows[0];
  let active = "";
  if (paiement.type === "abonnement") {
    await activerAbonnementManuel(paiement); active = "abonnement " + paiement.plan_vendeur;
  } else if (paiement.type === "boost") {
    const b = await sb("/rest/v1/rpc/activer_boost", { method: "POST", body: JSON.stringify({ p_ref: paiement.ref }) });
    active = (b.ok && (await b.json().catch(() => null)) === true) ? "boost" : "boost (non activé : vérifier l'annonce)";
  } else if (paiement.type === "verification") {
    await sb(`/rest/v1/utilisateurs?id=eq.${paiement.vendeur_id}`, {
      method: "PATCH", headers: { Prefer: "return=minimal" }, body: JSON.stringify({ verifie: true }),
    });
    active = "badge vérifié";
  } else if (paiement.type === "produit") {
    active = "téléchargement du produit";
  } else if (paiement.type === "commission") {
    await creerAnnoncePourPaiement(paiement);
    active = paiement.metadata?.titre ? "annonce (en modération)" : "";
  }
  return json({ ok: true, statut: "confirme", active });
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  try {
    const path = new URL(req.url).pathname;
    if (req.method === "POST" && path.endsWith("/invite")) {
      return await declarerAchatInvite(req);
    }

    const user = await identifierAppelant(req);
    if (!user) return json({ error: "Non authentifié" }, 401);

    if (req.method === "GET" && path.endsWith("/statut")) {
      return await statutPaiement(req, user);
    }
    if (req.method === "POST" && path.endsWith("/manuel")) {
      return await declarerPaiementManuel(req, user);
    }
    if (req.method === "POST" && path.endsWith("/valider")) {
      return await validerPaiementManuel(req, user);
    }
    if (req.method === "POST") {
      return await initierPaiement(req, user);
    }
    return json({ error: "Route inconnue" }, 404);
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
});
