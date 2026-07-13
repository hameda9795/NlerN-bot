# Telegram Bot API 10.1 — Rich Messages Technical Reference

**Status:** Project source of truth  
**Official release:** Bot API 10.1, 11 June 2026  
**Last verified:** 16 June 2026  
**Official API:** https://core.telegram.org/bots/api  
**Official changelog:** https://core.telegram.org/bots/api-changelog

---

## 1. Purpose

Telegram Rich Messages let bots send structured content beyond ordinary
`sendMessage` formatting. Supported structures include headings, paragraphs,
lists, task lists, tables, quotations, footnotes, formulas, collapsible blocks,
media blocks, collages, slideshows, maps, keyboards, and streamed temporary
Rich Message drafts.

Do not confuse Rich Markdown with the older `parse_mode="MarkdownV2"` used by
`sendMessage`.

---

## 2. Core methods

### 2.1 `sendRichMessage`

Use this method to send and persist a Rich Message.

```text
POST https://api.telegram.org/bot<BOT_TOKEN>/sendRichMessage
```

Minimum JSON request:

```json
{
  "chat_id": 123456789,
  "rich_message": {
    "markdown": "# Hello\n\nThis is a **Rich Message**."
  }
}
```

On success, Telegram returns the standard Bot API envelope with a `Message`
object in `result`.

Important parameters:

| Parameter | Required | Type | Purpose |
|---|---:|---|---|
| `chat_id` | Yes | Integer or String | Target chat or supported `@username` |
| `rich_message` | Yes | `InputRichMessage` | Rich content |
| `business_connection_id` | No | String | Business connection |
| `message_thread_id` | No | Integer | Forum/private-chat topic |
| `direct_messages_topic_id` | Conditional | Integer | Direct-messages topic |
| `disable_notification` | No | Boolean | Silent send |
| `protect_content` | No | Boolean | Prevent forwarding/saving |
| `allow_paid_broadcast` | No | Boolean | Paid high-throughput broadcast |
| `message_effect_id` | No | String | Private-chat effect |
| `suggested_post_parameters` | No | Object | Suggested post settings |
| `reply_parameters` | No | Object | Reply target |
| `reply_markup` | No | Object | Inline/reply keyboard |

If the Rich Message contains media, the bot must have permission to send that
media type in the target chat.

### 2.2 `sendRichMessageDraft`

Use this only to stream a partial Rich Message while content is generated.

```text
POST https://api.telegram.org/bot<BOT_TOKEN>/sendRichMessageDraft
```

Rules:

- It is intended for private chats.
- `draft_id` is required and must be non-zero.
- Reusing the same `draft_id` updates the animated draft.
- The draft is ephemeral and acts as a temporary 30-second preview.
- Persist the completed result by calling `sendRichMessage`.

```json
{
  "chat_id": 123456789,
  "draft_id": 42,
  "rich_message": {
    "markdown": "# Generating…\n\nCurrent section: **Analysis**"
  }
}
```

---

## 3. `InputRichMessage`

```json
{
  "markdown": "optional string",
  "html": "optional string",
  "is_rtl": false,
  "skip_entity_detection": false
}
```

Rules:

- Exactly one of `markdown` or `html` must be present.
- Never send both and never send neither.
- Set `is_rtl` to `true` for Persian output.
- `skip_entity_detection` disables automatic recognition of URLs, emails,
  usernames, hashtags, cashtags, bot commands, phone numbers, and similar
  entities.

Persian example:

```json
{
  "chat_id": 123456789,
  "rich_message": {
    "markdown": "# گزارش روزانه\n\nوضعیت سیستم: **فعال**",
    "is_rtl": true
  }
}
```

---

## 4. Official limits

| Limit | Maximum |
|---|---:|
| UTF-8 characters in Rich Message text | 32,768 |
| Blocks including nested blocks and rows/items | 500 |
| Nesting levels | 16 |
| Total media attachments | 50 |
| Table columns | 20 |

