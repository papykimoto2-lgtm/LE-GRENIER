const { chromium } = require('/opt/node22/lib/node_modules/playwright/node_modules/playwright-core');
const path = require('path');

const OUT = path.join(__dirname, 'capture', 'screenshots', 'categories');

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', headless: true });
  const page = await browser.newPage({ viewport: { width: 430, height: 932 }, deviceScaleFactor: 2 });
  await page.goto('http://127.0.0.1:8934/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);

  // Seed des données de démonstration réalistes (réseau Supabase bloqué dans
  // ce bac à sable) pour des captures présentables plutôt que des écrans vides.
  await page.evaluate(() => {
    const emoji = (c) => ({'Électronique':'📱','Mobilier':'🛋️','Vêtements':'👗'}[c] || '📦');
    for (let i = 1; i <= 8; i++) {
      DAO._local.annonces.push({
        id: 9000 + i, titre: ['iPhone 13 Pro','Canapé 3 places','Robe wax','Frigo Samsung','Moto Yamaha','TV LED 55"','Chaussures Nike','Table à manger'][i-1],
        cat: 'Électronique', valeur: [180000,95000,15000,220000,650000,140000,25000,75000][i-1], etat: 'Bon état',
        ville: ['Abidjan','Cocody','Yopougon','Marcory','Plateau','Abobo','Treichville','Bingerville'][i-1],
        vendeurId: 1, statut: 'en-ligne', vues: 40+i*7, emoji: emoji('Électronique'), photos: [], typeTab: 'tab-marche',
        date: '2026-09-20'
      });
    }
    if (typeof appliquerFiltres === 'function') appliquerFiltres();

    DB_BOULOTS && DB_BOULOTS.length === 0 && DB_BOULOTS.push(
      {id:1,nom:'Kouassi Jean',metier:'Plombier',zone:'Cocody',note:4.8,nbAvis:56,photo:null,ico:'🔧',gratuit:false,tel:'0700000000'},
      {id:2,nom:'Aya Marie',metier:'Coiffeuse',zone:'Yopougon',note:4.9,nbAvis:112,photo:null,ico:'💇',gratuit:false,tel:'0700000001'},
      {id:3,nom:'Ibrahim Traoré',metier:'Électricien',zone:'Marcory',note:4.7,nbAvis:38,photo:null,ico:'⚡',gratuit:false,tel:'0700000002'}
    );
    if (typeof renderBoulots === 'function') renderBoulots();
  });
  await page.waitForTimeout(300);

  async function shot(name, setupFn) {
    if (setupFn) await page.evaluate(setupFn);
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${OUT}/${name}.png` });
    console.log('captured', name);
  }

  await shot('accueil');
  await shot('marche', () => switchMainTab(document.createElement('div'), 'tab-marche'));
  await shot('boulots', () => switchMainTab(document.createElement('div'), 'tab-boulots'));
  await shot('logement', () => switchMainTab(document.createElement('div'), 'tab-logement'));
  await shot('resto', () => switchMainTab(document.createElement('div'), 'tab-resto'));
  await shot('supermarche', () => switchMainTab(document.createElement('div'), 'tab-supermarche'));
  await shot('livraison', () => switchMainTab(document.createElement('div'), 'tab-livraison'));
  await shot('dons', () => switchMainTab(document.createElement('div'), 'tab-dons'));
  await shot('auto', () => switchMainTab(document.createElement('div'), 'tab-auto'));
  await shot('beaute', () => switchMainTab(document.createElement('div'), 'tab-beaute'));
  await shot('nounou', () => switchMainTab(document.createElement('div'), 'tab-nounou'));

  await browser.close();
})();
