import pytest

from app.security import validate_signing_configuration


VALID_SECRET = "staging-signing-secret-not-a-credential"


def test_signing_configuration_accepts_hs256_and_a_long_secret():
    validate_signing_configuration(VALID_SECRET, "HS256")


@pytest.mark.parametrize("algorithm", ["HS512", "none", "RS256", ""])
def test_signing_configuration_rejects_other_algorithms(algorithm):
    with pytest.raises(RuntimeError, match="HS256"):
        validate_signing_configuration(VALID_SECRET, algorithm)


@pytest.mark.parametrize(
    "secret",
    [None, "", "short", "changeme", "x" * 31],
)
def test_signing_configuration_rejects_a_missing_or_short_secret(secret):
    with pytest.raises(RuntimeError, match="missing or too short"):
        validate_signing_configuration(secret, "HS256")
