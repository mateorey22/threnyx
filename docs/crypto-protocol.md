# Conception de migration cryptographique — Threnyx

## 1. Objet et statut

Ce document décrit une **cible de migration**, non un protocole actuellement activé. Il a pour objectif de rendre une évaluation externe possible avant tout changement des conversations. Les formats actifs restent : `legacy` pour les contacts plus anciens et `nip17` pour les contacts qui annoncent mutuellement la capacité NIP-17.

Une future version `session-v3` ne sera annoncée comme offrant forward secrecy ou post-compromise security que si elle s’appuie sur une implémentation maintenue, que son état persistant est audité et que les tests décrits à la section 8 passent de manière automatique.

## 2. Décision d’architecture

| Besoin | Décision de conception | Raison |
|---|---|---|
| Conversations legacy | Lecture uniquement, marquage explicite `legacy`. | Ne pas casser l’historique et ne pas prétendre moderniser rétroactivement les anciens messages. |
| Conversations NIP-17 | Continuer en `nip17` tant que `session-v3` n’est pas validé. | Format Nostr standardisé, rétrocompatibilité déjà déployée. |
| Session moderne 1:1 | Évaluer une bibliothèque maintenue de protocole ratcheté plutôt que coder Double Ratchet dans la PWA. | Les invariants de ratchet, rollback d’état, skipped keys et préclés sont trop sensibles pour une implémentation improvisée. |
| Groupes et multi-appareil | Évaluer Marmot-TS / MLS avec stockage IndexedDB chiffré et Nostr comme distribution. | MLS cible les groupes, epochs et appareils comme membres distincts ; Marmot-TS indique des adaptateurs de stockage et réseau enfichables. |
| Transport | Nostr et WebRTC demeurent des transports non fiables. | La validité doit être imposée au niveau cryptographique, jamais par un relais ou l’ordre d’arrivée. |

## 3. Versionnement et négociation

Les capacités des contacts doivent annoncer des identifiants de protocole explicites. La réception doit refuser toute ambiguïté et ne jamais deviner un format.

| Version | Statut | Comportement |
|---|---|---|
| `legacy` | Actif, compatibilité | Déchiffrement du format historique uniquement pour les conversations qui l’utilisent déjà. |
| `nip17` | Actif, standardisé | Envoi après capacité réciproque ; NIP-44 v2 + NIP-59, lecteur legacy conservé. |
| `session-v3` | Conception seulement | Aucun envoi avant disponibilité réciproque, prekeys valides, état local chiffré et tests de propriétés validés. |

Un échec de `session-v3` ne doit pas provoquer un repli silencieux vers `legacy`. L’interface doit indiquer qu’une conversation existante est en ancien protocole, en protocole NIP-17 ou en session moderne validée.

## 4. Exigences d’une session ratchetée

Un éventuel protocole `session-v3` doit déléguer les primitives à une bibliothèque auditée et maintenir les invariants suivants :

1. Une clé de message distincte par envoi, supprimée dès emploi.
2. Une root key, une chaîne d’envoi et une chaîne de réception évolutives.
3. Un mécanisme DH ratchet effectif qui introduit une nouvelle entropie après compromission temporaire.
4. Des en-têtes authentifiés contenant identifiant opaque de session, clé de ratchet publique et compteurs.
5. L’Associated Data doit lier le protocole, les deux identités, l’appareil émetteur, l’appareil destinataire, l’identifiant de session, la direction et l’en-tête encodé de façon non ambiguë.
6. Une limite stricte de clés sautées et une persistance transactionnelle : aucun ratchet ne doit avancer définitivement si l’AEAD échoue.
7. Une protection anti-rejeu et anti-duplication locale par identifiant de session et compteur, distincte de l’anti-doublon d’événement Nostr.
8. La destruction des prekeys à usage unique après consommation réussie, avec récupération sûre après crash.

## 5. Handshake asynchrone et appareils

