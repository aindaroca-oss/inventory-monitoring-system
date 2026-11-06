# GitHub Pages and separate API deployment

## Current state

This repository contains a Flask/Jinja application. Its HTML templates call Flask routes, use Flask sessions, and load inventory from SQLite. GitHub Pages cannot execute Flask, Python, or SQLite, so publishing the current templates as static files would leave login, inventory, requests, transactions, and administration nonfunctional.

The current plan is to host the complete Flask + SQLite application on PythonAnywhere. GitHub Pages is only suitable if the UI is later rebuilt as a static frontend that calls an HTTP API. The frontend build must not contain database credentials, SMTP credentials, session secrets, or other private keys.

## GitHub Pages target

For a root URL such as `https://USERNAME.github.io/`, the GitHub repository must be named exactly `USERNAME.github.io`. The deployment workflow should run on pushes to `main`, build the static frontend, upload only its generated static output with GitHub Pages Actions, and deploy that artifact. Configure repository **Settings → Pages → Build and deployment → Source → GitHub Actions**.

The target repository is [`aindaroca-oss/inventory-monitoring-system`](https://github.com/aindaroca-oss/inventory-monitoring-system), whose remote `main` branch currently contains only a README. The project Pages URL will be `https://aindaroca-oss.github.io/inventory-monitoring-system/`. This checkout is still on `master`; its `.git` directory is read-only in this environment, so it is not connected to that remote. GitHub CLI authentication is also unavailable here.

## API and secrets

- Configure only a public API base URL in the frontend, for example `https://api.example.com`; it is safe to be visible in browser source.
- Keep `SECRET_KEY`, SMTP credentials, and any API signing keys in the backend hosting provider's secret/environment settings.
- Use HTTPS for the backend API and restrict CORS to the exact Pages origin once the username is known.
- Keep the SQLite database file on the backend host; do not put the database file or its contents in Pages artifacts or frontend files.
- Keep `.env` files out of Git. `.env.example` contains blank placeholders only.

## Before the first deployment

1. Provide the GitHub username and connect this folder to the intended `USERNAME.github.io` repository.
2. Convert the current Jinja pages into a static frontend while preserving the existing design and interactions.
3. Add the HTTP API/authentication layer and configure its Pages origin for CORS and session/token handling.
4. Add the Pages workflow to build and deploy the static frontend on pushes to `main`.
5. If a static Pages frontend is still desired, deploy the Flask API and SQLite database on a separate backend host, then configure the frontend with the public API URL.
