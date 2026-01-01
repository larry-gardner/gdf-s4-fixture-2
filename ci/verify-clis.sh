#!/usr/bin/env bash
# Each CLI checked against a source independent of the npm registry, after install-clis.sh has
# checked the npm SHA-512 pins (docs/GDF_MVP_01C_S4_PLAN.md §8.3 row 6).
#   Claude Code: Anthropic's signed manifest, verified with the committed release key, whose
#     fingerprint must equal the one Anthropic publishes; the binary must match the manifest.
#   Codex: the npm tarball must equal the release asset's digest that GitHub computed for
#     openai/codex's own release (no signature is verified here).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
fail() { echo "::error::$1"; exit 1; }

key="$here/provenance/claude-code.asc"
manifest="$here/provenance/claude-code-${CLAUDE_VERSION}-manifest.json"
signature="$manifest.sig"
[[ "$CLAUDE_KEY_FINGERPRINT" =~ ^[0-9A-F]{40}$ ]] || fail "bad pinned key fingerprint"
[[ "$CODEX_RELEASE_SHA256" =~ ^[0-9a-f]{64}$ ]] || fail "bad pinned release digest"
gnupg="$(mktemp -d)"
chmod 700 "$gnupg"
export GNUPGHOME="$gnupg"
gpg --batch --quiet --import "$key" 2>/dev/null || fail "release key unreadable"
primaries="$(gpg --batch --with-colons --fingerprint | awk -F: '$1=="pub"{p=1; next} p&&$1=="fpr"{print $10; p=0}')"
[ "$primaries" = "$CLAUDE_KEY_FINGERPRINT" ] || fail "release key is not exactly the pinned key"
# VALIDSIG's last field is the primary key's fingerprint: the signature must be by the pinned key.
status="$(gpg --batch --status-fd 1 --verify "$signature" "$manifest" 2>/dev/null)" || fail "manifest signature invalid"
grep -Eq "^\[GNUPG:\] VALIDSIG [0-9A-F]{40} .* ${CLAUDE_KEY_FINGERPRINT}\$" <<<"$status" || fail "manifest not signed by the pinned key"
want="$(python3 -I - "$manifest" "$CLAUDE_VERSION" <<'PY'
import json, re, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
entry = data["platforms"]["linux-x64"]
assert data["version"] == sys.argv[2] and entry["binary"] == "claude"
assert re.fullmatch(r"[0-9a-f]{64}", entry["checksum"])
print(entry["checksum"])
PY
)" || fail "manifest has no linux-x64 checksum for this version"
[ "$(sha256sum "$CLAUDE_BIN" | cut -d' ' -f1)" = "$want" ] || fail "claude binary differs from the signed manifest"
[ "$(sha256sum "$RUNNER_TEMP/cli/codex.tgz" | cut -d' ' -f1)" = "$CODEX_RELEASE_SHA256" ] || fail "codex tarball differs from the release digest"
rm -rf "$gnupg"
echo "provenance: claude matches the signed manifest; codex matches the release digest"
