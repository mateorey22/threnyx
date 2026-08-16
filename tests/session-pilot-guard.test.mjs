import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const plan = readFileSync(new URL('../docs/session-pilot-qualification.md', import.meta.url), 'utf8');

assert.match(plan, /NIP-17\/NIP-44\/NIP-59/, 'le plan doit préserver les conversations actives');
assert.match(plan, /marmot-ts/, 'le pilote doit nommer la dépendance évaluée');
assert.match(plan, /Non admissible en production sans revue indépendante/, 'le statut alpha/non audité doit bloquer la production');
assert.match(plan, /564 tests réussis et 1 échec/, 'la qualification doit conserver le résultat de test observé avant toute intégration');
assert.match(plan, /Non intégré à Threnyx/, 'la dépendance non qualifiée ne doit pas être intégrée au chat actif');
assert.match(plan, /Aucun export Constellation de state MLS/, 'l’état ratcheté ne doit pas être répliqué entre appareils');
assert.match(plan, /Crash/, 'la persistance atomique et la reprise après crash doivent être testées');
assert.match(plan, /Forward secrecy/, 'le plan doit définir un test de forward secrecy');
assert.match(plan, /Post-compromise security/, 'le plan doit définir un test de post-compromise security');
assert.ok(!/forward secrecy active/i.test(html), 'la PWA ne doit pas déclarer de forward secrecy avant qualification');
assert.ok(!/post-compromise security active/i.test(html), 'la PWA ne doit pas déclarer de post-compromise security avant qualification');

console.log('session pilot guard checks: OK');
