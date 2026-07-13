# پرامپت‌های تولید سؤال — Dutch Learning Bot (A2 / B1 / B2)

این فایل برای **تولید آفلاینِ سؤال‌های باکیفیت** با مدلِ خودت است. خروجی JSON را به من بده تا
مستقیم در دیتابیس وارد کنم (بدون نیاز به AI در زمان اجرا).

## طرز استفاده
1. بلوک **🔧 GLOBAL RULES** (پایین) را اولِ هر اجرا کپی کن.
2. بلوکِ باکتِ موردنظر (مثلاً «A2 · Grammar») را زیرش بگذار.
3. در همان بلوک، یک **زیربخش (subtopic)** را برای این اجرا انتخاب کن و در فیلد `SUBTOPIC TO GENERATE NOW` بنویس.
4. مدل ۱۵۰ تا ۲۰۰ سؤالِ JSON برای همان زیربخش می‌سازد. خروجی را برای من بفرست.

> هر زیربخش = یک فایل/اجرای جدا (۱۵۰–۲۰۰ سؤال). slugِ زیربخش را عیناً در فیلد `topic` بگذار تا import درست شود.

**هنگام import** ما این‌ها را ست می‌کنیم: `status="approved"`، `created_by="curated"`، `reviewed_by="curated"`.
پس مدل **status نمی‌سازد** — فقط محتوای سؤال را تولید کن.

---

## 🔧 GLOBAL RULES — این بلوک را اولِ هر اجرا کپی کن

```
ROLE
You are a senior NT2 (Dutch-as-a-second-language) exam author and examiner. You
know the REAL level of the Dutch Inburgering and Staatsexamen NT2 (Programma I =
A2/B1, Programma II = B2) and exactly what counts as natural, idiomatic, correct
Dutch. Your learners are Persian speakers. You NEVER ship a grammatically wrong,
unnatural, or ambiguous item.

TASK
Generate 150–200 four-option multiple-choice questions for EXACTLY the one bucket
and the one SUBTOPIC named in the BUCKET BLOCK below.

NON-NEGOTIABLE CORRECTNESS GATE  (apply to EVERY question; if it fails, DROP it and
make a new one — never ship a failing item)
  1. BLIND RE-SOLVE: read the item with only the 4 options, WITHOUT looking at the
     answer you marked. Independently decide which option(s) produce a fully
     correct, natural Dutch result / the single best answer.
  2. EXACTLY ONE correct: keep the item only if exactly one option is correct/best.
     If zero or two+ options work, or the blank actually needs a word that is NOT
     among the options, the item is broken — discard it.
  3. NATURAL DUTCH: with the correct option inserted, the sentence/dialogue must
     read 100% natural to a native speaker. No calque/Persian-style Dutch.
  4. RIGHT LEVEL: the item must truly sit at the stated CEFR level (vocabulary,
     grammar, length) — not easier, not harder.
  5. MATCH: the field "is_correct": true must be on the very option you chose in
     step 1.
  6. NO PLACEHOLDERS like [NAME], [CITY]; write real words. Do not reference audio
     or images unless the bucket block explicitly puts the text inside the question.

DISTRACTORS
  The three wrong options must be PLAUSIBLE and reflect REAL learner mistakes
  (wrong person/number, zijn/hebben or de/het confusion, wrong word order, wrong
  preposition, wrong register). They must be clearly wrong to an expert, but
  tempting to a learner. Never use silly/impossible distractors.

PERSIAN EXPLANATIONS (always in Persian, for a Persian-speaking learner)
  • explanation_fa  : 1–2 sentences: why the correct answer is right.
  • grammar_rule_fa : one short Persian line — the rule or skill being tested.
  • feedback_fa (per option): for the correct one a short confirmation; for each
    wrong one, the exact mistake (e.g. «‹bent› برای jij/u است، نه ik»).
  • extra_example_nl + extra_example_fa: one extra CORRECT Dutch example + Persian
    translation that reinforces the point.

DIVERSITY & QUANTITY
  • 150–200 items, ALL for the single subtopic given.
  • Vary subjects, situations, and everyday contexts; no two items nearly identical.
  • Spread difficulty: field "difficulty" = 1 (easy) … 3 (harder, still in-level).

OUTPUT (STRICT)
  Return ONLY a JSON array, no prose, no markdown fences. Each element EXACTLY:
{
  "level": "<A2|B1|B2 — copy from bucket>",
  "section": "<section key — copy from bucket>",
  "topic": "<subtopic slug — copy from bucket>",
  "life_context": "<short tag, e.g. home|work|health|gemeente|shopping|school>",
  "question_type": "mcq_4",
  "difficulty": 1,
  "question_text_nl": "<the Dutch question/sentence; use ___ for a blank>",
  "question_text_fa": "<short Persian instruction>",
  "explanation_fa": "<Persian explanation of the correct answer>",
  "grammar_rule_fa": "<one-line Persian rule/skill note>",
  "extra_example_nl": "<one extra correct Dutch example>",
  "extra_example_fa": "<its Persian translation>",
  "options": [
    {"key":"A","text_nl":"<option>","is_correct":false,"feedback_fa":"<Persian>"},
    {"key":"B","text_nl":"<option>","is_correct":false,"feedback_fa":"<Persian>"},
    {"key":"C","text_nl":"<option>","is_correct":false,"feedback_fa":"<Persian>"},
    {"key":"D","text_nl":"<option>","is_correct":false,"feedback_fa":"<Persian>"}
  ]
}
  Exactly ONE option per item has "is_correct": true. Keys must be A, B, C, D.
  Do not number the questions. Output valid JSON only.
```

---
---

# سطح A2
هدف A2: کاربر در موقعیت‌های ساده‌ی روزمره جمله‌های کوتاه را بفهمد، جواب بدهد و اشتباهات پایه را کم کند.

## A2 · Grammar
```
BUCKET
  level = "A2"  | section = "grammar"
SUBTOPICS (set "topic" to ONE slug per run; target 150–200 each):
  zijn_hebben, present_tense, perfect_tense, modal_verbs, question_structure,
  word_order, niet_geen, articles, plural_nouns, prepositions, separable_verbs,
  time_days_dates
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Simple present and basic perfect tense; short main-clause sentences; everyday
  A2 vocabulary; all persons (ik/jij/u/hij/zij/het/wij/jullie/zij).
QUESTION STYLES (NL.md): جای خالی · انتخاب جمله‌ی درست · تصحیح جمله‌ی کوتاه · انتخاب فعل درست
SECTION CORRECTNESS NOTES
  • All four options must be plausible fillers for the SAME blank (e.g. all forms
    of the same verb / the right set of articles).
  • If the sentence is in the perfect tense (contains a past participle like
    "gegaan", "opgeruimd"), the blank for a zijn/hebben item must be the AUXILIARY
    and the correct auxiliary (heb/hebt/heeft/hebben/ben/bent/is/zijn) MUST be one
    of the four options. Never leave a blank whose only correct word is absent.
WORKED EXAMPLE (topic = "zijn_hebben")
{
  "level":"A2","section":"grammar","topic":"zijn_hebben","life_context":"health",
  "question_type":"mcq_4","difficulty":1,
  "question_text_nl":"Ik ___ vandaag erg moe.",
  "question_text_fa":"کدام شکل درست فعل است؟",
  "explanation_fa":"با ضمیر «ik» فعل zijn به‌صورت «ben» می‌آید؛ «moe zijn» یعنی خسته بودن.",
  "grammar_rule_fa":"صرف zijn: ik ben، jij bent، hij/zij/het is، wij/jullie/zij zijn.",
  "extra_example_nl":"Hij is vandaag ziek.","extra_example_fa":"او امروز مریض است.",
  "options":[
    {"key":"A","text_nl":"ben","is_correct":true,"feedback_fa":"✅ درست. «ik ben» یعنی «من هستم»."},
    {"key":"B","text_nl":"bent","is_correct":false,"feedback_fa":"«bent» برای jij/u است، نه ik."},
    {"key":"C","text_nl":"is","is_correct":false,"feedback_fa":"«is» برای سوم‌شخص مفرد (hij/zij/het) است."},
    {"key":"D","text_nl":"heb","is_correct":false,"feedback_fa":"«heb» از hebben است؛ اینجا فعلِ بودن لازم است."}
  ]
}
```

