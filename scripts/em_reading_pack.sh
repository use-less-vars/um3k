#!/bin/sh
# Curated EM reading pack: ~96 kB, labelled, byte-capped per slice.
# Usage: sh scripts/em_reading_pack.sh > /tmp/pack.txt; wc -c /tmp/pack.txt
cd "$(dirname "$0")/.." || exit 1
RD() {
  label=$1; cap=$2; f=$3; a=$4; b=$5
  printf '\n=== %s\n' "$label"
  if [ ! -f "$f" ]; then printf '### MISSING: %s\n' "$f"; return; fi
  printf -- '--- %s  lines %s-%s\n' "$f" "$a" "$b"
  sed -n "${a},${b}p" "$f" | head -c "$cap"
  printf '\n'
}
printf '##### EM READING PACK #####\n'
printf '\n=== 0a. Shape of the repo (sizes, not contents)\n'
wc -c -l docs/design/EM_SOLVER_LEDGER.md docs/design/defect_register.md server/poc_app.py tests/test_huygens_fields.py emfit/ntff.py docs/design/GEN13_HANDOFF.md 2>/dev/null
printf '\n=== 0b. Python modules\n'
ls -F emfit/ | head -60
printf '\n=== 0c. C++ kernel files\n'
ls -l src/ 2>/dev/null | head -20 || printf 'no src/ directory\n'
printf '\n=== 0d. Ledger section index\n'
grep -n '^#' docs/design/EM_SOLVER_LEDGER.md | head -40
printf '\n=== 0e. KB section index\n'
grep -rn '^#' .thoughtmachine/knowledge/ 2>/dev/null | head -80
RD '1. THE HANDOFF - read first' 5000 docs/design/GEN13_HANDOFF.md 1 50
RD '2. THE LEDGER - what is built' 30000 docs/design/EM_SOLVER_LEDGER.md 1 49
RD '3. DEFECT REGISTER - first page only' 8000 docs/design/defect_register.md 1 60
RD '4a. UI: pyvista grid + offscreen mesh/volume' 5000 server/poc_app.py 3512 3625
RD '4b. UI: far-field panel builder' 4000 server/poc_app.py 6202 6299
RD '4c. UI: far-field panel loader' 2500 server/poc_app.py 7396 7446
RD '4d. UI: far-field panel emitters' 2500 server/poc_app.py 7912 7947
RD '4e. UI: mode picker emitters' 2500 server/poc_app.py 8240 8300
RD '4f. UI: the player bar (this is "playback")' 3000 server/poc_app.py 8386 8469
RD '4g. UI: the five tabs' 2500 server/poc_app.py 8540 8580
RD '5a. NTFF: schema + keys' 2000 emfit/ntff.py 150 178
RD '5b. NTFF: SurfaceDump' 5000 emfit/ntff.py 245 330
RD '5c. NTFF: angles + radiation_vectors' 7000 emfit/ntff.py 557 702
RD '5d. NTFF: FarField, _radiated_power, far_field' 9000 emfit/ntff.py 702 865
RD '6a. FLUX TEST: fixtures' 2000 tests/test_huygens_fields.py 827 860
RD '6b. FLUX TEST: helpers + convergence + absolute' 10000 tests/test_huygens_fields.py 1505 1727
printf '\n##### END OF PACK #####\n'
