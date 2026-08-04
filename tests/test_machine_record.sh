#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
REPO="$TMP/repo"
HOME_DIR="$TMP/home"
CONF_DIR="$TMP/config"
FAKE_BIN="$TMP/bin"
mkdir -p "$REPO" "$HOME_DIR" "$CONF_DIR/models.d" "$FAKE_BIN"
cp "$ROOT/llmctl" "$REPO/llmctl"
chmod +x "$REPO/llmctl"
git -C "$REPO" init -q
printf 'FAKE_VLLM_KEY_CONTENT\n' > "$CONF_DIR/vllm-key"
printf 'FAKE_LLAMA_KEY_CONTENT\n' > "$CONF_DIR/llama-key"
chmod 000 "$CONF_DIR/vllm-key" "$CONF_DIR/llama-key"

for command in systemctl curl docker nvidia-smi rocm-smi hostname; do
  printf '#!/usr/bin/env bash\nprintf "%%s\\n" %q >> %q\nexit 97\n' \
    "$command" "$TMP/external-command-touched" > "$FAKE_BIN/$command"
  chmod +x "$FAKE_BIN/$command"
done
printf '#!/usr/bin/env bash\nprintf "%%q " "$@" >> %q\nprintf "\\n" >> %q\nexec /usr/bin/git "$@"\n' \
  "$TMP/git-calls" "$TMP/git-calls" > "$FAKE_BIN/git"
chmod +x "$FAKE_BIN/git"

cat > "$CONF_DIR/machine.conf" <<'EOF'
# comments and unknown settings are not repository data
# COMMENT_MUST_NOT_BE_RECORDED — rationale belongs in NOTES, not a comment
MACHINE_NAME="test-box"
NOTES="cpu-only fixture; rationale survives as a value"
ACCEL=cpu
GPUS_DEFAULT=""
VRAM_PER_GPU_MB=0
MODELS_DIR="/models"
VLLM_BIN="/opt/vllm"
VLLM_KEYFILE="/keys/vllm"
LLAMA_SERVER="/opt/llama-server"
LLAMA_KEYFILE="/keys/llama"
ENABLE_BUILTIN_MODELS=0
HERMES_ENABLE=0
OPENCLAW_ENABLE=0
WEBUI_ENABLE=0
UNKNOWN_FIELD="omit-me"
HERMES_CFG="/agents/omit-me"
EOF
sed -i "s#/keys/vllm#$CONF_DIR/vllm-key#; s#/keys/llama#$CONF_DIR/llama-key#" \
  "$CONF_DIR/machine.conf"
cat > "$CONF_DIR/models.d/demo.conf" <<'EOF'
# only model schema fields are retained
# COMMENT_MUST_NOT_BE_RECORDED — rationale belongs in NOTES, not a comment
BACKEND=llamacpp
PORT=19438
MODEL_REF="/models/demo.gguf"
MODEL_ID="demo"
CTX=4096
NOTES="flash-attn on because the fixture pretends to be a GPU box"
SERVER_CTX=4096
STREAMS=2
EXTRA_ARGS="--flash-attn on"
UNKNOWN_MODEL_FIELD="omit-me"
EOF
cat > "$CONF_DIR/stats.jsonl" <<'EOF'
{"model":"demo","ts":"2026-08-03T12:00:00","load_s":1.5,"ttft_s":0.2,"prompt_tokens":10,"prompt_tps":50.0,"gen_tps":25.0,"tok_s":20.0,"bench_tokens":5,"bench_time_s":0.4,"gpu":[{"power_w":null,"mem_mib":12.5,"util_pct":75.0,"gpu":0,"phase":"gen"}]}
EOF
cp "$CONF_DIR/stats.jsonl" "$CONF_DIR/stats.good"

run_llmctl() {
  HOME="$HOME_DIR" PATH="$FAKE_BIN:/usr/bin:/bin" \
    MACHINE_CONF="$CONF_DIR/machine.conf" MODELS_D="$CONF_DIR/models.d" \
    STATS_FILE="$CONF_DIR/stats.jsonl" AGENTS_D="$CONF_DIR/agents.d" \
    /usr/bin/timeout 10 "$REPO/llmctl" "$@"
}

