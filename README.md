# Research Intelligence Platform

A Streamlit research workspace for discovering academic papers, exploring current web context, reviewing recent research-related news, comparing evidence, and turning research questions into practical student project plans.

## Highlights

- **Multi-source academic search:** OpenAlex, Semantic Scholar, arXiv, Crossref, Europe PMC, and Google Scholar through SerpApi.
- **Research Radar:** one workflow for Google Scholar, Google Search, and Google News, powered by SerpApi's official Python SDK and Search Tools package.
- **AI-assisted paper analysis:** summaries, possible research gaps, comparison, and project planning using configured AI providers, with extractive fallback when AI is unavailable.
- **Full-text support:** open-access links, Unpaywall discovery, arXiv PDFs, and user-uploaded PDFs. Publisher restrictions such as HTTP 403 are reported clearly; abstract fallback remains available.
- **Research organization:** workspaces, citations, and Markdown/Word/PDF exports.
- **Security basics:** API keys are read from environment variables; `.env`, databases and virtual environments are excluded from Git.

## Quick start (Windows)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and add keys for the services you want to use, then run:

```powershell
python -m streamlit run app.py
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python -m streamlit run app.py
```

## API configuration

- `SERPAPI_KEY`: enables Google Scholar, Google Search, Google News and Research Radar. Get a key from [SerpApi](https://serpapi.com/users/sign_up?plan=free).
- `GEMINI_API_KEY`: enables live AI analysis. Optional `GROQ_API_KEY` and `OPENROUTER_API_KEY` can provide additional AI fallbacks.
- `CONTACT_EMAIL`: recommended for polite API access and Unpaywall open-access lookup.
- `OPENALEX_API_KEY`: recommended for higher OpenAlex allowance.
- `S2_API_KEY`: optional Semantic Scholar key.

Only configure the keys you have. Without a SerpApi key, the free scholarly sources remain available; without an AI key, live AI synthesis is unavailable and the app uses its supported offline fallbacks. Never paste secrets into source code or commit `.env`.

## Research Radar workflow

1. Enter a research topic.
2. Run a cross-source sweep across Google Scholar, Google Search and Google News.
3. Review scholarly results separately from webpages and news.
4. Generate an AI research brief from retrieved snippets and metadata when an AI provider is configured.
5. Verify important claims by opening the original source links.

Search result snippets are discovery aids, not proof. News is not a substitute for peer-reviewed research, and an apparent gap is a hypothesis rather than proof of novelty.

## Tests

```bash
pytest -q
```

The test suite uses mocked API responses and should not require paid API calls.

## Deployment

For a Streamlit-compatible host, use:

```bash
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

Set secrets as host environment variables instead of uploading `.env`. Persistent SQLite workspaces require a host with persistent disk; ephemeral hosts can erase local data on restart. Configure a persistent `DB_PATH` where supported.

## Important limitations

- API providers enforce quotas and rate limits; search results may be cached.
- Some publishers block automated full-text downloads. The platform does not bypass access controls; use legal open-access copies or an uploaded PDF you are entitled to use.
- Scanned PDFs need OCR, which is not currently included.
- The local sign-in implementation is an MVP, not a production identity system. For a public deployment, use a mature identity provider and review session management, account recovery, privacy and security requirements.
- AI-generated summaries and research gaps require human verification against original sources.

## Project layout

```text
app.py
services/       # search, paper retrieval, AI, citations, exports, storage
views/          # Streamlit pages and shared UI
 tests/         # offline tests
.env.example    # documented configuration template
```


## Research Agent (SerpApi)
The **Research Agent** page lets the AI choose between Google Scholar, Search, News, Patents and Trends through SerpApi, read the results, and write a brief that cites only them. Details, demo script and submission checklist: `HACKATHON.md`.

**Hosting note:** on free hosts the SQLite file is wiped on restart, so accounts, workspaces and caches reset. Guest mode and JSON backups still work.
