import json

d = json.load(open('task2-inbox-agent/datasets/emails-sample.json'))
emails = [e for e in d['emails'] if e.get('expected')]
print('=== escalate=True:')
for e in emails:
    x = e['expected']
    if x['escalate']:
        print(' %-7s %-20s %s' % (x['urgency'], x['category'], e['subject'][:62]))
print('=== escalate=False but high/medium:')
for e in emails:
    x = e['expected']
    if not x['escalate'] and x['urgency'] in ('high', 'medium'):
        print(' %-7s %-20s %s' % (x['urgency'], x['category'], e['subject'][:62]))