run_llmctl machine record
TARGET="$REPO/inventory/machines/test-box"
[[ -f "$TARGET/machine.conf" ]]
[[ -f "$TARGET/models.d/demo.conf" ]]
[[ -f "$TARGET/stats.jsonl" ]]

grep -qx 'MACHINE_NAME="test-box"' "$TARGET/machine.conf"
grep -qx 'ACCEL=cpu' "$TARGET/machine.conf"
grep -qx 'MODEL_REF="/models/demo.gguf"' "$TARGET/models.d/demo.conf"
# Note: a bare '! cmd' is exempt from 'set -e', so refutations must exit
# explicitly or they silently pass.
if grep -R -E 'VLLM_KEYFILE|LLAMA_KEYFILE|HERMES_CFG|UNKNOWN_|omit-me|/keys/|FAKE_.*_KEY_CONTENT' \
  "$TARGET"; then
  echo "machine record leaked a key file, agent path, or unknown field" >&2
  exit 1
fi

# NOTES is recordable rationale; the agent enable flags are machine state.
grep -qx 'NOTES="cpu-only fixture; rationale survives as a value"' "$TARGET/machine.conf"
grep -qx 'NOTES="flash-attn on because the fixture pretends to be a GPU box"' \
  "$TARGET/models.d/demo.conf"
grep -qx 'HERMES_ENABLE=0' "$TARGET/machine.conf"
grep -qx 'OPENCLAW_ENABLE=0' "$TARGET/machine.conf"
# ...but comments remain local scratch space, in both file kinds.
if grep -R 'COMMENT_MUST_NOT_BE_RECORDED' "$TARGET"; then
  echo "machine record recorded a comment" >&2
  exit 1
fi
if grep -R '^#' "$TARGET/machine.conf" "$TARGET/models.d/demo.conf"; then
  echo "machine record recorded a comment line" >&2
  exit 1
fi

expected='{"bench_time_s":0.4,"bench_tokens":5,"gen_tps":25.0,"gpu":[{"gpu":0,"mem_mib":12.5,"phase":"gen","power_w":null,"util_pct":75.0}],"load_s":1.5,"model":"demo","prompt_tokens":10,"prompt_tps":50.0,"tok_s":20.0,"ts":"2026-08-03T12:00:00","ttft_s":0.2}'
[[ "$(cat "$TARGET/stats.jsonl")" == "$expected" ]]

cp "$CONF_DIR/machine.conf" "$CONF_DIR/machine.good"
sed 's/MACHINE_NAME="test-box"/MACHINE_NAME="..\/..\/escape"/' \
  "$CONF_DIR/machine.good" > "$CONF_DIR/machine.conf"
if run_llmctl machine record >"$TMP/invalid-id.out" 2>&1; then
  echo "machine record accepted a traversal identity" >&2
  exit 1
fi
[[ ! -e "$REPO/escape" ]]
mv "$CONF_DIR/machine.good" "$CONF_DIR/machine.conf"

sed 's/MACHINE_NAME="test-box"/MACHINE_NAME="type-box"/' \
  "$CONF_DIR/machine.conf" > "$CONF_DIR/machine.type"
mv "$CONF_DIR/machine.type" "$CONF_DIR/machine.conf"
cat > "$CONF_DIR/stats.jsonl" <<'EOF'
{"ts":"2026-08-03T12:00:00","model":"demo","load_s":null,"ttft_s":null,"prompt_tokens":"not-an-integer","prompt_tps":null,"gen_tps":null,"tok_s":null,"bench_tokens":null,"bench_time_s":1.0,"gpu":[]}
EOF
if run_llmctl machine record >"$TMP/invalid-stats.out" 2>&1; then
  echo "machine record accepted invalid benchmark field types" >&2
  exit 1
