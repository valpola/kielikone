PYTHON := python

.PHONY: export publish

export:
	$(PYTHON) scripts/export_quiz.py

publish: export
	git add data/lexicon.json web/data/quiz.json
	git commit -m "Update vocab" || true
	git push
