# Model Availability and Fallback

The Model Availability system provides health tracking, failure classification, and policy-driven fallback mechanisms for resilient AI interactions. This system ensures your application gracefully handles model failures without user-visible errors.

## Overview

This system enables:

- **Health tracking** for models (healthy, transient, terminal failures)
- **Failure classification** (rate limits, auth errors, capacity issues)
- **Policy-driven fallback** with ordered model chains
- **Retry-once-per-turn** semantics for transient failures
- **User intent integration** for manual control

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   ModelAvailabilityService                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌───────────────────┐   ┌───────────────────────────────────┐ │
│  │    HealthState    │   │        FailureCategory            │ │
│  │  ┌─────────────┐  │   │  ┌─────────┐  ┌─────────────┐    │ │
│  │  │ Model Name  │  │   │  │TERMINAL │  │ TRANSIENT   │    │ │
│  │  │ Status      │──┼───┼─▶│ (auth)  │  │ (rate limit)│    │ │
│  │  │ Fail Count  │  │   │  └─────────┘  └─────────────┘    │ │
│  │  │ Retry State │  │   │  ┌─────────┐  ┌─────────────┐    │ │
│  │  └─────────────┘  │   │  │NOT_FOUND│  │  HEALTHY    │    │ │
│  └───────────────────┘   │  └─────────┘  └─────────────┘    │ │
│                          └───────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       PolicyCatalog                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ModelPolicy 1│→ │ModelPolicy 2│→ │ModelPolicy N│             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                  │
│  Evaluates → FallbackAction (SWITCH_MODEL, RETRY, STOP, etc.)   │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```python
from joshu.models import (
    get_model_availability_service,
    get_policy_catalog,
    FailureCategory,
)

# Get global service
service = get_model_availability_service()

# Start of turn - reset retry state
service.reset_turn_state("turn_123")

# Mark model states based on API responses
service.mark_healthy("gpt-4o")
service.mark_transient_failure("gpt-4o-mini", "Rate limit exceeded")
service.mark_terminal_failure("old-model", "Model deprecated")

# Select best available model from candidates
result = service.select_model(
    candidates=["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
    turn_id="turn_123"
)

if result.selected_model:
    print(f"Using: {result.selected_model}")
    print(f"Reason: {result.selection_reason}")
else:
    print(f"All unavailable!")
    for model, reason in result.skipped_models.items():
        print(f"  {model}: {reason}")
```

## Health States

### HealthStatus Enum

```python
from joshu.models import HealthStatus

class HealthStatus(Enum):
    HEALTHY = "healthy"                         # Model is available and working
    UNHEALTHY_TRANSIENT = "unhealthy_transient" # Temporary issue (may recover)
    UNHEALTHY_TERMINAL = "unhealthy_terminal"   # Permanent issue (won't recover)
    UNKNOWN = "unknown"                         # No information yet
```

### HealthState Dataclass

Detailed health record for a model:

```python
from joshu.models import HealthState

@dataclass
class HealthState:
    model_name: str                          # Model identifier
    status: HealthStatus                     # Current health status
    failure_category: FailureCategory        # Type of failure (if any)
    failure_reason: Optional[str]            # Human-readable reason
    failure_count: int                       # Consecutive failures
    last_updated: datetime                   # When state was last changed
    retry_attempted_this_turn: bool          # Already retried this turn?
    turn_id: Optional[str]                   # Current turn identifier
```

### Accessing Health State

```python
# Get current health
state = service.get_health("gpt-4o")
print(f"Status: {state.status.value}")
print(f"Failures: {state.failure_count}")

# Check if model is usable
is_healthy = service.is_healthy("gpt-4o")
is_usable = service.is_usable("gpt-4o", turn_id="turn_123")

# Get all model states
all_states = service.get_all_health()
for model, state in all_states.items():
    print(f"{model}: {state.status.value}")
```

## Failure Classification

### FailureCategory Enum

