# SerpApi India Hackathon 2026: submission notes

Official pages checked on 12 Oct 2026: [site](https://serpapi.github.io/serpapi-india-hackathon-2026/), [rules](https://serpapi.github.io/serpapi-india-hackathon-2026/rules.html), [terms](https://serpapi.github.io/serpapi-india-hackathon-2026/terms.html). **Deadline: 12 Oct 2026, 23:59 IST.** Drafts do not count until you press "Submit project". This file is a checklist, not a guarantee of eligibility or of winning: SerpApi alone decides what counts as meaningful usage.

## How SerpApi is used (copy into the submission form)
SerpApi is the live evidence layer, through the official Python SDK (`pip install serpapi`, `serpapi.Client`):
| Engine | Where | Why |
|---|---|---|
| `google_scholar` | Paper search (merged with 5 free scholarly APIs) and the agent's `search_scholar` tool | Citation counts and papers the open APIs miss |
| `google` | Agent tool `search_web` | Datasets, code, official pages and tutorials a student needs to build a project |
| `google_news` | Agent tool `search_news` | Recent developments, so gaps are not based on stale papers |
| `google_patents` | Agent tool `search_patents` | Prior-art check: has an applied project idea already been patented? |
| `google_trends` | Agent tool `check_trend` | Is interest in the topic rising or falling (computed from the 5-year time series)? |

The **Research agent** page runs a tool loop: the AI replies with JSON choosing a tool and query, the app calls SerpApi, the results are fed back, and after at most 5 searches the AI writes a brief that may cite only the returned results (`[n]` links to the source list). The page shows every tool call. If no AI is available the same three searches run as a fixed plan with an extractive digest, and the page says so. Results are cached 24 h (saves credits), errors are mapped to readable messages (401, 429, timeout).

Not used: `serpapi-search-tools` package, SerpApi MCP, and the other ~100 engines (shopping, maps, flights, etc. do not help academic discovery). The Google Scholar Profiles API is documented as discontinued, so it is not used. Do not claim any of these.

## Originality warning (read before writing the description)
The official showcase already lists **ResearchRadar** (Google Scholar -> themes -> research gaps) and **Research Brief Bot** (Scholar + News + Search -> brief). Judges score originality, so do not pitch "papers + gaps + brief" alone. What this project adds, and what is actually in the code: 5 free scholarly APIs merged with Scholar; side-by-side paper comparison; patent prior-art and trend checks inside the agent; a student **project planner** (week-by-week roadmap); Beginner/Technical modes; no-login private workspaces; provenance labels on every output. Lead with "from a research question to a finishable student project", not "paper search".

## What I could not read
The site's Resources, Tracks and Timeline sections were not available as text (they appear to load dynamically), and the submission dashboard form only shows "Loading". Track names come from the Rules page. Open the Resources section yourself and check nothing there adds a requirement.

## Requirement matrix
| Requirement (official) | Status | Evidence | Check |
|---|---|---|---|
| Live SerpApi data central to the project | Done in code; **needs a live run with your key** | `services/serpapi_service.py`, `services/agent_service.py`, `views/agent.py` | Add key, run agent, see 3 tool calls with URLs |
| Explain which SerpApi products/engines and why | Done | section above | paste into form |
| Public GitHub repo + setup instructions | **You must do** | README.md | open the repo in a private window |
| Screen demo < 3 min, runs locally, public/unlisted link | **You must do** | script below | check link in incognito |
| One track chosen | **You must decide** | Fits *AI Agents* or *Knowledge & Public Interest* | SerpApi may move it |
| Disclose project predates hackathon | **You must do** | project existed before | form field |
| AI tools disclosure | **You must do** | e.g. Claude (code assistance), Gemini (runtime AI) | form field |
| No API keys / personal data in repo | Checked: no keys in files; `.env` and `data/` git-ignored | `.gitignore` | `git ls-files | grep -i env` before pushing |
| Team details, phone, rules + terms acceptance | **You must do** | dashboard | |

Tested offline (fake SerpApi + AI): parsers, caching, error mapping, agent loop passes step-1 results to step 2, fixed-plan fallback, missing key. **Never tested against live SerpApi or Gemini.** Run it once before recording.

## Auth, plans, pricing
No login or accounts by your earlier decision; workspaces use a private `?space=` link, so there is no sign-in screen to fake. Pro licence code stays off unless `LICENSE_SECRET` is set; no payment is integrated, so the app does not claim purchases work.

## Demo script (about 2:30, screen recording, local)
1. 0:00 Title + one line: "Turns a research question into evidence, a comparison, gaps and a project plan." Show `.env` is not in the repo (don't show keys).
2. 0:15 Home → pick Beginner mode → search "explainable AI for intrusion detection". Show merged results with source badges including Google Scholar.
3. 0:45 Filters (survey only, open access) → tick 3 papers → Compare → table.
4. 1:15 **Research agent** → run → point at the trace: Scholar, then Web, then News, with result counts, and the cited sources with links.
5. 1:50 Open one paper → Find research gaps → note the "AI interpretation" label.
6. 2:10 Project planner → 12-week plan → save to workspace → download PDF.
7. 2:30 Close: "SerpApi supplies the live evidence; every claim links to a source."

## Final checklist
- [ ] `.env` filled locally, one full live run works (search, agent, gaps)
- [ ] `git ls-files` shows no `.env`, no `data/`
- [ ] Public repo opens in a private window; README setup works from scratch
- [ ] Video < 3 min, unlisted/public, opens in incognito
- [ ] Form: track, predates-hackathon = yes, AI tools, team, SerpApi usage text above
- [ ] Press **Submit project** before 23:59 IST

## Live check (run before recording)
`python scripts/smoke_test.py` calls every SerpApi engine, the free paper sources, the AI model and the agent once, and prints PASS/FAIL (about 5 SerpApi credits).
