# Change Description — CardioPatch CP-2 detection model v1.1 -> v1.2

FICTIONAL DEMONSTRATION DOCUMENT. Meridian Medical and the CardioPatch
CP-2 are invented; every name, number and date below is illustrative.

Device: CardioPatch CP-2 wearable ECG monitor (fictional).
Component changed: arrhythmia detection model, version 1.1 -> 1.2.

What changed:
1. Training data refresh: 18 months of additional adjudicated ECG
   segments added to the training pool (no change to labelling rules).
2. Decision threshold adjusted from 0.50 to 0.46 after the locked-set
   evaluation in the accompanying report.
3. No change to inputs, outputs, intended use, or the alert pathway.

What did not change: the device hardware, the firmware shell, the
clinical workflow, and the model's output format.

Planned-change reference: this change is of the kind listed in the
manufacturer's predetermined change plan for the CP-2 detection model
(retraining on adjudicated data within the stated bounds, threshold
adjustment within the validated range). This evidence set does not
assess whether the change plan itself is adequate; it records what was
changed, what was measured, and who approved it.

Evidence set contents:
- change-description.md (this file)
- evaluation-report.md (locked-set evaluation of v1.2)
- approval-record.md (change review board decision)
- previous-version-manifest.md (v1.1 file inventory being superseded)
