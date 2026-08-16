# Sécurité Threnyx

## Position de sécurité actuelle

Threnyx est une PWA statique distribuée par GitHub Pages. Elle chiffre le coffre local, utilise des événements Nostr signés et transporte les nouveaux messages persistants dans des enveloppes NIP-17 fondées sur NIP-44 v2 et NIP-59. Les appels s’appuient sur WebRTC et les snapshots Constellation sont chiffrés avant réplication sur plusieurs relais.

> Threnyx **ne revendique pas**, à ce jour, la forward secrecy ni la post-compromise security pour ses conversations. NIP-17 standardise l’enveloppe de messagerie et réduit certaines fuites de métadonnées, mais ne remplace pas un protocole à état tel que Double Ratchet ou MLS.

## Modèle de menace

| Adversaire | Capacité considérée | Protection actuelle | Limite résiduelle |
|---|---|---|---|
| Réseau passif | Observe le trafic HTTP(S), WebSocket et WebRTC. | HTTPS, WSS, chiffrement applicatif des messages et DTLS-SRTP. | Peut observer des métadonnées de réseau et de volume. |
| Relais Nostr malveillant | Retarde, duplique, supprime, réordonne ou injecte des événements. | Vérification de signature, contrôles de kind/destinataire, anti-doublon local et outbox. | Disponibilité non garantie ; NIP-17 n’apporte pas seul de session ratchetée. |
| Compromission locale | Accède au téléphone, IndexedDB ou mémoire après déverrouillage. | Coffre Argon2id, WebAuthn PRF facultatif, verrouillage, wipe local. | Un appareil déverrouillé ou compromis reste un événement grave. |
| Compromission de clé d’identité | Récupère une clé Nostr à long terme. | Alerte locale de changement de clé, fingerprint QR/hors bande. | Les conversations actuelles ne disposent pas encore de récupération cryptographique de session. |
| Relais WebRTC / réseau pair | Observe candidates ICE, IP et métadonnées de connexion. | DTLS-SRTP, TURN configurable. | P2P n’est pas de l’anonymat ; TURN peut voir l’IP source selon sa configuration. |
| Attaquant physique NFC | Copie ou remplace un tag NDEF. | TCV1 ne contient pas le compte en clair et la récupération vérifie des artefacts signés/chiffrés. | Un tag NDEF ordinaire n’est pas un secure element et peut être cloné. |
| Chaîne de livraison frontend | Altère le dépôt, GitHub Pages, le navigateur ou une extension. | CSP stricte, bundles locaux, HTTPS, service worker versionné. | Le JavaScript livré et le navigateur restent dans le TCB du client. |

## Garanties et non-garanties

| Sujet | Statut |
|---|---|
| Chiffrement du coffre local | Implémenté avec Argon2id et AES-GCM ; WebAuthn PRF facultatif. |
| Chiffrement du contenu des nouveaux messages persistants | Implémenté via NIP-17/NIP-44 v2/NIP-59 avec vérification Nostr. |
| Vérification d’identité hors bande | Disponible par fingerprint et QR ; elle dépend d’un canal de comparaison réellement fiable. |
| Forward secrecy / post-compromise security | **Non revendiquées.** Nécessitent un protocole de session validé par tests. |
| Anonymat / absence de métadonnées | **Non revendiqués.** Relais, transport et WebRTC exposent des métadonnées. |
| Effacement global après wipe local | **Non garanti.** Les données déjà publiées ou reçues par des pairs ne peuvent pas être retirées localement. |

## Signalement responsable

Ne publiez pas une vulnérabilité sensible avec une preuve d’exploitation ou des secrets dans un relais, une discussion publique ou une issue ouverte. Contactez le mainteneur du dépôt en décrivant l’impact, les versions concernées, les conditions de reproduction et une proposition de correction si possible. Les secrets, clés privées et sauvegardes de test ne doivent jamais accompagner un rapport.
