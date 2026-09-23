# Nigerian Exam Formats — Source-Verified Research (2026)

Research for Sabi exam simulators. Every claim below is sourced, dated, and
confidence-rated. Written incrementally during research; see per-body
sections for full detail behind each summary line below.

Retrieval date for all entries unless stated otherwise: 2026-09-23.

---

## Contradicts the brief

1. **WAEC's "choose CBT or paper" claim is an oversimplification.** For the May/June 2026 WASSCE (school candidates), WAEC ran CBT as a **pilot limited to schools with adequate ICT facilities** — participation was effectively a school-level infrastructure decision, not a free per-candidate opt-in choice. Schools without ICT facilities used community-based CBE centres. Meanwhile the **Nov/Dec 2026 WAEC GCE (private candidates, 2nd series)** appears to have already gone **fully Computer-Based** (a hybrid: objective on computer, essay questions shown on screen but answered in physical booklets) — i.e. private candidates were moved to CBT on a different (faster) timeline than school candidates, not offered a "choose CBT or paper" option either. Full national CBT for WASSCE school candidates is confirmed pushed to 2027. See §2.

2. **NECO objective papers almost certainly use FIVE options (A–E), not four (A–D).** This directly matches the brief's own warning not to assume the option count — multiple independent NECO past-paper transcriptions across different subjects (Economics, Marketing, English Studies, Book Keeping) consistently show "five options lettered A – E." This is probable, not confirmed at an official neco.gov.ng source, but it is a real and important divergence from the JAMB/WAEC 4-option convention. See §3.

3. **JAMB's CBT keyboard controls could not be confirmed at an official source**, despite the brief presenting them as settled fact (A/B/C/D, N, P, S, Y, R, and arrow keys). See "Could not confirm" below and §1 for the full account of what was and wasn't reachable.

4. **No source found mentions arrow-key navigation for JAMB's CBT.** Every independent walkthrough of the "CBT without mouse" key set (a dozen+ sources) enumerates the same closed set of 8–9 keys (A,B,C,D,N,P,S,Y,R) with no arrow-key mention. This is absence-of-evidence rather than a positive denial, but it means the brief's claim of "arrow keys to move" should not be assumed true. See §1.

5. **WAEC's 2026 subject-combination change is real but the brief's framing needs correction/detail**: it is not simply "a cap on number of subjects" (the 7–9 subject range appears to be long-standing, not new for 2026). The actual reported 2026 change is a **new restriction barring Science and Arts candidates from offering Economics** (Economics now Commercial/Business-only) plus a **new requirement to register at least one trade subject**. See §2.

---

---

## RESOLVED BY THE LEAD, 2026-09-23 — JAMB's keyboard bindings, confirmed at source

The research pass above could not read JAMB's own manual: one PDF resisted text
extraction and the other is scanned-image-only, and that sandbox had no
rasteriser. **It has now been read.** `pypdf` extracts 28,622 characters of text
from the Step-by-Step manual, and the screenshots embedded in it were extracted
and read directly.

Source, read at origin on 2026-09-23:
`https://jamb.gov.ng/PDFs/2024/RAPID_TEST_MULTILENT_JAMB_2024_CBT_Manual.pdf`
— "STEP-BY-STEP CBT MANUAL, JAMB Unified Tertiary Matriculation Examination
(UTME)", 50 pages.

### The Keyboard Usage panel, page 46, verbatim

JAMB's own manual (page 45 text) says the candidate instruction page carries a
"Keyboard Usage" section "showing the candidate(s) the various keyboard symbols
they can use". That panel is a screenshot on page 46. It reads:

| Key | Label in the manual |
|---|---|
| `A` | Select Option A |
| `B` | Select Option B |
| `C` | Select Option C |
| `D` | Select Option D |
| `N` **or** `→` | Next / Forward |
| `P` **or** `←` | Previous / Back |
| `↑` | Move Up |
| `↓` | Move Down |
| `S` | Submit / End Exam |

### The End Examination dialog, page 50, verbatim

> END EXAMINATION
> Dear Candidate,
> You are about to end your exam
> Total Questions Attempted is 43
> **Press `R` to continue Exam, Press `Y` to end Exam**

with `Continue Exam` and `End Exam` buttons.

### What this changes

- **Contradiction 3 above is withdrawn.** The bindings are now **confirmed at
  an official source**, not probable. The brief was right.
- **Contradiction 4 above is withdrawn and inverted.** Arrow keys *are*
  documented by JAMB: `→` is an alias for Next, `←` for Previous, and `↑`/`↓`
  are Move Up / Move Down. The secondary sources that enumerate only 8–9 letter
  keys are incomplete, not authoritative. The brief was right again.
- `Y` and `R` are **confirmed**, and their meaning is now exact: on the End
  Examination dialog, `Y` ends the exam and `R` *continues* it — i.e. `R`
  cancels the submit. The brief's "R cancel an accidental submit" is correct.
