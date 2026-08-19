# Connecteur Python Hermes × Threnyx

Ce répertoire contient le **code source autonome** du bridge entre Threnyx, les relais Nostr et une API Hermes interne. Il est isolé sous `connectors/` : GitHub Pages ne l’importe pas, ne l’exécute pas et ne peut donc pas modifier la PWA publiée.

> **Statut : pilote d’intégration.** Lancez-le seulement sur une machine que vous contrôlez, avec une identité Nostr bot dédiée. Consultez [SECURITY-NOTES.md](SECURITY-NOTES.md) avant tout déploiement.

## Périmètre réellement disponible

| Fonction | État | Détail |
| --- | --- | --- |
| Appairage | Disponible | Vérifie `THX-HERMES1`, BIP-340, expiration, permissions et rejeu durable. |
| Texte 1:1 | Disponible | Accepte uniquement les messages chiffrés adressés au bot appairé et les transmet à l’API Hermes configurée. |
| Commandes | Disponible | Le manifeste `THX-HERMES-UI1` est envoyé après appairage ; chaque `/commande` est transmise telle quelle au gateway. |
| Boutons | Transport prêt | Valide `agentPromptResponse`, option déclarée, expiration et anti-rejeu. Le pont final vers le dispatcher `prompt_response` Hermes doit être ajouté par l’opérateur du gateway. |
| Médias | Désactivé par défaut | La bibliothèque de cache chiffré existe, mais le routeur média de production n’est pas relié au bridge. |
| Appels | Hors périmètre | Les appels WebRTC ne passent jamais par le connecteur. |

## Structure des sources

| Fichier | Rôle |
| --- | --- |
| `connector.py` | Processus persistant Nostr ↔ API Hermes, commandes, prompts et révocation. |
| `grant.py` | Contrôle `THX-HERMES1` et index anti-rejeu persistant. |
| `nostr_crypto.py`, `nip44.py` | Primitives Nostr/NIP-17 utilisées par le bridge. |
| `threnyx_crypto.py` | Repli legacy Threnyx pour la compatibilité de messages. |
| `media_store.py` | Cache temporaire chiffré, non encore branché au transport applicatif. |
| `test_connector.py` | Tests de grants, rejeu, révocation, NIP-17, média et options de prompt. |
| `config.example.json` | Exemple sans secret à copier localement. |

## Installation locale

Créez un environnement virtuel sur l’hôte persistant du bot ; ne placez ni ce processus ni les clés dans GitHub Pages.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
umask 077
mkdir -p state
cp config.example.json config.json
# Renseignez config.json localement, sans le commiter.
python3 test_connector.py
python3 connector.py
```

La clé privée du bot appartient dans `config.json` ou dans `THRENYX_BOT_PRIV_KEY`. Le jeton de l’API Hermes appartient dans `HERMES_API_KEY`. `config.json`, `state/` et `media_cache/` sont exclus par `.gitignore`.

## Appairage avec Threnyx

1. Démarrez le connecteur avec une clé publique bot stable.
2. Dans Threnyx, ouvrez **Réglages → Agents Hermes / Relay** et collez cette clé publique, jamais la clé privée.
3. Créez et transmettez le code `THX-HERMES1` au connecteur par un canal de confiance.
4. Le connecteur valide le grant puis envoie `agentAck` et `agentManifest` à l’utilisateur appairé.
5. Vérifiez l’empreinte bot par un canal indépendant avant d’échanger des informations sensibles.

## Déploiement et limites de sécurité

Le connecteur est un service continu. Exécutez-le sur un hôte contrôlé, avec un compte système dédié, un répertoire à permissions restreintes et un chemin `state/grants.json` sauvegardé de manière chiffrée. Ne rendez pas l’API Hermes publique et n’activez jamais une autorisation générale.

Le bridge utilise actuellement une API HTTP compatible OpenAI. Il ne constitue pas une implémentation complète du WebSocket Hermes Relay officiel. L’opérateur doit finaliser et tester le pont `prompt_response` vers le dispatcher Hermes avant de présenter les boutons comme une action opérationnelle. Les médias restent désactivés par défaut jusqu’à la validation de leur transport de bout en bout.

## Licence

MIT — voir [LICENSE](LICENSE).