Formula source and custom emoji alternative text count toward the character
limit.

---

## 5. Rich Markdown

Pass content in `rich_message.markdown`.

Rich Markdown follows GitHub-Flavored Markdown where possible and may use
Telegram-supported Rich HTML tags for features without Markdown syntax.

### 5.1 Inline formatting

```markdown
**bold**
__bold__
*italic*
_italic_
~~strikethrough~~
`inline code`
==marked text==
||spoiler||
[link](https://t.me/)
[email](mailto:user@example.com)
[telephone](tel:+123456789)
[user mention](tg://user?id=123456789)
$x^2 + y^2$
```

Additional inline tags:

```html
<u>underline</u>
<ins>underline</ins>
<sub>subscript</sub>
<sup>superscript</sup>
<tg-spoiler>spoiler</tg-spoiler>
```

### 5.2 Headings

```markdown
# Heading 1
## Heading 2
### Heading 3
#### Heading 4
##### Heading 5
###### Heading 6
```

### 5.3 Code blocks

````markdown
```python
print("Hello")
```
````

### 5.4 Divider

```markdown
---
```

### 5.5 Lists

```markdown
- first item
- second item

1. first step
2. second step

- [ ] pending task
- [x] completed task
```

### 5.6 Block quotation

```markdown
> First quotation line
>
> Second quotation line
```

### 5.7 Table

```markdown
| Name | Score | Status |
|:-----|------:|:------:|
| Sara | 95 | Excellent |
| Ali | 82 | Passed |
```

Table rules:

- Maximum 20 columns.
- Cells may contain only inline formatting.
- Do not place headings, lists, media, or nested tables inside cells.

### 5.8 Footnotes

```markdown
The value was verified.[^source]

[^source]: Internal calculation performed by the bot.
```

### 5.9 Mathematical expressions

Inline LaTeX:

```markdown
The area is $A = \pi r^2$.
```

Block LaTeX:

```markdown
$$
E = mc^2
$$
```

Alternative math block:

````markdown
```math
\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
```
````

Telegram treats formula source as raw LaTeX. Preserve backslashes correctly in
the host language. In Python, prefer raw strings.

```python
formula = r"""
$$
\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
$$
"""
```

### 5.10 Collapsible details

```html
<details>
<summary>Show explanation</summary>

## Explanation

This content is initially collapsed.

</details>
```

Expanded by default:

```html
<details open>
<summary>Explanation</summary>
Visible content
</details>
```

### 5.11 Media blocks

Media must be a separate block and use an HTTP or HTTPS URL.

```markdown
![](https://example.com/photo.jpg)
![](https://example.com/video.mp4)
![](https://example.com/audio.mp3)
![](https://example.com/voice.ogg)
![](https://example.com/animation.gif)
```

Caption:

```markdown
![](https://example.com/photo.jpg "Project photo")
```

The media type is determined from MIME type and URL.

### 5.12 Collage

```html
<tg-collage>

![](https://example.com/photo-1.jpg)
![](https://example.com/photo-2.jpg)
![](https://example.com/video.mp4)

</tg-collage>
```

### 5.13 Slideshow

```html
<tg-slideshow>

![](https://example.com/photo-1.jpg)
![](https://example.com/photo-2.jpg)
![](https://example.com/video.mp4)

</tg-slideshow>
```

---

## 6. Rich HTML

Pass content in `rich_message.html`.

Only Telegram-supported tags should be used. Do not assume arbitrary browser
HTML, CSS, or JavaScript is supported.

### 6.1 Inline tags

```html
<b>bold</b>
<strong>bold</strong>
<i>italic</i>
<em>italic</em>
<u>underline</u>
<ins>underline</ins>
<s>strikethrough</s>
<strike>strikethrough</strike>
<del>strikethrough</del>
<code>inline code</code>
<mark>marked</mark>
<sub>subscript</sub>
<sup>superscript</sup>
<tg-spoiler>spoiler</tg-spoiler>
<tg-math>x^2 + y^2</tg-math>
```

