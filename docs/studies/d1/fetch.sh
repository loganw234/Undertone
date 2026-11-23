#!/bin/bash
# fetch.sh LIST DATA_DIR MANIFEST LOG
#
# Fetches the requests of a list, ONE AFTER ANOTHER, never two at once.
#   LIST      "name TAB url" a line, as `download_list.py --fetch` prints it
#   DATA_DIR  where the files go; outside the repository; nothing in it is committed
#   MANIFEST  a tab-separated file this script appends to, one line a request:
#             name, url, time fetched (UTC), HTTP status, bytes, SHA-256
#   LOG       the parcel's request log; one line a request, with its time
#
# It never overwrites: a name already in DATA_DIR is skipped and said so.
# A request that does not answer 200 leaves no file; its line in the manifest
# carries the status, 0 bytes and a dash for the hash.
# It sends no personal detail: the default headers of curl and nothing else.
# CURL names the curl to use (default: curl). On the round's desktop the
# Git Bash curl fails on some hosts, so it is run with
#   CURL=/c/Windows/system32/curl.exe
# It waits one second between requests.
#
# What it cannot see: whether a file holds what was asked for. Its hash says
# only that the file is the one that was fetched.
set -u
list="$1"; dir="$2"; manifest="$3"; log="$4"
curl_bin="${CURL:-curl}"
mkdir -p "$dir"
if [ ! -s "$manifest" ]; then
  printf '# file\trequest\tfetched (UTC)\tHTTP status\tbytes\tSHA-256\n' > "$manifest"
fi
while IFS="$(printf '\t')" read -r name url; do
  [ -z "$name" ] && continue
  case "$name" in \#*) continue;; esac
  if [ -e "$dir/$name" ]; then
    echo "SKIPPED, already there: $name"
    continue
  fi
  printf '%s\t%s\tfetch.sh\n' "$(date '+%Y-%m-%d %H:%M:%S %z')" "$url" >> "$log"
  when="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  out="$dir/$name"
  if command -v cygpath > /dev/null 2>&1; then out="$(cygpath -w "$dir/$name")"; fi
  code="$("$curl_bin" -sS -L --compressed --max-time 300 -o "$out" -w '%{http_code}' "$url")"
  if [ "$code" = "200" ] && [ -s "$dir/$name" ]; then
    bytes="$(python -c "import os,sys; print(os.path.getsize(sys.argv[1]))" "$out")"
    sum="$(python -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$out")"
  else
    rm -f "$dir/$name"
    bytes=0; sum="-"
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$url" "$when" "$code" "$bytes" "$sum" >> "$manifest"
  echo "$name: HTTP $code, $bytes bytes"
  sleep 1
done < "$list"
