# Qualification d’un pilote de session à forward secrecy — Threnyx

**Statut :** conception et qualification uniquement. Ce document ne modifie pas le protocole de messagerie actif et n’autorise aucune communication publique affirmant que Threnyx fournit déjà une forward secrecy ou une post-compromise security.

## Décision de sécurité

Threnyx conserve le transport NIP-17/NIP-44/NIP-59 pour les conversations existantes. NIP-44 indique explicitement qu’il ne fournit pas, à lui seul, de forward secrecy ni de post-compromise security ; il ne doit donc pas être transformé en protocole ratcheté par une dérivation de clé applicative improvisée.[1]

Le candidat de pilote retenu est le **protocole Marmot sur MLS (RFC 9420)**, et non une implémentation maison de Double Ratchet. MLS normalise l’établissement de clés de groupe asynchrone avec forward secrecy et post-compromise security pour des groupes de deux à plusieurs milliers de clients.[2] Le protocole Marmot relie cette couche MLS à l’identité et au transport Nostr.[3]

| Sujet | Décision du pilote | Motif |
|---|---|---|
| Messages existants | Rester en NIP-17/NIP-44/NIP-59 | Aucune migration silencieuse, aucun historique rendu illisible. |
| Bibliothèque candidate | `marmot-ts`, version strictement épinglée | Elle cible Marmot v2, Nostr et des stores fournis par le client.[4] |
| Statut de bibliothèque | Non admissible en production sans revue indépendante | La bibliothèque se déclare elle-même en alpha, susceptible de changements d’API et non auditée.[4] |
| Portée initiale | Groupe MLS de deux **appareils** de test, sans UI utilisateur | La sécurité MLS est attachée aux clients/appareils, pas à une identité partagée entre appareils.[5] |
| Synchronisation Constellation | Exclue de l’état MLS | La copie d’un état ratcheté sur plusieurs appareils peut casser l’indépendance par appareil. |

## Qualification des implémentations observées

| Candidat | Vérification effectuée | Décision |
|---|---|---|
| `marmot-ts` 0.6.0 avec `ts-mls` au commit de sous-module épinglé | Compilation locale réussie après initialisation explicite du sous-module. La suite exécutée a rapporté **564 tests réussis et 1 échec** (`this.peeler.idOf is not a function` dans le scénario de convergence B5). La documentation du projet le qualifie en outre d’alpha et non auditée.[4] | **Non intégré à Threnyx.** Candidat de pilote seulement après une version corrigée, épinglée, et une suite entièrement verte. |
| `2key-ratchet` | Le dépôt indique qu’il n’est plus activement maintenu ; le paquet npm public date de six ans et la documentation réserve son usage à l’expérimentation.[6] | Écarté. |
| `pqc-ratchet` | Projet très récent, sans garantie de stabilité d’API ou de wire format et explicitement non prêt pour la production.[7] | Écarté. |

Ces constats excluent de raccorder aujourd’hui l’une de ces dépendances au chat Threnyx. Ajouter un composant non qualifié à une messagerie active créerait un risque plus grave que de conserver provisoirement le chemin NIP-17, dont les limites sont déjà déclarées.

## Architecture isolée du pilote

Chaque appareil participant crée un matériel MLS distinct et chiffré par le coffre local. La clé Nostr existante sert uniquement à authentifier la publication et la découverte des KeyPackages ; elle ne sert jamais de clé MLS de groupe. Un pilote doit maintenir des stores séparés par appareil : état de groupe MLS, KeyPackages privés, invitations en attente, journal de transition et messages reçus.

> Les KeyPackages permettent une invitation asynchrone ; les Proposals et Commits font évoluer un groupe MLS par époques ; les Welcomes permettent au nouvel appareil d’initialiser son état.[2]

Le pilote transporte les octets Marmot/MLS comme événements Nostr, mais il ne les remet jamais à `MSG.sendText` ni au lecteur NIP-17 existant. Cette séparation protège les conversations actuelles et évite tout repli silencieux : un échange pilote ne peut démarrer que si les deux appareils annoncent explicitement la même version, la même suite cryptographique et les mêmes capacités de stockage.

## Invariants non négociables

