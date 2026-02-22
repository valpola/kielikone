PYTHON := python

.PHONY: export publish test-results

export:
	$(PYTHON) scripts/export_quiz.py

publish: export
	git add data/lexicon.json web/data/quiz.json
	git commit -m "Update vocab" || true
	git push

test-results:
	$(PYTHON) scripts/test_results_endpoint.py
