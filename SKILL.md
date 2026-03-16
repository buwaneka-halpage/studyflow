---
name: studyflow
description: StudyFlow — NotebookLM × Notion learning system for CSE students. Generates structured notes, flashcards (SM-2 spaced repetition), quizzes, Feynman explanations, and mind maps from NotebookLM notebooks into a Notion workspace.
triggers:
  - /studyflow
---

# StudyFlow Skill

You are an intelligent study system orchestrator. When the user invokes `/studyflow`, you execute commands that bridge **NotebookLM** (knowledge source) and **Notion** (structured output) to create a world-class learning environment for a CSE undergraduate student.

## Tools Available
- **notebooklm CLI** — via Bash tool: `PYTHONIOENCODING=utf-8 notebooklm <cmd>`
- **Notion MCP** — via `mcp__claude_ai_Notion__*` tools
- **Claude's intelligence** — synthesizing, structuring, generating pedagogically-sound content

## Autonomy Rules
Run the following **without asking for confirmation**:
- All `notebooklm list`, `notebooklm use`, `notebooklm ask`, `notebooklm source list`, `notebooklm artifact list` commands
- All Notion read operations (search, fetch)
- All Notion create/update operations for notes, flashcards, quizzes, databases

Ask before running:
- `notebooklm generate audio/video/slide-deck` (long-running)
- `notebooklm delete` (destructive)

---

## Commands

### `/studyflow setup`
Create the full Notion workspace. Run this once.

**Workflow:**
1. Use `mcp__claude_ai_Notion__notion-search` to check if "StudyFlow" root page already exists
2. If not, create the root structure using `mcp__claude_ai_Notion__notion-create-pages`
3. Create all four databases (Knowledge Base, Flashcard Vault, Quiz Bank, Study Sessions)
4. Create the Courses and Projects sections as child pages
5. Print all created page/database IDs — copy these into the `Permanent Notion IDs` section below

**Notion Page Structure:**
```
📚 StudyFlow                    (root page)
├── 📈 Dashboard                (page with command reference)
├── 🗂️ Courses                  (page — course sub-pages go here)
├── 🔧 Projects & Freelance     (page — project sub-pages go here)
├── 📚 Knowledge Base           (database)
├── 🃏 Flashcard Vault          (database)
├── ❓ Quiz Bank                (database)
└── 📅 Study Sessions           (database)
```

**Database Schemas:**

#### Knowledge Base (Notes database)
- `Name` (title), `Course` (select), `Type` (select: Concept/Algorithm/Technology/Lecture/Pattern)
- `Mastery` (select: ⬜ New / 🟥 Learning / 🟨 Familiar / 🟩 Mastered)
- `NotebookLM ID` (rich_text), `Source Type` (multi_select), `Tags` (multi_select)
- `Last Reviewed` (date), `Feynman Done` (checkbox)

#### Flashcard Vault
- `Front` (title), `Back` (rich_text), `Course` (select)
- `Status` (select: 🆕 New / 📖 Learning / 🔄 Review / ✅ Mastered)
- `Ease Factor` (number, default 2.5), `Interval` (number, default 1)
- `Next Review` (date), `Repetitions` (number, default 0), `Last Reviewed` (date)
- `Card Type` (select: Standard / Cloze / Code)

#### Quiz Bank
- `Question` (title), `Type` (select: MCQ / True-False / Short Answer)
- `Options` (rich_text), `Answer` (rich_text), `Explanation` (rich_text)
- `Course` (select), `Times Attempted` (number), `Times Correct` (number), `Last Attempted` (date)

#### Study Sessions
- `Session` (title: "YYYY-MM-DD — [Notebook]"), `Date` (date), `Notebook` (rich_text)
- `Topics Covered`, `What I Learned`, `Confusions`, `Next Actions` (all rich_text)
- `Cards Reviewed` (number), `Notes Created` (number)

---

### `/studyflow notes <notebook-name-or-id> [--topic <topic>] [--type concept|algo|tech|lecture]`

Generate a structured note page in Notion's Knowledge Base.

**Workflow:**
1. Run `PYTHONIOENCODING=utf-8 notebooklm list --json` to find the notebook by name
2. Set notebook context: `PYTHONIOENCODING=utf-8 notebooklm use <id>`
3. Run targeted NotebookLM queries:
   - `notebooklm ask "Explain [topic] comprehensively — core concept, definitions, how it works, why it matters"`
   - `notebooklm ask "What are 3-5 common pitfalls or misconceptions about [topic]?"`
   - `notebooklm ask "Give me a concrete example or code example of [topic] in action"`
   - `notebooklm ask "What are 5-8 active recall questions that test deep understanding of [topic]?"`
   - `notebooklm ask "How does [topic] connect to or differ from related concepts?"`
