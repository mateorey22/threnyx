# Recherche — commandes et interactions Hermes pour Threnyx

Date de vérification : 19 août 2026.

## Constats officiels

Hermes construit automatiquement le menu Telegram à partir d’un registre central de commandes et des commandes éligibles de plugins ou skills. Le menu est plafonné à 60 commandes par défaut, même si Telegram peut en accepter 100. Les commandes et leur priorité sont donc des **capacités déclarées par le gateway**, pas une liste figée dans le client [1].

La documentation Hermes liste notamment `/new`, `/reset`, `/model`, `/status`, `/whoami`, `/approve`, `/deny`, `/sessions`, `/reasoning`, `/voice`, `/background` et `/help`. Un choix `/model` reste associé à la session après un redémarrage, tandis que `/new` et `/reset` effacent ce choix de session [2].

Hermes Relay est expérimental et négocie les capacités d’un connecteur pendant le handshake. Les capacités explicitement décrites sont les médias, les demandes natives d’approbation ou de clarification, les réactions, les fils, l’indicateur de saisie et le streaming [2]. La documentation ne définit pas de frame publique séparée pour un clavier de boutons généraliste dans le Relay.

Hermes sait toutefois rendre une clarification avec choix unique ou multiple sous forme de boutons natifs lorsque la plateforme le permet ; la réponse doit rester possible sous forme de texte ou numéro afin de conserver un repli accessible [2].

## Conséquence pour Threnyx

Threnyx ne doit pas prétendre répliquer le protocole interne Telegram. Le connecteur Python doit plutôt déclarer un petit catalogue signé de commandes et d’actions autorisées pour **un appairage THX-HERMES1 précis**. Threnyx affiche ce catalogue dans le chat agent, transmet chaque choix au bot dans un message NIP-17 corrélé, puis attend un accusé ou une réponse agent. Les boutons ne peuvent jamais exécuter du JavaScript, accéder au coffre, modifier des réglages locaux ou appeler WebRTC.

## Références

[1] [Hermes Agent — Telegram Setup](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram)

[2] [Hermes Agent — Messaging Gateway](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/)