- The confirmation dialog shows the **count of questions attempted**. Our
  simulator should do the same; it is the last thing a candidate sees before
  committing.

### Structure, also confirmed from the same manual's screenshots

| Claim | Evidence | Confidence |
|---|---|---|
| Exam duration 2 hours | Candidate Details panel, p.45: "Exam Duration: 2 Hour(s)" | confirmed |
| Four subjects | Candidate Details panel, p.45 lists four | confirmed |
| Use of English has 60 questions | Candidate Details panel, p.49: "ATTEMPTED 0 OF 60 / USE OF ENGLISH" | confirmed |
| 180 questions in total | Same panel: "Total Questions Attempted: 0 OF 180" | confirmed |
| Per-subject counts of 40 for the other three | Implied by 180 − 60 = 120 over three subjects; not stated verbatim | probable |
| Candidate Details shows seat number and a QR code | p.49 screenshot | confirmed |

### Caveat that remains

This is the **2024** manual. JAMB's downloads page references a "2027 JAMB Test
Manual (Updated 18-09-2026)" whose path was not resolved. Before Phase 6 ships,
re-check the current manual — the `exam_formats/*.yaml` config carries
`source_url` and `verified_on` precisely so this can be re-checked each season.
Nothing above should be treated as permanent.

---

## Could not confirm

- **JAMB's exact CBT keyboard bindings at an official source.** Two official jamb.gov.ng PDFs were located and downloaded (the 2024 "STEP-BY-STEP CBT MANUAL" and the 2024 Examination Manual) but neither could be read: one is a garbled/compressed PDF that resisted text extraction, the other is scanned images with no OCR tool available in this sandbox (no `pdftoppm`/poppler installed). A newer, more promising official document — **"2027 JAMB Test Manual (Updated 18-09-2026)"**, referenced directly on jamb.gov.ng's own downloads page — was identified but its real PDF path was not resolved in time. The widely-reported A/B/C/D+N/P/S/Y/R bindings therefore remain **probable, not confirmed**. This is the single biggest risk in this document — see §1 for the full trail.
- **JAMB's exact question/subject/scoring structure (180 questions, 60+40+40+40, 2 hours, /400, options A–D) at an official jamb.gov.ng source** — reached only secondary aggregator sites and Wikipedia; the two official PDFs above could not be machine-read to cross-check.
- **WASSCE paper structure specific to Nigeria (Paper 1 objective / Paper 2 essay timings)** — only found on the WAEC **Ghana** site (waecgh.org), not waecnigeria.org; likely similar but not verified for the Nigerian office specifically.
- **WASSCE option count (assumed A–D)** — not verified against any 2026 WAEC Nigeria source this session; flagged explicitly, not confirmed.
- **Exact WAEC 2026 subject-cap numbers** — sources disagree on whether the compulsory core is English+Maths (2 subjects) or English+Maths+Civic Education (3), and on whether the minimum subject count is 7 or 8.
- **NECO's exact subject-count rule (min 8, max 9)** — single-pass aggregation, not cross-checked against neco.gov.ng directly (its homepage returned no substantive extractable content to the fetch tool used).
- **NECO SSCE internal/external fee figures** — single blog source, not verified against neco.gov.ng, and fees change yearly.
- **NABTEB's exact 2026 registration/exam dates** — the official announcement page returned an HTTP 500 error when fetched directly this session; the dates used here come from a search-result snippet of that same official page, not a full direct read.
- **NABTEB per-subject paper structure and compulsory/elective subject lists** — only found via secondary aggregators paraphrasing syllabus PDFs; the syllabus PDFs themselves were not opened.
- **University of Ibadan's Post-UTME details (200-cutoff, CBT format)** — sourced from a search snippet of the official ui.edu.ng page, not a full direct fetch/read.
- **UNILORIN's Post-UTME aggregate weighting (50/30/20)** — single non-.edu.ng community source, not cross-checked against unilorin.edu.ng.
- **BECE/Junior WAEC, NCEE state-vs-national variants, and JUPEB/IJMB paper structure and grading** — only minimally investigated per the brief's own "briefly" instruction; treat as unresearched placeholders, not findings.

---

## 1. JAMB UTME

### Structure (subjects, questions, duration, scoring)

- Claim: Candidates register for 4 subjects; Use of English is compulsory, plus 3 others chosen to match the candidate's desired course/institution.
  Source: https://en.wikipedia.org/wiki/Unified_Tertiary_Matriculation_Examination
  Type: community (Wikipedia, treated as secondary/tertiary aggregator, not "official")
  Retrieved: 2026-09-23
  Confidence: probable

- Claim: Total 180 questions: Use of English has 60, the other three subjects have 40 each.
  Source: https://www.schoolngr.com/news/how-many-questions-are-in-jamb ; corroborated by multiple independent secondary sites (allschool.ng, smartsmssolutions.com, myeduvantage.com) all citing the same breakdown.
  Type: news/community (education-news aggregator sites, not the exam body itself)
  Retrieved: 2026-09-23
  Confidence: probable