## A2 · Vocabulary in Context
```
BUCKET
  level = "A2"  | section = "vocab_in_context"
SUBTOPICS:
  home, family, shopping, supermarket, doctor_pharmacy, school, simple_work,
  transport, weather, time_appointments, food_drink, clothing
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  High-frequency A2 everyday words used IN a short context sentence. Test meaning
  and correct use, not isolated translation.
QUESTION STYLES (NL.md): معنی کلمه در جمله · انتخاب کلمه‌ی مناسب · فرق دو کلمه‌ی ساده · کاربرد کلمه در موقعیت واقعی
SECTION CORRECTNESS NOTES
  • The four options are usually words of the same class (e.g. four nouns) where
    only one fits the sentence meaning. The other three are real A2 words but wrong
    here. Avoid trick synonyms where two could fit.
WORKED EXAMPLE (topic = "home")
{
  "level":"A2","section":"vocab_in_context","topic":"home","life_context":"home",
  "question_type":"mcq_4","difficulty":1,
  "question_text_nl":"In de woonkamer staat een ___ voor de televisie.",
  "question_text_fa":"کدام کلمه در جمله مناسب است؟",
  "explanation_fa":"در اتاق نشیمن جلوی تلویزیون معمولاً «bank» (کاناپه) است.",
  "grammar_rule_fa":"واژگان خانه: bank=کاناپه، tafel=میز، bed=تخت، kast=کمد.",
  "extra_example_nl":"We zitten samen op de bank.","extra_example_fa":"با هم روی کاناپه می‌نشینیم.",
  "options":[
    {"key":"A","text_nl":"bank","is_correct":true,"feedback_fa":"✅ درست؛ «bank» یعنی کاناپه."},
    {"key":"B","text_nl":"bed","is_correct":false,"feedback_fa":"«bed» (تخت) در اتاق خواب است."},
    {"key":"C","text_nl":"koelkast","is_correct":false,"feedback_fa":"«koelkast» (یخچال) در آشپزخانه است."},
    {"key":"D","text_nl":"douche","is_correct":false,"feedback_fa":"«douche» (دوش) در حمام است."}
  ]
}
```

## A2 · Reading
```
BUCKET
  level = "A2"  | section = "reading"
SUBTOPICS:
  whatsapp_message, simple_email, sign_notice, school_message, doctor_message,
  gemeente_message, simple_ad, simple_schedule
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  A SHORT authentic A2 text (1–3 sentences) is placed INSIDE "question_text_nl",
  followed by one comprehension question about it.
QUESTION STYLES (NL.md): متن چه می‌گوید؟ · کاربر باید چه کاری انجام دهد؟ · زمان/مکان/شخص را پیدا کن · درست یا غلط
SECTION CORRECTNESS NOTES
  • Put the text and the question together in "question_text_nl" (e.g. «Bericht: …»
    then the question). The answer must be findable ONLY from the text. Options are
    short factual answers; exactly one matches the text.
WORKED EXAMPLE (topic = "whatsapp_message")
{
  "level":"A2","section":"reading","topic":"whatsapp_message","life_context":"appointment",
  "question_type":"mcq_4","difficulty":1,
  "question_text_nl":"Bericht: «Hoi! Ik ben iets later. Ik ben er om 19:00 uur. Tot zo!»  —  Hoe laat komt de afzender?",
  "question_text_fa":"بر اساس پیام، فرستنده ساعت چند می‌رسد؟",
  "explanation_fa":"در پیام نوشته «om 19:00 uur»، پس ساعت ۱۹:۰۰ می‌رسد.",
  "grammar_rule_fa":"اطلاعاتِ زمان را مستقیم از متن پیدا کن.",
  "extra_example_nl":"Ik kom om 20:00 uur.","extra_example_fa":"ساعت ۲۰:۰۰ می‌آیم.",
  "options":[
    {"key":"A","text_nl":"om 17:00 uur","is_correct":false,"feedback_fa":"در متن این ساعت نیامده."},
    {"key":"B","text_nl":"om 18:00 uur","is_correct":false,"feedback_fa":"در متن این ساعت نیامده."},
    {"key":"C","text_nl":"om 19:00 uur","is_correct":true,"feedback_fa":"✅ درست؛ متن می‌گوید 19:00 uur."},
    {"key":"D","text_nl":"om 20:00 uur","is_correct":false,"feedback_fa":"در متن این ساعت نیامده."}
  ]
}
```

## A2 · Meaning & Intention
```
BUCKET
  level = "A2"  | section = "meaning"
SUBTOPICS:
  sentence_meaning, simple_request, apology, suggestion, accept_refuse,
  simple_warning, reminder
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  A short everyday utterance is given; the learner must understand its INTENTION
  (what the speaker wants) or pick the best simple reaction.
QUESTION STYLES (NL.md): گوینده چه می‌خواهد؟ · جمله در این موقعیت یعنی چه؟ · بهترین واکنش چیست؟
SECTION CORRECTNESS NOTES
  • Exactly one option correctly states the intention / is the appropriate
    reaction. Wrong options are plausible misreadings of tone or meaning.
WORKED EXAMPLE (topic = "simple_request")
{
  "level":"A2","section":"meaning","topic":"simple_request","life_context":"home",
  "question_type":"mcq_4","difficulty":1,
  "question_text_nl":"Iemand zegt: «Kun je het raam misschien dichtdoen?»  Wat wil de spreker?",
  "question_text_fa":"گوینده چه می‌خواهد؟",
  "explanation_fa":"«dichtdoen» یعنی بستن؛ پس گوینده می‌خواهد پنجره را ببندی.",
  "grammar_rule_fa":"درخواست مودبانه با «Kun je …?» بیان می‌شود.",
  "extra_example_nl":"Kun je de deur dichtdoen?","extra_example_fa":"می‌توانی در را ببندی؟",
  "options":[
    {"key":"A","text_nl":"Het raam sluiten","is_correct":true,"feedback_fa":"✅ درست؛ dichtdoen = بستن."},
    {"key":"B","text_nl":"Het raam openen","is_correct":false,"feedback_fa":"باز کردن «opendoen» است، نه dichtdoen."},
    {"key":"C","text_nl":"Naar buiten gaan","is_correct":false,"feedback_fa":"درباره‌ی بیرون رفتن چیزی نگفت."},
    {"key":"D","text_nl":"Het licht aandoen","is_correct":false,"feedback_fa":"درباره‌ی چراغ چیزی نگفت."}
  ]
}
```

## A2 · Dialogue
```
BUCKET
  level = "A2"  | section = "dialogue"
SUBTOPICS:
  greetings, shopping, making_appointment, doctor, child_school, work, neighbour,
  restaurant, asking_directions
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  A 1–2 line mini-dialogue; the learner picks the natural next line / best reply.
QUESTION STYLES (NL.md): جمله‌ی بعدی در مکالمه · جواب مناسب · کامل کردن دیالوگ · انتخاب واکنش طبیعی
SECTION CORRECTNESS NOTES
  • Show the prior line(s) in "question_text_nl". Exactly one option is the
    natural, polite, situation-appropriate continuation. Others are off-topic or
    rude/unnatural but grammatically possible.
WORKED EXAMPLE (topic = "shopping")
{
  "level":"A2","section":"dialogue","topic":"shopping","life_context":"shopping",
  "question_type":"mcq_4","difficulty":1,
  "question_text_nl":"Verkoper: «Goedemiddag, waarmee kan ik u helpen?»  Klant: «___»",
  "question_text_fa":"کدام جواب برای مشتری مناسب است؟",
  "explanation_fa":"در فروشگاه، مشتری نیازش را می‌گوید؛ گزینه‌ی درخواستِ یک محصول مناسب است.",
  "grammar_rule_fa":"پاسخ به «waarmee kan ik u helpen?» = گفتنِ نیاز.",
  "extra_example_nl":"Ik zoek een nieuwe jas.","extra_example_fa":"دنبال یک کت نو هستم.",
  "options":[
    {"key":"A","text_nl":"Ik wil graag een brood, alstublieft.","is_correct":true,"feedback_fa":"✅ درست و مودبانه؛ نیاز را می‌گوید."},
    {"key":"B","text_nl":"Tot ziens!","is_correct":false,"feedback_fa":"این خداحافظی است، نه شروع خرید."},
    {"key":"C","text_nl":"Het gaat goed.","is_correct":false,"feedback_fa":"این جوابِ «حالت چطور است» می‌باشد."},
    {"key":"D","text_nl":"Ik woon in Utrecht.","is_correct":false,"feedback_fa":"بی‌ربط به موقعیت خرید است."}
  ]
}
```

