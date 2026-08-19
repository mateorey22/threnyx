# Guide de raccordement Hermes Relay pour Threnyx

Cette interface Threnyx prépare un appairage volontaire vers **une identité Nostr de bot dédiée**. Elle ne déploie pas un gateway Hermes ; le connecteur Relay et le gateway doivent être hébergés dans un processus persistant séparé.

## Ce que l’application produit

Dans **Réglages → Agents Hermes / Relay**, l’utilisateur renseigne la clé publique hexadécimale du bot, choisit les permissions médias, puis génère un code `THX-HERMES1`. Le code porte un grant signé BIP-340, limité à dix minutes, pour une seule clé publique bot et un seul utilisateur Nostr.

> Le code n’est pas une clé privée, une phrase secrète de coffre ou un secret `GATEWAY_RELAY_SECRET`. Il autorise seulement le bot désigné à accepter les messages que l’utilisateur lui adresse volontairement.

## Contrôles obligatoires côté connecteur

Le connecteur doit vérifier le préfixe, décoder la charge JSON, rejeter un grant expiré ou déjà consommé, vérifier que `userPub` et `botPub` sont valides, puis vérifier la signature BIP-340 sur SHA-256 de `threnyx/hermes-grant/v1:` concaténé à la chaîne JSON de la charge. Il doit persister l’identifiant de grant et son nonce de façon idempotente pour bloquer tout rejeu.

Après provisionnement, le bot envoie au seul utilisateur appairé un message NIP-17 de forme :

```json
{"t":"agentAck","aid":"<grant id>","nonceHash":"<hash du nonce>"}
```

Threnyx ne passe l’agent à l’état connecté que si cet accusé provient de la clé publique bot attendue et correspond à l’appairage local chiffré.

## Règles de sécurité de déploiement

Le gateway Hermes doit utiliser une instance isolée, une identité bot séparée, des approbations manuelles, aucune liste `allow all`, et un stockage média temporaire chiffré. Le Relay Hermes est expérimental : commencez avec le texte. Images, fichiers et vocaux nécessitent une permission explicite dans Threnyx ; les appels WebRTC restent hors périmètre.

La révocation Threnyx bloque les prochains envois localement et émet `agentRevoke` vers le bot lorsque le réseau le permet. Le connecteur doit aussi supprimer les permissions, sessions et médias temporaires liés à l’appairage.

## Commandes et réponses enrichies

Threnyx transmet les messages commençant par `/` uniquement au bot explicitement appairé. La PWA n’exécute aucune commande Hermes localement. L’interface rend visibles les conventions `/model <nom>`, `/new`, `/reset` et `/status`; leur disponibilité concrète dépend du connecteur Hermes. La commande `/help` affiche l’aide locale Threnyx avant tout envoi.

Les réponses du bot utilisent un sous-ensemble Markdown strict : gras, italique, barré, code en ligne ou en bloc, titres, citations, listes et tableaux. Le texte est toujours échappé comme donnée non fiable avant que Threnyx n’ajoute ses propres balises de présentation. Les liens actifs et tout HTML transmis par l’agent restent du texte inerte afin de réduire le risque de phishing et d’injection XSS.
