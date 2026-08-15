# Threnyx PWA — déploiement GitHub Pages

Ce kit transforme Threnyx en **vraie Progressive Web App** Android. Contrairement à un simple raccourci, le manifeste et le service worker sont maintenant des fichiers réels, servis sur la même origine que l’application. Une fois installée, la PWA demande le mode `standalone` : elle s’ouvre sans barre d’adresse Chrome, avec son icône dans le lanceur d’applications. Les navigateurs Chromium exigent un manifeste, des icônes 192 et 512 px, une URL de démarrage et HTTPS pour promouvoir l’installation.[1]

## Fichiers à publier

Copiez **le contenu** de ce dossier dans le même répertoire GitHub Pages que l’application. Le fichier principal doit s’appeler `index.html` et les quatre fichiers associés doivent rester à côté de lui.

| Fichier | Rôle |
|---|---|
| `index.html` | Application Threnyx avec bouton d’installation et enregistrement du service worker. |
| `manifest.webmanifest` | Nom, icônes, écran de lancement et ouverture autonome. |
| `service-worker.js` | Cache du shell de l’application, clic sur notification et écoute des Push futurs. |
| `icon-192.png` et `icon-512.png` | Icônes requises par Android/Chrome. |
| `icon-maskable-512.png` | Icône adaptée aux masques des lanceurs Android. |

L’exemple suivant conserve une URL GitHub Pages du type `https://utilisateur.github.io/mon-repo/`. Les chemins du manifeste sont relatifs : le kit fonctionne aussi si votre site Pages est publié depuis le dossier `/docs` ou une branche dédiée, tant que les fichiers restent ensemble.

## Installation Android correcte

Après le déploiement, ouvrez l’URL HTTPS dans Chrome Android. Ouvrez ensuite le menu `⋮` et choisissez **Installer l’application** — et non **Ajouter à l’écran d’accueil**. Chrome doit afficher la fenêtre d’installation avec l’icône Threnyx. Une fois acceptée, l’icône apparaît parmi les applications et l’ouverture se fait en fenêtre autonome, sans URL Chrome.[1] [2]

Si Android réutilise l’ancien raccourci, supprimez ce raccourci une seule fois, rechargez l’URL GitHub Pages, puis choisissez explicitement **Installer l’application**. Après une modification du service worker, fermez les fenêtres et l’application existantes puis rouvrez-la : un nouveau worker attend généralement que les anciens clients aient quitté avant de prendre le contrôle.[4]

## Ce que le kit apporte déjà

Le service worker est enregistré à la racine de l’application, met en cache le shell nécessaire et permet à la PWA de démarrer plus proprement lorsqu’elle est installée. Il peut afficher une notification Android via `showNotification()` lorsque la page est active, et il contient aussi le gestionnaire standard d’un événement `push` pour une passerelle de notification future.

> Le kit ne prétend pas recevoir des messages lorsque Threnyx est fermé. Un service worker ne peut pas garder une connexion Nostr ouverte en permanence ; il se réveille pour une requête, un événement de synchronisation ou un Push.[4]

## Notifications Android quand l’application est fermée

Une notification réellement persistante demande trois éléments : un service worker actif, une souscription Push du téléphone et un serveur qui envoie la notification à cette souscription. Le serveur est indispensable : c’est lui qui déclenche l’événement `push` même lorsque l’application n’est pas ouverte.[3]

| Solution | Résultat pour l’utilisateur | Confidentialité et compromis | Coût et complexité |
|---|---|---|---|
| **PWA seule, déjà fournie** | Notification et son lorsque l’application est ouverte ou en arrière-plan léger, suivant Android/Chrome. Pas de garantie après fermeture complète. | Aucun nouveau serveur ni partage de métadonnées. | Gratuit, prêt maintenant. |
| **Passerelle Web Push minimale** | Notification Android « Nouveau message Threnyx » même application fermée. | La passerelle connaît l’identifiant de souscription et l’instant de réception ; elle ne reçoit pas le contenu chiffré du message. | Configuration modérée : un petit service sécurisé, clé VAPID et stockage des souscriptions. |
| **Service compagnon connecté aux relais** | Notification fiable, même si le destinataire ne lance jamais l’application. | Le service observe la livraison d’enveloppes chiffrées aux clés publiques et envoie une alerte générique ; le contenu reste chiffré. | Plus robuste, mais demande un hébergement persistant et une revue de confidentialité. |

La solution à retenir dépend de votre tolérance aux métadonnées et à un service additionnel. La PWA seule est la plus privée ; une passerelle Web Push offre l’expérience Android que vous demandez, mais nécessite un choix d’hébergement et des clés de production. Ne placez jamais une clé privée VAPID dans GitHub Pages ou dans le fichier HTML.

## Vérification après déploiement

Ouvrez l’URL GitHub Pages puis, dans Chrome sur ordinateur, utilisez `Application → Manifest` et `Application → Service workers` pour confirmer que le manifeste est chargé et que le worker est activé. Sur Android, l’installation et l’absence de barre d’adresse au lancement sont les contrôles pratiques les plus importants.

## Références

[1] [MDN — Making PWAs installable](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable)

[2] [MDN — Manifest `display`](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest/Reference/display)

[3] [MDN — Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)

[4] [web.dev — Service workers](https://web.dev/learn/pwa/service-workers)
