#!/usr/bin/env bash
# Fetch the agent-facing paths as each AI crawler and check every one gets
# a 200 and the same bytes a plain curl gets (W7: no crawler-only content).
#
# Usage: bash scripts/check_crawlers.sh [BASE_URL]
#   BASE_URL defaults to http://localhost:8199 (the night-shift server).
# Exit code 1 on any non-200 or body mismatch, 0 when every row is OK.
#
# User agents are the published strings where known. Google-Extended is a
# robots.txt token only (Google fetches as Googlebot), and Exa publishes no
# fixed UA string, so both are sent as their bare names.

set -u

BASE="${1:-http://localhost:8199}"
BASE="${BASE%/}"

PATHS=(/robots.txt /about/agent/ /llms.txt)

AGENTS=(
  "GPTBot|Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.1; +https://openai.com/gptbot"
  "OAI-SearchBot|Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot"
  "ChatGPT-User|Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot"
  "ClaudeBot|Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)"
  "PerplexityBot|Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)"
  "Google-Extended|Google-Extended"
  "Exa|Exa"
)

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

sha() { [ -f "$1" ] && shasum -a 256 "$1" | cut -d' ' -f1 || echo none; }

fail=0
printf '%-16s %-14s %-5s %-12s %s\n' AGENT PATH CODE SHA256 RESULT
for path in "${PATHS[@]}"; do
  url="$BASE$path"
  rm -f "$TMP/plain"
  plain_code="$(curl -s -o "$TMP/plain" -w '%{http_code}' "$url")"
  plain_sha="$(sha "$TMP/plain")"
  printf '%-16s %-14s %-5s %-12s %s\n' "(plain curl)" "$path" "$plain_code" "${plain_sha:0:12}" \
    "$([ "$plain_code" = 200 ] && echo OK || echo FAIL)"
  [ "$plain_code" = 200 ] || fail=1
  for entry in "${AGENTS[@]}"; do
    name="${entry%%|*}"
    ua="${entry#*|}"
    rm -f "$TMP/body"
    code="$(curl -s -A "$ua" -o "$TMP/body" -w '%{http_code}' "$url")"
    body_sha="$(sha "$TMP/body")"
    result=OK
    if [ "$code" != 200 ]; then
      result="FAIL (status)"
    elif [ "$body_sha" != "$plain_sha" ]; then
      result="FAIL (body differs)"
    fi
    [ "$result" = OK ] || fail=1
    printf '%-16s %-14s %-5s %-12s %s\n' "$name" "$path" "$code" "${body_sha:0:12}" "$result"
  done
done

if [ "$fail" -ne 0 ]; then
  echo "check_crawlers: FAIL against $BASE"
  exit 1
fi
echo "check_crawlers: all OK against $BASE"
