# Free web deployment with GitHub Pages

The web version uses the same dashboard and scan logic as the desktop app. A scheduled GitHub Action runs the seven Finviz filters, stores the SQLite history in `web-data/finviz_history.db`, exports a browser-only data bundle, and publishes it to GitHub Pages. Visitors always receive the newest deployment; they do not install or update an app.

## One-time setup

1. Create a **public** GitHub repository and upload this project. Do not add account passwords, API keys, or other secrets.
2. In the repository, open **Settings → Pages**. Under **Build and deployment**, choose **GitHub Actions** as the source.
3. Open **Actions → Scan and publish website → Run workflow** for the first scan and deployment.
4. When the workflow finishes, its deployment step shows the public `github.io` address. Share that address with the other users.

The included schedule runs at 4:30 PM Monday through Friday in `America/Monterrey`. Edit `.github/workflows/publish-web.yml` if a different time is required. Scheduled jobs can start later than the exact requested minute when GitHub is busy.

## Important behavior

- GitHub Pages is public on the free plan. The published ticker/filter results and the public repository can be viewed by anyone with the URL.
- GitHub Pages is static; it cannot run Python, contact Finviz, or open SQLite when somebody visits. The GitHub Action performs those jobs before publishing.
- The workflow makes up to three bounded scan attempts. If Finviz remains unavailable, the website preserves the honest partial-scan warning instead of treating missing filters as zero.
- Each successful workflow commits only the SQLite history database. Generated debug pages and the deployable `site/` directory are not committed.
- For an immediate update, use **Actions → Scan and publish website → Run workflow**. No visitor needs to reinstall anything.

## Preview the static website locally

```bash
.venv/bin/python -m src.static_site --db data/finviz_history.db --output site
.venv/bin/python -m http.server 8766 --directory site
```

Then open `http://127.0.0.1:8766`. Do not open `site/index.html` directly because browsers restrict module scripts loaded from `file://` URLs.

With the optional browser-test dependencies installed, verify the generated site with:

```bash
.venv/bin/python scripts/check_static_site.py
```
