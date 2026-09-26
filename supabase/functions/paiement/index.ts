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
//    POST /paiement                → paiement CinetPay (redirection)
//    GET  /paiement/statut         → statut d'un paiement du client connecté
//    POST /paiement/manuel         → le client déclare un transfert Mobile Money
//                                     direct (Wave/Orange/MTN/Moov) vers le numéro
//                                     du Grenier, avec l'ID de transaction reçu par SMS
//    POST /paiement/invite         → achat express d'un produit numérique SANS compte
//                                     (QR code, lien partagé) : transfert Mobile Money
//                                     direct + nom et WhatsApp du client ; renvoie un
//                                     jeton secret qui ouvrira le téléchargement une
//                                     fois le paiement confirmé par l'admin
//    POST /paiement/valider        → (admin) confirme ou refuse un paiement manuel
//                                     après l'avoir vu arriver sur son téléphone ;
//                                     la confirmation active le service acheté.
//    GET  /paiement/mes-echeances  → mes paiements en plusieurs fois (BNPL) en cours
//    POST /paiement/echeance       → règle une échéance en attente (Mobile Money direct)
//    POST /paiement/achat-protege  → paiement séquestre SANS COMPTE : l'acheteur envoie le
//                                     prix de l'article + frais de protection au Grenier
//                                     (jamais au vendeur) ; suivi/confirmation ensuite via
//                                     l'edge function "achat-protege" (jeton).
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

// Frais de protection acheteur (paiement séquestre) : 3% du prix de
// l'article, minimum 300 F — à la charge de l'acheteur.
const FRAIS_PROTECTION_PCT = 3;
const FRAIS_PROTECTION_MIN = 300;
// Délai avant confirmation automatique de réception si l'acheteur ne
// signale rien (cf. confirmer_achats_proteges_expires en base).
const DELAI_CONFIRMATION_JOURS = 5;

// Paiement en plusieurs fois (BNPL) : uniquement pour les frais vendeur avec
// activation automatique — jamais pour une vente entre particuliers (déjà
// réglée directement) ni pour un produit numérique (livraison immédiate).
const TYPES_ECHELONNABLES = ["abonnement", "boost", "verification"];
// Frais de service pour l'échelonnement, en % du prix — couvre le risque
// d'impayé et incite à payer en une fois quand c'est possible.
const FRAIS_ECHELONNEMENT: Record<number, number> = { 2: 6, 3: 10 };

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

// Prix officiel du service demandé, jamais celui envoyé par le client —
// c'est sur cette valeur que l'échelonnement (BNPL) calcule ses échéances.
async function prixReference(type: string, metadata: any, montantEnvoye: number): Promise<number | null> {
  if (type === "abonnement") {
    const nom = metadata && typeof metadata.plan === "string" ? metadata.plan : "";
    if (!nom) return null;
    const r = await sb(`/rest/v1/plans?nom=eq.${encodeURIComponent(nom)}&select=prix`);
    const rows = r.ok ? await r.json() : [];
    return rows.length && Number(rows[0].prix) > 0 ? Number(rows[0].prix) : null;
  }
  if (type === "boost") {
    const code = metadata && typeof metadata.boost_plan === "string" ? metadata.boost_plan : "";
    if (!code) return null;
    const r = await sb(`/rest/v1/boost_plans?code=eq.${encodeURIComponent(code)}&active=eq.true&select=price_fcfa`);
    const rows = r.ok ? await r.json() : [];
    return rows.length && Number(rows[0].price_fcfa) > 0 ? Number(rows[0].price_fcfa) : null;
  }
  if (type === "verification") return montantEnvoye > 0 ? montantEnvoye : null;
  return null;
}

// Répartit le prix + frais de service sur N échéances égales (la dernière
// absorbe l'arrondi).
function calculerEcheances(prixRef: number, n: number): { montantTotal: number; fraisPct: number; montants: number[] } {
  const fraisPct = FRAIS_ECHELONNEMENT[n] || 0;
  const montantTotal = Math.round(prixRef * (1 + fraisPct / 100));
  const base = Math.floor(montantTotal / n);
  const montants = Array(n).fill(base);
  montants[n - 1] = montantTotal - base * (n - 1);
  return { montantTotal, fraisPct, montants };
}