fi
[[ ! -e "$REPO/inventory/machines/type-box" ]]

sed 's/MACHINE_NAME="type-box"/MACHINE_NAME="secret-box"/' \
  "$CONF_DIR/machine.conf" > "$CONF_DIR/machine.secret"
mv "$CONF_DIR/machine.secret" "$CONF_DIR/machine.conf"
cp "$CONF_DIR/stats.good" "$CONF_DIR/stats.jsonl"
sed -i 's#EXTRA_ARGS=.*#EXTRA_ARGS="--api-key-file /tmp/fake-key"#' \
  "$CONF_DIR/models.d/demo.conf"
if run_llmctl machine record >"$TMP/credential-model.out" 2>&1; then
  echo "machine record accepted credential-bearing model arguments" >&2
  exit 1
fi
[[ ! -e "$REPO/inventory/machines/secret-box" ]]

sed 's/MACHINE_NAME="secret-box"/MACHINE_NAME="url-box"/' \
  "$CONF_DIR/machine.conf" > "$CONF_DIR/machine.url"
mv "$CONF_DIR/machine.url" "$CONF_DIR/machine.conf"
sed -i 's#MODEL_REF=.*#MODEL_REF="https://fake-user@example.invalid/model"#' \
  "$CONF_DIR/models.d/demo.conf"
sed -i 's#EXTRA_ARGS=.*#EXTRA_ARGS="--enable-prefix-caching"#' \
  "$CONF_DIR/models.d/demo.conf"
if run_llmctl machine record >"$TMP/credential-url.out" 2>&1; then
  echo "machine record accepted URL userinfo" >&2
  exit 1
fi
[[ ! -e "$REPO/inventory/machines/url-box" ]]

sed 's/MACHINE_NAME="url-box"/MACHINE_NAME="query-box"/' \
  "$CONF_DIR/machine.conf" > "$CONF_DIR/machine.query"
mv "$CONF_DIR/machine.query" "$CONF_DIR/machine.conf"
sed -i 's#MODEL_REF=.*#MODEL_REF="https://example.invalid/model?token=FAKE_QUERY_CREDENTIAL"#' \
  "$CONF_DIR/models.d/demo.conf"
if run_llmctl machine record >"$TMP/credential-query.out" 2>&1; then
  echo "machine record accepted a credential-bearing URL query" >&2
  exit 1
fi
[[ ! -e "$REPO/inventory/machines/query-box" ]]

sed 's/MACHINE_NAME="query-box"/MACHINE_NAME="access-token-box"/' \
  "$CONF_DIR/machine.conf" > "$CONF_DIR/machine.access-token"
mv "$CONF_DIR/machine.access-token" "$CONF_DIR/machine.conf"
sed -i 's#MODEL_REF=.*#MODEL_REF="https://example.invalid/model?access_token=FAKE_ACCESS_TOKEN_CREDENTIAL"#' \
  "$CONF_DIR/models.d/demo.conf"
if run_llmctl machine record >"$TMP/credential-access-token.out" 2>&1; then
  echo "machine record accepted an access_token URL query" >&2
  exit 1
fi
[[ ! -e "$REPO/inventory/machines/access-token-box" ]]

sed 's/MACHINE_NAME="access-token-box"/MACHINE_NAME="allowed-field-box"/' \
  "$CONF_DIR/machine.conf" > "$CONF_DIR/machine.allowed-field"
mv "$CONF_DIR/machine.allowed-field" "$CONF_DIR/machine.conf"
sed -i 's#MODEL_REF=.*#MODEL_REF="safe/model"#' "$CONF_DIR/models.d/demo.conf"
printf 'GPUS="token=FAKE_ALLOWED_FIELD_CREDENTIAL"\n' >> "$CONF_DIR/models.d/demo.conf"
if run_llmctl machine record >"$TMP/credential-allowed-field.out" 2>&1; then
  echo "machine record accepted a credential in an allowlisted model field" >&2
  exit 1
fi
[[ ! -e "$REPO/inventory/machines/allowed-field-box" ]]

