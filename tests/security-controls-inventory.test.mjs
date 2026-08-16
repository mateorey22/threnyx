import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const inventory = readFileSync(new URL('../docs/security-controls-inventory.md', import.meta.url), 'utf8');

for (const control of [
  'NIP-17',
  'Forward secrecy',
  'Post-compromise security',
  'Argon2id',
  'Code de détresse',
  'Wipe par flamme',
  'Vérification de fingerprint',
  'CSP et intégrité du script',
  'Constellation et conflits hors ligne',
  'Invitations de groupe GC1',
]) {
  assert.match(inventory, new RegExp(control), `inventaire incomplet : ${control}`);
}

assert.match(inventory, /\*\*Non active\.\*\*/, 'les garanties de session non qualifiées doivent rester explicitement inactives');
assert.match(inventory, /doivent continuer à exclure toute promesse de forward secrecy/, 'la communication publique doit rester honnête');

console.log('security controls inventory checks: OK');
