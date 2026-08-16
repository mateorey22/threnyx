# Inventaire traçable des contrôles de sécurité — Threnyx

**Version de l’inventaire :** août 2026. Ce document fait la correspondance entre les demandes de sécurité exprimées pour Threnyx, l’état observé dans le dépôt et les contrôles qui restent ouverts. Il ne remplace pas un audit indépendant.

| Contrôle demandé | État réel | Preuve de code ou de test | Limite et suite à faire |
|---|---|---|---|
| Formats Nostr standardisés | **Actif.** Les nouveaux messages persistants emploient NIP-17 avec NIP-44 v2 et NIP-59 ; l’ancien chemin demeure un repli versionné. | `index.html`, `tests/security-baseline.test.mjs`, `docs/crypto-protocol.md` | NIP-44/NIP-59 n’apportent pas seuls forward secrecy ni post-compromise security. |
| Forward secrecy | **Non active.** | `docs/security-session-migration-research.md`, `docs/session-pilot-qualification.md`, `tests/session-pilot-guard.test.mjs` | Le pilote MLS/Marmot reste bloqué tant qu’une version épinglée corrigée, une suite entièrement verte et une revue indépendante ne sont pas disponibles. |
| Post-compromise security | **Non active.** | `docs/security-session-migration-research.md`, `docs/session-pilot-qualification.md`, `tests/session-pilot-guard.test.mjs` | Même condition de qualification que la forward secrecy ; ne pas la présenter comme active. |
| Session ratchetée sans crypto maison | **Protégée par un garde-fou.** Aucune migration silencieuse des chats n’est autorisée. | `docs/session-pilot-qualification.md`, `tests/session-pilot-guard.test.mjs` | Le pilote futur doit traiter préclés/KeyPackages, anti-rejeu, crash, révocation et appareils distincts. |
| Coffre local résistant au bruteforce | **Actif.** Les coffres récents utilisent Argon2id ; PBKDF2 est limité à la migration des anciens formats. | `docs/security-architecture-map.md`, `tests/security-baseline.test.mjs` | Un appareil déverrouillé ou compromis reste un risque de point terminal. |
| Déverrouillage biométrique | **Actif lorsque configuré.** WebAuthn PRF protège l’accès local et le parcours tente la biométrie au démarrage. | `index.html`, `tests/v21-controls-webrtc.test.mjs` | Validation Android/iOS avec chaque authenticator et secours manuel à maintenir. |
| Code de détresse | **Actif.** Un hash séparé peut déclencher l’effacement local depuis l’écran verrouillé. | `index.html`, `tests/security-baseline.test.mjs`, `docs/security-audit-report.md` | Efface les données locales ; ne rétracte pas les données ou copies déjà reçues par des tiers. |
| Wipe par flamme | **Actif mais désactivé par défaut.** | `index.html`, `tests/v21-controls-webrtc.test.mjs` | Action irréversible sur l’appareil ; doit rester opt-in et explicitement confirmée. |
| Vérification de fingerprint de contact | **Active.** Le badge de vérification devient invalide si la clé du contact change. | `index.html`, `docs/security-audit-report.md` | Une comparaison hors-bande reste nécessaire pour contrer une substitution initiale de clé. |
| Alerte clé modifiée | **Active localement.** | `index.html`, `docs/security-architecture-map.md` | Ne prouve pas qu’une nouvelle clé est légitime ; elle alerte seulement sur le changement. |
| Limitation d’essais du coffre | **Active.** Les échecs augmentent le délai de tentative. | `index.html`, `tests/security-baseline.test.mjs` | Ne protège pas contre un attaquant qui contrôle déjà l’environnement d’exécution. |
| Verrouillage automatique raisonnable | **Actif avec délai et protection par interaction**, plutôt qu’au moindre changement de focus, afin de ne pas interrompre un choix de média. | `index.html`, `docs/security-audit-report.md` | Le compromis d’expérience doit être revalidé sur Android ; une PWA n’a pas les garanties d’un verrou natif. |
| CSP et intégrité du script | **Active.** CSP à hash, `connect-src 'self' wss: blob:` et test de correspondance du hash. | `index.html`, `tests/security-baseline.test.mjs`, `docs/security-audit-report.md` | `'unsafe-inline'` pour les styles reste une dette documentée ; la chaîne GitHub Pages demeure dans le modèle de menace. |
| Régression PWA/cache | **Corrigée en v26.** Le cache est versionné et le hash du script est contrôlé avant publication. | `service-worker.js`, `tests/security-baseline.test.mjs` | Les mises à jour demandent encore une connexion et l’activation du service worker par le navigateur. |
| Constellation et conflits hors ligne | **Actif pour contacts, groupes et préférences compatibles.** Yjs fusionne les branches prévues. | `index.html`, `docs/security-architecture-map.md` | Messages, suppressions, appels et gros médias ne sont pas fusionnés par Yjs. |
| Restauration NFC Constellation | **Active.** Le tag TCV1 aide à retrouver puis vérifier un snapshot chiffré. | `index.html`, `tests/gc1-format.test.mjs`, `docs/security-architecture-map.md` | Un tag NDEF classique est clonable ; il doit être protégé comme une clé sensible. |
| Invitations de groupe GC1 | **Active.** Format séparé avec quota, expiration, révocation et accusés. | `index.html`, `tests/gc1-format.test.mjs` | Les quotas concurrents multi-client nécessitent encore une validation sur appareils réels. |
| Appels WebRTC | **Actif avec signalisation Nostr et diagnostic local.** | `index.html`, `tests/v21-controls-webrtc.test.mjs` | Les pairs et l’infrastructure STUN/TURN peuvent voir des métadonnées réseau ; la disponibilité dépend du réseau. |

## Décision de communication publique

La landing et la fiche `llms.txt` peuvent mettre en avant les formats NIP-17, NIP-44 v2, NIP-59, le coffre local, le fingerprint, les contrôles de détresse et les limites de Constellation. Elles doivent continuer à exclure toute promesse de forward secrecy, de post-compromise security, d’anonymat total, de retrait de données déjà livrées ou de disponibilité permanente.

## Contrôles à conserver ouverts

La qualification d’un véritable protocole de sessions reste le principal chantier cryptographique. Elle doit démarrer seulement avec une dépendance corrigée et revue, puis être validée par les tests de propriété définis dans `docs/session-pilot-qualification.md`. Les validations physiques NFC/biométrie, les quotas GC1 sous concurrence et les scénarios de récupération CRDT sur plusieurs relais restent également à effectuer sur appareils réels.
