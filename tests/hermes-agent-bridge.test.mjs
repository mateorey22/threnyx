import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

assert.match(html, /indexedDB\.open\('threnyx_secure_v3',3\)/, 'le schéma IndexedDB doit versionner le stockage agent');
assert.match(html, /'agents'/, 'les appairages agent doivent être stockés dans un store dédié chiffré');
assert.match(html, /const AgentBridge=\{/, 'le pont agent doit être explicitement isolé');
assert.match(html, /TAG:'THX-HERMES1'/, 'le format de grant doit être versionné');
assert.match(html, /TTL:10\*60e3/, 'le grant doit expirer en dix minutes');
assert.match(html, /await Secp\.sign\(digest,S\.me\.priv\)/, 'le grant doit être signé localement par l’identité Threnyx');
assert.match(html, /await Secp\.verify\(/, 'le format de grant doit pouvoir être vérifié cryptographiquement');
assert.match(html, /protocols:\['nip17'\]/, 'le grant doit limiter explicitement le transport au protocole NIP-17');
assert.match(html, /S\.contacts\.get\(pub\)\?\.agent/, 'les identités agent ne doivent jamais déclencher un lien P2P');
assert.match(html, /case 'agentAck':\{await AgentBridge\.acknowledge/, 'seul un accusé bot contrôlé doit activer l’état connecté');
assert.match(html, /AgentBridge\.can\(S\.activeChat,agentKind\)/, 'les pièces jointes doivent respecter les permissions agent');
assert.match(html, /AgentBridge\.can\(S\.activeChat,'voice'\)/, 'les vocaux doivent respecter les permissions agent');
assert.match(html, /agentRevoke/, 'la révocation doit notifier le bot sans attendre sa confirmation');
assert.match(html, /id="agent-open"/, 'les réglages doivent offrir un point d’entrée visible pour connecter un agent');
assert.match(html, /id="agent-image"/, 'le consentement image doit être explicite');
assert.match(html, /id="agent-file"/, 'le consentement fichier doit être explicite');
assert.match(html, /id="agent-voice"/, 'le consentement vocal doit être explicite');
assert.match(html, /id="agent-qr"/, 'le code d’appairage doit être disponible sous forme de QR');
assert.match(html, /COPIER LE GUIDE POUR HERMES/, 'le guide de raccordement doit être copiable depuis le parcours');
assert.ok(!html.includes('GATEWAY_RELAY_SECRET'), 'la PWA ne doit jamais contenir un secret gateway Hermes');
assert.ok(!html.includes('GATEWAY_ALLOW_ALL_USERS'), 'la PWA ne doit jamais demander une autorisation Hermes ouverte');

console.log('hermes agent bridge checks: OK');
