# Evaluation Report — CardioPatch CP-2 detection model v1.2

FICTIONAL DEMONSTRATION DOCUMENT. All results below are invented.

Dataset: locked validation set LSV-2026-09, 4,096 adjudicated ECG
segments, frozen before v1.2 training began. The tuning set was not
used for any figure in this report.

Model: v1.2, decision threshold 0.46.

Results on the locked set:
- Sensitivity: 0.947 (1,842 / 1,945 positive segments detected)
- Specificity: 0.982 (2,112 / 2,151 negative segments cleared)
- Missed-event review: 103 false negatives, all reviewed; no new
  failure mode versus v1.1; the dominant residual class remains
  low-amplitude episodes during motion artefacts.

Comparison with v1.1 on the same locked set: sensitivity 0.931,
specificity 0.979.

Conclusion of the evaluating engineer: v1.2 meets the pre-registered
acceptance bounds (sensitivity >= 0.94, specificity >= 0.98) on the
locked set.

Evaluator: R. Osei, Verification Engineering (fictional).
Date: 2026-11-12.
