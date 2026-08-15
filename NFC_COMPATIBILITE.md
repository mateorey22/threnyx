# NFC MeshChat — compatibilité vérifiée

Web NFC dans Chrome Android lit et écrit des messages **NDEF** sur des tags NFC compatibles, dans un contexte HTTPS et après une action explicite de l’utilisateur. L’API est limitée aux messages NDEF, exige l’autorisation NFC et ne fonctionne que lorsque la page est visible.[1]

> Chrome Android ne prend pas en charge le mode NFC pair-à-pair ni l’émulation de carte hôte dans Web NFC. Deux téléphones ne peuvent donc pas échanger directement une carte MeshChat par simple rapprochement depuis une PWA. La mise en œuvre doit utiliser un tag NFC NDEF comme support de carte de contact, avec QR/invitation comme solution immédiate entre deux téléphones.[1]

La PWA peut toutefois offrir deux opérations pratiques : **écrire ma carte** sur un tag NFC NDEF vierge ou réinscriptible et **lire une carte** déposée sur un tag. La carte ne transporte qu’une invitation MeshChat à capacité limitée, exactement comme le QR ; elle ne contient jamais la clé privée.

## Référence

[1] [Chrome for Developers — Interact with NFC devices on Chrome for Android](https://developer.chrome.com/docs/capabilities/nfc)

## Vérification de l’implémentation

La version locale avec parcours NFC, repli QR et iconographie modernisée passe la vérification de syntaxe JavaScript, la vérification du hash CSP et le chargement navigateur sans erreur de console. Le test matériel NFC reste à effectuer sur Chrome Android, avec NFC activé et une carte/tag NDEF compatible.

La première vérification publique après le commit NFC a encore détecté la version précédente : ni le module NFC ni les nouveaux contrôles n’étaient présents. La construction GitHub Pages doit être contrôlée puis la page rechargée après propagation.

La vérification publique finale de `https://mateorey22.github.io/zenithchat/` confirme la présence du module NFC, des contrôles « ÉCRIRE MA CARTE » et de l’iconographie de contact modernisée. Le service worker de la PWA reste actif.
