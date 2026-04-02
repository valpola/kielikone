# Changelog

All notable changes to this project are documented here.

## Unreleased
- Add a durable client-side queue for Google Sheets result logging so transient
	network or Apps Script failures do not silently drop graded entries.

## 2026-03-25
- Add Unit 5C vocabulary (26 items after deduplication).
- Implement duplicate detection system with normalized Turkish text matching.
- Apply POS tagging to all Unit 5C entries (14 verbs, 5 nouns, 4 adverbs, 3 adjectives).
- Add unit-a1-5c tag registry entry.
- Create alias mapping for beklemek duplicate (5C→4C).
- Add Unit 5B vocabulary (34 items) with comprehensive POS tagging (10 verbs, 20 nouns, 2 adjectives, 2 adverbs).
- Apply gloss corrections to 5B OCR errors (geçirmek, sörf yapmak, tur, and others).
- Create 11 alias mappings for 5B duplicates across units 0A–4C.
- Expand canonical valiz entry to include bavul variant (valiz / bavul).
- Add Unit 5A vocabulary (37 items) with unit and POS tagging.
- Create 6 alias mappings for 5A duplicates.
- Approve all Unit 5A, 5B, and 5C candidates and add to quiz system.

## Earlier Gloss Clarifications (March 2026)
- Clarify asla vs hiçbir zaman ("never / never ever" vs "never / at no time").
- Clarify mağaza vs market ("shop / store (general)" vs "grocery store / supermarket").
- Update saat gloss to "clock / hour" for clarity.
- Clarify boat (sandal vs teknе) glosses.
- Clarify never expressions (asla, hiçbir zaman).
- Clarify old (eski, yaşlı) glosses.
- Merge teneffüs entries and update vocab exports.
- Add both and and fix gloss entries.
- Approve Unit 5A candidates.
- Extract Unit 5A candidates with tags, gloss fixes, and duplicate aliases.
- Reorganise analysis output.
- Clarify aded (added) entry.
- Analyse the least recent words.
- Clarify shop / market distinctions.

## 2026-02-25
- Add web-side today recompute and shared scoring module.
- Add offline and live integration tests for today scoring parity.
- Align web results endpoint with build_today and require api_key for CSV reads.
- Add cache-busting versioning for web assets and data fetches.
- Move developer maintenance notes into docs/handover.

## 2026-02-24
- Merge A1-3B vocab, add candidates/aliases, and remove duplicates.
- Tune scoring and stats_analysis views; adjust wrong-weighting.
- Add and then remove today_score debug fields after validation.
- Fix “sıkılmak” gloss and refresh vocab exports.

## 2026-02-23
- Tune scoring and add stats_analysis workflow.
- Clarify multiple glosses and merge teneffüs entry.
- Refresh vocab exports.

## 2026-02-22
- Document handover, specs, and Sheets setup.
- Add make targets for publish and testing.
