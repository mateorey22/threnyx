# Prompt court — mise à jour du connecteur Python Hermes × Threnyx

Copiez le bloc suivant dans votre agent Hermes chargé du connecteur Python.

```text
Mets à jour le connecteur Python Hermes Relay pour Threnyx en suivant la documentation officielle Hermes Relay et le guide GitHub Threnyx docs/hermes-relay-connector-guide.md.

Après validation d’un code THX-HERMES1 et envoi de agentAck, récupère le registre réel des commandes Hermes. Si le hello Relay fournit command_manifest, utilise-le ; sinon utilise le registre central de commandes du gateway. Envoie uniquement au pubkey Nostr appairé un message NIP-17 :
{t:"agentManifest",v:1,aid:<grantId>,revision:<monotone>,commands:[{name,description,options?}]}
Ne fabrique pas de commandes et limite le catalogue aux capacités effectivement autorisées pour cet utilisateur.

Quand Hermes émet une action Relay prompt (approval, clarify ou choice), convertis-la en message NIP-17 agentPrompt avec aid, prompt_id opaque, prompt_kind, content, options[{id,label,style?}] et timeout_s. Conserve la correspondance prompt_id → session Hermes et son expiration. Pour un choix de modèle, utilise précisément ce mécanisme prompt afin que Threnyx affiche des boutons.

Quand Threnyx envoie agentPromptResponse, vérifie : signature/event NIP-17, pubkey utilisateur appairé, aid, prompt_id actif, option_id déclarée, expiration et response_id jamais consommé. Convertis ensuite la réponse en prompt_response Hermes ; n’exécute aucune action locale depuis le texte du bouton. Accuse ou réponds au chat normalement.

Toutes les commandes / envoyées par Threnyx, y compris /help, doivent être remises au dispatcher Hermes sans interprétation côté connecteur. Préserve les contrôles Hermes d’autorisation, de session et d’approbation. N’accorde jamais au bot l’accès aux clés privées Threnyx, au coffre local, aux appels WebRTC ou aux conversations humaines non adressées au bot. Ajoute des tests de replay, prompt expiré, mauvais aid, mauvaise pubkey et option inconnue.
```