### 6.2 Links, anchors, and references

```html
<a href="https://t.me/">Telegram</a>
<a href="mailto:user@example.com">Email</a>
<a href="tel:+123456789">Call</a>
<a href="tg://user?id=123456789">Mention user</a>

<a name="chapter-1"></a>
<a href="#chapter-1">Jump to chapter 1</a>

<a href="#note-1">Read note</a>
<tg-reference name="note-1">Referenced note text</tg-reference>
```

### 6.3 Block tags

```html
<h1>Heading</h1>
<h2>Subheading</h2>
<p>Paragraph</p>
<hr/>
<footer>Footer</footer>
<pre>Preformatted text</pre>
<pre><code class="language-python">print("Hello")</code></pre>
```

### 6.4 Lists and checkboxes

```html
<ul>
  <li>First item</li>
  <li>Second item</li>
</ul>

<ol>
  <li>First step</li>
  <li>Second step</li>
</ol>

<ul>
  <li><input type="checkbox" checked>Completed</li>
  <li><input type="checkbox">Pending</li>
</ul>
```

### 6.5 Quotes

```html
<blockquote>
  Quotation text
  <cite>The Author</cite>
</blockquote>

<aside>
  Pull quotation
  <cite>The Author</cite>
</aside>
```

### 6.6 Media with captions

```html
<img src="https://example.com/photo.jpg"/>
<video src="https://example.com/video.mp4"></video>
<audio src="https://example.com/audio.mp3"></audio>

<figure>
  <img src="https://example.com/photo.jpg"/>
  <figcaption>Project photo<cite>Photo credit</cite></figcaption>
</figure>
```

### 6.7 Details, collage, slideshow, and map

```html
<details>
  <summary>Show details</summary>
  <p>Hidden content</p>
</details>

<tg-collage>
  <img src="https://example.com/one.jpg"/>
  <img src="https://example.com/two.jpg"/>
</tg-collage>

<tg-slideshow>
  <img src="https://example.com/one.jpg"/>
  <video src="https://example.com/two.mp4"></video>
</tg-slideshow>

<tg-map lat="41.9" long="12.5" zoom="14"/>
```

---

## 7. Complete request examples

### 7.1 cURL

```bash
curl --request POST \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendRichMessage" \
  --header "Content-Type: application/json" \
  --data @- <<JSON
{
  "chat_id": "${TELEGRAM_CHAT_ID}",
  "rich_message": {
    "markdown": "# System report\n\n| Metric | Value |\n|:--|--:|\n| Status | **OK** |\n| Latency | 42 ms |\n\n\$\$E = mc^2\$\$",
    "is_rtl": false
  }
}
JSON
```

### 7.2 Python with `httpx`

```python
from __future__ import annotations

import os
import httpx

token = os.environ["TELEGRAM_BOT_TOKEN"]
chat_id = os.environ["TELEGRAM_CHAT_ID"]

markdown = r"""
# گزارش آموزشی

| موضوع | وضعیت |
|:---|:---:|
| جدول | **فعال** |
| فرمول | **فعال** |

$$
E = mc^2
$$

<details>
<summary>توضیحات بیشتر</summary>

این بخش تاشو است.

</details>
""".strip()

payload = {
    "chat_id": chat_id,
    "rich_message": {
        "markdown": markdown,
        "is_rtl": True,
    },
}

url = f"https://api.telegram.org/bot{token}/sendRichMessage"

with httpx.Client(timeout=30.0) as client:
    response = client.post(url, json=payload)
    response.raise_for_status()
    body = response.json()

if not body.get("ok"):
    raise RuntimeError(body.get("description", "Telegram API error"))
```

---

## 8. Recommended architecture

Do not mix AI content generation, formatting, and HTTP delivery in one function.

```text
bot/
├── content/
│   └── report_builder.py
├── formatting/
│   └── rich_markdown.py
├── telegram/
│   ├── client.py
│   └── errors.py
└── handlers/
    └── report_handler.py
```