```python
from joshu.models import FailureCategory

class FailureCategory(Enum):
    TERMINAL = "terminal"       # Auth errors, model removed, billing issues
    TRANSIENT = "transient"     # Rate limits, capacity, timeouts
    NOT_FOUND = "not_found"     # Model doesn't exist
    HEALTHY = "healthy"         # No failure
```

### Classification Rules

| Error Type | Status Code | Category | Example |
|------------|-------------|----------|---------|
| `AuthenticationError` | 401, 403 | TERMINAL | Invalid API key |
| `RateLimitError` | 429 | TRANSIENT | Too many requests |
| `ServiceCapacityError` | 503 | TRANSIENT | Server overloaded |
| `ModelNotFoundError` | 404 | NOT_FOUND | Invalid model name |
| `BillingError` | 402 | TERMINAL | Payment required |
| `TimeoutError` | - | TRANSIENT | Request timeout |
| `ContentFilterError` | - | TRANSIENT | Content blocked |

### Automatic Classification

```python
# Classify based on error details
category = service.classify_error(
    error_type="RateLimitError",
    error_message="Rate limit exceeded. Try again in 30s.",
    status_code=429,
)
# Returns: FailureCategory.TRANSIENT

# Classify authentication failure
category = service.classify_error(
    error_type="AuthenticationError",
    error_message="Invalid API key",
    status_code=401,
)
# Returns: FailureCategory.TERMINAL

# Classification with exception
try:
    # API call
    pass
except Exception as e:
    category = service.classify_exception(e)
    if category == FailureCategory.TRANSIENT:
        # Maybe retry
        pass
    elif category == FailureCategory.TERMINAL:
        # Don't retry, mark terminal
        pass
```

## Marking Model State

```python
# Mark as healthy after successful call
service.mark_healthy("gpt-4o")

# Mark transient failure (may retry)
service.mark_transient_failure(
    model_name="gpt-4o",
    reason="Rate limit exceeded",
    turn_id="turn_123"
)

# Mark terminal failure (no retry)
service.mark_terminal_failure(
    model_name="gpt-4o",
    reason="API key revoked"
)

# Mark as not found
service.mark_not_found("nonexistent-model")

# Generic failure with category
service.mark_failure(
    model_name="gpt-4o",
    category=FailureCategory.TRANSIENT,
    reason="Service timeout",
    turn_id="turn_123"
)
```

## Model Selection

### Basic Selection

```python
result = service.select_model(
    candidates=["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
    turn_id="turn_1",
)

if result.selected_model:
    print(f"Selected: {result.selected_model}")
    # Use result.selected_model for API call
else:
    print("No models available")
    # Handle fallback or error
```

### ModelSelectionResult

```python
@dataclass
class ModelSelectionResult:
    selected_model: Optional[str]          # Chosen model (None if all unavailable)
    skipped_models: Dict[str, str]         # Model -> skip reason
    all_unavailable: bool                  # True if no model could be selected
    selection_reason: str                  # Why this model was chosen
    retrying: bool                         # True if this is a retry attempt
```

### Selection Priority

Models are evaluated in order. First usable model is selected:

1. **HEALTHY** - Use immediately
2. **UNKNOWN** - Use (no negative information)
3. **UNHEALTHY_TRANSIENT** - Use IF retry not attempted this turn
4. **UNHEALTHY_TERMINAL** - Skip
5. **NOT_FOUND** - Skip

```python
# GPT-4o is rate limited (transient), haven't retried yet
result = service.select_model(["gpt-4o"], "turn_1")
# result.selected_model == "gpt-4o" (retry allowed)

# After retry fails, record it
service.record_retry_attempt("gpt-4o", "turn_1")

# Now it will skip to next candidate
result = service.select_model(["gpt-4o", "gpt-4o-mini"], "turn_1")
# result.selected_model == "gpt-4o-mini"
# result.skipped_models == {"gpt-4o": "Already retried this turn"}
```

## Retry-Once-Per-Turn Semantics

The system implements "retry at most once per conversation turn":

