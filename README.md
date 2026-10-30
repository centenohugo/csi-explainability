# Telecom bachelor's thesis (TFG): code and experiments

Working repository for the thesis: proofs of concept, dataset download and analysis and, later on,
the implementation.

## Layout

```
exploration/   Dated experiments (YYYY-MM-DD_topic/). Each one has a NOTES.md: what was tried,
               what came out and what is pending. Versioned even if never reused: it is the
               record for the thesis write-up.
src/           Reusable code, once something in exploration/ is consolidated.
data/          Not versioned (see data/README.md). raw/ = full datasets, samples/ = samples.
docs/          Log and documentation.
```

Branches:
- `main`: everything worth keeping, exploration included.
- `feat/...` branches once implementation of something specific starts.

## Environment

```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

## Log

See [docs/LOG.md](docs/LOG.md).
