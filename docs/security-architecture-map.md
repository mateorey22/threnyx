# Cartographie de sécurité actuelle — Threnyx

> **Portée.** Cette cartographie décrit l’état observé dans le dépôt `mateorey22/threnyx` avant une éventuelle migration de protocole de session. Elle n’atteste pas une propriété cryptographique qui n’est pas démontrée par une implémentation et une suite de tests dédiées.

## Surface applicative

| Domaine | Implémentation observée | Données ou sécurité concernées |
|---|---|---|
| Identité | Clé secp256k1 Nostr générée localement par `Secp.genPriv()` ; clé publique dérivée localement. | La clé privée d’identité reste dans le coffre local chiffré. Elle reste un secret à très forte valeur. |
| Coffre | `Vault` avec Argon2id et chiffrement AES-GCM ; voie historique PBKDF2 uniquement pour compatibilité de migration. WebAuthn PRF protège l’accès biométrique lorsqu’il est configuré. | Le mot de passe n’est pas stocké ni envoyé au réseau. Les secrets chargés vivent néanmoins en mémoire JavaScript durant une session ouverte. |
| Données locales | `DB` s’appuie sur IndexedDB pour coffre, contacts, groupes, messages, fragments, outbox et préférences. | Les données de coffre sont chiffrées ; les structures de l’interface et certains états applicatifs restent nécessaires au fonctionnement local. |
| Messagerie relais | Nouveau chemin NIP-17 : NIP-44 v2 et gift wrap NIP-59 via bundle local `nostr-tools`, avec contrôle de signature, kind et destinataire. Chemin historique conservé pour compatibilité de contacts. | NIP-17 améliore l’enveloppe et l’interopérabilité ; il ne fournit pas seul forward secrecy ou post-compromise security. |
| Anti-doublon | Identifiants d’événements reçus mémorisés dans `S.seen` et les `shards`, avec purge temporelle. | Réduit le retraitement des mêmes événements acheminés par plusieurs relais. Cela ne constitue pas un état Double Ratchet. |
| Constellation | Snapshots fragmentés chiffrés, manifeste signé, dérivation HKDF par fragment, réplication multi-relais, restauration NFC TCV1. Updates Yjs pour contacts, groupes et préférences compatibles. | Le tag NFC classique est clonable ; il permet une reprise mais ne remplace pas un secure element. Les messages et médias ne sont pas fusionnés par Yjs. |
| WebRTC | `RTCPeerConnection`, ICE STUN/TURN optionnel, signalisation Nostr, pistes distantes et diagnostic local des compteurs RTP. | DTLS-SRTP protège le média en transit ; l’IP et les candidates peuvent être visibles du pair ou des serveurs STUN/TURN selon la configuration. |
| NFC et QR | Cartes de contact MC1, récupération TCV1 et invitations de groupe GC1 séparées par préfixe et validation. | Les entrées sont des données non fiables jusqu’à validation de format, de signature et de capacité. |
| PWA | Service worker same-origin versionné `threnyx-pwa-v22`, cache shell et activation supprimant les caches Threnyx précédents. | L’ancienne version de cache est supprimée à l’activation ; GitHub Pages et le navigateur restent dans la chaîne de confiance de livraison du JavaScript. |

## Primitives et usages observés

| Primitive | Usage actuel | Observation d’audit |
|---|---|---|
| AES-GCM 256 | Chiffrement du coffre, sauvegardes et enveloppes applicatives. | Les IV sont générés aléatoirement par `crypto.getRandomValues`. Le code doit garder l’invariant clé/IV non réutilisé. |
| HKDF-SHA-256 | Dérivations Constellation et flux historiques. | Une dérivation de clé ne remplace pas un protocole de ratchet à état. |
| Argon2id | KDF de coffre et de sauvegarde récente. | Les paramètres sont versionnés dans les enveloppes. La migration PBKDF2 historique reste explicitement limitée aux anciens coffres. |
| BIP-340 / secp256k1 | Identité Nostr et signatures d’événements. | La vérification d’événement est exécutée avant le routage des charges utiles Nostr. |
| NIP-44 v2 / NIP-59 / NIP-17 | Messages persistants entre contacts qui annoncent la capacité correspondante. | La capacité est négociée ; le repli historique reste nécessaire pour les appareils plus anciens. |
| Yjs | Fusion CRDT des données Constellation compatibles. | Ne fusionne pas les messages, suppressions ni médias ; il ne gère pas la sécurité d’une session de messagerie. |

## Limites et risques à traiter avant une annonce de session moderne

1. **Aucune forward secrecy démontrée.** Les messages NIP-17 n’emploient pas encore une session Double Ratchet, des prekeys ou une suppression vérifiable de clés de message.
2. **Aucune post-compromise security démontrée.** Il n’existe pas de root key de session évoluant par ratchet DH après une compromission temporaire.
3. **Multi-appareil à renforcer.** Les appareils liés à portée minimale restent un chantier distinct ; une même identité Nostr ne doit pas devenir une clé symétrique globale partagée entre appareils.
4. **État de session absent.** Il faudra définir la persistance atomique du ratchet, la limite de skipped keys, la récupération après crash, l’anti-rejeu par session et la suppression de secrets.
5. **PWA et chaîne de livraison.** HTTPS, CSP et SRI local limitent certaines attaques, mais une compromission de GitHub Pages, du dépôt ou d’un navigateur/extension peut compromettre le JavaScript livré.
6. **Métadonnées.** Les relais, le navigateur, les serveurs STUN/TURN et le pair WebRTC peuvent observer diverses métadonnées. Threnyx ne doit pas être présenté comme anonyme.

## Décision de migration

La prochaine étape est une **conception versionnée**, une évaluation de bibliothèques maintenues et une suite de tests de propriétés. Le protocole en production ne sera pas remplacé par un Double Ratchet écrit sur mesure dans `index.html`.
