// Appelé par build.py : imprime la couverture (sans pied de page) et le corps
// (pied de page + numéro) de chaque guide, et capture la couverture en PNG.
// Usage : NODE_PATH=$(npm root -g) node build-pdf.js <slug> [<slug>…]
// CHROMIUM_PATH permet d'indiquer un Chromium déjà installé.
const path = require('path');
const { chromium } = require('playwright');

const DIST = path.join(__dirname, 'dist');

(async () => {
  const navigateur = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const page = await navigateur.newPage();
  for (const slug of process.argv.slice(2)) {
    await page.goto('file://' + path.join(DIST, slug + '-couverture.html'), { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    await page.pdf({ path: path.join(DIST, slug + '-couverture.pdf'), preferCSSPageSize: true, printBackground: true });
    await page.setViewportSize({ width: 560, height: 794 });
    await page.locator('.couverture').screenshot({ path: path.join(DIST, slug + '-couverture.png') });

    await page.goto('file://' + path.join(DIST, slug + '-corps.html'), { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    const titre = (await page.title()).replace(/</g, '&lt;');
    await page.pdf({
      path: path.join(DIST, slug + '-corps.pdf'),
      preferCSSPageSize: true,
      printBackground: true,
      displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate: `<div style="font-size:7px;width:100%;padding:0 13mm;color:#8A857B;display:flex;justify-content:space-between;font-family:Arial">
        <span>${titre} · Le Grenier CI</span><span class="pageNumber"></span></div>`,
    });
  }
  await navigateur.close();
})();
