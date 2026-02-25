PYTHON := .venv/bin/python

.PHONY: export publish test-results build-today
.PHONY: validate-tags extract-candidates merge-candidates check-venv
.PHONY: rebuild-reviewed rebuild-reviewed-today

check-venv:
	@test -x $(PYTHON) || (echo "Missing .venv. Run: python3 -m venv .venv && source .venv/bin/activate"; exit 1)


export: check-venv
	$(PYTHON) scripts/export_quiz.py

publish: export
	git add data/vocab data/tags.json web/data/quiz.json web/data/aliases.json
	git commit -m "Update vocab" || true
	git push

test-results: check-venv
	$(PYTHON) scripts/test_results_endpoint.py

build-today: check-venv
	$(PYTHON) scripts/build_today.py

validate-tags: check-venv
	$(PYTHON) scripts/validate_tags.py

extract-candidates: check-venv
	$(PYTHON) scripts/extract_vocab_candidates.py $(INPUT)

merge-candidates: check-venv
	$(PYTHON) scripts/merge_candidates.py $(CANDIDATE)

rebuild-reviewed: check-venv
	$(PYTHON) scripts/rebuild_reviewed.py

rebuild-reviewed-today: rebuild-reviewed
	$(PYTHON) scripts/dedupe_vocab.py --apply
	$(PYTHON) scripts/build_today.py
