from prompts.clarify import CLARIFY_PROMPT
from prompts.finalize import FINALIZE_PROMPT
from prompts.intent import INTENT_PROMPT
from prompts.planner import PLANNER_PROMPT
from prompts.validation import VALIDATION_PROMPT


PROMPT_REGISTRY = {
    "intent": INTENT_PROMPT,
    "clarify": CLARIFY_PROMPT,
    "planner": PLANNER_PROMPT,
    "validation": VALIDATION_PROMPT,
    "finalize": FINALIZE_PROMPT,
}
