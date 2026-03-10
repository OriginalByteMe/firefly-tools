import json
from firefly_mcp.resources import get_bank_config


def test_get_bank_config_hsbc():
    result = get_bank_config("hsbc")
    data = json.loads(result)
    assert data["version"] == 3
    assert data["content_type"] == "csv"


def test_get_bank_config_maybank():
    result = get_bank_config("maybank")
    data = json.loads(result)
    assert data["version"] == 3


def test_get_bank_config_unknown():
    result = get_bank_config("unknown_bank")
    data = json.loads(result)
    assert "error" in data
    assert "available" in data
    assert "hsbc" in data["available"]
