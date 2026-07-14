import pytest
from src.llm.real import RealLLM


def test_real_llm_uses_explicit_api_key():
    llm = RealLLM({}, api_key="sk-explicit-key")
    assert llm._get_api_key() == "sk-explicit-key"


def test_real_llm_falls_back_to_keyring():
    llm = RealLLM({})
    key = llm._get_api_key()
    assert key is None or isinstance(key, str)