4. Synthesize into a structured page using the Note Page Template below
5. Create in Knowledge Base using `mcp__claude_ai_Notion__notion-create-pages`
6. Log a Study Session entry

**Note Page Template:**
```
[TOPIC NAME] — page title

> Course: [course] | Type: [type] | Mastery: ⬜ New

## 🎯 Learning Objectives
- [ ] Understand [core idea]
- [ ] Be able to [apply it]
- [ ] Explain [it simply] without notes

## 📖 Core Explanation
[2-4 paragraphs. Prose, not bullet dump. What → How → Why it matters]

## 💡 Key Definitions
[Table: Term | Definition — 4-8 rows]

## 🔍 Active Recall Questions
> Close this page. Can you answer these from memory?
- ❓ [Question 1–5]

## 🧠 Feynman Explanation
[Plain English analogy. Avoid jargon.]
**Still fuzzy on:** [ ] [gap]

## 💻 Code Example
[Well-annotated example with inline comments explaining WHY]

## ⚠️ Common Pitfalls
- ❌ [Mistake] → ✅ [Correct approach]

## 🔗 Related Concepts
- [Concept A] — [1-line connection]

## 📝 One-Line Summary
[Single sentence: what + why + when]
```

**Type-specific additions:**
- **algo**: Add `⏱️ Complexity` section with Time/Space/Best/Worst/Average
- **tech**: Add `🔧 Quick Setup` section
- **lecture**: Replace code section with `📋 Lecture Key Points` bullets

---

### `/studyflow flashcards <notebook-name-or-id> [--count N] [--cloze] [--topic <topic>]`

Generate flashcards and add them to the Flashcard Vault.

**Default count:** 15. Use `--count N` to override.

**Workflow:**
1. Find and set notebook context
2. Query NotebookLM:
   - Standard: `notebooklm ask "Generate [N] flashcard Q&A pairs. Format: Q: [question]\nA: [answer]\n---"`
   - Cloze: `notebooklm ask "Generate [N] cloze sentences. Format: CLOZE: [sentence with ___]\nANSWER: [fill]\n---"`
3. Parse into individual cards
4. For each card, create entry in Flashcard Vault with:
   - Status: "🆕 New", Ease Factor: 2.5, Interval: 1, Next Review: today, Repetitions: 0

**Quality guidelines:** Atomic cards, test understanding not just recall. Prefer "How does X work?" over "What is X?"

---

### `/studyflow review`

Process today's due flashcards using SM-2 spaced repetition.

**Workflow:**
1. Query Flashcard Vault for cards where Next Review ≤ today
2. Show each card: FRONT → reveal BACK → ask **[E]asy / [H]ard / [A]gain**
3. Apply SM-2:
   - **Again (A):** interval=1, repetitions=0
   - **Hard (H):** interval=max(1, round(interval×1.2)), ease_factor=max(1.3, ef-0.15)
   - **Easy (E):** interval=1 (rep 0), 6 (rep 1), else round(interval×ef); repetitions+=1, ef=min(4.0, ef+0.1)
   - Next Review = today + interval days
4. Status: reps=0→New, 1-2→Learning, 3-5→Review, 6+ and interval>21→Mastered
5. Update Notion card, show summary

---

## SM-2 Algorithm Reference

```
Again (score=0): interval=1, repetitions=0, ease_factor unchanged
Hard  (score=3): interval=max(1, round(interval × 1.2))
                 ease_factor=max(1.3, ease_factor - 0.15)
Easy  (score=5): if repetitions=0: interval=1
                 elif repetitions=1: interval=6
                 else: interval=round(interval × ease_factor)
                 repetitions += 1
                 ease_factor = min(4.0, ease_factor + 0.1)
Next Review = today + interval days
```

---

## Notebook Name Resolution

1. `PYTHONIOENCODING=utf-8 notebooklm list --json`
2. Case-insensitive partial match on `title` field
3. One match → use it; multiple → ask user; zero → show all and ask

---

## Permanent Notion IDs (do NOT re-create these)

Run `/studyflow setup` to populate. Then update this section with your IDs.

| Resource | Notion ID |
|----------|-----------|
| 📚 StudyFlow (root) | `YOUR_ROOT_PAGE_ID` |
| 📈 Dashboard | `YOUR_DASHBOARD_ID` |
| 🗂️ Courses | `YOUR_COURSES_ID` |
| 🔧 Projects & Freelance | `YOUR_PROJECTS_ID` |
| 📚 Knowledge Base (DB) | `YOUR_KNOWLEDGE_BASE_ID` |
| 🃏 Flashcard Vault (DB) | `YOUR_FLASHCARD_VAULT_ID` |
| ❓ Quiz Bank (DB) | `YOUR_QUIZ_BANK_ID` |
| 📅 Study Sessions (DB) | `YOUR_STUDY_SESSIONS_ID` |

**When creating entries in databases**, use `data_source_id` as the parent type.
