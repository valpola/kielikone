PYTHON := .venv/bin/python

.PHONY: check-venv build export publish test validate-tags
.PHONY: extract-candidates merge-candidates build-today stats

check-venv:
	@test -x $(PYTHON) || (echo "Missing .venv. Run: python3 -m venv .venv && source .venv/bin/activate"; exit 1)

# The full pipeline, candidates -> web/data/quiz.json. Run this after editing
# anything under data/: export alone is not enough, since reviewed.json and the
# alias merge are both regenerated from the candidate files.
build: check-venv
	$(PYTHON) scripts/rebuild_reviewed.py
	$(PYTHON) scripts/dedupe_vocab.py --apply
	$(PYTHON) scripts/validate_tags.py
	$(PYTHON) scripts/export_quiz.py

export: build

# Deliberately does not commit or push: the cache-bust in web/config.js and
# web/index.html has to be bumped first, or browsers keep serving the old app.js
# against the new deck.
publish: build test
	@echo
	@echo "Now bump cacheBust in web/config.js and the ?v= strings in web/index.html,"
	@echo "then commit and push. GitHub Actions publishes web/ from main."

test: check-venv
	node scripts/tests/test_answer_matching.js
	node scripts/tests/test_today_scoring_offline.js
	node scripts/tests/test_today_filters_offline.js
	node scripts/tests/test_recompute_today_app.js
	$(PYTHON) scripts/tests/test_deck_invariants.py
	$(PYTHON) scripts/tests/test_supabase_sync.py

validate-tags: check-venv
	$(PYTHON) scripts/validate_tags.py

extract-candidates: check-venv
	$(PYTHON) scripts/extract_vocab_candidates.py $(INPUT)

merge-candidates: check-venv
	$(PYTHON) scripts/merge_candidates.py $(CANDIDATE)

# Offline scoring analysis only. It writes the practice-set tag into the vocab
# files, which export_quiz.py then strips — the app computes its own set.
build-today: check-venv
	$(PYTHON) scripts/build_today.py

stats: check-venv
	$(PYTHON) scripts/stats_analysis.py
