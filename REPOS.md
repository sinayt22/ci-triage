# Candidate repos for CI failure sourcing

## Tried
- encode/httpx        — too few recent failed runs in the 90-day window, deprioritized

## Original picks (not yet tried)
- pandas-dev/pandas     — heavy CI matrix, high PR volume
- pytest-dev/pytest     — thematically apt, rigorous root-cause discussions
                          (worth a quick --limit 5 probe first — same "might be thin" risk as httpx)
- huggingface/transformers — heavy CI, rich source of dependency-or-env cases

## Suggested as higher-volume alternatives (not yet tried)
- apache/airflow          — real infra/config failures (DB, Docker, external services)
- ray-project/ray         — distributed systems testing, likely rich source of flaky-test
- scikit-learn/scikit-learn — heavy OS/numpy/scipy matrix
- pytorch/pytorch         — huge CI volume, but noisier/more C++-CUDA mixed in

## Secondary mention
- matplotlib/matplotlib   — rendering-related flakiness, mid-size