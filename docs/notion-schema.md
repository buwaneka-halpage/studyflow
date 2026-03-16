# Notion Database Schemas

This document describes the exact property schemas for all four StudyFlow databases.
These are created automatically by `/studyflow setup`.

## Knowledge Base (Notes)

| Property | Type | Values / Notes |
|----------|------|----------------|
| Name | title | Topic name |
| Course | select | Matches notebook title |
| Type | select | Concept / Algorithm / Technology / Lecture / Pattern / Design / Tutorial |
| Mastery | select | ⬜ New / 🟥 Learning / 🟨 Familiar / 🟩 Mastered |
| NotebookLM ID | rich_text | Notebook UUID |
| Source Type | multi_select | Notes / Podcast / Slides / Mind Map / Quiz / Research |
| Tags | multi_select | Topic tags |
| Last Reviewed | date | Updated on review |
| Feynman Done | checkbox | Whether Feynman block is written |

## Flashcard Vault

| Property | Type | Values / Notes |
|----------|------|----------------|
| Front | title | Question / prompt |
| Back | rich_text | Answer |
| Course | select | Same options as Knowledge Base |
| Status | select | 🆕 New / 📖 Learning / 🔄 Review / ✅ Mastered |
| Ease Factor | number | SM-2 factor, default 2.5 |
| Interval | number | Days until next review, default 1 |
| Next Review | date | Calculated by SM-2 |
| Repetitions | number | SM-2 counter, default 0 |
| Last Reviewed | date | Last review date |
| Card Type | select | Standard / Cloze / Code |

## Quiz Bank

| Property | Type | Values / Notes |
|----------|------|----------------|
| Question | title | Question text |
| Type | select | MCQ / True-False / Short Answer |
| Options | rich_text | For MCQ: "A) ...\nB) ...\nC) ...\nD) ..." |
| Answer | rich_text | Correct answer |
| Explanation | rich_text | Why it's correct |
| Course | select | Course name |
| Times Attempted | number | Default 0 |
| Times Correct | number | Default 0 |
| Last Attempted | date | Last attempt date |

## Study Sessions

| Property | Type | Values / Notes |
|----------|------|----------------|
| Session | title | "YYYY-MM-DD — [Notebook]" |
| Date | date | Session date |
| Notebook | rich_text | Notebook name used |
| Topics Covered | rich_text | Topics studied |
| What I Learned | rich_text | Student reflection |
| Confusions | rich_text | Open questions |
| Next Actions | rich_text | Planned follow-up |
| Cards Reviewed | number | Count of cards reviewed |
| Notes Created | number | Count of notes created |
