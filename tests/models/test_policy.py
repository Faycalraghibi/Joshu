"""
Unit tests for policy-driven fallback mechanisms.

Run with: pytest tests/models/test_policy.py -v
"""

import pytest

from joshu.models.availability import FailureCategory
from joshu.models.policy import (
    FallbackAction,
    FallbackActionType,
    FallbackIntent,
    ModelPolicy,
    ModelPolicyChain,
    PolicyCatalog,
    create_default_policy_chain,
    get_policy_catalog,
)


class TestModelPolicy:
    """Test ModelPolicy data structure."""

    def test_create_policy(self):
        """Test creating a policy."""
        policy = ModelPolicy(
            name="test_policy",
            model_pattern="gpt-4*",
            failure_category=FailureCategory.TRANSIENT,
            fallback_models=["gpt-3.5-turbo"],
        )
        assert policy.name == "test_policy"
        assert policy.allow_retry is True

    def test_matches_model_exact(self):
        """Test exact model name matching."""
        policy = ModelPolicy(
            name="test",
            model_pattern="gpt-4o",
            failure_category=FailureCategory.TRANSIENT,
        )
        assert policy.matches_model("gpt-4o")
        assert not policy.matches_model("gpt-4")

    def test_matches_model_wildcard(self):
        """Test wildcard pattern matching."""
        policy = ModelPolicy(
            name="test",
            model_pattern="gpt-4*",
            failure_category=FailureCategory.TRANSIENT,
        )
        assert policy.matches_model("gpt-4o")
        assert policy.matches_model("gpt-4-turbo")
        assert not policy.matches_model("gpt-3.5")

    def test_matches_model_star(self):
        """Test catch-all pattern."""
        policy = ModelPolicy(
            name="test",
            model_pattern="*",
            failure_category=FailureCategory.TRANSIENT,
        )
        assert policy.matches_model("any-model")

    def test_matches_failure(self):
        """Test failure category matching."""
        policy = ModelPolicy(
            name="test",
            model_pattern="*",
            failure_category=FailureCategory.TERMINAL,
        )
        assert policy.matches_failure(FailureCategory.TERMINAL)
        assert not policy.matches_failure(FailureCategory.TRANSIENT)

    def test_to_dict_from_dict(self):
        """Test serialization round-trip."""
        policy = ModelPolicy(
            name="test",
            model_pattern="gpt-*",
            failure_category=FailureCategory.TRANSIENT,
            fallback_models=["gpt-3.5-turbo"],
            allow_retry=True,
        )
        data = policy.to_dict()
        restored = ModelPolicy.from_dict(data)

        assert restored.name == policy.name
        assert restored.model_pattern == policy.model_pattern
        assert restored.fallback_models == policy.fallback_models


class TestFallbackAction:
    """Test FallbackAction data structure."""

    def test_switch_model_action(self):
        """Test switch model action."""
        action = FallbackAction(
            action_type=FallbackActionType.SWITCH_MODEL,
            target_model="gpt-3.5-turbo",
            reason="Fallback due to rate limit",
        )
        assert action.action_type == FallbackActionType.SWITCH_MODEL
        assert action.target_model == "gpt-3.5-turbo"

    def test_to_dict(self):
        """Test serialization."""
        action = FallbackAction(
            action_type=FallbackActionType.STOP,
            reason="No fallback available",
        )
        data = action.to_dict()
        assert data["action_type"] == "stop"


class TestModelPolicyChain:
    """Test ModelPolicyChain evaluation."""

    @pytest.fixture
    def chain(self):
        """Create a test chain."""
        chain = ModelPolicyChain(name="test_chain")
        chain.add_policy(
            ModelPolicy(
                name="gpt4_transient",
                model_pattern="gpt-4*",
                failure_category=FailureCategory.TRANSIENT,
                action_type=FallbackActionType.SWITCH_MODEL,
                fallback_models=["gpt-3.5-turbo"],
            )
        )
        chain.add_policy(
            ModelPolicy(
                name="terminal_any",
                model_pattern="*",
                failure_category=FailureCategory.TERMINAL,
                action_type=FallbackActionType.PROMPT_USER,
            )
        )
        return chain

    def test_find_matching_policy(self, chain):
        """Test finding matching policy."""
        policy = chain.find_matching_policy("gpt-4o", FailureCategory.TRANSIENT)
        assert policy is not None
        assert policy.name == "gpt4_transient"

    def test_find_no_match(self, chain):
        """Test when no policy matches."""
        policy = chain.find_matching_policy("claude-3", FailureCategory.TRANSIENT)
        assert policy is None

    def test_evaluate_switch_model(self, chain):
        """Test evaluation produces switch action."""
        action = chain.evaluate("gpt-4o", FailureCategory.TRANSIENT)

        assert action.action_type == FallbackActionType.SWITCH_MODEL
        assert action.target_model == "gpt-3.5-turbo"

    def test_evaluate_prompt_user(self, chain):
        """Test evaluation produces prompt action."""
        action = chain.evaluate("any-model", FailureCategory.TERMINAL)

        assert action.action_type == FallbackActionType.PROMPT_USER

    def test_evaluate_default_action(self, chain):
        """Test default action when no match."""
        chain.default_action = FallbackActionType.STOP
        action = chain.evaluate("claude-3", FailureCategory.TRANSIENT)

        assert action.action_type == FallbackActionType.STOP

    def test_evaluate_with_available_models(self, chain):
        """Test evaluation respects available models."""
        # gpt-3.5-turbo is not available
        action = chain.evaluate(
            "gpt-4o",
            FailureCategory.TRANSIENT,
            available_models=["gpt-4-turbo"],
        )

        # Should stop since fallback not available
        assert action.action_type == FallbackActionType.STOP


