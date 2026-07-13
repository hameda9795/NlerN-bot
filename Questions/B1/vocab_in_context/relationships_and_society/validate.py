import json
from collections import Counter

path = "relationships_and_society.json"
with open(path, encoding="utf-8") as f:
    data = json.load(f)

print("Total items:", len(data))
issues = []
expected_keys = ['level','section','topic','life_context','question_type','difficulty',
                  'question_text_nl','question_text_fa','explanation_fa','grammar_rule_fa',
                  'extra_example_nl','extra_example_fa','options']
for i, item in enumerate(data):
    keys = list(item.keys())
    if keys != expected_keys:
        issues.append(f"Item {i}: key order mismatch {keys}")
    if item['level'] != 'B1':
        issues.append(f"Item {i}: level {item['level']}")
    if item['topic'] != 'relationships_and_society':
        issues.append(f"Item {i}: topic wrong")
    if '___' not in item['question_text_nl']:
        issues.append(f"Item {i}: no blank")
    opts = item['options']
    if len(opts) != 4:
        issues.append(f"Item {i}: options count {len(opts)}")
    correct = [o for o in opts if o['is_correct']]
    if len(correct) != 1:
        issues.append(f"Item {i}: correct count {len(correct)}")
    keysAB = [o['key'] for o in opts]
    if keysAB != ['A', 'B', 'C', 'D']:
        issues.append(f"Item {i}: option keys {keysAB}")
    if item['difficulty'] not in (3, 4, 5):
        issues.append(f"Item {i}: difficulty {item['difficulty']}")
    for o in opts:
        if not o['feedback_fa'].strip():
            issues.append(f"Item {i} option {o['key']}: empty feedback")
    if correct:
        if not correct[0]['feedback_fa'].startswith('✅'):
            issues.append(f"Item {i}: correct feedback missing checkmark")

print("Issues:", len(issues))
for x in issues:
    print(x)

texts = [item['question_text_nl'] for item in data]
dups = set(t for t in texts if texts.count(t) > 1)
print("Duplicate question_text_nl:", dups)

print("Difficulty distribution:", Counter(item['difficulty'] for item in data))
