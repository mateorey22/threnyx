import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const sw = readFileSync(new URL('../service-worker.js', import.meta.url), 'utf8');
const csp = html.match(/<meta http-equiv="Content-Security-Policy" content="([^"]+)"/i)?.[1] || '';
const inlineScript = html.match(/<script>([\s\S]*?)<\/script>/i)?.[1] || '';
const scriptHash = `sha256-${createHash('sha256').update(inlineScript).digest('base64')}`;

assert.ok(csp.startsWith("default-src 'none'"), 'le CSP doit partir d’un refus par défaut');
assert.match(csp, /script-src 'sha256-[A-Za-z0-9+/=]+' 'wasm-unsafe-eval'/, 'le script principal doit être autorisé par hash CSP');
assert.ok(csp.includes(`'${scriptHash}'`), 'le hash CSP doit correspondre exactement au script inline réellement publié');
assert.ok(!csp.includes("script-src 'unsafe-inline'"), 'le CSP ne doit pas autoriser les scripts inline arbitraires');
assert.ok(!csp.includes("script-src 'unsafe-eval'"), 'le CSP ne doit pas autoriser eval pour les scripts applicatifs');
assert.match(csp, /object-src 'none'/, 'les objets embarqués doivent être interdits');
assert.match(csp, /base-uri 'none'/, 'la base URL doit être verrouillée');
assert.match(csp, /form-action 'none'/, 'les soumissions de formulaires doivent être interdites');
assert.match(csp, /frame-ancestors 'none'/, 'l’application ne doit pas être intégrable dans une frame');
assert.match(csp, /connect-src 'self' wss: blob:/, 'les connexions applicatives doivent autoriser seulement l’origine de la PWA, les relais WSS et les blobs nécessaires');
assert.ok(!/connect-src[^;]*\bhttps:/.test(csp), 'le CSP ne doit pas autoriser les requêtes HTTPS sortantes arbitraires');
assert.ok(/connect-src[^;]*'self'/.test(csp), 'le CSP doit autoriser les mises à jour et requêtes internes de la PWA sur sa propre origine');
assert.ok(!/<script[^>]+src=/i.test(html), 'aucun script externe ne doit être chargé par le HTML');
assert.ok(!/<link[^>]+href="https?:\/\//i.test(html), 'aucune feuille ou police distante ne doit être chargée par le HTML');
assert.ok(html.includes('Vault.rawArgon'), 'le coffre moderne doit conserver le chemin Argon2id');
assert.ok(html.includes('await Nostr.verifySigned(ev)'), 'un événement Nostr reçu doit être vérifié avant routage');
assert.ok(html.includes('unwrapNip17'), 'le lecteur NIP-17 doit rester présent');
assert.ok(html.includes("console.error('THRENYX_BOOT_ERROR');"), 'le démarrage doit journaliser uniquement un marqueur sans détails sensibles');
assert.ok(!html.includes("console.error('THRENYX_BOOT_ERROR',e);"), 'le démarrage ne doit pas journaliser l’objet d’erreur');
assert.ok(sw.includes("const CACHE='threnyx-pwa-v30'"), 'le cache PWA doit être explicitement versionné');
assert.ok(sw.includes("keys.filter(k=>k.startsWith('threnyx-pwa-')&&k!==CACHE)"), 'les anciens caches Threnyx doivent être nettoyés à l’activation');

console.log('security baseline checks: OK');