class TestPolicyCatalog:
    """Test PolicyCatalog management."""

    @pytest.fixture
    def catalog(self):
        """Create fresh catalog."""
        cat = PolicyCatalog()
        cat.clear()
        return cat

    def test_register_chain(self, catalog):
        """Test registering a chain."""
        chain = ModelPolicyChain(name="my_chain")
        catalog.register_chain(chain)

        assert "my_chain" in catalog.list_chains()

    def test_default_chain(self, catalog):
        """Test default chain registration."""
        chain = ModelPolicyChain(name="default")
        catalog.register_chain(chain, is_default=True)

        assert catalog.get_default_chain() is chain

    def test_evaluate_fallback(self, catalog):
        """Test fallback evaluation through catalog."""
        chain = ModelPolicyChain(name="test")
        chain.add_policy(
            ModelPolicy(
                name="catch_all",
                model_pattern="*",
                failure_category=FailureCategory.TRANSIENT,
                action_type=FallbackActionType.RETRY_SAME,
                allow_retry=True,
            )
        )
        catalog.register_chain(chain, is_default=True)

        action = catalog.evaluate_fallback("any-model", FailureCategory.TRANSIENT)

        assert action.action_type == FallbackActionType.RETRY_SAME

    def test_apply_user_intent_stop(self, catalog):
        """Test applying STOP intent."""
        action = FallbackAction(
            action_type=FallbackActionType.SWITCH_MODEL,
            target_model="gpt-3.5",
        )
        modified = catalog.apply_user_intent(action, FallbackIntent.STOP)

        assert modified.action_type == FallbackActionType.STOP

    def test_apply_user_intent_upgrade(self, catalog):
        """Test applying UPGRADE intent."""
        action = FallbackAction(action_type=FallbackActionType.PROMPT_USER)
        modified = catalog.apply_user_intent(action, FallbackIntent.UPGRADE)

        assert modified.action_type == FallbackActionType.SUGGEST_UPGRADE

    def test_apply_user_intent_retry_always(self, catalog):
        """Test applying RETRY_ALWAYS intent."""
        action = FallbackAction(
            action_type=FallbackActionType.SWITCH_MODEL,
            target_model="gpt-3.5",
        )
        modified = catalog.apply_user_intent(action, FallbackIntent.RETRY_ALWAYS)

        assert modified.metadata.get("max_retries") == -1


class TestDefaultPolicyChain:
    """Test default policy chain creation."""

    def test_create_default_chain(self):
        """Test default chain has expected policies."""
        chain = create_default_policy_chain()

        assert chain.name == "default"
        assert len(chain.policies) >= 4

    def test_default_chain_handles_transient(self):
        """Test default chain handles transient failures."""
        chain = create_default_policy_chain()
        action = chain.evaluate("gpt-4o", FailureCategory.TRANSIENT)

        # Should try to switch or retry
        assert action.action_type in (
            FallbackActionType.SWITCH_MODEL,
            FallbackActionType.RETRY_SAME,
        )


class TestGlobalCatalog:
    """Test global catalog singleton."""

    def test_get_policy_catalog(self):
        """Test singleton access."""
        cat1 = get_policy_catalog()
        cat2 = get_policy_catalog()
        assert cat1 is cat2

    def test_catalog_has_default_chain(self):
        """Test catalog is initialized with default chain."""
        catalog = get_policy_catalog()
        default = catalog.get_default_chain()

        assert default is not None
        assert default.name == "default"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
