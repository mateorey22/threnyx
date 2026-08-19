# Notes de sécurité et limites du connecteur

Le répertoire contient un **connecteur Python externe** ; il ne fait pas partie du fichier `index.html`, du service worker ou des fichiers servis par GitHub Pages. GitHub héberge le code source, mais n’exécute pas ce processus.

## Contrôles inclus

| Sujet | Contrôle présent |
| --- | --- |
| Appairage | `THX-HERMES1`, signature BIP-340, clé bot attendue, expiration et permissions minimales. |
| Rejeu du grant | Index durable atomique de l’identifiant de grant et du hash de nonce sous `state/grants.json`, permissions `0600`. |
| Messages | Vérification de signature, destinataire bot, déduplication en mémoire et refus des expéditeurs non appairés. |
| Actions UI | `agentPrompt` / `agentPromptAck` versionnés `v:1`, option déclarée, expiration et `response_id` unique par prompt. |
| Révocation | Suppression des permissions, du contexte local et des médias temporaires. |

## Limites à connaître

Le bridge livré appelle une API HTTP compatible OpenAI à l’adresse configurée. Il **n’est pas** un connecteur WebSocket Hermes Relay officiel complet ; l’adaptateur qui convertit un `prompt_response` vers le dispatcher Hermes doit être finalisé et testé par l’opérateur du gateway avant de présenter un choix comme exécutable.

Le code déchiffre les messages NIP-17 reçus, mais ses réponses opérationnelles utilisent encore le repli legacy Threnyx afin de rester compatible avec les contacts dont la négociation NIP-17 n’est pas attestée. Il ne faut pas annoncer une interopérabilité NIP-17 sortante complète avant les tests croisés avec le connector et le bot réels.

Le `MediaStore` chiffre les fichiers temporaires mais son index et ses clés restent en mémoire. Après un redémarrage, les médias antérieurs doivent échouer fermement plutôt que de devenir accessibles. Les échanges média de bout en bout ne sont pas encore routés par `connector.py` : gardez images, fichiers et vocaux désactivés dans l’appairage jusqu’à l’implémentation et aux tests dédiés.

## Déploiement attendu

Exécutez ce connecteur sur une machine contrôlée qui reste disponible, avec un compte système dédié et un répertoire de travail à permissions restreintes. Conservez les clés privées et `config.json` hors du dépôt. Le chemin d’état doit être sauvegardé de manière chiffrée et accessible uniquement au processus du connecteur.