async function creerEcheancier(utilisateurId: number, type: string, referenceInitiale: string, plan: { montantTotal: number; fraisPct: number; montants: number[] }) {
  const insEch = await sb(`/rest/v1/echeanciers`, {
    method: "POST",
    headers: { Prefer: "return=representation" },
    body: JSON.stringify({
      utilisateur_id: utilisateurId, type, paiement_initial_ref: referenceInitiale,
      montant_total: plan.montantTotal, frais_pct: plan.fraisPct, nb_echeances: plan.montants.length,
    }),
  });
  const rows = insEch.ok ? await insEch.json() : [];
  if (!rows.length) return;
  const echeancierId = rows[0].id;
  const jourMs = 24 * 3600 * 1000;
  const lignes = plan.montants.map((montant, i) => ({
    echeancier_id: echeancierId,
    numero: i + 1,
    montant,
    date_prevue: new Date(Date.now() + (i + 1) * 30 * jourMs).toISOString().slice(0, 10),
    // La 1ère échéance correspond au paiement qu'on vient d'initier.
    paiement_ref: i === 0 ? referenceInitiale : null,
  }));
  await sb(`/rest/v1/echeances`, { method: "POST", headers: { Prefer: "return=minimal" }, body: JSON.stringify(lignes) });
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
  const type = ["commission", "abonnement", "boost", "produit", "verification"].includes(body.type) ? body.type : "commission";
  const reference = genererReference();

  const { pct, planNom } = await commissionPourUtilisateur(user.id);
  const commission = type === "commission" ? Math.round(montant * pct / 100) : 0;

  // Métadonnées nécessaires pour créer l'annonce/l'abonnement UNE FOIS le
  // paiement confirmé par le webhook — jamais avant. `annonce` n'est que
  // du contenu (titre/description/photos...), aucune valeur financière
  // n'y est relue.
  const metadata = body.annonce && typeof body.annonce === "object" ? body.annonce : null;

  // Paiement en plusieurs fois (BNPL) : le prix officiel du service décide
  // des échéances, jamais le montant envoyé par le client.
  const nEchelons = [2, 3].includes(Number(body.echelonner)) ? Number(body.echelonner) : 0;
  let planEcheances: { montantTotal: number; fraisPct: number; montants: number[] } | null = null;
  let montantAPayerMaintenant = montant;
  if (nEchelons && TYPES_ECHELONNABLES.includes(type)) {
    const prixRef = await prixReference(type, metadata, montant);
    if (!prixRef || prixRef < 1000) return json({ error: "Échelonnement indisponible pour ce service" }, 400);
    planEcheances = calculerEcheances(prixRef, nEchelons);
    montantAPayerMaintenant = planEcheances.montants[0];
  }

  let planVendeur: string | null;
  if (type === "abonnement") {
    planVendeur = planEcheances
      ? (typeof metadata?.plan === "string" ? metadata.plan : null)
      : await planAchete(metadata, montant);
    if (!planVendeur) return json({ error: "Plan d'abonnement invalide" }, 400);
  } else {
    planVendeur = planNom;
  }
  if (type === "produit" && !(await produitAchete(metadata, montant))) return json({ error: "Produit indisponible ou montant invalide" }, 400);

  const insertRes = await sb(`/rest/v1/paiements`, {
    method: "POST",
    headers: { Prefer: "return=representation" },
    body: JSON.stringify({
      vendeur_id: user.id, annonce_titre: description, valeur: montantAPayerMaintenant, commission,
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
        amount: montantAPayerMaintenant,
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
    if (planEcheances) await creerEcheancier(user.id, type, reference, planEcheances);
    return json({ payment_url: cp.payment_url, reference, echeancier: planEcheances });
  }

  const cpRes = await fetch("https://api-checkout.cinetpay.com/v2/payment", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      apikey: CINETPAY_API_KEY,
      site_id: CINETPAY_SITE_ID,
      transaction_id: reference,
      amount: montantAPayerMaintenant,
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

  if (planEcheances) await creerEcheancier(user.id, type, reference, planEcheances);
  return json({ payment_url: cpData.data.payment_url, reference, echeancier: planEcheances });
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

// ── Mes échéanciers en cours (BNPL) : pour l'écran "Mes paiements" du tableau
// de bord vendeur — affiche ce qui reste à payer et les retards éventuels.
async function mesEcheances(req: Request, user: any) {
  await sb("/rest/v1/rpc/verifier_echeances_retard", { method: "POST" }).catch(() => {});
  const r = await sb(`/rest/v1/echeanciers?utilisateur_id=eq.${user.id}&order=created_at.desc&select=id,type,montant_total,frais_pct,nb_echeances,statut,created_at,echeances(id,numero,montant,date_prevue,statut,payee_le)`);
  const rows = r.ok ? await r.json() : [];
  return json({ echeanciers: rows });
}

// ── Règlement d'une échéance en attente/retard, par transfert Mobile Money
// direct (même principe que /paiement/manuel, mais pour une échéance existante
// plutôt qu'un nouvel achat). Le service reste actif tant que l'échéancier
// n'a pas basculé "défaillant" (5 jours de retard, cf. verifier_echeances_retard).
async function payerEcheance(req: Request, user: any) {
  const body = await req.json().catch(() => ({}));
  const echeanceId = Number(body.echeance_id);
  if (!echeanceId) return json({ error: "echeance_id requis" }, 400);

  const canal = String(body.canal || "").toLowerCase();
  if (!CANAUX_MANUELS.includes(canal)) return json({ error: "Moyen de paiement invalide" }, 400);
  const txnId = String(body.txn_id || "").trim().toUpperCase().replace(/\s+/g, "");
  if (!/^[A-Z0-9.\-_]{4,40}$/.test(txnId)) return json({ error: "ID de transaction invalide" }, 400);

  const echRes = await sb(`/rest/v1/echeances?id=eq.${echeanceId}&select=id,numero,montant,statut,paiement_ref,echeancier_id,echeanciers(id,type,utilisateur_id,statut)`);
  const echRows = echRes.ok ? await echRes.json() : [];
  if (!echRows.length) return json({ error: "Échéance introuvable" }, 404);
  const ech = echRows[0];
  const echeancier = ech.echeanciers;
  if (!echeancier || echeancier.utilisateur_id !== user.id) return json({ error: "Échéance introuvable" }, 404);
  if (!["a_venir", "en_retard"].includes(ech.statut)) return json({ error: "Cette échéance est déjà réglée" }, 409);

  const dejaRes = await sb(`/rest/v1/paiements?metadata->>txn_id=eq.${encodeURIComponent(txnId)}&select=id&limit=1`);
  if (dejaRes.ok && (await dejaRes.json()).length) return json({ error: "Cet ID de transaction a déjà été déclaré" }, 409);

  const reference = "MM" + Date.now().toString().slice(-10) + Math.floor(Math.random() * 900 + 100);
  const telPayeur = String(body.tel || "").replace(/[^\d+]/g, "").slice(0, 20);

  // On rattache d'abord la référence à l'échéance (le trigger de confirmation
  // se contente ensuite de faire correspondre paiements.ref = echeances.paiement_ref).
  const majEch = await sb(`/rest/v1/echeances?id=eq.${echeanceId}&statut=in.(a_venir,en_retard)`, {
    method: "PATCH", headers: { Prefer: "return=representation" }, body: JSON.stringify({ paiement_ref: reference }),
  });
  const majEchRows = majEch.ok ? await majEch.json() : [];
  if (!majEchRows.length) return json({ error: "Échéance déjà réglée entre-temps" }, 409);

  const insertRes = await sb(`/rest/v1/paiements`, {
    method: "POST",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify({
      vendeur_id: user.id, annonce_titre: `Échéance ${ech.numero}/${echeancier.type}`, valeur: ech.montant, commission: 0,
      ref: reference, passerelle: PASSERELLE_MANUELLE, moyen: canal, statut: "attente",
      plan_vendeur: null, type: echeancier.type, metadata: { txn_id: txnId, tel_payeur: telPayeur, echeancier_id: echeancier.id },
    }),
  });
  if (!insertRes.ok) {
    await sb(`/rest/v1/echeances?id=eq.${echeanceId}`, { method: "PATCH", headers: { Prefer: "return=minimal" }, body: JSON.stringify({ paiement_ref: null }) });
    return json({ error: "Échec d'enregistrement du paiement" }, 500);
  }
  return json({ reference });
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

  const nEchelons = [2, 3].includes(Number(body.echelonner)) ? Number(body.echelonner) : 0;
  let planEcheances: { montantTotal: number; fraisPct: number; montants: number[] } | null = null;
  let montantAPayerMaintenant = montant;
  if (nEchelons && TYPES_ECHELONNABLES.includes(type)) {
    const prixRef = await prixReference(type, contenu, montant);
    if (!prixRef || prixRef < 1000) return json({ error: "Échelonnement indisponible pour ce service" }, 400);
    planEcheances = calculerEcheances(prixRef, nEchelons);
    montantAPayerMaintenant = planEcheances.montants[0];
  }

  const metadata = { ...contenu, txn_id: txnId, tel_payeur: telPayeur };

  if (type === "produit" && !(await produitAchete(contenu, montant))) {
    return json({ error: "Produit indisponible ou montant invalide" }, 400);
  }

  let planVendeur: string | null;
  if (type === "abonnement") {
    planVendeur = planEcheances
      ? (typeof contenu?.plan === "string" ? contenu.plan : null)
      : await planAchete(contenu, montant);
    if (!planVendeur) return json({ error: "Plan d'abonnement invalide" }, 400);
  } else {
    planVendeur = (await commissionPourUtilisateur(user.id)).planNom;
  }

  const reference = "MM" + Date.now().toString().slice(-10) + Math.floor(Math.random() * 900 + 100);
  const insertRes = await sb(`/rest/v1/paiements`, {
    method: "POST",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify({
      vendeur_id: user.id, annonce_titre: description, valeur: montantAPayerMaintenant,
      commission: type === "commission" ? montantAPayerMaintenant : 0,
      ref: reference, passerelle: PASSERELLE_MANUELLE, moyen: canal,
      statut: "attente", plan_vendeur: planVendeur, type, metadata,
    }),
  });
  if (!insertRes.ok) return json({ error: "Échec d'enregistrement du paiement" }, 500);
  if (planEcheances) await creerEcheancier(user.id, type, reference, planEcheances);
  return json({ reference, echeancier: planEcheances });
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

// Achat protégé (paiement séquestre) : l'acheteur (avec ou sans compte)
// déclare avoir envoyé le prix de l'article + les frais de protection au
// numéro du Grenier — jamais directement au vendeur. Le prix officiel est
// TOUJOURS celui de l'annonce en base, jamais un montant envoyé par le
// client. Rien n'est retenu ni versé avant validation admin (cf.
// validerPaiementManuel), qui crée la ligne "achats_proteges".
async function declarerAchatProtege(req: Request) {
  const body = await req.json().catch(() => ({}));
  const annonceId = Number(body.annonce_id);
  if (!annonceId) return json({ error: "annonce_id requis" }, 400);

  const canal = String(body.canal || "").toLowerCase();
  if (!CANAUX_MANUELS.includes(canal)) return json({ error: "Moyen de paiement invalide" }, 400);
  const txnId = String(body.txn_id || "").trim().toUpperCase().replace(/\s+/g, "");
  if (!/^[A-Z0-9.\-_]{4,40}$/.test(txnId)) return json({ error: "ID de transaction invalide" }, 400);
  const nom = String(body.nom || "").trim().slice(0, 80);
  if (nom.length < 2) return json({ error: "Nom requis" }, 400);
  const telAcheteur = String(body.tel || "").replace(/[^\d+]/g, "").slice(0, 20);
  if (telAcheteur.replace(/\D/g, "").length < 8) return json({ error: "Numéro WhatsApp requis" }, 400);

  const aRes = await sb(`/rest/v1/annonces?id=eq.${annonceId}&statut=eq.actif&select=id,titre,valeur,vendeur_id`);
  const aRows = aRes.ok ? await aRes.json() : [];
  if (!aRows.length) return json({ error: "Annonce indisponible" }, 400);
  const annonce = aRows[0];
  if (!annonce.vendeur_id) return json({ error: "Annonce indisponible" }, 400);

  const montantArticle = Number(annonce.valeur) || 0;
  if (montantArticle < 500) return json({ error: "Achat protégé indisponible pour cette annonce" }, 400);
  const fraisProtection = Math.max(FRAIS_PROTECTION_MIN, Math.round(montantArticle * FRAIS_PROTECTION_PCT / 100));

  const dejaRes = await sb(`/rest/v1/paiements?metadata->>txn_id=eq.${encodeURIComponent(txnId)}&select=id&limit=1`);
  if (dejaRes.ok && (await dejaRes.json()).length) return json({ error: "Cet ID de transaction a déjà été déclaré" }, 409);

  const jeton = nouveauJeton();
  const reference = "MM" + Date.now().toString().slice(-10) + Math.floor(Math.random() * 900 + 100);
  const insertRes = await sb(`/rest/v1/paiements`, {
    method: "POST",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify({
      vendeur_id: annonce.vendeur_id, annonce_titre: "Achat protégé : " + annonce.titre,
      valeur: montantArticle + fraisProtection, commission: fraisProtection,
      ref: reference, passerelle: PASSERELLE_MANUELLE, moyen: canal, statut: "attente",
      plan_vendeur: null, type: "achat_protege",
      metadata: {
        annonce_id: annonce.id, montant_article: montantArticle, frais_protection: fraisProtection,
        acheteur_nom: nom, acheteur_tel: telAcheteur, txn_id: txnId, tel_payeur: telAcheteur, jeton,
      },
    }),
  });
  if (!insertRes.ok) return json({ error: "Échec d'enregistrement du paiement" }, 500);
  return json({ reference, jeton, montant_article: montantArticle, frais_protection: fraisProtection });
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
// `dureeJours` : durée pleine du plan pour un 1er paiement (30j par défaut,
// éventuellement multipliée si l'échéancier couvre plusieurs mois) ; une
// échéance suivante (2e/3e règlement) ne prolonge rien, elle règle juste la dette.
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

// Une échéance suivante (2e/3e règlement d'un échéancier) ne doit jamais
// réactiver le service depuis zéro — seule la 1ère échéance (celle qui porte
// la référence de paiement_initial_ref d'un échéancier, ou aucun échéancier)
// déclenche l'activation normale.
async function estEcheanceSuivante(paiement: any): Promise<boolean> {
  if (!paiement.metadata?.echeancier_id) return false;
  const r = await sb(`/rest/v1/echeanciers?id=eq.${paiement.metadata.echeancier_id}&select=paiement_initial_ref`);
  const rows = r.ok ? await r.json() : [];
  return rows.length ? rows[0].paiement_initial_ref !== paiement.ref : false;
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
  const suivante = await estEcheanceSuivante(paiement);
  let active = "";
  if (suivante) {
    active = "échéance réglée";
  } else if (paiement.type === "abonnement") {
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
  } else if (paiement.type === "achat_protege") {
    const m = paiement.metadata || {};
    const dateLimite = new Date(Date.now() + DELAI_CONFIRMATION_JOURS * 24 * 3600 * 1000).toISOString().slice(0, 10);
    await sb("/rest/v1/achats_proteges", {
      method: "POST", headers: { Prefer: "return=minimal" },
      body: JSON.stringify({
        annonce_id: m.annonce_id || null, vendeur_id: paiement.vendeur_id, paiement_ref: paiement.ref,
        acheteur_nom: m.acheteur_nom || "Client", acheteur_tel: m.acheteur_tel || "",
        montant_article: m.montant_article || paiement.valeur, frais_protection: m.frais_protection || paiement.commission || 0,
        jeton: m.jeton, date_limite_confirmation: dateLimite,
      }),
    });
    active = "achat protégé — en attente de livraison";
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
    if (req.method === "POST" && path.endsWith("/achat-protege")) {
      return await declarerAchatProtege(req);
    }

    const user = await identifierAppelant(req);
    if (!user) return json({ error: "Non authentifié" }, 401);

    if (req.method === "GET" && path.endsWith("/statut")) {
      return await statutPaiement(req, user);
    }
    if (req.method === "GET" && path.endsWith("/mes-echeances")) {
      return await mesEcheances(req, user);
    }
    if (req.method === "POST" && path.endsWith("/echeance")) {
      return await payerEcheance(req, user);
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
