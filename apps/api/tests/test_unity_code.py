import pytest

from app.providers import ProviderFailure, RUNTIME_SCRIPT_TEMPLATE, validate_unity_code


def test_curated_mock_script_passes_narrow_safety_gate() -> None:
    source = validate_unity_code(RUNTIME_SCRIPT_TEMPLATE)
    assert source.endswith("\n")
    assert "MonoBehaviour" in source


@pytest.mark.parametrize("forbidden", ["System.IO", "System.Net", "UnityEditor", "Process.", "DllImport"])
def test_generated_script_rejects_dangerous_capabilities(forbidden: str) -> None:
    unsafe = RUNTIME_SCRIPT_TEMPLATE.replace("using UnityEngine;", f"using UnityEngine;\n// {forbidden}")
    with pytest.raises(ProviderFailure, match="窄权限校验"):
        validate_unity_code(unsafe)