## A2 · Error Correction
```
BUCKET
  level = "A2"  | section = "error_correction"
SUBTOPICS:
  verb_error, de_het_error, word_order_error, niet_geen_error, preposition_error,
  plural_error, question_form_error
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Either "which sentence is correct?" or "fix the error". Mistakes are typical A2
  basic errors. Only ONE option is fully correct Dutch.
QUESTION STYLES (NL.md): جمله‌ی اشتباه را درست کن · کدام جمله درست است؟ · اشتباه جمله کجاست؟
SECTION CORRECTNESS NOTES
  • In "which is correct?" items, the three wrong options must each contain exactly
    one realistic A2 error; the correct option must be flawless.
WORKED EXAMPLE (topic = "verb_error")
{
  "level":"A2","section":"error_correction","topic":"verb_error","life_context":"food",
  "question_type":"mcq_4","difficulty":1,
  "question_text_nl":"Welke zin is correct?",
  "question_text_fa":"کدام جمله درست است؟",
  "explanation_fa":"«honger hebben» با hebben می‌آید و «ik» می‌شود «heb»: «Ik heb honger.»",
  "grammar_rule_fa":"گرسنه بودن در هلندی = «honger hebben» (با hebben).",
  "extra_example_nl":"Ik heb dorst.","extra_example_fa":"تشنه‌ام.",
  "options":[
    {"key":"A","text_nl":"Ik heb honger.","is_correct":true,"feedback_fa":"✅ درست."},
    {"key":"B","text_nl":"Ik ben honger.","is_correct":false,"feedback_fa":"«honger» با hebben می‌آید، نه zijn."},
    {"key":"C","text_nl":"Ik hebt honger.","is_correct":false,"feedback_fa":"«hebt» برای jij است؛ ik می‌شود heb."},
    {"key":"D","text_nl":"Ik heeft honger.","is_correct":false,"feedback_fa":"«heeft» برای سوم‌شخص است."}
  ]
}
```

## A2 · Listening
```
BUCKET
  level = "A2"  | section = "listening"
SUBTOPICS:
  daily_short_sentence, numbers, clock_time, days, appointment, simple_address,
  simple_shopping, short_message
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Comprehension of one short spoken utterance. Put the spoken text in
  "question_text_nl" after the marker «Je hoort: …» then ask one question.
  NOTE: later the bot can play «Je hoort: …» with text-to-speech; for now it is the
  audio source. Keep utterances short and clearly pronounceable.
QUESTION STYLES (NL.md): چه شنیدی؟ · کدام گزینه با صوت یکی است؟ · زمان یا مکان چیست؟ · گوینده چه می‌خواهد؟
SECTION CORRECTNESS NOTES
  • The answer must come ONLY from the spoken text. Number/time items must be
    unambiguous (e.g. «kwart over acht» = 8:15).
WORKED EXAMPLE (topic = "clock_time")
{
  "level":"A2","section":"listening","topic":"clock_time","life_context":"transport",
  "question_type":"mcq_4","difficulty":1,
  "question_text_nl":"Je hoort: «De trein vertrekt om kwart over acht.»  Hoe laat vertrekt de trein?",
  "question_text_fa":"قطار ساعت چند حرکت می‌کند؟",
  "explanation_fa":"«kwart over acht» یعنی یک‌ربع بعد از هشت = ۸:۱۵.",
  "grammar_rule_fa":"ساعت: «kwart over acht» = 8:15، «kwart voor acht» = 7:45.",
  "extra_example_nl":"Het is half negen.","extra_example_fa":"ساعت هشت‌و‌نیم است.",
  "options":[
    {"key":"A","text_nl":"7:45","is_correct":false,"feedback_fa":"این «kwart voor acht» می‌شود."},
    {"key":"B","text_nl":"8:08","is_correct":false,"feedback_fa":"«kwart» یعنی یک‌ربع، نه ۸ دقیقه."},
    {"key":"C","text_nl":"8:15","is_correct":true,"feedback_fa":"✅ درست؛ kwart over acht = 8:15."},
    {"key":"D","text_nl":"8:45","is_correct":false,"feedback_fa":"این «kwart voor negen» می‌شود."}
  ]
}
```

## A2 · Writing
```
BUCKET
  level = "A2"  | section = "writing"
SUBTOPICS:
  short_whatsapp, simple_apology, saying_delay, request_appointment,
  reply_simple_email, short_problem_description
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Productive skill tested as MCQ: a short situation is given; the learner chooses
  the BEST short message/sentence to write. (Free typing comes later; for now it is
  "choose the best message".)
QUESTION STYLES (NL.md): انتخاب جمله/پیام مناسب · بهتر کردن جمله · انتخاب ترجمه‌ی درست فارسی→هلندی
SECTION CORRECTNESS NOTES
  • Exactly one option is correct, polite, and appropriate for the situation and
    register. Wrong options are too rude, wrong content, or grammatically broken.
WORKED EXAMPLE (topic = "saying_delay")
{
  "level":"A2","section":"writing","topic":"saying_delay","life_context":"work",
  "question_type":"mcq_4","difficulty":1,
  "question_text_nl":"Je bent ziek en kunt niet werken. Welk bericht is het beste voor je werkgever?",
  "question_text_fa":"کدام پیام برای کارفرما بهترین است؟",
  "explanation_fa":"پیامِ مودبانه و روشن که می‌گویی مریضی و امروز نمی‌توانی بیایی بهترین است.",
  "grammar_rule_fa":"پیام رسمی کوتاه: مودب، روشن، با عذرخواهی.",
  "extra_example_nl":"Sorry, ik ben ziek en kom vandaag niet.","extra_example_fa":"ببخشید، مریضم و امروز نمی‌آیم.",
  "options":[
    {"key":"A","text_nl":"Hallo, ik ben ziek en kan vandaag niet komen. Sorry voor het ongemak.","is_correct":true,"feedback_fa":"✅ مودبانه، روشن و درست."},
    {"key":"B","text_nl":"Ik kom niet. Doei.","is_correct":false,"feedback_fa":"برای کارفرما بی‌ادبانه و ناقص است."},
    {"key":"C","text_nl":"ik ziek niet werk vandaag","is_correct":false,"feedback_fa":"دستور جمله غلط است."},
    {"key":"D","text_nl":"Waarom moet ik komen?","is_correct":false,"feedback_fa":"به موقعیت ربط ندارد."}
  ]
}
```

## A2 · Speaking
```
BUCKET
  level = "A2"  | section = "speaking"
SUBTOPICS:
  self_introduction, telling_a_problem, short_answer, asking_help, daily_routine,
  short_sentence_pronunciation
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Spoken interaction tested as MCQ: pick the natural, correct spoken sentence/reply
  for the situation. (Real voice answers come later.)
QUESTION STYLES (NL.md): انتخاب جمله‌ی گفتاری درست · بهترین جواب کوتاه در مکالمه · جمله‌ی طبیعی برای گفتن
SECTION CORRECTNESS NOTES
  • Exactly one option is the natural spoken response. Wrong options answer a
    different question, are off-topic, or unnatural.
WORKED EXAMPLE (topic = "short_answer")
{
  "level":"A2","section":"speaking","topic":"short_answer","life_context":"greetings",
  "question_type":"mcq_4","difficulty":1,
  "question_text_nl":"Iemand vraagt: «Hoe gaat het met je?»  Wat is een goede, natuurlijke reactie?",
  "question_text_fa":"کدام واکنش طبیعی و درست است؟",
  "explanation_fa":"به «hoe gaat het?» معمولاً با «Het gaat goed, dank je» جواب می‌دهیم.",
  "grammar_rule_fa":"احوالپرسی: «Hoe gaat het?» → «Het gaat goed, en met jou?»",
  "extra_example_nl":"Het gaat wel, dank je.","extra_example_fa":"بد نیست، ممنون.",
  "options":[
    {"key":"A","text_nl":"Het gaat goed, dank je. En met jou?","is_correct":true,"feedback_fa":"✅ جوابِ طبیعی و درست."},
    {"key":"B","text_nl":"Ik ben twaalf jaar.","is_correct":false,"feedback_fa":"این جوابِ «چند سالته» است."},
    {"key":"C","text_nl":"Het is maandag.","is_correct":false,"feedback_fa":"این درباره‌ی روز است."},
    {"key":"D","text_nl":"In Amsterdam.","is_correct":false,"feedback_fa":"این جوابِ «کجا زندگی می‌کنی» است."}
  ]
}
```

