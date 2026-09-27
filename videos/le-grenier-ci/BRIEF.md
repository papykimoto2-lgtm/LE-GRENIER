---
workflow: product-launch-video
flow: automation
storyboard: no
message: "Le Grenier CI : tout ce dont vous avez besoin, en un seul endroit"
destination: whatsapp-instagram-tiktok
aspect: 1080x1920
language: fr
length: 35s
audience: "Grand public ivoirien, utilisateurs mobiles (acheteurs, vendeurs, artisans, livreurs)"
angle: site-tour
narration: yes
---

## Intent

Vidéo courte de présentation générale de Le Grenier CI, une marketplace
ivoirienne multi-services : petites annonces, artisans/boulots, nounous,
covoiturage/colis, location de véhicules, dons, salons de beauté, logements,
restaurants, supermarché en ligne, livraison à domicile. Montrer le site tel
qu'il est (site tour), pas une vidéo de vente agressive — ton chaleureux,
accessible, ancré dans le quotidien ivoirien. Objectif : faire comprendre en
quelques secondes l'étendue des services disponibles en un seul endroit.

## Assets

- capture/ — captures d'écran du serveur de développement local
  (http://127.0.0.1:8934, identique à l'appli en production ci-legrenier.com),
  couvrant l'accueil et les principales catégories.
- logo — extrait directement du HTML de l'application (data URI base64 inline).

## Customizations

- Contrainte réseau de l'environnement : ni l'URL en ligne (ci-legrenier.com)
  ni les services cloud HeyGen ne sont joignables depuis ce bac à sable.
  Capture d'écran via le serveur de développement local à la place du crawl
  distant habituel ; narration vocale via le moteur local hors-ligne Kokoro
  (déjà installé), pas la voix cloud HeyGen.
- Palette couleurs de la marque : vert (--vert), or/jaune (--or), blanc —
  cohérent avec le logo et l'identité visuelle déjà présente dans l'appli.

## Notes

- Aucune capture automatique via `npx hyperframes capture` (URL distante hors
  de portée) : les visuels viennent de captures manuelles (Playwright) du
  serveur local, avec des données de démonstration réalistes déjà présentes
  dans l'appli.
- Voix off en français uniquement, courte et énergique — pas de sous-titres
  obligatoires mais un texte à l'écran pour chaque catégorie mise en avant.
