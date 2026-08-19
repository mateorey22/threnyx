# Code source du connecteur Hermes × Threnyx

Le code source du connecteur Python est publié dans [`connectors/hermes-relay-python/`](../connectors/hermes-relay-python/). Il est délibérément séparé de la PWA, qui reste un seul fichier HTML statique et est servie par GitHub Pages.

> GitHub Pages publie uniquement l’application web. Il ne lance jamais `connector.py`, ne lit pas `config.json` et ne reçoit pas les clés du bot ou du gateway Hermes.

Le connecteur sert d’exemple de déploiement sur un hôte persistant et contrôlé. Consultez son [README](../connectors/hermes-relay-python/README.md) pour l’installation et ses [notes de sécurité](../connectors/hermes-relay-python/SECURITY-NOTES.md) avant de créer un bot réel.

La PWA reçoit seulement les données Nostr chiffrées destinées à l’identité bot appairée. Les fonctionnalités média et le raccordement du `prompt_response` au dispatcher Hermes doivent être testés et explicitement activés côté connecteur ; ils ne sont pas activés par la simple présence du code source dans ce dépôt.