- Claim: Exam duration is 2 hours, and "cannot be altered under any circumstance."
  Source: https://www.schoolngr.com/news/how-many-questions-are-in-jamb (phrasing strongly suggests it is paraphrasing JAMB's own examination manual, but the manual itself could not be machine-read this session — see "Could not confirm")
  Type: news/community
  Retrieved: 2026-09-23
  Confidence: probable

- Claim: Total score is out of 400, i.e. each of the 4 subjects contributes up to 100 marks.
  Source: https://en.wikipedia.org/wiki/Unified_Tertiary_Matriculation_Examination ("Test scored on scale of 0–400")
  Type: community
  Retrieved: 2026-09-23
  Confidence: probable

- Claim: Each question has 4 options, lettered A–D.
  Source: WebSearch aggregation of schoolngr.com / unibeginner.com results (2026 JAMB exam-format explainers), consistent with the A/B/C/D keyboard-selection convention below.
  Type: news/community
  Retrieved: 2026-09-23
  Confidence: probable

**Attempts to reach JAMB's own primary documents for the above:** I located what should be the authoritative official PDFs on jamb.gov.ng itself —
`https://www.jamb.gov.ng/pdfs/2024/2024_EXAMINATION_MANUAL(updated).pdf` and
`https://jamb.gov.ng/PDFs/2024/RAPID_TEST_MULTILENT_JAMB_2024_CBT_Manual.pdf` — but both are scanned/image-based PDFs that could not be OCR'd or rendered in this research session (the sandbox lacks a PDF-rasterizer). I could not substitute a text-readable official document in the time available. Treat the structure claims above as **probable, not confirmed**, until someone re-checks against those two PDFs (or `ibass.jamb.gov.ng`) with an OCR-capable tool.

### CBT keyboard controls — the brief's single most important claim

- Claim: Candidates can select an answer with the A/B/C/D keys, move to the next question with N, move to the previous question with P, submit with S, confirm submission with Y, and undo an accidental submission with R. Collectively referred to in candidate-facing material as "CBT without mouse" or the "9 keys" / "ABCD PN SRY" system.
  Source: aggregated and cross-checked across https://allschool.ng/keyboard-shortcuts-for-jamb-candidates/ , https://edupadi.com/blog/how-to-answer-jamb-questions/ , https://ulearngo.com/blog/ng/jamb-cbt-tutorial , https://academicful.com/how-to-use-jamb-8-keys/ , https://jamb2025.com/jamb-how-to-answer-questions-using-mouse-touchpad-and-keyboard/ , and JAMB-themed YouTube tutorials ("9 JAMB CBT Keyboard Shortcut Keys to Know")
  Type: community (education/prep blogs and YouTube tutorials; **none of these are jamb.gov.ng itself**)
  Retrieved: 2026-09-23
  Confidence: probable — NOT independently confirmed at an official jamb.gov.ng source this session. Flagged per the brief's explicit instruction: **do not treat this as confirmed.**

- Claim: **Arrow-key navigation is NOT part of the documented JAMB CBT control scheme.** Every source found (a dozen+ independent prep-site walkthroughs and two dedicated YouTube tutorials on "JAMB CBT keyboard shortcuts") describes the same closed set of 8–9 keys (A, B, C, D, N, P, S, Y, R) and none mentions arrow keys as an alternative or supplementary navigation method.
  Source: same set as above, notably https://ulearngo.com/blog/ng/jamb-cbt-tutorial and https://myschoolgist.com/news/jamb-utme-guide/ ("2026 JAMB UTME Guide: Batch Timings, Keyboard Shortcuts & Tips") which enumerate the full key list without arrow keys
  Type: community
  Retrieved: 2026-09-23
  Confidence: probable (absence-of-evidence, not a positive official denial)

**This is the single most load-bearing gap in this document.** I made a genuine, multi-pronged attempt to confirm the keyboard bindings at an official JAMB source:
  1. Fetched `jamb.gov.ng/PDFs/2024/RAPID_TEST_MULTILENT_JAMB_2024_CBT_Manual.pdf` directly — this is JAMB's own "STEP-BY-STEP CBT MANUAL." It downloaded (2.1MB) but is a compressed/garbled PDF that a text-extraction fetch could not parse.
  2. Fetched `jamb.gov.ng/pdfs/2024/2024_EXAMINATION_MANUAL(updated).pdf` (9.3MB) — downloaded successfully but is image-only (scanned pages as JPEG streams inside the PDF); the research sandbox has no `pdftoppm`/poppler installed, so page images could not be rasterized and read visually either.
  3. Located a newer official candidate document referenced directly on jamb.gov.ng's own downloads page (`jamb.gov.ng/JAMBTEST_Downloads`): **"2027 JAMB Test Manual (Updated 18-09-2026)"** — this is the most current and most promising primary source, but its exact PDF URL could not be resolved (a guessed URL 404'd) and it was not reached this session.
  4. Checked `jamb.gov.ng/FAQ` directly — no keyboard/navigation content there.

  **Net result: the A/B/C/D + N/P/S/Y/R key bindings are widely and consistently reported by independent secondary sources, which gives moderate confidence they are real (JAMB has publicly marketed a "CBT without mouse" feature under this name for several exam cycles), but I could NOT confirm them against JAMB's own primary text this session. Do not hard-code these bindings as gospel — re-verify against the "2027 JAMB Test Manual" on jamb.gov.ng (find its real PDF path, or run an OCR pass on the two manuals already identified) before shipping a simulator that depends on exact key parity.**

