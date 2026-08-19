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

## 9. Synchronisation d’interface `THX-HERMES-UI1`

Le connecteur ne maintient pas une seconde liste de commandes propre à Threnyx. Il lit le registre Hermes — le `command_manifest` Relay lorsqu’il est fourni au handshake, ou le registre de commandes du gateway — puis transmet le catalogue filtré au seul appairage concerné, dans un message NIP-17 signé par la clé bot.

```json
{
  "t": "agentManifest",
  "v": 1,
  "aid": "<id THX-HERMES1>",
  "revision": 1,
  "commands": [
    {"name": "model", "description": "Afficher ou changer le modèle", "options": [{"name": "name"}]},
    {"name": "new", "description": "Démarrer une nouvelle session"}
  ]
}
```

Threnyx limite le catalogue à 60 commandes et n’accepte que des noms courts `[a-z][a-z0-9_-]`. Tant qu’aucun manifeste n’a été reçu, l’interface affiche un petit jeu de commandes Hermes conventionnelles et indique qu’il n’est pas encore synchronisé. Toute commande, **y compris `/help`**, est transmise au bot ; Threnyx n’interprète ni la commande ni ses arguments.

## 10. Boutons, choix de modèle et confirmations

Le Relay Hermes définit une opération abstraite `prompt` pour les clarifications, confirmations et choix. Le connecteur Threnyx doit convertir cette opération en un message NIP-17 `agentPrompt` :

```json
{
  "t": "agentPrompt",
  "v": 1,
  "aid": "<id THX-HERMES1>",
  "prompt_id": "<id opaque Hermes>",
  "prompt_kind": "choice",
  "content": "Choisir le modèle pour cette session",
  "options": [
    {"id": "fast", "label": "Rapide", "style": "primary"},
    {"id": "reasoning", "label": "Raisonnement", "style": "secondary"}
  ],
  "timeout_s": 300
}
```

Threnyx affiche les options sous forme de boutons dans le chat agent. Lors d’une pression, il émet `agentPromptResponse` avec `aid`, `prompt_id`, `option_id`, un `response_id` aléatoire et l’horodatage. Le connecteur doit vérifier la clé Nostr de l’émetteur, l’appairage, l’expiration, l’option et l’unicité de `response_id`, puis convertir le choix en `prompt_response` Hermes. Un bouton n’a jamais accès au coffre, aux réglages locaux, aux clés privées ou aux appels WebRTC.

> Hermes Relay est expérimental : le connecteur doit annoncer seulement les capacités effectivement reçues au handshake. Lorsqu’un prompt ou un manifeste n’est pas disponible, il faut conserver le repli texte et ne pas inventer une interaction.
