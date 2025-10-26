from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.settings import Settings


def test_settings_invalid_env():
    """Verify that an invalid ENV value raises a validation error."""
    with pytest.raises(ValidationError):
        Settings(env="invalid")
