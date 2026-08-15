import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const callStart = source.indexOf('const CALL={');
const callEnd = source.indexOf('/* ================================================================\n   NOTIFICATIONS', callStart);
const callSource = source.slice(callStart, callEnd);

assert.ok(source.includes('if(bio&&!duress)'), 'un coffre ayant un code de détresse doit afficher le choix avant la biométrie');
assert.ok(source.includes('id="gate-duress"'), 'l’écran verrouillé doit exposer le code de détresse');
assert.ok(source.includes('body.panic-flame::before'), 'le wipe doit avoir un retour visuel local');
assert.ok(source.includes('id="set-panic"'), 'la flamme doit rester désactivable depuis les réglages');
assert.ok(!source.includes('panicTap'), 'le geste triple-tap caché ne doit plus exister');
assert.ok(source.includes('.voice-play::before'), 'le lecteur vocal doit utiliser une icône centrée personnalisée');
assert.ok(source.includes('id="set-avatar-name"'), 'le sélecteur de portrait doit afficher le fichier choisi');
assert.ok(!callSource.includes('addTransceiver'), 'addTrack ne doit pas être doublé par des transceivers explicites');
assert.ok(callSource.includes('pc.restartIce?.()'), 'les échecs ICE doivent demander un redémarrage');
assert.ok(callSource.includes('m.restart&&S.call.peerId===pid'), 'une offre de redémarrage du pair en appel doit être acceptée');
assert.ok(callSource.includes('call-media-debug'), 'les compteurs locaux de média doivent être disponibles au test');

console.log('v21 controls + WebRTC regression checks: OK');