---

## 2. WAEC WASSCE

### School (May/June) vs Private/GCE (Nov/Dec)

- Claim: WASSCE "school candidates" sit in May/June; WASSCE for private candidates is run as the WAEC GCE, whose 2026 second series ran roughly late October–20 December 2026 (registration opened 4 May 2026, closed 28 August 2026 after an extension).
  Source: https://schoolinfospot.com/waec-gce-2026-registration-fees-timetable-private-candidates/ ; https://www.vanguardngr.com/2026/05/what-to-know-about-2026-wassce-for-private-candidates-2nd-series/ (Vanguard, published 2026-05-13)
  Type: news/community (Vanguard is reputable Nigerian press; schoolinfospot is a prep-site aggregator)
  Retrieved: 2026-09-23
  Confidence: probable

- Claim: There is also a WAEC GCE "first series" that ran registration closing 27 January 2026, exams 28 January–14 February 2026 (i.e. an earlier private-candidate sitting distinct from the Nov/Dec second series).
  Source: https://schoolinfospot.com/waec-gce-2026-registration-fees-timetable-private-candidates/
  Type: community
  Retrieved: 2026-09-23
  Confidence: unconfirmed (only one secondary source seen; not cross-checked against a second independent source or WAEC's own site)

### The 2026 CBT transition — what the brief claims vs what appears to have happened

- Claim (brief): "2026 candidates could choose CBT or paper, full CBT targeted 2027."
  **Finding: this is an oversimplification — the real picture is more granular and differs between school and private candidates.**

- Claim: For the May/June 2026 WASSCE (school candidates), WAEC Nigeria's Head of National Office, Amos Dangut, stated the plan was **pilot testing only in schools with the required ICT facilities** — i.e. participation was effectively decided at the school/infrastructure level, not as a free per-candidate choice of format — with community-based CBE centres available for schools lacking ICT facilities. Full national CBT migration for WASSCE was pushed to **2027** after the Federal Government had originally directed 2026.
  Source: https://businessday.ng/news/article/2026-wassce-remains-computer-based-test-waec-insists/ (Businessday, published 2025-11-24) and https://tribuneonlineng.com/waec-shifts-full-cbt-exam-to-2027/ (Tribune Online, published 2025-11-20)
  Type: news (reputable Nigerian business/general press)
  Retrieved: 2026-09-23
  Confidence: probable

- Claim: WAEC Federal Government Nominee Hajia Binta Abdulkadir stated: "So, I want to assure that no candidate sitting the 2026 WASSCE will be disenfranchised in any form" — i.e. an explicit assurance that candidates would not be forced into a format their school couldn't support.
  Source: https://tribuneonlineng.com/waec-shifts-full-cbt-exam-to-2027/
  Type: news
  Retrieved: 2026-09-23 (article dated 2025-11-20)
  Confidence: probable

- Claim: In contrast, for the **Nov/Dec 2026 WAEC GCE second series (private candidates)**, multiple sources describe the exam as run "fully Computer-Based" — with a hybrid mechanic where objective papers are answered entirely on computer, while essay/theory papers display the question on screen but candidates write answers in physical answer booklets (and practicals are a hybrid of on-screen questions with physical/written responses).
  Source: WebSearch aggregation citing WAEC's own X/Twitter announcement of the 2nd series registration start (4 May 2026) plus https://www.vanguardngr.com/2026/05/what-to-know-about-2026-wassce-for-private-candidates-2nd-series/ ("Mode: Fully Computer-Based Examination (CBE)"); hybrid on-screen-question/paper-answer mechanic reported by https://ulearngo.com/blog/ng/preparing-waec-cbt-2026-students-guide
  Type: news (Vanguard) + community (ulearngo, prep site)
  Retrieved: 2026-09-23
  Confidence: probable for "GCE 2nd series 2026 was run CBT"; the specific hybrid on-screen/paper-booklet mechanic is **unconfirmed at an official WAEC source** — only seen on a prep blog

**This is a genuine, reportable contradiction of the brief**: it is not accurate to say simply "2026 candidates could choose CBT or paper" — school candidates' access to CBT in May/June 2026 depended on their school's ICT infrastructure (a pilot, not an individual opt-in choice), while private GCE candidates in the Nov/Dec 2026 sitting were apparently already moved to a fully-CBT (hybrid) format ahead of the "full CBT by 2027" school-candidate target. A faithful simulator needs to model these as two different tracks, not one "choose CBT or paper" toggle.

### Subject-combination cap

- Claim: WASSCE candidates must take a minimum of 7–8 and maximum of 9 subjects; English Language and Mathematics are compulsory for all candidates regardless of stream; for 2026, WAEC additionally restricted Economics to Commercial/Business students only (barring Science and Arts candidates from offering it), and added a requirement that each candidate register for at least one trade subject.
  Source: aggregated from https://edugist.org/waec-introduces-new-subject-combinations-for-2026-examination/ and https://dtwtutorials.com/waec-2026-subject-combinations-economics-ban/ , cross-checked against https://www.insideojodu.com/waec-gives-update-on-five-compulsory-subjects-ahead-of-mayjune-2026/amp/ (mentions English Language, Mathematics, and Civic Education as compulsory — note this conflicts slightly with the "English + Maths only" framing in other sources)
  Type: news/community (education-news blogs; not WAEC's own site)
  Retrieved: 2026-09-23
  Confidence: unconfirmed — sources disagree on whether the compulsory core is 2 subjects (English + Maths) or 3 (+ Civic Education), and on whether the min is 7 or 8. None of these sources is waecnigeria.org itself. **Treat the "reported cap on number of subjects" the brief asks about as real in direction (there was a 2026 subject-combination policy change) but not verified in exact numbers.**

### Paper structure and options

- Claim: WASSCE papers are typically split into Paper 1 (objective, ~1 hour) and Paper 2 (essay/theory, 1.5–2.5 hours), with practicals up to 3 hours for science subjects — durations vary by subject.
  Source: WebSearch aggregation citing waecgh.org (**note: this is the WAEC Ghana site, not Nigeria** — structure is broadly shared across the WAEC sub-regions but should be re-confirmed against Nigeria-specific timetables)
  Type: official (but wrong country office — Ghana, not Nigeria)
  Retrieved: 2026-09-23
  Confidence: unconfirmed for Nigeria specifically — flagged because the source is the Ghanaian WAEC office, not waecnigeria.org

- Claim: WASSCE objective questions use 4 options (A–D), consistent with JAMB's convention.
  Source: not independently confirmed this session — carried over from general familiarity with WAEC exam format, not from a session source.
  Type: —
  Retrieved: 2026-09-23
  Confidence: unconfirmed — **do not hard-code without checking a real WAEC syllabus/past-paper PDF.**

### Where the authoritative timetable/syllabus lives

- Claim: WAEC Nigeria's official candidate/timetable information is published at waecnigeria.org (national office news page) and registration/exam operations run through waecdirect.org / waeconline.org.ng. Per-subject syllabus documents were not individually located this session.
  Source: https://www.waecnigeria.org/national-office (fetched directly this session — page exists and lists WASSCE-private-candidate timetable/syllabus news items, but no direct per-subject syllabus index was found during this pass)
  Type: official
  Retrieved: 2026-09-23
  Confidence: confirmed (site exists and is reachable; the specific syllabus document was not located, see "Could not confirm")

---

## 3. NECO SSCE

### Internal vs External (GCE)

- Claim: NECO SSCE "internal" is for final-year secondary school students registered through their school, sat around June/July. NECO SSCE External (branded "NECO GCE") is for private candidates, run in two series — roughly April–May (first series) and October–November (second series).
  Source: https://jayget.com/difference-between-neco-gce-and-internal-neco-exams/ ; official external portal confirmed reachable at https://ssceexternal.neco.gov.ng/
  Type: community (jayget.com is a prep blog, not NECO itself) + official (the ssceexternal.neco.gov.ng domain itself, existence only)
  Retrieved: 2026-09-23
  Confidence: probable

- Claim: NECO SSCE Internal registration fee ≈ ₦22,250; External (GCE) ≈ ₦30,000 (includes a mathematical table and certificate jacket).
  Source: https://jayget.com/difference-between-neco-gce-and-internal-neco-exams/
  Type: community
  Retrieved: 2026-09-23
  Confidence: unconfirmed (single blog source, fees change yearly, not cross-checked)

### Options: NOT A–D — NECO uses five options, A–E

- **Claim: NECO objective (multiple-choice) papers use FIVE lettered options, A through E — not four (A–D) like JAMB and (apparently) WAEC.** Past-paper instruction text consistently reads: "each question is followed by five options lettered A – E... choose the correct option for each question."
  Source: aggregated across multiple independent NECO past-paper transcriptions: https://www.scribd.com/document/464084383/NECO-Economics-Past-Questions-Objective-and-Theory , https://stcharlesedu.files.wordpress.com/2021/08/free-neco-marketing-past-questions-and-answers-objective-and-theory.pdf , and other subject past-papers (English Studies, Book Keeping) surfaced independently and showing the same instruction wording.
  Type: community (past-paper repositories/prep sites reproducing NECO's own printed instructions verbatim — not NECO's own site, but the instruction text itself is quoted from real exam papers, which is stronger evidence than an ordinary blog claim)
  Retrieved: 2026-09-23
  Confidence: probable — this is exactly the kind of assumption the brief warned against defaulting to; **this finding should be cross-checked against an actual scanned NECO objective answer sheet (OMR sheet) or a current NECO syllabus PDF before being hard-coded**, since past-paper transcriptions could theoretically be inconsistent across subjects or have changed in recent years. No official neco.gov.ng document was reachable this session to confirm directly (neco.gov.ng's homepage returned no substantive text content to the fetch tool).

### CBT transition

- Claim: NECO has also moved toward CBT, described by multiple sources as a "hybrid" model — objective papers answered on computer at accredited CBT centres, while some essay/theory papers still use traditional answer booklets during a transition period. This transition is reported as beginning with the May/June 2026 SSCE.
  Source: https://www.pulse.ng/story/neco-to-begin-computer-based-exams-2026-details-2026050808255541081 (Pulse Nigeria — general entertainment/news outlet, borderline as "reputable Nigerian press"; treat as secondary) and corroborating prep-site coverage (ulearngo.com, campusninja.com.ng, schoolinfospot.com)
  Type: news (Pulse Nigeria) + community
  Retrieved: 2026-09-23
  Confidence: probable — direction (hybrid CBT rollout starting 2026) is corroborated by multiple independent outlets, consistent with the Federal Government's April 2025 directive to both WAEC and NECO to adopt CBT (see §2); exact per-subject mechanics not confirmed at neco.gov.ng directly.

### Subject requirements

- Claim: NECO candidates must register for a minimum of 8 and a maximum of 9 subjects; English Language is compulsory, Mathematics is required by most tertiary institutions even though not always NECO-compulsory itself.
  Source: WebSearch aggregation (kollegescout.com, myeduvantage.com) — no single article fetched directly and verified in full text this session.
  Type: community
  Retrieved: 2026-09-23
  Confidence: unconfirmed

### Where the authoritative timetable/syllabus lives

- Claim: NECO's SSCE External (GCE) operations run through https://ssceexternal.neco.gov.ng/ ; the main body site is neco.gov.ng. Per-subject syllabus/timetable documents were not individually located or read this session (the neco.gov.ng homepage fetch returned no substantive extractable content).
  Source: direct fetch of https://www.neco.gov.ng and https://ssceexternal.neco.gov.ng/ (existence confirmed by search result)
  Type: official
  Retrieved: 2026-09-23
  Confidence: confirmed (domains exist) / unconfirmed (specific syllabus page not located)

---

## 4. NABTEB (NBC/NTC)

- Claim: NABTEB runs two main certificate series per year — **May/June** and **November/December** — for the National Technical Certificate (NTC) and National Business Certificate (NBC), plus Advanced versions (ANTC/ANBC) and a Modular Trades Certificate Examination (MTCE) series, and a Common Entrance exam.
  Source: https://nabteb.gov.ng/examinations/ (official NABTEB site, fetched directly this session)
  Type: official
  Retrieved: 2026-09-23
  Confidence: confirmed

- Claim: For 2026, registration for NTC/NBC commenced Monday 26 January 2026, closed Sunday 31 May 2026, with examinations beginning Monday 15 June 2026; registration/administration runs through school.nabteb.gov.ng, field offices, and Remita for payment.
  Source: https://nabteb.gov.ng/2026/01/26/commencement-of-registration-and-examination-dates-for-the-2026-national-technical-certificate-ntc-and-national-business-certificate-nbc-examinations/ — page title/summary confirmed via search result; **direct fetch of the page itself returned an HTTP 500 error this session**, so this is sourced from the search snippet of the official page, not a full read of it.
  Type: official (source domain) but **not independently re-verified by direct fetch** — re-check by re-fetching the URL later.
  Retrieved: 2026-09-23
  Confidence: probable

- Claim: Paper structure varies by subject/trade, generally combining Objective + Essay (theory) papers, with many technical/science-adjacent subjects also having a Practical or Alternative-to-Practical paper. Example structure seen for a biology-like technical subject: Paper 2 (Test of Practical) = 2 hours total, Section A = 15 short structured questions (30 min, 30 marks), Section B = 4 practical questions (1.5 hr, 70 marks).
  Source: WebSearch aggregation citing NABTEB subject syllabus PDFs (not individually fetched/verified this session — the specific PDF URL was not captured)
  Type: community (paraphrase of syllabus content via secondary aggregator, not a direct read of the syllabus PDF)
  Retrieved: 2026-09-23
  Confidence: unconfirmed — structure is plausible and subject-specific by nature (consistent with WAEC/NECO's own subject-by-subject variance) but not confirmed against a primary NABTEB syllabus document this session.

- Claim: Compulsory subjects include English and Mathematics; electives include ICT, Physics, Chemistry, Economics, Literature, etc., depending on trade/business specialization.
  Source: WebSearch aggregation (nabteb2026.blog, syllabus2026.blog)
  Type: community
  Retrieved: 2026-09-23
  Confidence: unconfirmed

### Where the authoritative timetable/syllabus lives

- Claim: The official 2026 May/June NABTEB timetable is published as a PDF directly on the official site: https://nabteb.gov.ng/wp-content/uploads/2026/06/2026-MAY.JUNE-TIME-TABLE.pdf ; the Nov/Dec registration portal is at https://novdec.nabteb.gov.ng/ with its own timetable at https://novdec.nabteb.gov.ng/docs/timetable.pdf.
  Source: found via WebSearch, both URLs are on the nabteb.gov.ng / novdec.nabteb.gov.ng official domains; **not individually fetched/opened this session** to confirm they resolve and contain the claimed content.
  Type: official (by domain)
  Retrieved: 2026-09-23
  Confidence: probable — domain and filename are consistent with an official artifact, but not opened and read this session.

---

## 5. Post-UTME — confirmed: no national format

**Claim confirmed: there is no single national Post-UTME format.** Each university sets its own screening mechanism (online aptitude test, in-person CBT, or in-person document/physical screening), its own fee, its own eligibility cutoff, and (where a test exists) its own question count/duration. Evidence: three different universities' own official pages describe three different mechanisms, checked directly this session.

- Claim: **University of Lagos (UNILAG)**, 2026/2027 cycle — runs its own "Post-UTME On-line Aptitude test," taken remotely (candidates need their own laptop with webcam/microphone per secondary sources; this specific detail wasn't in the primary notice). Registration 15 June – 8 July 2026; mock exams 22 June – 26 July 2026; actual test 27–31 July 2026. Screening fee ₦2,000 + application fee ₦3,500. The official notice itself does not state question count or duration; secondary sources (myschoolgist.com, campusninja.com.ng) separately report ~50 questions over 30–60 minutes covering the four UTME subjects plus current affairs/general aptitude — **this specific number was not in the official notice and is unconfirmed**.
  Source: https://unilag.edu.ng/important-notice-on-2026-2027-post-utme-screening-exercise/ (official, fetched directly) for dates/fees/mode; https://myschoolgist.com/news/unilag-post-utme-test-189249/ (community) for the ~50-question/30-60-minute claim
  Type: official (dates/fees/mode) + community (question count/duration)
  Retrieved: 2026-09-23
  Confidence: confirmed (dates/fees/online mode) / unconfirmed (exact question count and duration)

- Claim: **Obafemi Awolowo University (OAU)**, 2026/2027 cycle — screening is **in-person**: "Candidates will be required to present themselves physically for the screening exercise," held 25–30 September 2026 (registration deadline extended to 23 September 2026). The official notice does not state whether the in-person exercise is a CBT test, a written test, or document verification only.
  Source: https://oauife.edu.ng/oau-2026-post-utme-screening-exercise-new-date-announced/ (official, fetched directly)
  Type: official
  Retrieved: 2026-09-23
  Confidence: confirmed (in-person requirement, dates) / unconfirmed (exact mechanism — test vs verification)

- Claim: **University of Ibadan (UI)**, 2026/2027 cycle — runs an actual **Computer-Based Test**, not document-verification-only. Eligibility restricted to UTME candidates who scored 200+ in the 2026 UTME. Exam dates 27–29 July 2026; registration 22 June – 19 July 2026; portal-access fee ₦3,000 + screening fee ₦2,000. Candidates must also have O'Level results uploaded to JAMB CAPS for verification alongside the CBT.
  Source: https://ui.edu.ng/news/post-utmedirect-entry-screening-prospective-candidates-20262027-admission-exercise (official, referenced) — **note: this was summarized from search snippets rather than a full direct read of ui.edu.ng in this pass; re-verify with a direct fetch if precision matters**
  Type: official (by domain) but only search-snippet-level verification this session
  Retrieved: 2026-09-23
  Confidence: probable

- Claim: **University of Ilorin (UNILORIN)** — uses a weighted aggregate formula: 50% UTME/A-Level score + 30% Post-UTME screening score + 20% O-Level grades in five relevant subjects.
  Source: https://www.schoolngr.com/news/unilorin-20262027-post-utme-deform
  Type: community
  Retrieved: 2026-09-23
  Confidence: unconfirmed (single non-.edu.ng source; not cross-checked against unilorin.edu.ng directly)

**Conclusion for config design:** Post-UTME cannot be a single Sabi "exam format" config the way JAMB/WAEC/NECO/NABTEB can — it needs to be modeled per-institution (or left out of a v1 simulator scope), since format, question count, duration, mode (online/in-person/CBT/paper/document-only), fees, and cutoffs all vary independently by university and change every admission cycle.

---

## 6. Briefly: BECE/Junior WAEC, NCEE, JUPEB, IJMB

*(kept brief per the brief's own instruction — enough to know what a config needs, not full verification)*

- Claim: **BECE (Basic Education Certificate Examination)**, aka "Junior WAEC," is run by NECO (national BECE, for JSS3) and also state-level versions exist in some states; used for transition from junior to senior secondary school. Search results referenced "NECO BECE Past Questions" and a "2023 BASIC EDUCATION CERTIFICATE" NECO exam, confirming NECO is at least one body administering it.
  Source: search-result titles from earlier NECO queries (e.g. https://www.cliffsnotes.com/study-notes/28035333 referencing "NECO English Studies: Basic Education Exam Instructions... NATIONAL EXAMINATIONS COUNCIL 2023 BASIC EDUCATION CERTIFICATE")
  Type: community
  Retrieved: 2026-09-23
  Confidence: unconfirmed — not independently verified against neco.gov.ng or a state examination board this session; a config would need to distinguish "National BECE" (NECO) from any state-specific Junior WAEC variant, which was not investigated.

- Claim: **NCEE (National Common Entrance Examination)** — run by NECO, used for entry into Federal Government (Unity) Colleges at JSS1 level. A "2024 NCEE Common Entrance Past Questions" document surfaced in search results, confirming the exam's existence and NECO's association with it, but paper structure/question counts were not investigated this session.
  Source: https://www.docsity.com/en/docs/2024-ncee-common-entrance-past-questions-1/11627135/ (search snippet only)
  Type: community
  Retrieved: 2026-09-23
  Confidence: unconfirmed

- Claim: **JUPEB (Joint Universities Preliminary Examinations Board)** and **IJMB (Interim Joint Matriculation Board)** are both A-Level-equivalent, one-year (or 9-month) pre-degree programmes offered through affiliated universities/colleges, letting candidates bypass UTME for direct entry into 200-level.
  Source: not sourced this session (background knowledge only) — **do not treat as verified; this line is a placeholder flagging that JUPEB/IJMB need their own dedicated research pass before a config is built for them.**
  Type: —
  Retrieved: —
  Confidence: unconfirmed

**Recommendation:** if Sabi's roadmap reaches BECE/NCEE/JUPEB/IJMB, each needs its own dedicated research pass with the same rigor as JAMB/WAEC/NECO/NABTEB above — this session only had time to confirm they exist and roughly which body/level they belong to.

---

## Summary: claim counts by confidence

Counted across all numbered claim entries in §1–§6 above (not counting narrative/meta text):

- **confirmed:** 4 (NABTEB series existence; WAEC Nigeria national-office site reachable; NECO official domains reachable; UNILAG Post-UTME dates/fees/mode; OAU Post-UTME in-person requirement/dates — note several of these are "confirmed" for the *existence/reachability* of a source or a directly-quoted official detail, not for every number attached to that claim)
- **probable:** ~20 (the bulk of claims — corroborated by multiple independent secondary/community sources, or an official source reached only at snippet/domain level rather than fully read)
- **unconfirmed:** ~14 (option counts for WAEC, exact WAEC subject-cap numbers, NECO subject-count rule, NABTEB paper-structure detail, UNILORIN aggregate formula, all of §6's BECE/NCEE/JUPEB/IJMB claims, and others flagged inline)

(Exact counts are approximate — the point is directional: roughly 1 in 3 claims is "unconfirmed," and even most "confirmed"/"probable" claims rest on secondary sources rather than a fully-read official primary document, because several official PDFs could not be machine-read in this sandbox.)

## Biggest risk to building a faithful simulator

**JAMB's CBT keyboard control scheme (A–D select, N/P navigate, S/Y submit-confirm, R cancel, and whether arrow keys work) is the highest-priority claim in the whole brief, is the most consistently reported across secondary sources, and is simultaneously the one I could NOT confirm against JAMB's own primary text.** Two official PDFs were found and downloaded but were unreadable in this environment (one garbled/compressed, one image-only with no OCR tool available); a newer and more promising "2027 JAMB Test Manual" was located by reference but its real download path wasn't resolved in time. If Sabi ships a UTME simulator with hard-coded key bindings based only on the secondary-source consensus here, there is a real chance of a subtle mismatch (e.g., arrow-key support that doesn't actually exist, or a control JAMB has changed since these prep-site articles were last updated) — exactly the "students practise for an exam that no longer exists" failure mode the brief warns about. Before Phase 6 locks in the keyboard-control config, someone should either (a) get an OCR-capable tool on the two official JAMB PDFs already identified in this document, or (b) find and read the "2027 JAMB Test Manual" directly on jamb.gov.ng.

Secondary risks worth calling out:
- The WAEC CBT rollout is genuinely two-track (school vs. private candidates, on different timelines) — building it as a single toggle will misrepresent both tracks.
- NECO's 5-option (A–E) convention, if correct, means any shared "options" UI component built assuming 4 options (A–D) will not transfer cleanly to NECO — this should be verified early since it affects UI/data-model design, not just content.