## A2 · Formal vs Informal
```
BUCKET
  level = "A2"  | section = "formal_informal"
SUBTOPICS:
  jij_u, formal_informal_greeting, simple_formal_request, message_to_friend,
  message_to_gemeente_doctor, thanks_closing
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Recognise/choose the right register (formal vs informal) for a situation:
  jij vs u, greetings, openings/closings.
QUESTION STYLES (NL.md): رسمی یا غیررسمی؟ · کدام جمله برای دکتر/اداره بهتر است؟ · کدام برای دوست بهتر است؟ · طبیعی‌ترش کن
SECTION CORRECTNESS NOTES
  • Exactly one option matches the required register for the stated addressee.
WORKED EXAMPLE (topic = "message_to_gemeente_doctor")
{
  "level":"A2","section":"formal_informal","topic":"message_to_gemeente_doctor","life_context":"gemeente",
  "question_type":"mcq_4","difficulty":1,
  "question_text_nl":"Je schrijft een e-mail naar de gemeente. Welke aanhef is het meest gepast?",
  "question_text_fa":"کدام سرآغاز برای ایمیل به شهرداری مناسب‌تر است؟",
  "explanation_fa":"برای نامه‌ی رسمی به اداره از «Geachte heer/mevrouw,» استفاده می‌شود.",
  "grammar_rule_fa":"نامه‌ی رسمی: «Geachte heer/mevrouw,»؛ غیررسمی: «Hoi …».",
  "extra_example_nl":"Geachte mevrouw De Vries,","extra_example_fa":"خانم دِ‌فریسِ گرامی،",
  "options":[
    {"key":"A","text_nl":"Geachte heer/mevrouw,","is_correct":true,"feedback_fa":"✅ سرآغاز رسمی و درست."},
    {"key":"B","text_nl":"Hoi!","is_correct":false,"feedback_fa":"برای اداره خیلی غیررسمی است."},
    {"key":"C","text_nl":"Yo,","is_correct":false,"feedback_fa":"کاملاً غیررسمی و نامناسب."},
    {"key":"D","text_nl":"Hey jij,","is_correct":false,"feedback_fa":"برای نامه‌ی رسمی مناسب نیست."}
  ]
}
```

---
---

# سطح B1
هدف B1: کاربر مستقل‌تر صحبت کند، مشکل را توضیح دهد، دلیل بدهد، درخواست بنویسد و متن‌های واقعی را بهتر بفهمد.

## B1 · Grammar
```
BUCKET
  level = "B1"  | section = "grammar"
SUBTOPICS:
  perfect_tense_full, imperfect_tense, subordinate_omdat_als_dat,
  word_order_after_omdat, modal_verbs_long, separable_verbs_past, reflexive_verbs,
  comparative_superlative, pronouns, conjunctions, common_prepositions,
  relative_die_dat
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Perfect & imperfect; subordinate clauses (omdat/als/dat → verb to the end);
  comparatives; pronouns; common conjunctions and prepositions; simple relative
  clauses. Longer sentences than A2, still everyday.
QUESTION STYLES (NL.md): انتخاب ساختار درست · کامل کردن جمله · تشخیص ترتیب کلمات · تصحیح جمله
SECTION CORRECTNESS NOTES
  • For subordinate-clause items, the correct option must place the finite verb at
    the END of the clause (omdat hij ziek is). Distractors use main-clause order.
WORKED EXAMPLE (topic = "subordinate_omdat_als_dat")
{
  "level":"B1","section":"grammar","topic":"subordinate_omdat_als_dat","life_context":"work",
  "question_type":"mcq_4","difficulty":2,
  "question_text_nl":"Hij komt later omdat hij de bus ___.",
  "question_text_fa":"کدام گزینه جمله را درست کامل می‌کند؟",
  "explanation_fa":"بعد از «omdat» فعل به آخر می‌رود؛ «de bus mist» درست است.",
  "grammar_rule_fa":"در جمله‌ی فرعی با omdat/als/dat، فعل صرف‌شده به انتهای جمله می‌رود.",
  "extra_example_nl":"Ik blijf thuis omdat ik ziek ben.","extra_example_fa":"خانه می‌مانم چون مریضم.",
  "options":[
    {"key":"A","text_nl":"mist","is_correct":true,"feedback_fa":"✅ درست؛ فعل در آخر: omdat hij de bus mist."},
    {"key":"B","text_nl":"mist de bus","is_correct":false,"feedback_fa":"ترتیب اشتباه؛ «de bus» قبل از فعل می‌آید."},
    {"key":"C","text_nl":"heeft mist","is_correct":false,"feedback_fa":"صرف اشتباه است."},
    {"key":"D","text_nl":"missen","is_correct":false,"feedback_fa":"باید با فاعل hij صرف شود: mist."}
  ]
}
```

## B1 · Vocabulary in Context
```
BUCKET
  level = "B1"  | section = "vocab_in_context"
SUBTOPICS:
  work_contract, illness_doctor, school_child, house_rent, gemeente, bank_payment,
  simple_complaint, transport, insurance, formal_appointment, online_shopping,
  customer_service
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Practical B1 vocabulary for real Dutch life (work, gemeente, bank, insurance,
  rent, customer service), used in a context sentence.
QUESTION STYLES (NL.md): انتخاب واژه‌ی مناسب در متن · معنی اصطلاح ساده · فرق کلمات نزدیک · کاربرد واقعی
WORKED EXAMPLE (topic = "house_rent")
{
  "level":"B1","section":"vocab_in_context","topic":"house_rent","life_context":"home",
  "question_type":"mcq_4","difficulty":2,
  "question_text_nl":"Ik betaal elke maand ___ voor mijn appartement aan de verhuurder.",
  "question_text_fa":"کدام واژه در جمله مناسب است؟",
  "explanation_fa":"پولی که ماهانه برای خانه می‌دهی «huur» (اجاره) است.",
  "grammar_rule_fa":"واژگان اجاره: huur=اجاره، verhuurder=موجر، huurder=مستأجر.",
  "extra_example_nl":"De huur gaat volgend jaar omhoog.","extra_example_fa":"اجاره سال بعد بالا می‌رود.",
  "options":[
    {"key":"A","text_nl":"huur","is_correct":true,"feedback_fa":"✅ درست؛ huur = اجاره."},
    {"key":"B","text_nl":"salaris","is_correct":false,"feedback_fa":"«salaris» یعنی حقوق."},
    {"key":"C","text_nl":"belasting","is_correct":false,"feedback_fa":"«belasting» یعنی مالیات."},
    {"key":"D","text_nl":"korting","is_correct":false,"feedback_fa":"«korting» یعنی تخفیف."}
  ]
}
```

## B1 · Reading
```
BUCKET
  level = "B1"  | section = "reading"
SUBTOPICS:
  simple_formal_email, gemeente_letter, school_message, short_instruction, job_ad,
  simple_contract, service_notice, short_rules
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  A short B1 formal/practical text inside "question_text_nl", then one question
  about purpose, required action, or a key detail.
QUESTION STYLES (NL.md): هدف متن چیست؟ · چه کاری باید انجام شود؟ · کدام گزینه درست است؟ · اطلاعات مهم را پیدا کن · نتیجه‌ی متن چیست؟
WORKED EXAMPLE (topic = "gemeente_letter")
{
  "level":"B1","section":"reading","topic":"gemeente_letter","life_context":"gemeente",
  "question_type":"mcq_4","difficulty":2,
  "question_text_nl":"Brief: «U moet uw nieuwe adres binnen vijf dagen doorgeven aan de gemeente.»  Wat moet u doen?",
  "question_text_fa":"طبق نامه باید چه کار کنید؟",
  "explanation_fa":"نامه می‌گوید باید آدرس جدید را ظرف ۵ روز به شهرداری اطلاع دهید.",
  "grammar_rule_fa":"اقدامِ خواسته‌شده را از متن پیدا کن: «doorgeven» = اطلاع دادن.",
  "extra_example_nl":"Geef uw adreswijziging op tijd door.","extra_example_fa":"تغییر آدرس را به‌موقع اطلاع بده.",
  "options":[
    {"key":"A","text_nl":"Het nieuwe adres binnen vijf dagen doorgeven","is_correct":true,"feedback_fa":"✅ درست؛ دقیقاً همان چیزی که نامه می‌گوید."},
    {"key":"B","text_nl":"Vijf dagen wachten","is_correct":false,"feedback_fa":"متن درباره‌ی صبر کردن نیست."},
    {"key":"C","text_nl":"Naar een andere stad verhuizen","is_correct":false,"feedback_fa":"چنین چیزی نوشته نشده."},
    {"key":"D","text_nl":"Niets doen","is_correct":false,"feedback_fa":"متن یک اقدام لازم را می‌خواهد."}
  ]
}
```

## B1 · Meaning & Intention
```
BUCKET
  level = "B1"  | section = "meaning"
SUBTOPICS:
  indirect_meaning, polite_request, complaint, suggestion, advice, warning,
  agree_disagree, giving_reason
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Understand intention/tone of slightly indirect B1 utterances and pick the best
  interpretation or reaction.
QUESTION STYLES (NL.md): گوینده واقعاً چه می‌خواهد؟ · بهترین واکنش چیست؟ · لحن جمله چیست؟ · احساس جمله چیست؟
WORKED EXAMPLE (topic = "polite_request")
{
  "level":"B1","section":"meaning","topic":"polite_request","life_context":"work",
  "question_type":"mcq_4","difficulty":2,
  "question_text_nl":"Je collega zegt: «Zou je dit rapport vandaag nog kunnen afmaken?»  Wat bedoelt hij?",
  "question_text_fa":"همکار واقعاً چه می‌خواهد؟",
  "explanation_fa":"«Zou je … kunnen?» یک درخواستِ مودبانه است؛ او می‌خواهد امروز گزارش را تمام کنی.",
  "grammar_rule_fa":"«Zou je … kunnen?» = درخواستِ مودبانه و غیرمستقیم.",
  "extra_example_nl":"Zou je me even kunnen helpen?","extra_example_fa":"می‌شه یه لحظه کمکم کنی؟",
  "options":[
    {"key":"A","text_nl":"Hij vraagt je het rapport vandaag af te maken.","is_correct":true,"feedback_fa":"✅ درست؛ درخواستِ مودبانه است."},
    {"key":"B","text_nl":"Hij is boos op je.","is_correct":false,"feedback_fa":"لحن مودبانه است، نه عصبانی."},
    {"key":"C","text_nl":"Hij wil zelf het rapport doen.","is_correct":false,"feedback_fa":"از تو می‌خواهد، نه خودش."},
    {"key":"D","text_nl":"Hij geeft je een vrije dag.","is_correct":false,"feedback_fa":"درباره‌ی مرخصی چیزی نگفت."}
  ]
}
```

