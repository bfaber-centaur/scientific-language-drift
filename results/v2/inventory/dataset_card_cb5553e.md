---
pretty_name: Open Text Detector paper text
language: [en]
license: other
task_categories: [text-classification]
tags: [scientific-papers, openreview, ai-text-detection]
size_categories: [100K<n<1M]
configs:
- config_name: clean
  default: true
  data_files: clean/*.parquet
- config_name: direct
  data_files: direct/*.parquet
- config_name: omissions
  data_files: omissions/*.parquet
---

# Open Text Detector paper text

Full text of 93,249 machine-learning papers extracted from their PDFs: conference and journal submissions from OpenReview
(accepted, rejected and withdrawn where public), used by [Open Text Detector](https://opentextdetector.com).
Code: https://github.com/woog97/open-text-detector

## Configs

- `clean` (default): the text layer after cleanup (`positioned-clean-v2`: hyphenation, headers/footers, page numbers and
  similar layout artefacts removed).
- `direct`: the raw positioned text layer from poppler (`pdftotext -bbox-layout`), with page-level tesseract OCR only for
  pages without a usable text layer. `method` says which.
- `omissions`: the clean text with non-prose content replaced by markers: figure text, tables, display equations,
  garbled inline math, number runs and the reference list. `omissions_json` lists every omission with its type.

All three configs have one row per PDF, keyed by `pdf_sha256` (SHA-256 of the PDF), with `paper_id` (the OpenReview
forum id), `title`, `conference` and `year`. Rows join across configs on `pdf_sha256`.

## Contents

| Conference | Year | Extracted papers | Total papers |
|---|---:|---:|---:|
| ICLR | 2027 | 42,344 (99.8%) | 42,429 |
| ICLR | 2026 | 5,167 (26.1%) | 19,814 |
| ICLR | 2025 | 6,160 (52.8%) | 11,672 |
| ICLR | 2024 | 6,150 (83.1%) | 7,404 |
| ICLR | 2023 | 4,824 (97.4%) | 4,955 |
| ICLR | 2022 | 3,363 (98.3%) | 3,422 |
| ICLR | 2021 | 2,973 (98.6%) | 3,014 |
| ICLR | 2020 | 2,559 (98.7%) | 2,594 |
| ICLR | 2019 | 1,553 (98.4%) | 1,579 |
| ICLR | 2018 | 987 (97.0%) | 1,018 |
| ICLR | 2017 | 486 (99.2%) | 490 |
| ICLR | 2014 | 69 (100.0%) | 69 |
| ICLR | 2013 | 63 (94.0%) | 67 |
| COLM | 2026 | 0 (0.0%) | 856 |
| COLM | 2025 | 418 (100.0%) | 418 |
| COLM | 2024 | 299 (100.0%) | 299 |
| CoRL | 2025 | 0 (0.0%) | 263 |
| CoRL | 2024 | 264 (100.0%) | 264 |
| CoRL | 2023 | 198 (99.5%) | 199 |
| CoRL | 2022 | 197 (100.0%) | 197 |
| CoRL | 2021 | 153 (100.0%) | 153 |
| EMNLP | 2023 | 1,218 (60.3%) | 2,020 |
| ICML | 2026 | 0 (0.0%) | 6,556 |
| ICML | 2025 | 1,169 (34.2%) | 3,423 |
| ICML | 2024 | 0 (0.0%) | 2,610 |
| ICML | 2023 | 0 (0.0%) | 1,828 |
| NeurIPS | 2025 | 1,169 (19.1%) | 6,131 |
| NeurIPS | 2024 | 1,219 (25.6%) | 4,762 |
| NeurIPS | 2023 | 1,217 (32.6%) | 3,733 |
| NeurIPS | 2022 | 2,958 (99.0%) | 2,987 |
| NeurIPS | 2021 | 2,689 (89.0%) | 3,020 |
| TMLR | 2026 | 477 (18.2%) | 2,623 |
| TMLR | 2025 | 1,169 (49.9%) | 2,344 |
| TMLR | 2024 | 923 (58.8%) | 1,571 |
| TMLR | 2023 | 592 (54.9%) | 1,079 |
| TMLR | 2022 | 222 (34.6%) | 642 |

Total papers: public submissions on OpenReview (accepted, rejected, withdrawn and desk rejected), from our catalogue of
September 24, 2026 (ICLR 2027: October 4, 2026). The percentage is extracted papers over total papers.

ICLR 2027 papers are submissions under review at the time of extraction (October 2026).

## Notes

- Extraction quality varies with the PDF; scanned or unusual PDFs can produce garbled text. Known open issues in the
  omissions config: small-caps headings next to tables, pseudocode lines omitted as math, untruled tables leaking cells.
- Each paper remains under the licence its authors chose; see the paper's OpenReview page. To ask for a paper to be
  removed, open a discussion on this dataset.
