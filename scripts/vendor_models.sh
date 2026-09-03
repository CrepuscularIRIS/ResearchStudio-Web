#!/usr/bin/env bash
# Vendor a model repo as TRACKED FILES on research-trunk from a fresh official clone (never from the locally modified repos/*).
# Usage: bin/vendor_models.sh <name> <git-url> [ref]      e.g. bin/vendor_models.sh DFormer https://github.com/VCIP-RGBD/DFormer.git main
# Result: <repo>/models/<name>/ (no .git), models/VENDORED.json {name: {url, ref, commit, vendored_at}}, one commit on research-trunk.
# Why: the loop reviews a diff against research-trunk; a gitlink is invisible to review and the local copies carry years of edits
# nobody can account for. Every candidate starts from the official code; known bugs go into the spec explicitly (AVOID / anomalies).
set -euo pipefail
NAME="${1:?name}"; URL="${2:?git url}"; REF="${3:-}"
W="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(python3 - "$W" <<'EOF'
import re, sys, yaml, pathlib
w = pathlib.Path(sys.argv[1]); m = re.search(r"^```yaml\n(.*?)\n```", (w / "GOAL.md").read_text(encoding="utf-8"), re.S | re.M)
g = (yaml.safe_load(m.group(1)) or {}).get("campaign", {}) if m else {}
print(w / str(g.get("repo_root", ".")))
EOF
)"
[ "$(git -C "$REPO" branch --show-current)" = "research-trunk" ] || { echo "REFUSED: $REPO is not on research-trunk" >&2; exit 1; }
DEST="$REPO/models/$NAME"
[ -e "$DEST" ] && { echo "REFUSED: $DEST exists; remove it first if you mean to re-vendor" >&2; exit 1; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
if [ -n "$REF" ]; then git clone --quiet --depth 1 --branch "$REF" "$URL" "$TMP/src"; else git clone --quiet --depth 1 "$URL" "$TMP/src"; fi
COMMIT="$(git -C "$TMP/src" rev-parse HEAD)"; REF_USED="$(git -C "$TMP/src" rev-parse --abbrev-ref HEAD)"
rm -rf "$TMP/src/.git"
find "$TMP/src" -name "*.pth" -o -name "*.pt" -o -name "*.ckpt" | xargs -r rm -f          # weights are never tracked
mkdir -p "$REPO/models"; mv "$TMP/src" "$DEST"
python3 - "$REPO/models/VENDORED.json" "$NAME" "$URL" "$REF_USED" "$COMMIT" <<'EOF'
import json, sys, time, pathlib
p = pathlib.Path(sys.argv[1]); d = json.loads(p.read_text()) if p.exists() else {}
d[sys.argv[2]] = {"url": sys.argv[3], "ref": sys.argv[4], "commit": sys.argv[5], "vendored_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
p.write_text(json.dumps(d, indent=1) + "\n")
EOF
git -C "$REPO" add "models/$NAME" models/VENDORED.json
git -C "$REPO" commit -q -m "vendor: $NAME from $URL @ ${COMMIT:0:12} (fresh official clone, no .git, no weights)" -- "models/$NAME" models/VENDORED.json
echo "vendored models/$NAME @ ${COMMIT:0:12} ($REF_USED) — $(find "$DEST" -name '*.py' | wc -l) python files; committed on research-trunk"