## B1 · Dialogue
```
BUCKET
  level = "B1"  | section = "dialogue"
SUBTOPICS:
  call_doctor, talk_employer, school_conversation, call_gemeente,
  neighbour_conversation, service_complaint, booking_appointment, asking_clarification
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Slightly longer real-life conversations (doctor, employer, gemeente, service);
  pick the natural, polite continuation.
QUESTION STYLES (NL.md): ادامه‌ی طبیعی مکالمه · انتخاب جوابِ مودبانه · کامل کردن دیالوگ · تشخیص سوءتفاهم
WORKED EXAMPLE (topic = "booking_appointment")
{
  "level":"B1","section":"dialogue","topic":"booking_appointment","life_context":"health",
  "question_type":"mcq_4","difficulty":2,
  "question_text_nl":"Assistente: «De dokter kan u woensdag om 10:00 uur zien. Schikt dat?»  U: «___»",
  "question_text_fa":"کدام جواب مناسب و طبیعی است؟",
  "explanation_fa":"«Schikt dat?» یعنی «مناسب است؟»؛ جوابِ پذیرفتن و تشکر مناسب است.",
  "grammar_rule_fa":"«Schikt dat?» = آیا برایتان مناسب است؟",
  "extra_example_nl":"Ja, dat is prima. Bedankt.","extra_example_fa":"بله، عالیه. ممنون.",
  "options":[
    {"key":"A","text_nl":"Ja, dat is goed. Dank u wel.","is_correct":true,"feedback_fa":"✅ پذیرشِ مودبانه و درست."},
    {"key":"B","text_nl":"Ik weet niet waar de dokter woont.","is_correct":false,"feedback_fa":"بی‌ربط به سؤال است."},
    {"key":"C","text_nl":"Tot ziens.","is_correct":false,"feedback_fa":"هنوز وقت را تأیید نکرده‌ای."},
    {"key":"D","text_nl":"Ik ben de dokter.","is_correct":false,"feedback_fa":"با موقعیت نمی‌خواند."}
  ]
}
```

## B1 · Error Correction
```
BUCKET
  level = "B1"  | section = "error_correction"
SUBTOPICS:
  subclause_word_order, past_tense, modal_verbs, prepositions, pronouns,
  conjunctions, formal_informal_mix, persian_like_sentences
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Find/fix typical B1 errors: subordinate word order, past tense, prepositions,
  pronouns, calque ("Persian-style") sentences.
QUESTION STYLES (NL.md): جمله را طبیعی‌تر کن · اشتباه گرامری را پیدا کن · کدام نسخه بهتر است؟ · جمله را اصلاح کن
WORKED EXAMPLE (topic = "subclause_word_order")
{
  "level":"B1","section":"error_correction","topic":"subclause_word_order","life_context":"daily",
  "question_type":"mcq_4","difficulty":2,
  "question_text_nl":"Welke zin is correct?",
  "question_text_fa":"کدام جمله درست است؟",
  "explanation_fa":"بعد از «dat» فعل به آخر می‌رود: «… dat hij morgen komt.»",
  "grammar_rule_fa":"در جمله‌ی فرعی با dat، فعل در انتها می‌آید.",
  "extra_example_nl":"Ik denk dat het morgen regent.","extra_example_fa":"فکر می‌کنم فردا باران می‌بارد.",
  "options":[
    {"key":"A","text_nl":"Ik weet dat hij morgen komt.","is_correct":true,"feedback_fa":"✅ درست؛ فعل komt در آخر است."},
    {"key":"B","text_nl":"Ik weet dat hij komt morgen.","is_correct":false,"feedback_fa":"«morgen» نباید بعد از فعل بیاید."},
    {"key":"C","text_nl":"Ik weet dat komt hij morgen.","is_correct":false,"feedback_fa":"ترتیب فاعل/فعل اشتباه است."},
    {"key":"D","text_nl":"Ik weet hij morgen komt.","is_correct":false,"feedback_fa":"«dat» جا افتاده است."}
  ]
}
```

## B1 · Listening
```
BUCKET
  level = "B1"  | section = "listening"
SUBTOPICS:
  simple_voicemail, school_message, train_bus_announcement, simple_work_conversation,
  doctor_call, customer_service_talk, appointment
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Comprehension of a short B1 spoken message (voicemail, announcement, work call).
  Spoken text goes in "question_text_nl" after «Je hoort: …». (TTS later.)
QUESTION STYLES (NL.md): موضوع اصلی چیست؟ · گوینده چه می‌خواهد؟ · زمان/مکان چیست؟ · چه اقدامی لازم است؟
WORKED EXAMPLE (topic = "simple_voicemail")
{
  "level":"B1","section":"listening","topic":"simple_voicemail","life_context":"health",
  "question_type":"mcq_4","difficulty":2,
  "question_text_nl":"Je hoort: «Goedemorgen, met de huisartsenpraktijk. Uw afspraak van vrijdag is verzet naar maandag om 14:00 uur.»  Wat is er veranderd?",
  "question_text_fa":"چه چیزی تغییر کرده است؟",
  "explanation_fa":"پیام می‌گوید نوبتِ جمعه به دوشنبه ساعت ۱۴:۰۰ منتقل شده است.",
  "grammar_rule_fa":"«verzet naar …» یعنی جابه‌جا شد به …",
  "extra_example_nl":"De afspraak is verzet naar dinsdag.","extra_example_fa":"نوبت به سه‌شنبه منتقل شد.",
  "options":[
    {"key":"A","text_nl":"De afspraak is verzet naar maandag 14:00 uur.","is_correct":true,"feedback_fa":"✅ درست؛ همان چیزی که شنیدی."},
    {"key":"B","text_nl":"De afspraak is geannuleerd.","is_correct":false,"feedback_fa":"لغو نشده، جابه‌جا شده."},
    {"key":"C","text_nl":"De praktijk is gesloten.","is_correct":false,"feedback_fa":"چنین چیزی گفته نشد."},
    {"key":"D","text_nl":"De afspraak blijft op vrijdag.","is_correct":false,"feedback_fa":"به دوشنبه منتقل شده است."}
  ]
}
```

## B1 · Writing
```
BUCKET
  level = "B1"  | section = "writing"
SUBTOPICS:
  short_formal_email, problem_description, request_information, apology,
  simple_complaint, reply_invitation, message_school_doctor_employer
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  MCQ form: choose the best B1 sentence/structure for a short formal email or
  message (polite, clear, correct register).
QUESTION STYLES (NL.md): انتخاب جمله‌ی مناسب برای ایمیل · بهتر کردن متن · انتخاب ساختار درست
WORKED EXAMPLE (topic = "request_information")
{
  "level":"B1","section":"writing","topic":"request_information","life_context":"gemeente",
  "question_type":"mcq_4","difficulty":2,
  "question_text_nl":"Je wilt beleefd om informatie vragen in een formele e-mail. Welke zin is het beste?",
  "question_text_fa":"کدام جمله برای درخواستِ مودبانه‌ی اطلاعات در ایمیل رسمی بهترین است؟",
  "explanation_fa":"جمله‌ی مودبانه و رسمی با «Zou u mij kunnen laten weten …» بهترین انتخاب است.",
  "grammar_rule_fa":"درخواست رسمی: «Zou u mij kunnen laten weten of …».",
  "extra_example_nl":"Zou u mij meer informatie kunnen sturen?","extra_example_fa":"می‌شود اطلاعات بیشتری برایم بفرستید؟",
  "options":[
    {"key":"A","text_nl":"Zou u mij kunnen laten weten wat de kosten zijn?","is_correct":true,"feedback_fa":"✅ مودبانه و رسمی."},
    {"key":"B","text_nl":"Zeg mij de kosten nu.","is_correct":false,"feedback_fa":"دستوری و بی‌ادبانه است."},
    {"key":"C","text_nl":"Ik wil kosten weten doei.","is_correct":false,"feedback_fa":"غیررسمی و نادرست."},
    {"key":"D","text_nl":"Hoeveel kost het of niet?","is_correct":false,"feedback_fa":"جمله نامفهوم و نامودب است."}
  ]
}
```

