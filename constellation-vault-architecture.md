# Threnyx Constellation Vault — architecture proposée

## Positionnement

Constellation Vault est une couche de continuité d’identité et de réplication chiffrée pour Threnyx. Elle ne transforme pas les relais Nostr, IPFS ou Hypercore en « cloud magique ». Les appareils Threnyx restent les autorités de chiffrement ; les relais ne reçoivent que des enveloppes opaques et du routage minimal.

La première livraison doit synchroniser **l’identité, les contacts, les groupes, les réglages, les messages et les petits médias déjà présents dans le coffre local**. Les gros médias ne doivent pas être annoncés comme durablement disponibles tant que leur réplication fragmentée et leur restitution sur plusieurs relais ne sont pas validées avec de vrais appareils.

## Le format original : capsule, manifeste, fragments

| Élément | Rôle | Visible pour un relais | Secret nécessaire |
| --- | --- | --- | --- |
| **Identité Threnyx** | Clé Nostr principale de l’utilisateur. | Non, sauf les événements normaux de messagerie. | Coffre local ou capsule de reprise. |
| **Clé de synchronisation** | Paire secp256k1 distincte qui signe les manifestes de reprise. | Pubkey de synchronisation uniquement. | Partie privée présente dans la capsule et la clé physique. |
| **Clé de reprise** | Aléa de 256 bits chiffrant les capsules et fragments. | Jamais. | Clé NFC ou sauvegarde chiffrée de secours. |
| **Manifestes** | Dernière version connue, liste de fragments, horodatage logique et empreintes. | Signature, pubkey de synchronisation, identifiant de version. | Clé de reprise pour le contenu. |
| **Fragments** | Bloc chiffré de taille plafonnée contenant un sous-ensemble de données. | Taille approchée et identifiant de snapshot. | Clé de reprise. |

Les fragments sont chiffrés individuellement avec AES-GCM, à partir d’une sous-clé dérivée par HKDF de la clé de reprise, de l’identifiant de snapshot et du numéro de fragment. Chaque manifeste est signé par la clé de synchronisation. Ainsi, un relais ne peut ni lire un bloc ni fabriquer un manifeste valide ; il peut néanmoins supprimer, retenir ou rejouer des blocs, raison pour laquelle Threnyx requiert plusieurs destinations et vérifie les numéros de version.

La logique de convergence est volontairement simple pour la première version : un appareil produit un snapshot immuable numéroté et n’écrase jamais ses fragments. Le manifeste adressable désigne la dernière version observée. Les conflits sont détectés lorsque deux manifestes valides ont le même parent et sont alors présentés comme deux branches à choisir, jamais fusionnés silencieusement. Cette approche évite de prétendre offrir un CRDT complet alors que les médias, suppressions et clés exigent une politique de conflit explicite.

## Relais, IPFS et Hypercore

Nostr est retenu pour le premier transport parce que Threnyx possède déjà un pool de relais WebSocket, un chiffrement local et une file d’attente. Le manifeste utilise un événement NIP-78 chiffré et les fragments des événements NIP-78 normaux signés par une **clé de synchronisation dédiée**, non par la clé de messagerie. Trois accusés de réception de relais distincts constituent l’objectif de réplication avant d’afficher « protégé ».

IPFS / Helia n’est pas retenu comme stockage de base : l’adressage de contenu est intéressant pour dédupliquer et vérifier des médias, mais il ne garantit pas leur rétention sans nœud qui les conserve ou service de pinning. Hypercore inspire l’usage d’un journal signé et de blocs vérifiables ; son transport et sa découverte de pairs spécialisés ne sont pas intégrés directement dans la PWA GitHub Pages à ce stade. Ils restent des transports futurs possibles pour des appareils Threnyx qui s’annoncent explicitement entre eux.

## Clé NFC physique de reprise

Le tag NDEF contient un paquet compact `TCV1` : version, pubkey de synchronisation, clé privée de synchronisation, clé de reprise et identifiant d’époque. Ce paquet ne contient ni messages ni contacts ni nom de l’utilisateur. Après scan, le nouvel appareil recherche les manifestes signés par la pubkey de synchronisation, télécharge les fragments chiffrés depuis plusieurs relais, les vérifie, restaure le coffre local puis demande la création d’une **nouvelle** protection biométrique.

