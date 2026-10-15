#!/usr/bin/env bash
# Lane B (V2 Gate 2): full replication pipeline. ~1.5 h on 4 cores; intermediates in $W (default ~/work).
# Run from anywhere; scripts are addressed by absolute path (the shared mount can drop the cwd).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
W="${W:-$HOME/work}"
REV=2c0dd192a3d3ba6605ed3f5ed5df145dddbdcb27
FLAGS="$REPO/results/v2/replication/flags_v2.csv.gz"
OUT="$REPO/results/v2/replication"
export MLNGRAMS_REVISION=$REV
cd "$W"

# 1. per-record flags (version, V1 membership, ICLR title overlap, composite strata); checks V1 flags
python3 "$REPO/scripts/v2/replication_flags.py" --revision $REV

# 2. counts: main body n = 1-3, all text n = 1-2 (as in V1)
python3 "$REPO/scripts/count_ngrams.py" --revision $REV --merge-by-year --years 2017-2027 --body-only --flags "$FLAGS" --out "$W/v2_body"
python3 "$REPO/scripts/count_ngrams.py" --revision $REV --merge-by-year --years 2013 2014 2017-2027 --ns 1 2 --flags "$FLAGS" --out "$W/v2_all"

# 3. views (scripts/v2/replication_views.py documents each)
for v in v1repro add2024 add2026 v2def v2main member:v1 member:added; do
  python3 "$REPO/scripts/v2/replication_views.py" "$W/v2_body" "$W/views/${v/:/_}" "$v"
done
for v in v1repro v2def v2main; do
  python3 "$REPO/scripts/v2/replication_views.py" "$W/v2_all" "$W/views_all/$v" "$v" --ns 1 2
done

# 4. V1 tables recomputed from the V1 records (exactness check; not committed)
python3 "$REPO/scripts/make_tables.py" "$W/views/v1repro" "$W/v1repro_tables"
python3 "$REPO/scripts/make_tables.py" "$W/views_all/v1repro" "$W/v1repro_alltext_tables"
python3 "$REPO/scripts/longitudinal.py" "$W/views/v1repro" v1repro --sens "$W/views_all/v1repro" \
  --sens-label alltext --outroot "$W/v1repro_long" --tmp "$W/duck"

# 5. V2 tables and longitudinal runs (committed)
for v in v2main v2def; do
  python3 "$REPO/scripts/make_tables.py" "$W/views/$v" "$OUT/$v/body"
  python3 "$REPO/scripts/make_tables.py" "$W/views_all/$v" "$OUT/$v/alltext"
  python3 "$REPO/scripts/longitudinal.py" "$W/views/$v" "$v" --sens "$W/views_all/$v" --sens-label alltext \
    --outroot "$OUT" --tmp "$W/duck" $([ "$v" = v2main ] && echo --coverage v2)
done

# 6. other venues (per-paper target counts) and the V1/V2 comparison
python3 "$REPO/scripts/v2/paper_features.py" --revision $REV --out "$W/features"
python3 "$REPO/scripts/v2/venue_replication.py" --features "$W/features"
python3 "$REPO/scripts/v2/replication_compare.py" --views "$W/views" --v1repro-tables "$W/v1repro_tables" \
  --v1repro-alltext-tables "$W/v1repro_alltext_tables" --v1repro-long "$W/v1repro_long/v1repro/longitudinal"