## B1 · Speaking
```
BUCKET
  level = "B1"  | section = "speaking"
SUBTOPICS:
  explain_problem, explain_experience, give_reason, ask_help, simple_opinion,
  talk_work_home_family
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  MCQ form: pick the natural B1 spoken sentence to explain a problem, give a
  reason, or state a simple opinion.
QUESTION STYLES (NL.md): انتخاب جمله‌ی گفتاری مناسب · بهترین جواب در مکالمه‌ی موقعیتی · جمله‌ی طبیعی برای توضیح
WORKED EXAMPLE (topic = "give_reason")
{
  "level":"B1","section":"speaking","topic":"give_reason","life_context":"work",
  "question_type":"mcq_4","difficulty":2,
  "question_text_nl":"Je wilt uitleggen waarom je te laat was. Welke zin klinkt het meest natuurlijk?",
  "question_text_fa":"کدام جمله برای توضیحِ دلیلِ تأخیر طبیعی‌تر است؟",
  "explanation_fa":"توضیحِ روان با «omdat» و دلیلِ واقعی طبیعی‌ترین است.",
  "grammar_rule_fa":"بیان دلیل: «… omdat …» با ترتیب درستِ جمله‌ی فرعی.",
  "extra_example_nl":"Ik was te laat omdat de trein vertraging had.","extra_example_fa":"دیر کردم چون قطار تأخیر داشت.",
  "options":[
    {"key":"A","text_nl":"Sorry, ik was te laat omdat er een file was.","is_correct":true,"feedback_fa":"✅ طبیعی و درست."},
    {"key":"B","text_nl":"Te laat ik file zijn.","is_correct":false,"feedback_fa":"دستور جمله غلط است."},
    {"key":"C","text_nl":"Ik te laat want file.","is_correct":false,"feedback_fa":"فعل و ساختار ناقص است."},
    {"key":"D","text_nl":"File was omdat te laat.","is_correct":false,"feedback_fa":"ترتیب کلمات بی‌معنی است."}
  ]
}
```

## B1 · Formal vs Informal
```
BUCKET
  level = "B1"  | section = "formal_informal"
SUBTOPICS:
  friend_vs_organization, polite_request, simple_formal_complaint,
  email_opening_closing, u_jij_use, soften_direct_sentence
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Choose the right register / soften direct sentences for organizations vs friends.
QUESTION STYLES (NL.md): کدام رسمی‌تر است؟ · کدام طبیعی‌تر است؟ · جمله را مودبانه‌تر کن · جمله‌ی مناسب موقعیت
WORKED EXAMPLE (topic = "soften_direct_sentence")
{
  "level":"B1","section":"formal_informal","topic":"soften_direct_sentence","life_context":"customer_service",
  "question_type":"mcq_4","difficulty":2,
  "question_text_nl":"Direct: «Stuur me de factuur.»  Welke zin is beleefder voor een bedrijf?",
  "question_text_fa":"کدام جمله برای یک شرکت مودبانه‌تر است؟",
  "explanation_fa":"با «Zou u … kunnen sturen?» جمله مودبانه‌تر و رسمی‌تر می‌شود.",
  "grammar_rule_fa":"نرم‌کردن جمله: «Zou u … kunnen …?» به‌جای امرِ مستقیم.",
  "extra_example_nl":"Zou u mij de factuur kunnen sturen?","extra_example_fa":"می‌شود فاکتور را برایم بفرستید؟",
  "options":[
    {"key":"A","text_nl":"Zou u mij de factuur kunnen sturen?","is_correct":true,"feedback_fa":"✅ مودبانه و رسمی."},
    {"key":"B","text_nl":"Stuur nu de factuur.","is_correct":false,"feedback_fa":"همچنان دستوری است."},
    {"key":"C","text_nl":"Factuur sturen jij.","is_correct":false,"feedback_fa":"دستور جمله غلط است."},
    {"key":"D","text_nl":"Ik wil factuur of niet.","is_correct":false,"feedback_fa":"نامفهوم و نامودب."}
  ]
}
```

---
---

# سطح B2
هدف B2: کاربر دقیق‌تر، طبیعی‌تر و حرفه‌ای‌تر صحبت/نوشتار داشته باشد؛ نظر بدهد، استدلال کند، پیام رسمی قوی بنویسد و معنی‌های غیرمستقیم را بفهمد.

## B2 · Grammar
```
BUCKET
  level = "B2"  | section = "grammar"
SUBTOPICS:
  complex_subordinate, passive_voice, conditional, advanced_word_order,
  relative_clauses, er_constructions, om_te_infinitive, hoewel_ondanks,
  nuance_zou_kunnen_mogen, indirect_speech, advanced_connectors
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Advanced structures: passive, conditional, complex/relative clauses, er-
  constructions, om te + infinitive, concessive (hoewel/ondanks), nuance modals,
  indirect speech, advanced connectors. Natural, near-native correctness required.
QUESTION STYLES (NL.md): انتخاب ساختار طبیعی‌تر · بازنویسی جمله · تشخیص خطای ظریف · انتخاب بهترین ساختار رسمی
WORKED EXAMPLE (topic = "passive_voice")
{
  "level":"B2","section":"grammar","topic":"passive_voice","life_context":"work",
  "question_type":"mcq_4","difficulty":2,
  "question_text_nl":"Het rapport ___ gisteren door de manager goedgekeurd.",
  "question_text_fa":"کدام گزینه جمله‌ی مجهول را درست کامل می‌کند؟",
  "explanation_fa":"مجهولِ گذشته با «werd/werden» ساخته می‌شود؛ فاعلِ مفرد «het rapport» → «werd».",
  "grammar_rule_fa":"مجهولِ گذشته: «werd/werden + … + voltooid deelwoord».",
  "extra_example_nl":"De brief werd vandaag verstuurd.","extra_example_fa":"نامه امروز فرستاده شد.",
  "options":[
    {"key":"A","text_nl":"werd","is_correct":true,"feedback_fa":"✅ درست؛ مجهولِ گذشته‌ی مفرد."},
    {"key":"B","text_nl":"werden","is_correct":false,"feedback_fa":"«werden» برای جمع است؛ فاعل مفرد است."},
    {"key":"C","text_nl":"is","is_correct":false,"feedback_fa":"با «gisteren» زمانِ گذشته‌ی «werd» طبیعی‌تر است."},
    {"key":"D","text_nl":"wordt","is_correct":false,"feedback_fa":"«wordt» حال است؛ جمله گذشته است."}
  ]
}
```

## B2 · Vocabulary in Context
```
BUCKET
  level = "B2"  | section = "vocab_in_context"
SUBTOPICS:
  professional_work, job_interview, contract_law, tax_administratie,
  official_services, dispute_negotiation, giving_opinion, pros_cons,
  personal_finance, education_society, technology_media
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Professional/abstract B2 vocabulary, nuance between near-synonyms, common
  collocations, formal expressions.
QUESTION STYLES (NL.md): معنی واژه در متن · تفاوت nuance کلمات · انتخاب واژه‌ی حرفه‌ای‌تر · collocation رایج
WORKED EXAMPLE (topic = "professional_work")
{
  "level":"B2","section":"vocab_in_context","topic":"professional_work","life_context":"work",
  "question_type":"mcq_4","difficulty":2,
  "question_text_nl":"Na een lang gesprek hebben de twee partijen eindelijk een ___ bereikt.",
  "question_text_fa":"کدام واژه در این بافت حرفه‌ای مناسب است؟",
  "explanation_fa":"«een overeenkomst bereiken» یعنی به توافق رسیدن؛ collocationِ رایج است.",
  "grammar_rule_fa":"collocation: «een overeenkomst/akkoord bereiken».",
  "extra_example_nl":"We hebben een akkoord bereikt.","extra_example_fa":"به توافق رسیدیم.",
  "options":[
    {"key":"A","text_nl":"overeenkomst","is_correct":true,"feedback_fa":"✅ درست؛ «overeenkomst bereiken»."},
    {"key":"B","text_nl":"gebouw","is_correct":false,"feedback_fa":"«gebouw» یعنی ساختمان؛ بی‌ربط."},
    {"key":"C","text_nl":"vakantie","is_correct":false,"feedback_fa":"«vakantie» یعنی تعطیلات."},
    {"key":"D","text_nl":"maaltijd","is_correct":false,"feedback_fa":"«maaltijd» یعنی وعده‌ی غذایی."}
  ]
}
```