Le handshake doit séparer les rôles cryptographiques : identité de long terme, signed prekey à rotation, one-time prekeys, clé éphémère, matériel de session et clé de ratchet. Une préclé à usage unique doit être marquée réservée dans une transaction IndexedDB avant livraison, puis consommée ou libérée selon le résultat de traitement. Un relais ne doit jamais être considéré comme l’autorité de consommation.

Chaque appareil possède ses propres clés et ses propres sessions. Une restauration Constellation n’autorise pas la copie brute d’un état de ratchet sur plusieurs appareils : elle doit rétablir l’appareil comme membre distinct, puis négocier ses propres sessions ou rejoindre le groupe MLS avec son propre matériel cryptographique.

## 6. Stockage et récupération

L’état de session, les prekeys privées, les chain keys et les skipped keys doivent être chiffrés au repos par le coffre local et dissociés de la clé Nostr d’identité. Aucun de ces secrets ne doit entrer dans localStorage, Cache Storage, URLs, logs ou sauvegardes Constellation non chiffrées. Les clés sautées seront bornées et expireront selon des limites conservatrices documentées avant implémentation.

La récupération NFC ne peut pas être considérée comme une sauvegarde de forward secrecy : un tag NDEF reste clonable et l’état de session restauré doit être traité comme nécessitant une renégociation. Les artefacts publics Nostr restent des données hostiles jusqu’à vérification cryptographique et contrôle de taille.

## 7. Métadonnées et réseau

Nostr distribue des événements mais n’est pas une autorité de confiance. WebRTC chiffre le média, sans assurer l’anonymat réseau. Le protocole de session doit limiter les informations d’en-tête exposées aux transports, tandis que l’interface doit continuer d’avertir l’utilisateur que les relais, le rythme de trafic, les tailles, les adresses IP/candidates et l’activité peuvent révéler des métadonnées.

## 8. Barrière de tests avant activation

| Test de propriété | Résultat requis |
|---|---|
| AEAD et Associated Data modifiés | Échec de déchiffrement sans mutation d’état. |
| Clé de message unique | Deux envois produisent des clés et chiffres distincts. |
| Rejeu et doublon | Le même message ne s’affiche et ne fait avancer l’état qu’une seule fois. |
| Réordonnancement / pertes | Les messages dans la fenêtre de skipped keys sont déchiffrables une fois et l’état reste cohérent. |
| Limite de skipped keys | Un écart excessif est rejeté avant allocation ou calcul non borné. |
| Compromission actuelle | Les clés passées ne sont pas dérivables depuis l’état courant. |
| Récupération post-compromission | Après une étape de ratchet DH fraîche, les nouvelles clés sont inconnues de l’attaquant ayant observé un état temporaire. |
| Changement d’identité | La session est invalidée et l’interface signale l’état non vérifié. |
| Crash pendant handshake ou réception | Aucune prekey n’est réutilisée et aucun état partiel n’est accepté. |
| Événement relais hostile | Donnée malformée, oversized, injectée ou retardée rejetée sans fuite ni progression d’état. |

## 9. Déploiement progressif

1. Publier les documents, tests de base et l’inventaire sans changer la cryptographie active.
2. Construire un pilote isolé avec une bibliothèque maintenue, adaptateur IndexedDB chiffré et faux transport contrôlé.
3. Faire auditer le format, les propriétés, la migration et la gestion multi-appareil.
4. Introduire `session-v3` en opt-in pour nouveaux contacts de test, sans conversion des historiques.
5. Activer par défaut uniquement après tests de non-régression, revue externe et documentation des limites restantes.

## Références

1. Signal, [The Double Ratchet Algorithm](https://signal.org/docs/specifications/doubleratchet/).
2. Signal, [The X3DH Key Agreement Protocol](https://signal.org/docs/specifications/x3dh/).
3. Nostr, [NIP-EE: E2EE Messaging using MLS](https://nips.nostr.com/ee) — marqué *unrecommended* et remplacé par Marmot.
4. Marmot-TS, [Getting Started](https://marmot-protocol.github.io/marmot-ts/getting-started.html).
5. OpenMLS Book, [WebAssembly](https://book.openmls.tech/user_manual/wasm.html).
