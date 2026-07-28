# Soccer prediction pipeline

This directory contains the end-to-end modeling experiment used by the repository.

## Modules

| File | Responsibility |
|---|---|
| `data_collection.py` | Provider adapters and fixture/history collection |
| `data_preprocessing.py` | Schema normalization and cleaning |
| `feature_engineering.py` | Form, Elo-style, goal, and contextual features |
| `model_training.py` | Training and evaluation routines |
| `prediction.py` | Probability and score prediction |
| `api.py` | FastAPI endpoints |
| `main.py` | Command-line orchestration |
| `telegram_notifier.py` | Optional notification adapter |

## Basic verification

```bash
python -m pip install -r requirements.txt
python test_setup.py
```

Configure provider credentials through the repository-level `.env.example`. Run collection carefully: provider quotas and response schemas are external dependencies.

## Evaluation rule

Do not treat configured confidence thresholds as measured accuracy. Evaluate models on unseen, time-ordered data and report the dataset, period, sample size, calibration, and baseline alongside any result.