# NOTES is free-form prose, so it gets the same credential scan as any value —
# on the model side...
sed -i '/^GPUS=/d' "$CONF_DIR/models.d/demo.conf"
sed 's/MACHINE_NAME="allowed-field-box"/MACHINE_NAME="model-notes-box"/' \
  "$CONF_DIR/machine.conf" > "$CONF_DIR/machine.model-notes"
mv "$CONF_DIR/machine.model-notes" "$CONF_DIR/machine.conf"
sed -i 's#^NOTES=.*#NOTES="api_key=FAKE_MODEL_NOTES_CREDENTIAL"#' \
  "$CONF_DIR/models.d/demo.conf"
if run_llmctl machine record >"$TMP/credential-model-notes.out" 2>&1; then
  echo "machine record accepted a credential in model NOTES" >&2
  exit 1
fi
[[ ! -e "$REPO/inventory/machines/model-notes-box" ]]

# ...and on the machine side, which was never scanned before NOTES existed.
sed -i 's#^NOTES=.*#NOTES="safe model notes"#' "$CONF_DIR/models.d/demo.conf"
sed 's/MACHINE_NAME="model-notes-box"/MACHINE_NAME="machine-notes-box"/' \
  "$CONF_DIR/machine.conf" > "$CONF_DIR/machine.machine-notes"
mv "$CONF_DIR/machine.machine-notes" "$CONF_DIR/machine.conf"
sed -i 's#^NOTES=.*#NOTES="password=FAKE_MACHINE_NOTES_CREDENTIAL"#' \
  "$CONF_DIR/machine.conf"
if run_llmctl machine record >"$TMP/credential-machine-notes.out" 2>&1; then
  echo "machine record accepted a credential in machine NOTES" >&2
  exit 1
fi
[[ ! -e "$REPO/inventory/machines/machine-notes-box" ]]
sed -i 's#^NOTES=.*#NOTES="cpu-only fixture; rationale survives as a value"#' \
  "$CONF_DIR/machine.conf"

sed 's/MACHINE_NAME="machine-notes-box"/MACHINE_NAME="test-box"/' \
  "$CONF_DIR/machine.conf" > "$CONF_DIR/machine.update"
mv "$CONF_DIR/machine.update" "$CONF_DIR/machine.conf"
rm "$CONF_DIR/models.d/demo.conf"
cat > "$CONF_DIR/models.d/next.conf" <<'EOF'
BACKEND=vllm
PORT=19439
MODEL_REF="safe/model"
EXTRA_ARGS="--enable-prefix-caching"
EOF
printf 'stale\n' > "$TARGET/models.d/stale.conf"
cat > "$CONF_DIR/stats.jsonl" <<'EOF'
{"ts":"2026-08-03T13:00:00","model":"next","load_s":null,"ttft_s":null,"prompt_tokens":null,"prompt_tps":null,"gen_tps":null,"tok_s":null,"bench_tokens":null,"bench_time_s":1.0,"gpu":[]}
EOF
run_llmctl machine record
[[ -f "$TARGET/models.d/next.conf" ]]
[[ ! -e "$TARGET/models.d/demo.conf" ]]
[[ ! -e "$TARGET/models.d/stale.conf" ]]
[[ "$(wc -l < "$TARGET/stats.jsonl")" -eq 1 ]]
grep -q '"model":"next"' "$TARGET/stats.jsonl"

mv "$CONF_DIR/machine.conf" "$CONF_DIR/machine.real"
mkfifo "$CONF_DIR/machine.pipe"
ln -s "$CONF_DIR/machine.pipe" "$CONF_DIR/machine.conf"
set +e
run_llmctl machine record >"$TMP/symlink-source.out" 2>&1
rc=$?
set -e
if [[ "$rc" -eq 0 ]]; then
  echo "machine record accepted a symlinked machine.conf" >&2
  exit 1
fi
if [[ "$rc" -eq 124 ]]; then
  echo "machine record read a symlinked machine.conf before rejecting it" >&2
  exit 1