## B2 · Reading
```
BUCKET
  level = "B2"  | section = "reading"
SUBTOPICS:
  short_article, complex_formal_email, opinion_analysis, work_text, contract_terms,
  multistep_instruction, complaint_response, simplified_news
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  A short B2 text (2–4 sentences) in "question_text_nl"; ask about the author's
  opinion, a logical conclusion, paragraph purpose, or best summary.
QUESTION STYLES (NL.md): نویسنده چه نظری دارد؟ · نتیجه‌ی منطقی چیست؟ · کدام برداشت درست‌تر است؟ · هدف پاراگراف چیست؟ · بهترین خلاصه کدام است؟
WORKED EXAMPLE (topic = "opinion_analysis")
{
  "level":"B2","section":"reading","topic":"opinion_analysis","life_context":"society",
  "question_type":"mcq_4","difficulty":3,
  "question_text_nl":"Tekst: «Thuiswerken heeft voordelen, maar volgens de auteur verliezen werknemers op de lange termijn het contact met collega's.»  Wat vindt de auteur?",
  "question_text_fa":"نظر نویسنده چیست؟",
  "explanation_fa":"نویسنده مزایا را می‌پذیرد ولی نگرانِ از‌دست‌رفتنِ ارتباط با همکاران در درازمدت است.",
  "grammar_rule_fa":"نظر/اما را دنبال کن: «… maar volgens de auteur …».",
  "extra_example_nl":"Het is handig, maar niet zonder nadelen.","extra_example_fa":"راحت است، اما بدون عیب نیست.",
  "options":[
    {"key":"A","text_nl":"Thuiswerken heeft voordelen, maar ook een nadeel op lange termijn.","is_correct":true,"feedback_fa":"✅ درست؛ هم مزیت هم نگرانیِ درازمدت."},
    {"key":"B","text_nl":"Thuiswerken is alleen maar slecht.","is_correct":false,"feedback_fa":"نویسنده مزایا را هم قبول دارد."},
    {"key":"C","text_nl":"Thuiswerken heeft geen nadelen.","is_correct":false,"feedback_fa":"یک نگرانی را مطرح کرده."},
    {"key":"D","text_nl":"Werknemers willen niet thuiswerken.","is_correct":false,"feedback_fa":"چنین چیزی نگفته است."}
  ]
}
```

## B2 · Meaning & Intention
```
BUCKET
  level = "B2"  | section = "meaning"
SUBTOPICS:
  indirect_meaning, soft_irony, diplomacy, polite_refusal, indirect_suggestion,
  professional_warning, constructive_criticism
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Understand hidden/diplomatic intention and tone in professional contexts; pick
  the correct interpretation or the most professional response.
QUESTION STYLES (NL.md): منظور پنهان چیست؟ · لحن جمله چیست؟ · چقدر مستقیم/نرم است؟ · بهترین پاسخ حرفه‌ای چیست؟
WORKED EXAMPLE (topic = "polite_refusal")
{
  "level":"B2","section":"meaning","topic":"polite_refusal","life_context":"work",
  "question_type":"mcq_4","difficulty":3,
  "question_text_nl":"Je manager zegt: «Het is een interessant idee, maar misschien is dit niet het juiste moment.»  Wat bedoelt hij eigenlijk?",
  "question_text_fa":"منظورِ واقعیِ مدیر چیست؟",
  "explanation_fa":"این یک ردِ مودبانه است: فعلاً ایده را نمی‌پذیرد، هرچند با لحن نرم.",
  "grammar_rule_fa":"ردِ دیپلماتیک: تعریفِ کوتاه + «maar … niet het juiste moment».",
  "extra_example_nl":"Goed idee, maar laten we het later bespreken.","extra_example_fa":"ایده‌ی خوبیه، اما بذار بعداً صحبت کنیم.",
  "options":[
    {"key":"A","text_nl":"Hij wijst het idee voorlopig beleefd af.","is_correct":true,"feedback_fa":"✅ درست؛ ردِ مودبانه است."},
    {"key":"B","text_nl":"Hij accepteert het idee meteen.","is_correct":false,"feedback_fa":"«maar … niet het juiste moment» یعنی نه."},
    {"key":"C","text_nl":"Hij is boos over het idee.","is_correct":false,"feedback_fa":"لحن نرم و مودبانه است."},
    {"key":"D","text_nl":"Hij vraagt om meer geld.","is_correct":false,"feedback_fa":"درباره‌ی پول چیزی نگفت."}
  ]
}
```

## B2 · Dialogue
```
BUCKET
  level = "B2"  | section = "dialogue"
SUBTOPICS:
  business_meeting, job_interview, client_negotiation, formal_call,
  conflict_resolution, project_explanation, defend_opinion, ask_clarification
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Professional conversations; pick the most appropriate, diplomatic, natural reply.
QUESTION STYLES (NL.md): بهترین پاسخ در مکالمه‌ی حرفه‌ای · ادامه‌ی منطقیِ بحث · پاسخِ دیپلماتیک · مدیریت سوءتفاهم
WORKED EXAMPLE (topic = "job_interview")
{
  "level":"B2","section":"dialogue","topic":"job_interview","life_context":"work",
  "question_type":"mcq_4","difficulty":3,
  "question_text_nl":"Interviewer: «Wat zou u zien als uw grootste verbeterpunt?»  Wat is de beste reactie?",
  "question_text_fa":"کدام پاسخ در مصاحبه حرفه‌ای‌ترین است؟",
  "explanation_fa":"پاسخِ حرفه‌ای: یک نقطه‌ضعفِ واقعی + اینکه چطور رویش کار می‌کنی.",
  "grammar_rule_fa":"در مصاحبه، نقطه‌ضعف را با برنامه‌ی بهبود بیان کن.",
  "extra_example_nl":"Ik werk eraan om beter te delegeren.","extra_example_fa":"دارم روی بهتر واگذار‌کردن کار می‌کنم.",
  "options":[
    {"key":"A","text_nl":"Ik vind delegeren soms lastig, maar ik werk daar bewust aan.","is_correct":true,"feedback_fa":"✅ صادقانه و حرفه‌ای با برنامه‌ی بهبود."},
    {"key":"B","text_nl":"Ik heb geen verbeterpunten.","is_correct":false,"feedback_fa":"غیرواقعی و ضعیف است."},
    {"key":"C","text_nl":"Dat gaat u niets aan.","is_correct":false,"feedback_fa":"بی‌ادبانه و نامناسب."},
    {"key":"D","text_nl":"Ik weet het niet.","is_correct":false,"feedback_fa":"بدون محتوا و ضعیف است."}
  ]
}
```

## B2 · Error Correction
```
BUCKET
  level = "B2"  | section = "error_correction"
SUBTOPICS:
  unnatural_but_understandable, advanced_word_order, wrong_register,
  direct_persian_translation, subtle_prepositions, too_direct_sentences,
  weak_formal_text
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Find the subtle error or pick the most natural/professional rewrite. Errors are
  fine-grained (register, preposition nuance, calque), not basic.
QUESTION STYLES (NL.md): متن را طبیعی‌تر کن · بهترین بازنویسی کدام است؟ · اشتباه ظریف چیست؟ · حرفه‌ای‌ترش کن
WORKED EXAMPLE (topic = "subtle_prepositions")
{
  "level":"B2","section":"error_correction","topic":"subtle_prepositions","life_context":"work",
  "question_type":"mcq_4","difficulty":3,
  "question_text_nl":"Welke zin is correct?",
  "question_text_fa":"کدام جمله از نظر حرف اضافه درست است؟",
  "explanation_fa":"«afhankelijk zijn van» با «van» می‌آید: «afhankelijk van het weer».",
  "grammar_rule_fa":"collocation حرف اضافه: «afhankelijk van».",
  "extra_example_nl":"Het hangt af van de prijs.","extra_example_fa":"بستگی به قیمت دارد.",
  "options":[
    {"key":"A","text_nl":"De planning is afhankelijk van het weer.","is_correct":true,"feedback_fa":"✅ درست؛ afhankelijk van."},
    {"key":"B","text_nl":"De planning is afhankelijk op het weer.","is_correct":false,"feedback_fa":"«op» اشتباه است؛ باید «van» باشد."},
    {"key":"C","text_nl":"De planning is afhankelijk aan het weer.","is_correct":false,"feedback_fa":"«aan» اشتباه است."},
    {"key":"D","text_nl":"De planning is afhankelijk met het weer.","is_correct":false,"feedback_fa":"«met» اشتباه است."}
  ]
}
```

