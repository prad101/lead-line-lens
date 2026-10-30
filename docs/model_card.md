# Model card: Lead Line Lens LightGBM v1

_Draft. Gate 2 deliverable; updated at launch._

## Model details
Name, version, date, author, framework, training data snapshot.

## Intended use
Help residents and organizers interpret unknown entries; support prioritization of verification.

**Prohibited uses:** regulatory reclassification without state-accepted verification; deprioritizing any block.

## Data
Source, row counts by class, geographic coverage, known biases in what gets verified and recorded.

## Features
Features and their sources; how neighbor features avoid leakage.

## Training and validation
GroupKFold design, calibration method, hyperparameters.

## Metrics
PR-AUC, ROC-AUC, Brier, expected calibration error, reliability diagram, confusion matrix, baselines.

## Disaggregated performance
Error rates by income quartile and by majority race and ethnicity.

## Limitations and caveats
Unknowns are not random; verified records skew toward certain neighborhoods and years; transfer to other systems is unproven.

## Maintenance
How the model is retrained when the inventory updates; who to contact.
