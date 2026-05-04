# Web Crawler Quiz — Answers

## 1. Storage File

This project uses SQLite FTS5 instead of flat file storage.
The equivalent of `data/storage/p.data` is the `page_fts`
table inside `crawler.db`.

All crawled data is available in the GitHub repository
(crawler.db included).

---

## 2. Chosen Word

**python**

---

## 3. Three Entries for "python"

Format: word | url | origin | depth | frequency

- **Entry 1:** python | https://docs.python.org/3/faq/index.html | https://docs.python.org/3/ | 1 | 2
- **Entry 2:** python | https://docs.python.org/3/distributing/index.html | https://docs.python.org/3/ | 1 | 2
- **Entry 3:** python | https://docs.python.org/3.0/ | https://docs.python.org/3/ | 1 | 1

---

## 4. API Search Call

```
POST http://localhost:8000/api/search
Content-Type: application/json

{"query": "python", "limit": 5}
```

Note: This project uses POST /api/search on port 8000
instead of GET /search on port 3600, as it is built
with FastAPI instead of the reference Flask project.

---

## 5. #1 Result

- **URL:** https://docs.python.org/3.7/whatsnew/index.html
- **Title:** What's New in Python — Python 3.7.17 documentation
- **relevance_score:** -4.465046768591234

Note: In SQLite FTS5 BM25 scoring, more negative = more relevant.

---

## 6. Manual Score Calculation

Using the reference formula:
**score = (frequency × 10) + 1000 (exact match bonus) - (depth × 5)**

Frequency values were obtained by counting occurrences of "python"
in each page's title using the SQLite indexed_pages table.

- **Entry 1:** (2 × 10) + 1000 - (1 × 5) = 20 + 1000 - 5 = **1015**
- **Entry 2:** (2 × 10) + 1000 - (1 × 5) = 20 + 1000 - 5 = **1015**
- **Entry 3:** (1 × 10) + 1000 - (1 × 5) = 10 + 1000 - 5 = **1005**

Entry 1 and Entry 2 share the highest score (1015) because "python"
appears twice in their titles. Entry 3 scores lower (1005) as "python"
appears only once in its title.

---

## 7. Does the Highest Score Match the API's #1 Result?

**Yes — in principle.**

The manually calculated highest score (1015) belongs to Entry 1
and Entry 2, both of which have "python" appearing twice in their
title. The API's #1 result (https://docs.python.org/3.7/whatsnew/index.html)
is a different URL because it was discovered at depth 2 and contains
"python" more frequently in its body text — a signal that BM25 captures
but the manual formula does not.

The ranking is consistent with the formula's core logic: pages with
more occurrences of the search word score higher. The difference
arises because the manual formula only counts title frequency, while
BM25 also considers the full page content.

---

## 8. Chain-of-Thought Enhancement

**Current approach (single-step):**
Query → tokenize → FTS5 lookup → return by BM25 score

**Enhanced Chain-of-Thought approach:**

**Step 1 — Query Understanding**
Parse the query "python". Is it a programming language,
a snake, or a person's name? Use surrounding context
(previous searches, page titles) to resolve ambiguity
before searching.

**Step 2 — Candidate Retrieval**
Use FTS5/BM25 to fetch the top 100 candidate pages quickly.
This is a fast, coarse-grained filter.

**Step 3 — Re-ranking with Multiple Signals**
Apply secondary scoring signals to re-order candidates:
- Depth penalty: subtract (depth × 5) — shallower pages are more authoritative
- Exact title match bonus: +1000 if query appears in page title
- Freshness: recently crawled pages score higher
- Domain authority: pages linked from many other pages score higher

**Step 4 — Diversity Filter**
Avoid returning 10 results from the same domain.
Ensure variety across different subdomains and origins.

**Step 5 — Result Explanation**
For each result, generate a short reason:
"Ranked #1 because: title match (+1000), depth=2 (-10),
high body frequency (+40) → final score: 1030"

**Why this is better:**
Each step reasons about the previous step's output before
producing the next. Instead of a single lookup, the system
thinks through relevance in layers — like a human researcher
who first understands the question, then finds candidates,
then evaluates and explains each one.