## B2 · Listening
```
BUCKET
  level = "B2"  | section = "listening"
SUBTOPICS:
  work_conversation, two_person_discussion, formal_voicemail, longer_explanation,
  short_meeting, simple_news, customer_complaint, interview
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Comprehension of a longer B2 spoken passage (opinion, proposal, conclusion, tone).
  Spoken text in "question_text_nl" after «Je hoort: …». (TTS later.)
QUESTION STYLES (NL.md): نظر گوینده چیست؟ · چه پیشنهادی می‌دهد؟ · کدام نتیجه درست است؟ · لحنِ گوینده چیست؟ · نکته‌ی اصلی چیست؟
WORKED EXAMPLE (topic = "short_meeting")
{
  "level":"B2","section":"listening","topic":"short_meeting","life_context":"work",
  "question_type":"mcq_4","difficulty":3,
  "question_text_nl":"Je hoort: «Ik denk dat we het project moeten uitstellen; we hebben simpelweg niet genoeg mensen op dit moment.»  Wat stelt de spreker voor?",
  "question_text_fa":"گوینده چه پیشنهادی می‌دهد؟",
  "explanation_fa":"گوینده می‌گوید به‌خاطر کمبود نیرو پروژه باید به تعویق بیفتد.",
  "grammar_rule_fa":"«uitstellen» یعنی به تعویق انداختن.",
  "extra_example_nl":"We stellen de vergadering uit naar volgende week.","extra_example_fa":"جلسه را به هفته‌ی بعد موکول می‌کنیم.",
  "options":[
    {"key":"A","text_nl":"Het project uitstellen wegens te weinig mensen.","is_correct":true,"feedback_fa":"✅ درست؛ تعویق به‌خاطر کمبود نیرو."},
    {"key":"B","text_nl":"Meteen beginnen met het project.","is_correct":false,"feedback_fa":"برعکسِ چیزی است که گفت."},
    {"key":"C","text_nl":"Het project annuleren.","is_correct":false,"feedback_fa":"«uitstellen» تعویق است، نه لغو."},
    {"key":"D","text_nl":"Meer budget vragen.","is_correct":false,"feedback_fa":"درباره‌ی بودجه چیزی نگفت."}
  ]
}
```

## B2 · Writing
```
BUCKET
  level = "B2"  | section = "writing"
SUBTOPICS:
  full_formal_email, professional_complaint, collaboration_request, client_reply,
  project_explanation, opinion_for_against, simple_linkedin, short_motivation
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  MCQ form: choose the most professional, well-structured B2 sentence for a formal
  email, complaint, or opinion text.
QUESTION STYLES (NL.md): انتخاب جمله‌ی رسمی‌تر · بهترین بازنویسی · انتخاب ساختار حرفه‌ای متن
WORKED EXAMPLE (topic = "professional_complaint")
{
  "level":"B2","section":"writing","topic":"professional_complaint","life_context":"customer_service",
  "question_type":"mcq_4","difficulty":3,
  "question_text_nl":"Je schrijft een formele klacht over een te late levering. Welke openingszin is het meest professioneel?",
  "question_text_fa":"کدام جمله‌ی آغازین برای شکایتِ رسمی حرفه‌ای‌تر است؟",
  "explanation_fa":"شروعِ رسمی و روشن که موضوع شکایت را مودبانه بیان می‌کند بهترین است.",
  "grammar_rule_fa":"شکایت رسمی: مودب، روشن، با ذکرِ موضوع.",
  "extra_example_nl":"Ik schrijf u naar aanleiding van een probleem met mijn bestelling.","extra_example_fa":"درباره‌ی مشکلی با سفارشم برایتان می‌نویسم.",
  "options":[
    {"key":"A","text_nl":"Graag wil ik mijn ongenoegen uiten over de te late levering van mijn bestelling.","is_correct":true,"feedback_fa":"✅ رسمی، روشن و حرفه‌ای."},
    {"key":"B","text_nl":"Jullie zijn echt waardeloos.","is_correct":false,"feedback_fa":"توهین‌آمیز و غیرحرفه‌ای."},
    {"key":"C","text_nl":"levering laat ik boos.","is_correct":false,"feedback_fa":"دستور جمله ناقص است."},
    {"key":"D","text_nl":"Waarom is alles altijd te laat???","is_correct":false,"feedback_fa":"لحنِ احساسی و غیررسمی است."}
  ]
}
```

## B2 · Speaking
```
BUCKET
  level = "B2"  | section = "speaking"
SUBTOPICS:
  opinion_with_reason, work_experience, defend_choice, work_conversation,
  complex_problem, compare_options, interview_answer
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  MCQ form: pick the natural, well-argued B2 spoken sentence (opinion with reason,
  comparison, professional answer).
QUESTION STYLES (NL.md): انتخاب پاسخ حرفه‌ای · بهترین جمله در roleplay کاری · جمله‌ی طبیعی‌تر برای بیان نظر
WORKED EXAMPLE (topic = "opinion_with_reason")
{
  "level":"B2","section":"speaking","topic":"opinion_with_reason","life_context":"work",
  "question_type":"mcq_4","difficulty":3,
  "question_text_nl":"Je wilt je mening geven met een argument. Welke zin klinkt het meest natuurlijk en sterk?",
  "question_text_fa":"کدام جمله برای بیانِ نظر با دلیل طبیعی‌تر و قوی‌تر است؟",
  "explanation_fa":"بیانِ نظر + دلیل با ساختارِ روان («omdat …») قوی‌ترین است.",
  "grammar_rule_fa":"نظر + دلیل: «Ik denk dat …, omdat …».",
  "extra_example_nl":"Ik vind dit een goed plan, omdat het tijd bespaart.","extra_example_fa":"این برنامه را خوب می‌دانم، چون وقت ذخیره می‌کند.",
  "options":[
    {"key":"A","text_nl":"Volgens mij is dit de beste optie, omdat het op de lange termijn goedkoper is.","is_correct":true,"feedback_fa":"✅ نظر + دلیلِ روشن و طبیعی."},
    {"key":"B","text_nl":"Dit beste want goedkoop.","is_correct":false,"feedback_fa":"ساختار ناقص است."},
    {"key":"C","text_nl":"Ik denk niks ervan.","is_correct":false,"feedback_fa":"بدون استدلال و نامناسب."},
    {"key":"D","text_nl":"Optie beste omdat is goedkoop lange.","is_correct":false,"feedback_fa":"ترتیب کلمات بی‌معنی است."}
  ]
}
```

## B2 · Formal vs Informal
```
BUCKET
  level = "B2"  | section = "formal_informal"
SUBTOPICS:
  neutral_formal_professional, soften_sentence, avoid_rudeness, message_to_client,
  message_to_organization, message_to_colleague, professional_request, polite_followup
SUBTOPIC TO GENERATE NOW: <write one slug here>

SCOPE & LEVEL
  Fine register control: neutral vs formal vs professional; soften direct/blunt
  sentences; avoid unintended rudeness in professional messages.
QUESTION STYLES (NL.md): کدام حرفه‌ای‌تر است؟ · کدام زیادی مستقیم است؟ · دیپلماتیک‌ترش کن · بهترین لحن برای مشتری · رسمی را طبیعی‌تر کن
WORKED EXAMPLE (topic = "polite_followup")
{
  "level":"B2","section":"formal_informal","topic":"polite_followup","life_context":"work",
  "question_type":"mcq_4","difficulty":3,
  "question_text_nl":"Je hebt nog geen antwoord gekregen en wilt beleefd herinneren. Welke zin is het meest professioneel?",
  "question_text_fa":"کدام جمله برای یادآوریِ مودبانه حرفه‌ای‌تر است؟",
  "explanation_fa":"یادآوریِ نرم و مودب با «Ik wil u er vriendelijk aan herinneren …» بهترین است.",
  "grammar_rule_fa":"follow-up مودبانه: «Ik wil u er vriendelijk aan herinneren dat …».",
  "extra_example_nl":"Mag ik u vriendelijk vragen hierop te reageren?","extra_example_fa":"می‌شود لطفاً به این پاسخ دهید؟",
  "options":[
    {"key":"A","text_nl":"Ik wil u er vriendelijk aan herinneren dat ik nog op uw reactie wacht.","is_correct":true,"feedback_fa":"✅ مودبانه، حرفه‌ای و روشن."},
    {"key":"B","text_nl":"Waarom antwoordt u niet?","is_correct":false,"feedback_fa":"تند و تنش‌زا است."},
    {"key":"C","text_nl":"Reageer nu meteen.","is_correct":false,"feedback_fa":"دستوری و بی‌ادبانه است."},
    {"key":"D","text_nl":"U bent te traag.","is_correct":false,"feedback_fa":"توهین‌آمیز و غیرحرفه‌ای."}
  ]
}
```

---

## یادداشت برای import (برای من)
خروجی هر زیربخش که آماده شد، با `status="approved"`، `created_by="curated"`،
`reviewed_by="curated"` در جدول `nlern.questions` + `question_options` وارد می‌شود.
امتحان همان‌ها را با `get_next_question_for_section(level, section)` سرو می‌کند — سریع و بدون AI.