Responsibilities:

- content builder: domain data and wording;
- formatter: structured data to valid Rich Markdown/HTML;
- Telegram client: validation and HTTPS requests;
- errors: safe application exceptions;
- handler: user interaction orchestration.

---

## 9. Validation checklist

```text
[ ] Exactly one of html or markdown is present
[ ] Content is not empty
[ ] Character limit is not exceeded
[ ] is_rtl is true for Persian output
[ ] Table has no more than 20 columns
[ ] Media URLs use HTTP or HTTPS
[ ] Media is placed in separate blocks
[ ] Secrets come from environment variables
[ ] Telegram response body is checked even after HTTP 200
```

---

## 10. Error handling

Telegram errors generally use this shape:

```json
{
  "ok": false,
  "error_code": 400,
  "description": "Bad Request: ..."
}
```

Rules:

1. Configure connection and response timeouts.
2. Separate network failures from Telegram API failures.
3. Parse Telegram's JSON response where possible.
4. Raise an application exception with `error_code` and `description`.
5. Never expose or log the bot token.
6. Do not retry every 4xx response.
7. Retry transient network failures and selected 5xx responses with bounded
   exponential backoff.
8. Respect `retry_after` when rate-limit information is returned.
9. Avoid logging sensitive message content.

---

## 11. SDK compatibility strategy

Because this API is new, never guess that a wrapper supports it.

```text
Does the installed SDK officially expose sendRichMessage?
    |
    +-- Yes --> Verify its generated JSON, then use it.
    |
    +-- No or uncertain --> Use a small raw HTTPS client.
```

Keep the existing framework for updates and handlers. A dedicated raw HTTP
adapter is normally enough for Rich Message delivery.

---

## 12. Optional graceful fallback

Fallback behavior is product-dependent.

```python
try:
    await rich_client.send_markdown(chat_id, rich_markdown, is_rtl=True)
except RichMessageUnsupportedError:
    plain_text = create_plain_text_fallback(data)
    await normal_bot.send_message(chat_id=chat_id, text=plain_text)
```

Rules:

- Do not silently discard information.
- Convert tables into readable lines.
- Keep formulas as plain LaTeX when necessary.
- Remove unsupported details/collage syntax.
- Log that fallback was used.
- Do not use fallback to conceal implementation bugs.

---

## 13. Testing strategy

### Unit tests

Test without contacting Telegram:

- valid Markdown payload;
- valid HTML payload;
- rejection when both formats are supplied;
- rejection when neither is supplied;
- Persian RTL;
- character limit;
- endpoint construction;
- safe Telegram error parsing.

### Manual smoke test

Send to a private test chat:

1. heading;
2. bold text and inline formula;
3. three-column table;
4. block formula;
5. details block;
6. optional inline keyboard;
7. Persian RTL message.

Never run live Telegram smoke tests automatically in CI.

---

## 14. Acceptance criteria

Implementation is complete only when:

- normal messages still work;
- Rich Messages use `sendRichMessage`;
- Persian output uses `is_rtl: true`;
- exactly one input format is supplied;
- errors do not leak secrets;
- unit tests pass;
- a manual smoke-test command is documented;
- the code does not rely on invented SDK support;
- the implementation references this document.

---

## 15. Questions the agent must answer first

1. What language and bot framework does the project use?
2. Which exact dependency versions are installed?
3. Does that exact SDK version officially support `sendRichMessage`?
4. Where is outgoing Telegram communication centralized?
5. Is the output Persian/RTL?
6. Will the project use Markdown or HTML?
7. Is streaming with `sendRichMessageDraft` needed?
8. What is the fallback behavior?
9. Which tests prove the request shape?
10. How will a developer run the smoke test safely?

---

## 16. Official-source rule

If this local reference conflicts with the current official Telegram Bot API,
the official API wins. Update this document and its verification date after
confirming the change.