```python
# === Turn 1 ===
service.reset_turn_state("turn_1")

# First request - model works
response = call_model("gpt-4o")
service.mark_healthy("gpt-4o")

# === Turn 2 ===
service.reset_turn_state("turn_2")

# Request fails with rate limit
try:
    response = call_model("gpt-4o")
except RateLimitError as e:
    service.mark_transient_failure("gpt-4o", str(e), "turn_2")

# Selection allows retry (first failure this turn)
result = service.select_model(["gpt-4o"], "turn_2")
# result.selected_model == "gpt-4o"
# result.retrying == True

# Retry also fails
try:
    response = call_model(result.selected_model)
except RateLimitError as e:
    service.mark_transient_failure("gpt-4o", str(e), "turn_2")
    service.record_retry_attempt("gpt-4o", "turn_2")

# Now skip to fallback
result = service.select_model(["gpt-4o", "gpt-4o-mini"], "turn_2")
# result.selected_model == "gpt-4o-mini"
# result.skipped_models["gpt-4o"] == "Already retried this turn"

# === Turn 3 ===
service.reset_turn_state("turn_3")

# Fresh turn - can retry gpt-4o again
result = service.select_model(["gpt-4o"], "turn_3")
# result.selected_model == "gpt-4o" (retry allowed again)
```

## Policy-Driven Fallback

### ModelPolicy

Define fallback rules for specific model patterns:

```python
from joshu.models import (
    ModelPolicy,
    FallbackActionType,
    FailureCategory,
)

# Policy for GPT-4 rate limits
gpt4_rate_limit_policy = ModelPolicy(
    name="gpt4_rate_limit",
    model_pattern="gpt-4*",                    # Matches gpt-4o, gpt-4-turbo, etc.
    failure_category=FailureCategory.TRANSIENT,
    action_type=FallbackActionType.SWITCH_MODEL,
    fallback_models=["gpt-4o-mini", "gpt-3.5-turbo"],
    allow_retry=True,
    priority=10,
)

# Policy for terminal failures
terminal_policy = ModelPolicy(
    name="terminal_failure",
    model_pattern="*",                          # Matches all models
    failure_category=FailureCategory.TERMINAL,
    action_type=FallbackActionType.PROMPT_USER,
    fallback_models=[],
    allow_retry=False,
    priority=1,                                 # Lower priority = evaluated later
)
```

### ModelPolicyChain

Ordered chain of policies for evaluation:

```python
from joshu.models import ModelPolicyChain

chain = ModelPolicyChain(name="production")

# Add policies (evaluated by priority, then order added)
chain.add_policy(gpt4_rate_limit_policy)
chain.add_policy(claude_transient_policy)
chain.add_policy(terminal_policy)

# Evaluate a failure
action = chain.evaluate(
    model_name="gpt-4o",
    failure_category=FailureCategory.TRANSIENT,
    available_models=["gpt-4o-mini", "gpt-3.5-turbo"],
)

print(f"Action: {action.action_type.value}")
print(f"Switch to: {action.target_model}")
```

### PolicyCatalog

Central registry for policy chains:

```python
from joshu.models import get_policy_catalog, PolicyCatalog

catalog = get_policy_catalog()

# Register custom chain
catalog.register_chain(chain, is_default=True)

# Evaluate fallback using default chain
action = catalog.evaluate_fallback(
    model_name="gpt-4o",
    failure_category=FailureCategory.TRANSIENT,
    available_models=["gpt-4o-mini"],
)

# Get registered chains
chains = catalog.list_chains()
default_chain = catalog.get_default_chain()
```

### Default Policy Chain

Pre-configured sensible defaults:

```python
from joshu.models import create_default_policy_chain

chain = create_default_policy_chain()

# Includes policies for:
# 1. GPT-4 transient → switch to GPT-4o-mini
# 2. Claude transient → switch to Claude Haiku
# 3. Any terminal error → prompt user
# 4. Model not found → stop
# 5. Default transient → retry same model
```

## FallbackAction

Result of policy evaluation:

```python
from joshu.models import FallbackAction, FallbackActionType

@dataclass
class FallbackAction:
    action_type: FallbackActionType      # What to do
    target_model: Optional[str]          # Model to use (if switching)
    reason: str                          # Explanation
    policy_name: Optional[str]           # Which policy triggered
    allow_retry: bool                    # Whether retry is allowed
    metadata: Dict[str, Any]             # Additional data
```

### FallbackActionType

```python
class FallbackActionType(Enum):
    SWITCH_MODEL = "switch_model"        # Use a different model
    RETRY_SAME = "retry_same"            # Retry the same model
    STOP = "stop"                        # Stop trying
    PROMPT_USER = "prompt_user"          # Ask user what to do
    SUGGEST_UPGRADE = "suggest_upgrade"  # Suggest upgrading plan
    NO_ACTION = "no_action"              # No policy matched
```

## User Intent

Handle user choices for fallback:

```python
from joshu.models import FallbackIntent

class FallbackIntent(Enum):
    RETRY_ALWAYS = "retry_always"  # Keep retrying until success
    RETRY_ONCE = "retry_once"      # Retry once then use fallback
    STOP = "stop"                  # Stop immediately, don't retry
    UPGRADE = "upgrade"            # User wants to upgrade
    ASK_USER = "ask_user"          # Prompt for choice
    AUTO = "auto"                  # Use policy decision
```

### Applying User Intent

```python
# Get policy action
action = catalog.evaluate_fallback("gpt-4o", FailureCategory.TRANSIENT)

# Apply user preference
final_action = catalog.apply_user_intent(action, FallbackIntent.RETRY_ONCE)

# User chose to stop - override policy
final_action = catalog.apply_user_intent(action, FallbackIntent.STOP)
# final_action.action_type == FallbackActionType.STOP
```

## Integration Example

Complete integration with model calling:

```python
from joshu.models import (
    get_model_availability_service,
    get_policy_catalog,
    FailureCategory,
)

service = get_model_availability_service()
catalog = get_policy_catalog()

def call_with_fallback(
    prompt: str,
    candidates: list[str],
    turn_id: str,
    max_attempts: int = 3
) -> str:
    """Call model with automatic fallback."""

    for attempt in range(max_attempts):
        # Select best available model
        result = service.select_model(candidates, turn_id)

        if not result.selected_model:
            raise AllModelsUnavailable(result.skipped_models)

        try:
            # Make API call
            response = api_client.generate(
                model=result.selected_model,
                prompt=prompt
            )

            # Success - mark healthy
            service.mark_healthy(result.selected_model)
            return response

        except Exception as e:
            # Classify and record failure
            category = service.classify_exception(e)
            service.mark_failure(
                result.selected_model,
                category,
                str(e),
                turn_id
            )

            # Record retry if this was a retry
            if result.retrying:
                service.record_retry_attempt(result.selected_model, turn_id)

            # Get fallback action
            action = catalog.evaluate_fallback(
                result.selected_model,
                category,
                [c for c in candidates if c != result.selected_model]
            )

            if action.action_type == FallbackActionType.STOP:
                raise ModelUnavailable(str(e))

            # Continue to next attempt
            continue

    raise MaxRetriesExceeded()
```

## Best Practices

1. **Reset per turn**: Always call `reset_turn_state()` at the start of each conversation turn

2. **Classify errors consistently**: Use `classify_error()` for consistent categorization across your app

3. **Order candidates wisely**: Put preferred models first in the candidate list

4. **Use patterns**: Model patterns like `gpt-4*` match all variants (gpt-4o, gpt-4-turbo)

5. **Always have terminal fallback**: Include a policy for terminal failures to prevent infinite loops

6. **Log selection reasons**: Record `selection_reason` for debugging

7. **Test with mock service**: Use `MemoryCredentialStorage` for testing without real API calls

8. **Consider user intent**: Allow users to control fallback behavior in interactive apps

## See Also

- [Agent System](agent-system.md) - Agent definitions
- [Models and Providers](models-and-providers.md) - Model configuration
- [Chat & Scheduling](chat-and-scheduling.md) - Session management
- [Configuration](configuration.md) - System settings
