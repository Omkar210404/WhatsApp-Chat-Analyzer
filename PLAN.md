# PLAN — whatsapp-chat-analyzer

A Streamlit app, plus a reusable Python module, that analyzes an exported WhatsApp chat `.txt` file entirely on the user's own machine.

Status: **approved 2026-10-10**, with the defaults in section 11.

## 1. Environment (inspected 2026-10-10)

| Item | Found |
|------|-------|
| OS / shell | Windows 11, PowerShell |
| Python | 3.11.9 (Microsoft Store build, no `py` launcher) |
| Global packages | numpy and pillow only; streamlit, pandas, pytest **not** installed |
| Internet / PyPI | reachable; latest listed: streamlit 1.65.0, wordcloud 1.9.6, emoji 2.16.0 |
| Browsers | Chrome and Edge installed; a Playwright Chromium is cached, the Playwright Python package is not installed |
| Git | 2.49.0, identity `Omkar210404 <omkarnikamofficial21@gmail.com>`, sibling repos use `main` |
| GitHub CLI | `gh` not installed, so creating the GitHub repo and pushing is a manual step |
| GPU | not needed |

Consequence: everything runs in a project-local `.venv` (git-ignored). The repo is already initialised (`git init -b main`), nothing committed yet.

## 2. Scope

In: read one exported chat, parse it, show statistics and charts, filter by person.
Out: no account login, no WhatsApp API, no database, no sentiment or ML, no hosted demo. A hosted demo would mean uploading chats to someone else's server, which contradicts the point of the tool.

## 3. Parsing approach

One compiled regular expression per export style decides whether a line **starts a new message**. A line that does not match is a continuation and is appended to the previous message with a newline, which is how multi-line messages are kept together.

Supported line shapes (names are fictional):

| Style | Example |
|-------|---------|
| Android, 24-hour | `25/12/2023, 21:15 - Mira: Happy holidays!` |
| Android, 12-hour | `12/25/23, 9:15 PM - Mira: Happy holidays!` |
| iPhone, 24-hour | `[25/12/2023, 21:15:03] Mira: Happy holidays!` |
| iPhone, 12-hour | `[12/25/23, 9:15:03 PM] Mira: Happy holidays!` |
| Android system line (no sender) | `25/12/2023, 21:00 - Mira created group "Hiking Club"` |

Details the parser handles:

- **Date**: separators `/`, `.` or `-`; 2 or 4 digit year; year-first dates when the first part has 4 digits.
- **Day-first or month-first**: detected from the whole file. If any first part is above 12 the file is day-first, if any second part is above 12 it is month-first. If every date is ambiguous, the order that keeps timestamps in ascending order wins, and day-first is the final fallback. The app shows the detected order and has a manual override.
- **Time**: seconds optional; AM/PM optional, any case, with or without dots (`pm`, `PM`, `p.m.`); the space before AM/PM can be a normal space, a no-break space or the narrow no-break space newer exports use.
- **Hidden characters**: UTF-8 BOM and the left-to-right marks iPhone puts at the start of lines are stripped. LF and CRLF line endings both work.
- **Sender**: the text before the first `: ` after the timestamp. System patterns are checked against the whole line first, so a system line that happens to contain `: ` is not mistaken for a message.

Every parsed message gets a `kind`:

| kind | What it is | Counted as a message | Used for words and emojis |
|------|------------|----------------------|---------------------------|
| `text` | a real message | yes | yes |
| `media` | `<Media omitted>`, `image omitted`, `video omitted`, `sticker omitted`, `GIF omitted`, `audio omitted`, `document omitted`, `<attached: ...>`, `... (file attached)` | yes | no |
| `deleted` | `This message was deleted`, `You deleted this message` | no, reported separately | no |
| `system` | encryption notice, created group, added, removed, joined, left, changed the subject / icon / description, security code changed, disappearing messages | no | no |

Output: a list of `Message` dataclasses (`timestamp`, `sender`, `text`, `kind`) plus a `ParseResult` carrying the detected style, date order, clock type and the number of lines that could not be attached to any message. `to_dataframe()` turns it into a pandas DataFrame for the analysis functions.

