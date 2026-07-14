import pytest
import asyncio
from src.guardrail.hitl import HITLStateMachine, HITLDecision
from src.guardrail.classifier import InterceptResult


@pytest.mark.asyncio
async def test_hitl_web_mode_returns_future():
    hitl = HITLStateMachine(web_mode=True)
    result = InterceptResult(level=3, blocked=True, reason="rm -rf /")
    decision = hitl.check(result)
    assert decision is None

    future = hitl.wait_for_decision()
    assert not future.done()


@pytest.mark.asyncio
async def test_hitl_web_mode_resolve_approve():
    hitl = HITLStateMachine(web_mode=True)
    result = InterceptResult(level=3, blocked=True, reason="rm -rf /")
    hitl.check(result)
    future = hitl.wait_for_decision()
    hitl.resolve_decision(True)
    approved = await future
    assert approved is True


@pytest.mark.asyncio
async def test_hitl_web_mode_resolve_deny():
    hitl = HITLStateMachine(web_mode=True)
    result = InterceptResult(level=3, blocked=True, reason="rm -rf /")
    hitl.check(result)
    hitl.resolve_decision(False)
    approved = await hitl.wait_for_decision()
    assert approved is False


@pytest.mark.asyncio
async def test_hitl_web_mode_auto_deny_on_timeout():
    hitl = HITLStateMachine(web_mode=True, timeout=1)
    result = InterceptResult(level=3, blocked=True, reason="rm -rf /")
    hitl.check(result)
    approved = await hitl.wait_for_decision()
    assert approved is False


def test_hitl_non_web_mode_uses_input():
    hitl = HITLStateMachine(web_mode=False)
    result = InterceptResult(level=2, blocked=False, reason="write file")
    decision = hitl.check(result)
    assert decision == HITLDecision.ALLOW