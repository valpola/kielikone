PYTHON := python

.PHONY: export publish test-results
.PHONY: validate-tags extract-candidates merge-candidates

export:
	$(PYTHON) scripts/export_quiz.py

publish: export
	git add data/lexicon.json web/data/quiz.json
	git commit -m "Update vocab" || true
	git push

test-results:
	$(PYTHON) scripts/test_results_endpoint.py

validate-tags:
	$(PYTHON) scripts/validate_tags.py

extract-candidates:
	$(PYTHON) scripts/extract_vocab_candidates.py $(INPUT)

merge-candidates:
	$(PYTHON) scripts/merge_candidates.py $(CANDIDATE)
