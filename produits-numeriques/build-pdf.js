// Imprime chaque guide HTML de dist/ en PDF A5 (avec en-tête et numéro de page)
// et capture la couverture en PNG pour la boutique.
// Usage : NODE_PATH=$(npm root -g) node produits-numeriques/build-pdf.js
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

const DIST = path.join(__dirname, 'dist');

(async () => {
  const navigateur = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
  const page = await navigateur.newPage();
  for (const f of fs.readdirSync(DIST).filter(n => n.endsWith('.html'))) {
    const slug = f.replace(/\.html$/, '');
    await page.goto('file://' + path.join(DIST, f));
    const titre = await page.title();
    await page.pdf({
      path: path.join(DIST, slug + '.pdf'),
      preferCSSPageSize: true,
      printBackground: true,
      displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate: `<div style="font-size:7px;width:100%;padding:0 14mm;color:#736E64;display:flex;justify-content:space-between;font-family:Arial">
        <span>${titre.replace(/</g, '&lt;')} · Le Grenier CI</span><span class="pageNumber"></span></div>`,
    });
    await page.setViewportSize({ width: 560, height: 794 });
    await page.locator('.couverture').screenshot({ path: path.join(DIST, slug + '-couverture.png') });
    console.log('PDF + couverture :', slug);
  }
  await navigateur.close();
})();
