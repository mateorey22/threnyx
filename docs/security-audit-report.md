# Rapport d’audit de sécurité — Threnyx

**Périmètre :** PWA statique `index.html`, service worker, manifeste, mécanismes Nostr/WebRTC/NFC/Constellation, coffre local et documentation publiés jusqu’à la révision PWA v24. Ce rapport est une revue d’architecture et de code statique ; il ne remplace pas un audit indépendant du navigateur, une revue de cryptographie formelle ou un test matériel exhaustif.

## Synthèse

| Niveau | État | Élément |
|---|---|---|
| Critique | Ouvert | Les conversations n’emploient pas encore de protocole ratcheté démontré ; aucune forward secrecy ni post-compromise security ne peut être revendiquée. |
| Élevé | Ouvert | Une migration multi-appareil et préclés/MLS doit gérer l’état de session, les courses, la récupération après crash et la révocation avant activation. |
| Élevé | Réduit | Les entrées Nostr sont vérifiées et le lecteur NIP-17 contrôle signature, kind et destinataire avant routage. |
| Moyen | Réduit | Coffre local Argon2id, WebAuthn PRF facultatif, verrouillage et wipe local sont intégrés ; une compromission d’appareil déverrouillé reste grave. |
| Moyen | Ouvert | CSP `style-src 'unsafe-inline'` demeure nécessaire au rendu single-file actuel ; le CSP des scripts reste hashé et ne permet ni `unsafe-inline` ni `unsafe-eval`. |
| Moyen | Réduit | Caches de service worker versionnés et suppression des anciens caches Threnyx à l’activation. |
| Moyen | Ouvert | Les essais sur appareils Android/iOS de la biométrie, de la flamme, du code de détresse et du WebRTC doivent être conservés comme validations manuelles. |
| Faible | Réduit | Les objets d’erreur de démarrage ne sont plus transmis à `console.error`; seul un marqueur générique demeure. |

## Remédiations effectivement appliquées

| Domaine | Mesure publiée | Vérification disponible |
|---|---|---|
| Messagerie Nostr | NIP-17/NIP-44 v2/NIP-59, vérification de signature et contrôles de format avant routage. | `tests/security-baseline.test.mjs` et chemin `Nostr.unwrapNip17`. |
| Changement de clé | Alerte locale, invalidation du statut vérifié et fingerprint hors-bande. | Objet contact et `KeyGuard.profile`. |
| Coffre | Argon2id versionné, chiffrement AES-GCM, assistance WebAuthn PRF, limite d’échecs et wipe local. | Module `Vault`, test de base de présence Argon2id. |
| Chaîne de livraison | CSP de script par hash, aucun script HTML externe, `object-src/base-uri/form-action/frame-ancestors` verrouillés. | `tests/security-baseline.test.mjs`. |
| Service worker | Cache `threnyx-pwa-v23`, suppression des caches Threnyx plus anciens à l’activation. | `service-worker.js`, test de base. |
| Constellation / NFC | Manifestes signés, fragments chiffrés, vérification de kind, protection rollback et réauthentification avant export NFC. | `constellation-vault-architecture.md` et tests historiques associés. |
| Appels | Pistes distantes attachées au flux négocié, redémarrage ICE traité et compteurs RTP locaux pour diagnostic. | `tests/v21-controls-webrtc.test.mjs`. |
| Logs | Suppression de l’objet d’erreur du journal de démarrage. | `tests/security-baseline.test.mjs`. |

## Risques restants et conditions de fermeture

| Risque | Impact | Condition de fermeture |
|---|---|---|
| Absence de session ratchetée | Compromission d’identité/clé de conversation peut exposer des échanges NIP-17. | Intégrer une bibliothèque de session maintenue, tests forward secrecy et post-compromise security, revue externe. |
| Prekeys, ratchet et anti-rejeu de session absents | Pas de handshake asynchrone ni de clés par message démontrés. | Concevoir et tester persistance atomique, prekeys à usage unique, skipped keys bornées, AD et anti-rejeu par session. |
| Multi-appareil | Une copie d’état de session pourrait invalider l’indépendance par appareil. | Matériel cryptographique distinct par appareil et gestion MLS/ratchet par appareil. |
| GC1 concurrent | Quota strictement atomique et validation multi-appareil non finalisés. | Test multi-client/relais et mécanisme de réservation/consommation résistant aux courses. |
| Style inline CSP | Une injection CSS est moins contrainte que les scripts. | Extraire styles et attributs inline, introduire hashes/nonces appropriés, puis supprimer `style-src 'unsafe-inline'`. |
| Appareil compromis | Le coffre ouvert, le navigateur et la mémoire JS peuvent être attaqués. | Risque structurel du modèle web ; réduire la fenêtre de déverrouillage et renforcer les consignes utilisateur. |
| Métadonnées réseau | Relais et WebRTC peuvent voir du trafic, volume, timing et parfois IP/candidates. | Pas d’élimination complète dans ce modèle ; documenter et fournir TURN/VPN selon les besoins. |
| NFC clonable | Un tag NDEF classique peut être copié ou remplacé. | Utiliser un matériel sécurisé pour une garantie matérielle ; ne pas annoncer cette garantie avec un tag standard. |

## Conclusion de publication

Les remédiations de coffre, CSP de scripts, vérification d’événements, service worker, diagnostics WebRTC, NIP-17 et documentation réduisent des risques identifiés. Elles ne transforment pas le protocole de messagerie actuel en Signal/Double Ratchet ou MLS. La prochaine migration ne doit être engagée qu’après pilote isolé, tests de propriétés, analyse de persistance et revue de sécurité dédiée.
