# Pre-output rubric author

Task and original prompt provenance: {{TASK_AND_PROVENANCE}}
Frozen source and allowed paths: {{SOURCE_SCOPE}}
Mode: {{SOURCE_ONLY_PLANNING_OR_AUTHORIZED_IMPLEMENTATION}}
Existing rubric constraints: {{RUBRIC_CONSTRAINTS}}
Output: {{PRIVATE_RUBRIC_DESTINATION}}

Define the rubric before seeing candidate artifacts. Read actual source callers,
owners and relevant lifecycle paths. Build source-backed full/partial/poor credit
anchors under these categories: correctness/requirements 35, ownership/source 25,
simplicity/scope 15, actionable sequence 10, discriminating verification 10, honest
uncertainty 5. The category maximums total 100. For implementation, translate the
anchors to the authorized observable patch/verification evidence before freezing.

Produce a separate private expert checklist of requirements, concrete failure
paths, acceptable alternatives and unresolved source uncertainties. This checklist
is for graders/coordinator only and must not enter candidate prompts. Reference
comparators must be verified against source, not treated as gold answers.

Do not require a particular helper name, architecture or step order when another
approach meets the behavior. Distinguish an unconditional wrong fix from an honest
investigation with a gate before changes. Identify what could constitute an
essential defect, with source justification, without assigning a numeric cap.

Specify deduplication boundaries for likely defects, independent verification
assertions and evidence needed for severity. Perfect requires a complete review,
no unresolved claims and no confirmed defects of any severity. Confirmed Flaws
are descriptive; category points are the only numeric quality assessment.

Return task anchors, private checklist, source citations, rejected candidate
criteria and unknowns. Do not run candidates, tests, apps or new models. The
coordinator verifies and freezes the rubric/version before candidate dispatch.
