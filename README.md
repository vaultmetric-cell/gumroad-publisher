# Gumroad Auto-Publisher

One command. Clean folder. Versioned ZIP. Live on Gumroad.

```bash
./publish.sh
```

---

## What It Does

| Stage | What happens |
|-------|-------------|
| **1 · Version** | Reads `.version`, bumps patch/minor/major, or accepts an explicit `X.Y.Z` |
| **2 · Staging** | Copies your source files into a clean `builds/dist/<slug>-vX.Y.Z/` tree |
| **3 · Docs** | Auto-generates `README.md` and `CHANGELOG.md` from Jinja2 templates |
| **4 · ZIP** | Compresses the staging dir, writes a `SHA-256` sidecar for integrity |
| **5 · Upsert** | Creates the product on Gumroad if new; updates metadata if it already exists |
| **6 · Upload** | Attaches the ZIP to the product (removes old files first) |
| **7 · Publish** | Flips the product live (or saves as draft with `--unpublish`) |
| **8 · Receipt** | Writes a timestamped JSON receipt and appends to the persistent log |

---

## Quick Start

```bash
cd gumroad-publisher
cp .env.example .env
# Add your token to .env
pip install -r requirements.txt
./publish.sh
```

---

## CLI Reference

```
./publish.sh                     # patch bump, publish live
./publish.sh --bump minor        # minor version bump
./publish.sh --version 2.0.0    # explicit version
./publish.sh --dry-run          # build ZIP only, no API calls
./publish.sh --skip-upload      # update metadata only
./publish.sh --unpublish        # save as draft
./publish.sh --watch            # watch for file changes
```

---

## Security

- Never commit your API token. Use `.env` or export the env var.
- `.env` and `builds/` are in `.gitignore` by default.

---

*Built for repeatable, zero-friction Gumroad releases.*