fi
rm "$CONF_DIR/machine.conf"
rm "$CONF_DIR/machine.pipe"
mv "$CONF_DIR/machine.real" "$CONF_DIR/machine.conf"

mv "$CONF_DIR" "$TMP/config.real"
ln -s "$TMP/config.real" "$CONF_DIR"
if run_llmctl machine record >"$TMP/symlink-parent.out" 2>&1; then
  echo "machine record accepted a symlinked configuration parent" >&2
  exit 1
fi
rm "$CONF_DIR"
mv "$TMP/config.real" "$CONF_DIR"

mv "$CONF_DIR/models.d/next.conf" "$CONF_DIR/models.d/next.real"
mkfifo "$CONF_DIR/models.d/next.pipe"
ln -s "$CONF_DIR/models.d/next.pipe" "$CONF_DIR/models.d/next.conf"
set +e
run_llmctl machine record >"$TMP/symlink-model.out" 2>&1
rc=$?
set -e
if [[ "$rc" -eq 0 ]]; then
  echo "machine record accepted a symlinked model definition" >&2
  exit 1
fi
if [[ "$rc" -eq 124 ]]; then
  echo "machine record read a symlinked model definition before rejecting it" >&2
  exit 1
fi
rm "$CONF_DIR/models.d/next.conf"
rm "$CONF_DIR/models.d/next.pipe"
mv "$CONF_DIR/models.d/next.real" "$CONF_DIR/models.d/next.conf"

before="$(sha256sum "$TARGET/stats.jsonl")"
cat > "$CONF_DIR/stats.jsonl" <<'EOF'
{"ts":"2026-08-03T13:00:00","model":"next","load_s":null,"ttft_s":null,"prompt_tokens":null,"prompt_tps":null,"gen_tps":null,"tok_s":null,"bench_tokens":null,"bench_time_s":1.0,"gpu":[],"api_token":"fake"}
EOF
if run_llmctl machine record >"$TMP/unexpected-stats.out" 2>&1; then
  echo "machine record accepted unexpected stats fields" >&2
  exit 1
fi
[[ "$(sha256sum "$TARGET/stats.jsonl")" == "$before" ]]
if compgen -G "$REPO/inventory/machines/.record-*" >/dev/null; then
  echo "machine record left a staging directory behind" >&2
  exit 1
fi

cat > "$CONF_DIR/stats.jsonl" <<'EOF'
{"ts":"first","ts":"duplicate","model":"next","load_s":null,"ttft_s":null,"prompt_tokens":null,"prompt_tps":null,"gen_tps":null,"tok_s":null,"bench_tokens":null,"bench_time_s":1.0,"gpu":[]}
EOF
if run_llmctl machine record >"$TMP/duplicate-stats.out" 2>&1; then
  echo "machine record accepted a duplicate benchmark field" >&2
  exit 1
fi
[[ "$(sha256sum "$TARGET/stats.jsonl")" == "$before" ]]

cp "$CONF_DIR/stats.good" "$CONF_DIR/stats.jsonl"
cp "$TARGET/machine.conf" "$TMP/recorded-machine.good"
sed -i 's/MACHINE_NAME="test-box"/MACHINE_NAME="other-box"/' "$TARGET/machine.conf"
if run_llmctl machine record >"$TMP/mismatched-target.out" 2>&1; then
  echo "machine record replaced a mismatched recorded identity" >&2
  exit 1
fi
mv "$TMP/recorded-machine.good" "$TARGET/machine.conf"

mv "$TARGET" "$REPO/inventory/machines/real-target"
ln -s real-target "$TARGET"
if run_llmctl machine record >"$TMP/symlink-target.out" 2>&1; then
  echo "machine record accepted a symlinked target" >&2
  exit 1
fi
rm "$TARGET"
mv "$REPO/inventory/machines/real-target" "$TARGET"

sed 's/MACHINE_NAME="test-box"/MACHINE_NAME="empty-box"/' \
  "$CONF_DIR/machine.conf" > "$CONF_DIR/machine.empty"
