import assert from "node:assert/strict";

const pub = "a".repeat(64);
const gid = `g_${"b".repeat(32)}`;
const cap = "c".repeat(32);
const card = `GC1:${gid}:${cap}:${pub}`;
const parseGroup = raw => {
  const m = String(raw || "").trim().match(/^GC1:(g_[0-9a-f]{32}):([0-9a-f]{32}):([0-9a-f]{64})$/i);
  return m ? { groupId: m[1], cap: m[2].toLowerCase(), adminPub: m[3].toLowerCase() } : null;
};

assert.deepEqual(parseGroup(card), { groupId: gid, cap, adminPub: pub });
assert.equal(parseGroup(`MC1:${pub}:name:${cap}`), null);
assert.equal(parseGroup(`TCV1:${cap}`), null);

const invite = { maxUses: 2, uses: 0, revoked: false, expiresAt: Date.now() + 60_000 };
const accept = () => {
  if (invite.revoked) return "INVITATION_REVOQUEE";
  if (invite.expiresAt <= Date.now()) return "INVITATION_EXPIREE";
  if (invite.uses >= invite.maxUses) return "QUOTA_ATTEINT";
  invite.uses += 1;
  return "accepted";
};
assert.equal(accept(), "accepted");
assert.equal(accept(), "accepted");
assert.equal(accept(), "QUOTA_ATTEINT");
invite.revoked = true;
assert.equal(accept(), "INVITATION_REVOQUEE");
console.log("gc1 format/quota/revocation: ok");
