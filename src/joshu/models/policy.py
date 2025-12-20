"""
Policy-driven fallback mechanisms for model availability.

This module provides declarative policy structures for managing
model fallback strategies based on failure classification.

Key principles:
- ZERO execution logic - defines policies and produces actions
- Declarative policy chains with ordered fallbacks
- User intent integration (retry, stop, upgrade)
- Works with ModelAvailabilityService for health awareness
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from joshu.models.availability import FailureCategory

logger = logging.getLogger(__name__)


class FallbackIntent(Enum):
    """
    User intent for fallback actions.

    Represents user choices when a model failure occurs.
    """

    RETRY_ALWAYS = "retry_always"  # Always retry with fallback
    RETRY_ONCE = "retry_once"  # Retry once, then stop
    STOP = "stop"  # Stop operation entirely
    UPGRADE = "upgrade"  # Suggest service upgrade
    ASK_USER = "ask_user"  # Prompt user for decision
    AUTO = "auto"  # Automatic fallback based on policy


class FallbackActionType(Enum):
    """Types of fallback actions that can be taken."""

    SWITCH_MODEL = "switch_model"  # Switch to a different model
    RETRY_SAME = "retry_same"  # Retry with the same model
    STOP = "stop"  # Stop the operation
    PROMPT_USER = "prompt_user"  # Ask user what to do
    SUGGEST_UPGRADE = "suggest_upgrade"  # Suggest upgrade path
    NO_ACTION = "no_action"  # No fallback action possible


@dataclass
class FallbackAction:
    """
    Result of policy evaluation - the action to take.

    This is a pure data structure describing what action
    should be taken, without executing it.

    Attributes:
        action_type: Type of action to perform
        target_model: Model to switch to (for SWITCH_MODEL)
        reason: Human-readable explanation
        metadata: Additional action-specific data
    """

    action_type: FallbackActionType
    target_model: Optional[str] = None
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "action_type": self.action_type.value,
            "target_model": self.target_model,
            "reason": self.reason,
            "metadata": self.metadata,
        }


@dataclass
class ModelPolicy:
    """
    Declarative policy for handling model failures.

    Defines how the system should react to specific failure
    types for a model or model pattern.

    Attributes:
        name: Policy identifier
        model_pattern: Model name or pattern this policy applies to
        failure_category: Type of failure this policy handles
        action_type: Default action to take
        fallback_models: Ordered list of fallback model names
        allow_retry: Whether retry is allowed for this failure
        max_retries: Maximum retry attempts
        user_prompt_message: Message to show if prompting user
    """

    name: str
    model_pattern: str  # Can be exact name or pattern like "gpt-*"
    failure_category: FailureCategory
    action_type: FallbackActionType = FallbackActionType.SWITCH_MODEL
    fallback_models: List[str] = field(default_factory=list)
    allow_retry: bool = True
    max_retries: int = 1
    user_prompt_message: Optional[str] = None

    def matches_model(self, model_name: str) -> bool:
        """
        Check if this policy applies to a model.

        Supports exact match or simple wildcard patterns.

        Args:
            model_name: Model name to check

        Returns:
            True if policy applies to this model
        """
        if self.model_pattern == "*":
            return True
        if self.model_pattern.endswith("*"):
            prefix = self.model_pattern[:-1]
            return model_name.startswith(prefix)
        return self.model_pattern == model_name

    def matches_failure(self, category: FailureCategory) -> bool:
        """Check if policy applies to this failure category."""
        return self.failure_category == category

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "model_pattern": self.model_pattern,
            "failure_category": self.failure_category.value,
            "action_type": self.action_type.value,
            "fallback_models": self.fallback_models,
            "allow_retry": self.allow_retry,
            "max_retries": self.max_retries,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelPolicy":
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            model_pattern=data.get("model_pattern", "*"),
            failure_category=FailureCategory(data.get("failure_category", "transient")),
            action_type=FallbackActionType(data.get("action_type", "switch_model")),
            fallback_models=data.get("fallback_models", []),
            allow_retry=data.get("allow_retry", True),
            max_retries=data.get("max_retries", 1),
            user_prompt_message=data.get("user_prompt_message"),
        )


@dataclass
class ModelPolicyChain:
    """
    Ordered chain of policies for fallback evaluation.

    Policies are evaluated in order until one matches.
    Provides structured fallback decision-making.

    Attributes:
        name: Chain identifier
        policies: Ordered list of policies to evaluate
        default_action: Action if no policy matches
    """

    name: str
    policies: List[ModelPolicy] = field(default_factory=list)
    default_action: FallbackActionType = FallbackActionType.STOP

    def add_policy(self, policy: ModelPolicy) -> None:
        """Add a policy to the chain."""
        self.policies.append(policy)

    def find_matching_policy(
        self,
        model_name: str,
        failure_category: FailureCategory,
    ) -> Optional[ModelPolicy]:
        """
        Find the first matching policy for a failure.

        Args:
            model_name: Model that failed
            failure_category: Type of failure

        Returns:
            Matching policy or None
        """
        for policy in self.policies:
            if policy.matches_model(model_name) and policy.matches_failure(failure_category):
                return policy
        return None

    def evaluate(
        self,
        model_name: str,
        failure_category: FailureCategory,
        available_models: Optional[List[str]] = None,
    ) -> FallbackAction:
        """
        Evaluate the policy chain and determine fallback action.

        Args:
            model_name: Model that failed
            failure_category: Type of failure
            available_models: Optional list of currently available models

        Returns:
            FallbackAction describing what to do
        """
        policy = self.find_matching_policy(model_name, failure_category)

        if policy is None:
            return FallbackAction(
                action_type=self.default_action,
                reason=f"No policy matched for {model_name} ({failure_category.value})",
            )

        # Determine action based on policy
        if policy.action_type == FallbackActionType.SWITCH_MODEL:
            # Find first available fallback model
            target = None
            for fallback in policy.fallback_models:
                if available_models is None or fallback in available_models:
                    target = fallback
                    break

            if target:
                return FallbackAction(
                    action_type=FallbackActionType.SWITCH_MODEL,
                    target_model=target,
                    reason=f"Policy '{policy.name}' switching from {model_name} to {target}",
                )
            else:
                return FallbackAction(
                    action_type=FallbackActionType.STOP,
                    reason=f"No available fallback models for policy '{policy.name}'",
                )

        elif policy.action_type == FallbackActionType.RETRY_SAME:
            if policy.allow_retry:
                return FallbackAction(
                    action_type=FallbackActionType.RETRY_SAME,
                    target_model=model_name,
                    reason=f"Policy '{policy.name}' allows retry for {model_name}",
                )
            else:
                return FallbackAction(
                    action_type=FallbackActionType.STOP,
                    reason=f"Retry not allowed by policy '{policy.name}'",
                )

        elif policy.action_type == FallbackActionType.PROMPT_USER:
            return FallbackAction(
                action_type=FallbackActionType.PROMPT_USER,
                reason=policy.user_prompt_message or f"Model {model_name} failed",
                metadata={"policy": policy.name},
            )

        else:
            return FallbackAction(
                action_type=policy.action_type,
                reason=f"Policy '{policy.name}' action: {policy.action_type.value}",
            )


class PolicyCatalog:
    """
    Catalog for managing model policies.

    Provides a centralized registry for policies and chains,
    with support for default policies and chain lookup.
    """

    def __init__(self) -> None:
        """Initialize the policy catalog."""
        self._policies: Dict[str, ModelPolicy] = {}
        self._chains: Dict[str, ModelPolicyChain] = {}
        self._default_chain: Optional[str] = None

    def register_policy(self, policy: ModelPolicy) -> None:
        """Register a policy."""
        self._policies[policy.name] = policy
        logger.debug(f"Registered policy: {policy.name}")

    def register_chain(self, chain: ModelPolicyChain, is_default: bool = False) -> None:
        """Register a policy chain."""
        self._chains[chain.name] = chain
        if is_default:
            self._default_chain = chain.name
        logger.debug(f"Registered chain: {chain.name} (default={is_default})")

    def get_chain(self, name: str) -> Optional[ModelPolicyChain]:
        """Get a chain by name."""
        return self._chains.get(name)

    def get_default_chain(self) -> Optional[ModelPolicyChain]:
        """Get the default policy chain."""
        if self._default_chain:
            return self._chains.get(self._default_chain)
        return None

    def evaluate_fallback(
        self,
        model_name: str,
        failure_category: FailureCategory,
        chain_name: Optional[str] = None,
        available_models: Optional[List[str]] = None,
    ) -> FallbackAction:
        """
        Evaluate fallback action using catalog.

        Args:
            model_name: Model that failed
            failure_category: Type of failure
            chain_name: Optional chain to use (defaults to default chain)
            available_models: Currently available models

        Returns:
            FallbackAction to take
        """
        chain = None
        if chain_name:
            chain = self.get_chain(chain_name)
        if chain is None:
            chain = self.get_default_chain()

        if chain is None:
            return FallbackAction(
                action_type=FallbackActionType.STOP,
                reason="No policy chain available",
            )

        return chain.evaluate(model_name, failure_category, available_models)

    def apply_user_intent(
        self,
        action: FallbackAction,
        intent: FallbackIntent,
    ) -> FallbackAction:
        """
        Modify fallback action based on user intent.

        Args:
            action: Current fallback action
            intent: User's intent

        Returns:
            Modified FallbackAction
        """
        if intent == FallbackIntent.STOP:
            return FallbackAction(
                action_type=FallbackActionType.STOP,
                reason="User chose to stop",
            )

        if intent == FallbackIntent.UPGRADE:
            return FallbackAction(
                action_type=FallbackActionType.SUGGEST_UPGRADE,
                reason="User chose upgrade path",
            )

        if intent == FallbackIntent.RETRY_ONCE:
            if action.action_type == FallbackActionType.SWITCH_MODEL:
                return FallbackAction(
                    action_type=FallbackActionType.SWITCH_MODEL,
                    target_model=action.target_model,
                    reason=f"{action.reason} (user: retry once)",
                    metadata={"max_retries": 1},
                )

        if intent == FallbackIntent.RETRY_ALWAYS:
            return FallbackAction(
                action_type=action.action_type,
                target_model=action.target_model,
                reason=f"{action.reason} (user: retry always)",
                metadata={"max_retries": -1},  # Unlimited
            )

        # AUTO or ASK_USER - return original action
        return action

    def list_policies(self) -> List[str]:
        """List all registered policy names."""
        return list(self._policies.keys())

    def list_chains(self) -> List[str]:
        """List all registered chain names."""
        return list(self._chains.keys())

    def clear(self) -> None:
        """Clear all registered policies and chains."""
        self._policies.clear()
        self._chains.clear()
        self._default_chain = None


def create_default_policy_chain() -> ModelPolicyChain:
    """
    Create a default policy chain with common fallback rules.

    Returns:
        A pre-configured ModelPolicyChain
    """
    chain = ModelPolicyChain(name="default")

    # Transient failures - retry with fallback models
    chain.add_policy(
        ModelPolicy(
            name="transient_gpt4",
            model_pattern="gpt-4*",
            failure_category=FailureCategory.TRANSIENT,
            action_type=FallbackActionType.SWITCH_MODEL,
            fallback_models=["gpt-4o-mini", "gpt-3.5-turbo"],
            allow_retry=True,
        )
    )

    chain.add_policy(
        ModelPolicy(
            name="transient_claude",
            model_pattern="claude-*",
            failure_category=FailureCategory.TRANSIENT,
            action_type=FallbackActionType.SWITCH_MODEL,
            fallback_models=["claude-3-haiku-20240307", "gpt-4o-mini"],
            allow_retry=True,
        )
    )

    # Terminal failures - prompt user
    chain.add_policy(
        ModelPolicy(
            name="terminal_any",
            model_pattern="*",
            failure_category=FailureCategory.TERMINAL,
            action_type=FallbackActionType.PROMPT_USER,
            user_prompt_message="Model is permanently unavailable. Would you like to try a different model?",
            allow_retry=False,
        )
    )

    # Not found - stop
    chain.add_policy(
        ModelPolicy(
            name="not_found_any",
            model_pattern="*",
            failure_category=FailureCategory.NOT_FOUND,
            action_type=FallbackActionType.STOP,
            allow_retry=False,
        )
    )

    # Catch-all for transient
    chain.add_policy(
        ModelPolicy(
            name="transient_any",
            model_pattern="*",
            failure_category=FailureCategory.TRANSIENT,
            action_type=FallbackActionType.RETRY_SAME,
            allow_retry=True,
            max_retries=2,
        )
    )

    return chain


# Singleton catalog
_catalog: Optional[PolicyCatalog] = None


def get_policy_catalog() -> PolicyCatalog:
    """
    Get the global policy catalog.

    Initializes with default chain if empty.

    Returns:
        PolicyCatalog singleton
    """
    global _catalog
    if _catalog is None:
        _catalog = PolicyCatalog()
        # Register default chain
        default_chain = create_default_policy_chain()
        _catalog.register_chain(default_chain, is_default=True)
    return _catalog