mv "$CONF_DIR/machine.empty" "$CONF_DIR/machine.conf"
rm "$CONF_DIR/stats.jsonl"
run_llmctl machine record
[[ ! -s "$REPO/inventory/machines/empty-box/stats.jsonl" ]]

if run_llmctl machine record unexpected >"$TMP/extra-arg.out" 2>&1; then
  echo "machine record accepted an extra argument" >&2
  exit 1
fi
run_llmctl machine show >/dev/null
rm -f "$TMP/external-command-touched"
run_llmctl machine record >/dev/null
if [[ -e "$TMP/external-command-touched" ]]; then
  echo "machine record probed services, network, containers, GPUs, or host identity" >&2
  exit 1
fi

sed -i '/^ACCEL=/d; s/MACHINE_NAME="empty-box"/MACHINE_NAME="no-probe-box"/' \
  "$CONF_DIR/machine.conf"
rm -f "$TMP/external-command-touched"
run_llmctl machine record >/dev/null
if [[ -e "$TMP/external-command-touched" ]]; then
  echo "machine record auto-probed hardware when ACCEL was omitted" >&2
  exit 1
fi
if grep -Ev "^-C $REPO rev-parse --show-toplevel $" "$TMP/git-calls" >/dev/null; then
  echo "machine record performed a Git operation other than repository-root discovery" >&2
  exit 1
fi

mkdir -p "$CONF_DIR/agents.d"
mkfifo "$CONF_DIR/agents.d/must-not-read.conf"
sed -i 's/MACHINE_NAME="no-probe-box"/MACHINE_NAME="agent-free-box"/' \
  "$CONF_DIR/machine.conf"
if ! run_llmctl machine record >/dev/null; then
  echo "machine record read agent configuration" >&2
  exit 1
fi

# Benchmarks written before the throughput fields existed lack ttft_s,
# prompt_tokens, prompt_tps and gen_tps, and sampled the GPUs once rather than
# per phase. Those are still llmctl's own records, so they must be accepted and
# normalised to the current schema with nulls — not rejected, which would make
# `machine record` unusable on any machine with pre-existing history.
cat > "$CONF_DIR/stats.jsonl" <<'EOF'
{"model":"demo","ts":"2026-07-02T12:00:00","load_s":1.5,"tok_s":20.0,"bench_tokens":5,"bench_time_s":0.4,"gpu":[{"power_w":null,"mem_mib":12.5,"util_pct":75.0,"gpu":0}]}
EOF
sed -i 's/MACHINE_NAME="agent-free-box"/MACHINE_NAME="legacy-box"/' \
  "$CONF_DIR/machine.conf"
if ! run_llmctl machine record >/dev/null; then
  echo "machine record rejected a legacy benchmark record" >&2
  exit 1
fi
legacy_expected='{"bench_time_s":0.4,"bench_tokens":5,"gen_tps":null,"gpu":[{"gpu":0,"mem_mib":12.5,"phase":null,"power_w":null,"util_pct":75.0}],"load_s":1.5,"model":"demo","prompt_tokens":null,"prompt_tps":null,"tok_s":20.0,"ts":"2026-07-02T12:00:00","ttft_s":null}'
if [[ "$(cat "$REPO/inventory/machines/legacy-box/stats.jsonl")" != "$legacy_expected" ]]; then
  echo "legacy benchmark record was not normalised to the current schema" >&2
  exit 1
fi

# A genuinely malformed record must still be refused.
cat > "$CONF_DIR/stats.jsonl" <<'EOF'
{"model":"demo","ts":"2026-07-02T12:00:00","surprise":1}
EOF
sed -i 's/MACHINE_NAME="legacy-box"/MACHINE_NAME="bad-box"/' "$CONF_DIR/machine.conf"
if run_llmctl machine record >/dev/null 2>&1; then
  echo "machine record accepted a malformed benchmark record" >&2
  exit 1
fi

echo "PASS: machine record happy path"
