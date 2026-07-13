# Review Notes — A2 · grammar · zijn_hebben

## File
- `questions.json`: 100 four-option MCQ items

## Status
**DRAFT — needs human review before approval.**

Do NOT import with `status="approved"`.
Recommended import metadata:
- `status = "draft"`
- `created_by = "imported_ai"`
- `reviewed_by = NULL` until a reviewer signs off

## Internal grouping (v5)
The 100 items are intentionally split into five conceptual sub-skills to avoid
repetition and to make review easier:

| Group | Count | Description |
|-------|-------|-------------|
| `conjugation_zijn` | 25 | Fill-in-the-blank with the verb **zijn** |
| `conjugation_hebben` | 25 | Fill-in-the-blank with the verb **hebben** (no `u`) |
| `fixed_expressions` | 25 | Collocations such as *honger hebben*, *bang zijn*, *gelijk hebben*, *het koud hebben* |
| `weather_time` | 15 | General state/weather with *Het is …* |
| `sentence_choice` | 10 | *Welke zin is correct?* |

Correct-answer distribution: A=25, B=25, C=25, D=25.

## Quality fixes applied (v5)
1. **Fixed Persian translations**:
   - `Ik heb het koud.` → `من سردم است.`
   - `Ik ben jarig morgen.` → `فردا تولدم است.`
   - `De winkel is open.` → `فروشگاه باز است.`
   - `Ik heb mijn telefoon niet.` → `من تلفنم را ندارم.`
   - `Ik heb geen tijd.` → `من وقت ندارم.`
   - `Ik heb geen geld.` → `من پول ندارم.`
2. **Fixed remaining weather/state feedback**: all `feedback_fa` for `Het is …` items now use only `وضعیت کلی`, never `آب‌وهوا/زمان/وضعیت`.

## Quality fixes applied (v4)
1. **Fixed bad extra examples**:
   - `De winkel is moe.` → `De winkel is open.` / `فروشگاه باز است.`
2. **Fixed unnatural sentence**:
   - `Wij ___ een grote keuze.` → `Wij ___ veel keuze.`
3. **Improved contextual relevance of extra examples**: extra examples now match the topic of the question (e.g. *idee* → `Ik heb een vraag.`, *fiets* → `Ik heb een mooie auto.`) instead of always falling back to `Ik heb honger.`
4. **Fixed Persian verb agreement in extra examples**: Persian translations now agree with the subject of the extra example.
5. **Simplified `Het is …` feedback**: option feedback now says *وضعیت کلی* instead of the broader *آب‌وهوا/زمان/وضعیت*.

## Quality fixes applied (v3)
1. **Removed duplicate sentences**: no sentence stem appears twice (except the shared prompt `Welke zin is correct?`).
2. **Fixed unnatural weather/state sentences**:
   - `Het is sneeuwachtig in de bergen.` → `Het is wit in de bergen.`
   - `Het is laat op school vandaag.` removed; replaced with `Wij zijn laat op school vandaag.`
   - `Het is vroeg op zondag.` → `Het is vroeg op zondagochtend.`
3. **Fixed Persian instruction for `Het is …` items**: now reads `وضعیت کلی با het` instead of `آب‌وهوا/زمان`.
4. **Fixed Persian translations for `het warm/koud hebben`**:
   - `Ik heb het warm.` → `من گرمم.`
   - `Zij heeft het koud.` → `او سردش است.`

## Quality fixes applied (v2)
1. **Removed `u` ambiguity in hebben**: the pronoun `u` is only tested with `zijn` (→ `bent`). For `hebben`, `u` is avoided because both `u hebt` and `u heeft` are acceptable in modern Dutch.
2. **Removed perfectum items**: sentences with past participles (*gehad*, *gevonden*) were moved out of this basic topic.
3. **Removed ambiguous standalone `Zij ___`**: replaced with explicit singular/plural nouns.
4. **Removed `gisteren` with present tense**.
5. **Removed `Het heeft …` in weather/time contexts**.
6. **Fixed Persian explanations**: explanations refer to explicit subjects (e.g. *Mijn zus* = third-person singular feminine) instead of vague *zij*.
7. **Fixed gender/naturalness issues**:
   - Removed *Mijn zus … als hij lijkt*.
   - Removed unnatural sentences such as *Mijn vrienden hebben een grote keuze aan schoenen*.
8. **Improved `extra_example_nl/fa`**: examples are natural and relevant to the tested pattern.

## Hard filters applied during generation
- No exact duplicate sentence stems (except shared question prompts).
- No `Zij ___` without explicit singular/plural context.
- No `gisteren` with present-tense forms.
- No `Het heeft` in weather/state contexts.
- No past-participle forms (perfectum).
- No bad extra examples like `Het is moe`, `U hebt honger`, or `De winkel is moe`.
- No item where both `hebt` and `heeft` appear as options for a `U` subject.

## Recommended review checks
1. Spot-check ~10 items per group for natural Dutch.
2. Verify that every correct option is the only grammatically and naturally valid answer.
3. Confirm Persian translations are simple, clear, and idiomatic.
4. Run JSON validation before import.
5. If approved, consider splitting each group into its own file/topic for finer-grained exams.
