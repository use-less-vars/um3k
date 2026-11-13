#!/bin/sh
TSV=/workspace/artifacts/e3_sweep.tsv
LOGD=/workspace/artifacts/e3_logs
mkdir -p "$LOGD"
touch "$TSV"
BUDGET=${1:-900}
START=$(date +%s)
while read -r f; do
  [ -z "$f" ] && continue
  case "$f" in \#*) continue;; esac
  if grep -q "^${f}	" "$TSV" 2>/dev/null; then continue; fi
  now=$(date +%s); el=$((now-START))
  if [ "$el" -ge "$BUDGET" ]; then echo "BUDGET_EXHAUSTED after ${el}s"; exit 0; fi
  s=$(date +%s)
  log="$LOGD/$(echo "$f" | tr '/' '_').log"
  ( cd /workspace && PYTHONPATH=/workspace:/workspace/.venv/lib/python3.12/site-packages timeout 600 /usr/local/bin/python3.12 -m pytest -o addopts="" "$f" -q > "$log" 2>&1 )
  rc=$?
  e=$(date +%s); d=$((e-s))
  summary=$(grep -E "passed|failed|error|no tests ran|skipped" "$log" | tail -1)
  p=$(echo "$summary" | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+"); [ -z "$p" ] && p=0
  fa=$(echo "$summary" | grep -oE "[0-9]+ failed" | grep -oE "[0-9]+"); [ -z "$fa" ] && fa=0
  er=$(echo "$summary" | grep -oE "[0-9]+ error" | grep -oE "[0-9]+"); [ -z "$er" ] && er=0
  if [ "$rc" -eq 0 ]; then st=PASS
  elif [ "$er" -gt 0 ]; then st=ERROR
  elif [ "$fa" -gt 0 ]; then st=FAIL
  else st=ERROR
  fi
  printf "%s\t%s\t%s\t%s\t%s\n" "$f" "$st" "$p" "$fa" "$d" >> "$TSV"
  echo "$st $f  p=$p f=$fa e=$er ${d}s  :: $summary"
done < /workspace/artifacts/e3_queue.txt
echo "QUEUE_DONE"