## 4. Features

| Area | What is shown |
|------|---------------|
| Overall | total messages, words, media count, links shared, deleted count, people, first and last date, active days |
| Per person | messages, share of total, words, average message length (words and characters), media, links; bar chart of the most active people |
| Time | messages per day (line), per hour of day (bar), per weekday (bar), weekday by hour heatmap (7 x 24) |
| Words | top N words after lower-casing, removing links, numbers and stopwords; bundled English stopword list plus a text box for custom stopwords |
| Emojis | top N emojis, counted with the `emoji` package so skin tones and joined emojis count as one |
| Word cloud | optional, behind a checkbox; uses the same stopwords |
| Filter | "Everyone" or one person; applies to every view except the people comparison, which always shows the whole group |
| Input | upload a `.txt`, or the `.zip` iPhone produces (read in memory), or click "Use the synthetic sample" |

Charts use Altair, which Streamlit already depends on and bundles, so there is no extra chart dependency and no CDN request.

## 5. Privacy design

- The parser and analysis modules do plain in-memory text processing. They import no networking code; a test checks this.
- `.streamlit/config.toml` sets `browser.gatherUsageStats = false`, because Streamlit sends usage telemetry by default, and `server.address = "localhost"`, so the app is not reachable from other devices on the network.
- The uploaded file stays in the memory of the local Streamlit process. The app never writes it to disk and never logs message text.
- No custom web fonts or external scripts.
- The screenshot script records every network request the page makes and fails if any goes to a host other than localhost. The README will report what that run actually showed.
- The app shows a short "runs on your machine" notice above the uploader. The README gets a Privacy section that also says what this does **not** cover (for example, deploying the app to a public host yourself).

## 6. File layout

```
whatsapp-chat-analyzer/
├── app.py                        Streamlit UI only, no parsing or maths
├── whatsapp_analyzer/
│   ├── __init__.py
│   ├── parser.py                 text -> messages -> DataFrame
│   ├── analysis.py               pure functions over the DataFrame
│   ├── text.py                   tokenizer, stopwords, emojis, links
│   └── stopwords_en.txt
├── scripts/
│   ├── generate_sample_chat.py   builds the synthetic sample
│   └── capture_screenshots.py    dev only, Playwright
├── examples/
│   ├── sample_chat_android.txt   synthetic
│   └── sample_chat_iphone.txt    synthetic, same conversation
├── tests/
│   ├── conftest.py
│   ├── test_parser.py
│   ├── test_analysis.py
│   ├── test_sample_data.py
│   ├── test_privacy.py
│   └── test_app_smoke.py
├── docs/screenshots/
├── .streamlit/config.toml
├── .github/workflows/tests.yml
├── requirements.txt              streamlit, pandas, altair, emoji, wordcloud (pinned)
├── requirements-dev.txt          pytest, playwright (pinned)
├── pytest.ini  .gitignore  .gitattributes  LICENSE  README.md  PLAN.md
```

No `.env.example`: the project has no secrets and reads no environment variables, so the file would be misleading. This is the one deliberate departure from the brain.md checklist.

## 7. Sample data design

`scripts/generate_sample_chat.py` writes both example files from one fixed random seed, so the output is identical on every run.

- A fictional group, "Hiking Club (synthetic sample)", with five fictional members and invented text about planning hikes.
- The first message in the chat says it is a synthetic sample made by the script, so the file is labelled without breaking the export format.
- About three months of chat, in the low thousands of messages at most. Exact counts will be read from the real run, not stated in advance.
- Uneven on purpose so the charts have shape: some members talk more, evenings and weekends are busier, a few quiet days.
- Contains every case the parser must handle: multi-line messages, media placeholders, links (`example.com` only), emojis, a deleted message, system lines (encryption notice, group created, member added, member left, subject changed), a message containing `: ` and ` - `, and a continuation line that begins with a number.
- The same conversation is written once in Android style (day-first, 24-hour) and once in iPhone style (brackets, seconds, 12-hour).

