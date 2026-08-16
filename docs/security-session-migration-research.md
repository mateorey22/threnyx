# Recherche initiale — migration de session Threnyx

## Conclusion provisoire

Le chiffrement NIP-17/NIP-44/NIP-59 actuellement utilisé par Threnyx standardise l’enveloppe et masque une partie des métadonnées de routage, mais il ne fournit pas à lui seul la **forward secrecy** ni la **post-compromise security**. La documentation Nostr consacrée à MLS l’indique explicitement et décrit NIP-EE comme une proposition désormais marquée *unrecommended*, renvoyant vers Marmot Protocol. Il serait donc imprudent de remplacer le transport courant par une implémentation protocolaire faite maison.

Le Double Ratchet de Signal répond aux propriétés demandées pour une session à deux participants : chaînes symétriques à clé de message unique, ratchet Diffie-Hellman, root key, en-têtes avec compteurs, et cache strictement borné de clés sautées. Mais son déploiement asynchrone dépend d’un handshake de type X3DH/PQXDH avec clés d’identité, signed prekeys, one-time prekeys, suppression atomique et persistance transactionnelle de l’état. Ces propriétés imposent une conception et une suite de tests avant tout changement de messages dans Threnyx.

MLS est le candidat conceptuel le plus adapté aux groupes et au multi-appareil, et OpenMLS documente une compilation WebAssembly possible dans un navigateur. Cette voie reste un chantier d’intégration à évaluer : elle requiert une enveloppe WASM, une stratégie de stockage d’état MLS chiffré, la résolution des courses sur les commits et un audit de l’interopérabilité Nostr. Elle n’est pas intégrée à la PWA à ce stade.

La recherche a également identifié **Marmot-TS**, qui se présente comme une implémentation TypeScript de Marmot v2 (MLS sur Nostr). Sa documentation confirme une architecture enfichable, avec stockage et réseau fournis par le client ; la production navigateur doit donc fournir ses propres adaptateurs IndexedDB et Nostr. Cela le rend plus pertinent qu’un Double Ratchet maison pour un éventuel pilote, mais signifie aussi qu’un changement sûr ne se limite pas à ajouter une dépendance : les transitions MLS, KeyPackages, Welcomes, persistance chiffrée et résolution de fork doivent être intégrées et testées comme un sous-système complet.

## Décision de sécurité

1. Aucun message existant ne sera automatiquement basculé vers un protocole ratcheté.
2. Aucune mention de forward secrecy, post-compromise security ou Double Ratchet actif ne sera ajoutée à la PWA ou à la landing avant une implémentation auditée et des tests de propriétés réussis.
3. Le chemin NIP-17 existant reste le format moderne standardisé pour les messages persistants compatibles ; le format historique reste un repli explicitement versionné pour les anciens contacts.
4. Toute éventuelle migration devra être introduite sous une version de protocole distincte et un opt-in de capacité réciproque, sans repli silencieux après un échec de négociation moderne.

## Sources consultées

1. Signal, « The Double Ratchet Algorithm », révision 4, 2025-11-04 — https://signal.org/docs/specifications/doubleratchet/
2. Signal, « The X3DH Key Agreement Protocol » — https://signal.org/docs/specifications/x3dh/
3. Nostr, « NIP-EE: E2EE Messaging using MLS » — https://nips.nostr.com/ee
4. OpenMLS Book, « WebAssembly » — https://book.openmls.tech/user_manual/wasm.html
5. Marmot-TS, « Getting Started » — https://marmot-protocol.github.io/marmot-ts/getting-started.html