| Invariant | Contrôle requis |
|---|---|
| Aucune clé de message ne survit après usage normal | Utiliser la primitive de suppression fournie par la bibliothèque et tester que les sorties consommées ne persistent pas. |
| Pas de réutilisation d’un KeyPackage à usage unique | Réservation transactionnelle IndexedDB avant l’envoi du Welcome ; suppression confirmée ou marquage consommé après réception. |
| Aucune mutation d’état après message invalide | Déchiffrement/validation sur copie, puis commit atomique seulement après succès. |
| Rejeu et messages hors ordre bornés | Identifiant de groupe, époque, empreinte de message et limite stricte de clés/messages différés. |
| État par appareil | Aucun export Constellation de state MLS, KeyPackage privé, exporter secret ou secret de ratchet. |
| Révocation | Retrait de l’appareil du groupe, Commit observé par les membres, nouvel epoch ; la révocation ne retire pas les données déjà reçues. |
| Compatibilité | NIP-17 reste inchangé pour tous les contacts et appareils qui ne participent pas au pilote. |

## Tests de qualification obligatoires

Le pilote ne peut pas être relié à une interface de messagerie avant la réussite documentée des scénarios ci-dessous.

| Famille | Scénarios minimaux | Critère de réussite |
|---|---|---|
| Vecteurs et interopérabilité | Vecteurs RFC 9420 et interopérabilité avec une implémentation Marmot de référence | Même clair, mêmes transitions d’epoch, rejet des octets invalides. |
| Initialisation asynchrone | KeyPackage, Welcome hors ligne, consommation du KeyPackage et rotation | L’invité rejoint une fois ; un Welcome ou KeyPackage rejoué est rejeté. |
| Forward secrecy | Compromettre un état **après** un message ; tenter de déchiffrer l’ancien chiffré avec cet état | Échec du déchiffrement de l’ancien message, sous les hypothèses MLS documentées. |
| Post-compromise security | Simuler une compromission, puis un Commit/Update honnête postérieur | Les messages ultérieurs de l’epoch réparé ne sont plus lisibles par l’état compromis. |
| Anti-rejeu | Rejouer application message, Welcome, Proposal et Commit | Aucun doublon visible et aucune transition d’état secondaire. |
| Désordre / perte | Ordre inversé, messages retardés, messages manquants et limite de différés | État cohérent ou erreur bornée, jamais boucle, épuisement mémoire ou corruption. |
| Crash | Arrêt entre préparation, stockage et publication ; redémarrage | L’appareil retrouve soit l’ancien état intact, soit le nouvel état complet, jamais un hybride. |
| Multi-appareil | Deux appareils d’une même personne, retrait d’un appareil, reprise réseau | États matériels distincts ; retrait effectif pour les nouveaux messages. |
| Attaques d’entrée | Taille excessive, epoch invalide, signature/encodage invalide, métadonnées contradictoires | Rejet avant mutation persistante et journal de diagnostic non sensible. |

## Règles de mise en production

La migration pourra être proposée à un groupe volontaire seulement lorsque : la dépendance est épinglée et revue ; les tests ci-dessus sont automatisés ; les stores IndexedDB sont chiffrés par le coffre local ; une revue indépendante est réalisée ; la restauration après crash et la révocation sont testées sur appareils réels ; et un mécanisme de retour aux conversations NIP-17 est proposé uniquement **avant** la création d’un groupe pilote, jamais au milieu d’une session MLS.

## Références

[1] [NIP-44 — Encrypted Payloads (Versioned)](https://nips.nostr.com/44)

[2] [RFC 9420 — The Messaging Layer Security Protocol](https://datatracker.ietf.org/doc/rfc9420/)

[3] [Marmot Protocol — specification](https://github.com/marmot-protocol/marmot)

[4] [marmot-ts — TypeScript implementation and security disclaimer](https://github.com/marmot-protocol/marmot-ts)

[5] [NIP-EE — MLS clients, groups and multi-device model](https://nips.nostr.com/ee)

[6] [2key-ratchet — maintenance and security warning](https://github.com/PeculiarVentures/2key-ratchet)

[7] [pqc-ratchet — v0 stability notice](https://github.com/PeculiarVentures/pqc-ratchet)