> Un tag NDEF grand public est un objet à possession : il peut être lu et cloné. La biométrie créée sur le nouveau téléphone protège seulement la copie restaurée ; elle ne rend pas le scan initial plus secret. Perdre ou faire copier cette clé équivaut à perdre une clé de récupération. La première version doit exiger une confirmation explicite et recommander deux tags conservés séparément, ainsi qu’une sauvegarde chiffrée hors NFC.

La rotation crée une nouvelle époque, une nouvelle paire de synchronisation et une nouvelle clé de reprise. Elle empêche toute lecture des snapshots futurs avec l’ancien tag, mais ne peut pas rendre illisibles les snapshots déjà récupérés par une personne ayant copié le tag. Une vraie révocation contre un vol ancien impose donc de changer d’identité ou d’accepter que les données publiées avant la rotation restent récupérables par l’ancienne clé.

## Limites déclarées

| Garantie | Statut |
| --- | --- |
| Chiffrement des données avant publication | Oui, requis. |
| Intégrité des snapshots et des manifestes | Oui, par signature de synchronisation et vérification locale. |
| Récupération depuis plusieurs relais fonctionnels | Objectif de la première version ; disponibilité dépend des relais. |
| Absence de serveur Threnyx central | Oui. Les relais publics restent des tiers de transport, pas des détenteurs de clés. |
| Disponibilité si aucun appareil ni relais ne conserve la capsule | Impossible. |
| Secret matériel d’un tag NFC NDEF grand public | Non. Un tag peut être copié. |
| Synchronisation automatique en arrière-plan sur mobile | Non garantie par une PWA : le navigateur suspend fréquemment les tâches en arrière-plan. |
| Médias volumineux restaurés durablement | Non garanti avant validation de la réplication fragmentée réelle. |

## Validation réalisée le 15 août 2026

| Scénario | Résultat | Observation |
| --- | --- | --- |
| Publication d’un fragment de contrôle | Validée | Une première tentative a révélé que le tag Nostr `e` est réservé à un identifiant d’événement. Le protocole utilise désormais le tag applicatif `epoch`. |
| Quorum de réplication | Validé | Un fragment chiffré puis un manifeste ont reçu la confirmation demandée de plusieurs relais actifs. |
| Recherche de manifeste | Validée | Le manifeste NIP-78 signé par la clé de synchronisation a été retrouvé et déchiffré à partir de la clé de reprise. |
| Vérification de contenu | Validée | Le fragment récupéré a été déchiffré, recomposé et son SHA-256 correspondait à l’empreinte du manifeste. |
| Paquet de clé NFC | Validé en simulation | Le paquet `TCV1` a une longueur de 97 caractères, a été reconstruit sans perte et a restitué la même clé de synchronisation. L’écriture/lecture d’un tag physique reste à valider sur Chrome Android. |
| Restauration nouvel appareil | Validée en simulation isolée | Une origine locale sans coffre a restauré l’identité de contrôle depuis les relais, créé un nouveau coffre protégé par phrase secrète et ouvert l’application restaurée. |
| Clé de récupération altérée | Validée | Une clé de reprise aléatoire ne pouvait pas déchiffrer le manifeste pourtant retrouvé avec la même clé publique de synchronisation. |
| Confidentialité de l’événement | Validée sur l’échantillon de contrôle | Les contenus Nostr récupérés ne contenaient pas en clair le nom de l’identité de contrôle ; ils étaient constitués des champs de boîte chiffrée. |

## Références

1. NIP-78, données applicatives Nostr : <https://raw.githubusercontent.com/nostr-protocol/nips/master/78.md>
2. NIP-44, chiffrement Nostr et limites : <https://raw.githubusercontent.com/nostr-protocol/nips/master/44.md>
3. NIP-59, enveloppes cadeau : <https://raw.githubusercontent.com/nostr-protocol/nips/master/59.md>
4. Persistance IPFS : <https://docs.ipfs.tech/concepts/persistence/>
5. Hypercore : <https://docs.pears.com/reference/building-blocks/hypercore/>
6. Web NFC : <https://developer.chrome.com/docs/capabilities/nfc>
