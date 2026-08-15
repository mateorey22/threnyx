# Évaluation Nostr standardisée et convergence CRDT — Threnyx

## État livré dans la PWA v17

Threnyx utilise désormais **NIP-17** pour les nouveaux messages persistants. Cette construction standard associe une rumeur de kind 14, le chiffrement versionné de **NIP-44 v2**, un seal, puis un gift wrap de kind 1059 selon **NIP-59**. Le lecteur conserve le format chiffré historique en repli : les conversations existantes ne sont donc pas rendues illisibles par la mise à niveau. Les primitives `nip44` et `nip59` de `nostr-tools` 2.24.1 sont embarquées localement dans le script protégé par CSP ; aucun CDN ou script cryptographique distant n’est requis au moment de l’utilisation.[1] [2] [3] [4]

L’envoi ne bascule pas aveuglément vers NIP-17. Les profils et messages `hello` des appareils v17 annoncent la capacité `nip17` en plus de `legacy`, dans des champs optionnels ignorables par les appareils précédents. Tant qu’un contact n’a pas annoncé `nip17`, Threnyx conserve l’enveloppe historique ; après une annonce réciproque, les nouveaux messages persistants utilisent NIP-17. Cette négociation progressive protège les contacts existants contre une migration unilatérale.

| Élément | Comportement v17 | Limite à connaître |
|---|---|---|
| Nouveaux messages persistants | Écriture NIP-17/NIP-44/NIP-59 lorsque les primitives sont disponibles | L’interopérabilité dépend aussi des relais et clients du correspondant. |
| Historique existant | Lecture du format historique conservée après tentative NIP-17 | Le format historique reste moins interopérable ; il ne doit plus être retenu pour de nouvelles fonctions. |
| Manifestes et fragments Constellation | Événements Nostr signés, puis contenus chiffrés et réplication sur plusieurs relais | La disponibilité dépend du quorum de relais et de la conservation de leurs données. |
| Exécution des dépendances | Bundles locaux dans le script couvert par un hash CSP | Une mise à jour de code impose de recalculer ce hash et de versionner le cache PWA. |

## Confidentialité persistante et MLS

NIP-44 et NIP-17 ne fournissent pas de **forward secrecy**. Si la clé d’identité ou le matériau de conversation correspondant est compromis ultérieurement, des messages historiques chiffrés avec ce matériau peuvent être exposés. Threnyx ne prétend donc pas offrir de confidentialité persistante ou de post-compromise security.

NIP-EE décrit une direction fondée sur MLS, mais sa spécification officielle est signalée *unrecommended* et renvoie vers le Marmot Protocol. Aucune implémentation MLS/Marmot JavaScript, navigateur, interopérable et suffisamment mature n’a été intégrée dans cette PWA autonome. Une telle migration ne devra être envisagée qu’avec revue cryptographique, gestion explicite de l’état de groupe et essais sur plusieurs appareils.[5]

## Convergence Constellation par Yjs

La version 17 intègre **Yjs 13.6.32** sous forme de bundle local minifié d’environ **94 Ko**. Le choix de Yjs évite le bundle WebAssembly d’Automerge mesuré à environ 4,8 Mo dans cette architecture, tout en apportant une convergence CRDT déterministe et indépendante du transport. Yjs ne décide pas du réseau : les updates binaires produits localement sont inclus dans le snapshot Constellation, puis chiffrés et publiés avec les fragments existants. Les relais ne reçoivent donc pas un document CRDT lisible.[6] [7]

Lors d’une récupération NFC, Threnyx lit maintenant jusqu’à quatre manifestes distincts, télécharge les snapshots complets vérifiés, puis applique les updates Yjs de toutes les branches compatibles. Cette fusion concerne les contacts, groupes et préférences ; elle n’exige pas de serveur central et tolère l’arrivée des branches dans un ordre différent. Un test navigateur a confirmé la fusion d’un contact et d’un groupe créés sur deux branches concurrentes, avec un update final Yjs exploitable.

Le test d’intégration local v18 couvre également le chemin de stockage : deux snapshots concurrents sont encodés avec Yjs, chiffrés par dérivation distincte de fragment, signés comme événements Nostr kind 78, vérifiés, relus avec `readBundle`, puis fusionnés. Il ne remplace pas une revalidation complète avec un tag NFC physique et plusieurs relais publics ; cette dernière reste un contrôle à effectuer avant d’élargir la promesse de récupération multi-branches.

| Donnée | Politique v17 | Raisonnement |
|---|---|---|
| Contacts et groupes | Fusion CRDT Yjs par identifiant | Évite d’écraser les ajouts indépendants faits hors ligne. |
| Préférences | Valeur concurrente déterministe du CRDT pour une même clé | Deux valeurs différentes pour exactement la même préférence ne sont pas sémantiquement fusionnables. |
| Messages, statuts, appels, invitations | Provenance du snapshot principal ; pas de fusion CRDT automatique | Ces objets restent immuables ou comportent des règles métier et de rétention qui exigent une migration distincte. |
| Suppressions et médias | Hors périmètre de la fusion CRDT actuelle | Une suppression distribuée et la gestion des blobs nécessitent des tombstones et une politique de rétention explicitement auditée. |
| Snapshots antérieurs à v17 | Restauration du snapshot principal valide | Ils n’ont pas d’update Yjs ; la fusion est réservée aux branches v17 compatibles. |

## Garanties et limites opérationnelles

La réplication Constellation n’est pas une sauvegarde automatique invisible ni un stockage « chez tout le monde ». Un utilisateur doit déclencher un snapshot ; celui-ci est chiffré côté navigateur, fragmenté et envoyé à plusieurs relais Nostr configurés. La clé NFC TCV1 sert uniquement à récupérer le matériau Constellation puis à retrouver les snapshots : toute personne qui obtient cette clé physique peut tenter la récupération. Elle doit donc être conservée comme une clé de coffre, séparément du téléphone.

La sélection de branches est bornée à quatre manifestes afin de limiter la charge de récupération. Chaque événement est vérifié cryptographiquement, chaque fragment est déchiffré avec une dérivation dédiée, et le digest complet est contrôlé avant toute restauration. Ces contrôles limitent les corruptions et les substitutions, mais ne transforment pas les relais en stockage durable garanti.

## Références

[1]: https://nips.nostr.com/17 "NIP-17 — Private Direct Messages"
[2]: https://nips.nostr.com/44 "NIP-44 — Encrypted Payloads"
[3]: https://nips.nostr.com/59 "NIP-59 — Gift Wrap"
[4]: https://jsr.io/@nostr/tools/doc/nip59 "nostr-tools nip59 API"
[5]: https://nips.nostr.com/ee "NIP-EE — Encrypted Events"
[6]: https://docs.yjs.dev/ "Yjs documentation"
[7]: https://docs.yjs.dev/api/document-updates "Yjs document updates"