`.gitignore` blocks `*.txt` and `*.zip` by default and allow-lists only `requirements*.txt`, the stopword list and `examples/sample_chat_*.txt`. It also ignores `chats/`, `exports/` and `private/`. A real export dropped anywhere in the repo is ignored without anyone having to remember.

## 8. Tests

| File | What it checks |
|------|----------------|
| `test_parser.py` | each of the four line shapes; AM/PM variants including narrow no-break space; multi-line joining; system, media and deleted classification in both styles; day-first and month-first detection and the ambiguous fallback; BOM, LRM and CRLF handling; empty input; a file with no valid lines |
| `test_sample_data.py` | both sample files parse with zero unattached lines; the Android and iPhone samples give the same senders, kinds, text and minute-level timestamps; running the generator again reproduces the committed files byte for byte |
| `test_analysis.py` | overall and per-person numbers against a small hand-written chat where the right answers are known by counting; hour, weekday and heatmap shapes and totals; stopword and custom stopword filtering; emoji counting with skin tones; link counting; person filter; empty DataFrame |
| `test_privacy.py` | the package modules import no networking modules; `.streamlit/config.toml` has telemetry off |
| `test_app_smoke.py` | the Streamlit app runs on the sample through `streamlit.testing` with no exception |

CI: GitHub Actions on every push and pull request, Ubuntu and Windows, Python 3.11 and 3.13, same shape as the job-tracker-cli workflow. README carries the badge.

## 9. Build order (one commit per step, no co-author or session lines)

1. Repo scaffolding: `.gitignore`, `.gitattributes`, LICENSE, PLAN.md
2. Pinned requirements, `pytest.ini`, Streamlit config
3. Parser with its tests
4. Sample generator with the two generated files and their tests
5. Text helpers (stopwords, tokenizer, emojis, links) with tests
6. Analysis functions with tests
7. Streamlit app: upload, sample button, overall stats
8. People and time tabs
9. Words, emojis and word cloud tab
10. Privacy test and app smoke test
11. GitHub Actions workflow
12. Screenshots from the synthetic sample, then README

After step 12: full test run, launch the app, try at least five inputs (both samples, a 12-hour month-first file, a `.zip`, an empty file, a non-chat text file), then the Definition of Done checklist and a final report.

## 10. Risks and limits

| Risk | Handling |
|------|----------|
| **I have no real export to check against**, and must not use one. The formats above come from documented export shapes, not from a file on this machine. | Parser is tolerant by design; the app shows the detected style and how many lines failed to parse. You test on your own export locally and tell me only about format problems, never content. |
| Export format varies by phone language and region | English system and media phrases only. In other languages those lines may be counted as normal messages. Stated in the README. |
| All dates ambiguous (every day number is 12 or below) | Ascending-order check, day-first fallback, manual override in the sidebar |
| A multi-line message whose continuation line looks exactly like a message header (a pasted chat) | Parsed as a new message. Documented limitation. |
| A sender name containing `: ` | Split at the first `: `. Documented limitation. |
| Timestamps have no time zone | Shown as exported, in the exporting phone's local time |
| Word cloud needs a compiled wheel | `wordcloud` is imported only when the checkbox is ticked; the rest of the app works without it |
| Emoji glyphs in charts and screenshots depend on system fonts | Checked visually when screenshots are captured |
| Python 3.13 and Ubuntu can only be verified by CI after the first push | I report local 3.11 results only; the badge shows the rest once you push |
| Stopwords are English only | Custom stopword box; other languages listed under future ideas |

## 11. Defaults I will use unless you say otherwise

1. **GitHub repo for the badge and clone URL**: `Omkar210404/WhatsApp-Chat-Analyzer`, matching how the sibling repos are named. You create the repo and push; `gh` is not installed here.
2. **Charts**: Altair rather than Plotly.
3. **Deleted-message placeholders** are not counted as messages and are shown as their own number.
4. **`.zip` upload** is included, since iPhone always exports a zip.
5. **Screenshots** are captured with Playwright driving the installed Chrome, on the synthetic sample only.
6. **Python package name**: `whatsapp_analyzer`.
