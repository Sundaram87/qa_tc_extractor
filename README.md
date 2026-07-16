# qa_tc_extractor

Automation-ready analyzer for CR inflow and release evidence that proposes impacted Level 0 regression tests for QA sign-off and email handoff.

## What it does

- searches evidence supplied from files, emails, meetings, and Teams
- separates confirmed facts from hypotheses
- explains confidence and evidence gaps per impacted Level 0 test case
- emits stable JSON that can be reused in nightly regression planning

## Usage

```bash
python /home/runner/work/qa_tc_extractor/qa_tc_extractor/qa_tc_extractor.py /path/to/input.json
```

### Input shape

```json
{
  "change_requests": [
    {
      "id": "CR-101",
      "title": "Checkout payment tax fix",
      "component": "checkout",
      "description": "Fix tax total in payment review",
      "release_notes": "Checkout and payment totals updated",
      "references": ["PAY-1"]
    }
  ],
  "release_evidence": [
    {
      "source_type": "emails",
      "title": "Release note confirms checkout tax fix",
      "content": "CR-101 updates checkout payment total behavior."
    }
  ],
  "level0_test_cases": [
    {
      "id": "L0-200",
      "title": "User can complete checkout payment review",
      "level": "L0",
      "area": "checkout",
      "keywords": ["payment", "tax"]
    }
  ]
}
```
