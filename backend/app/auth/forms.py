from __future__ import annotations

from typing import Any, Mapping

import re

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LoginForm(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not _EMAIL_RE.match(value):
            raise ValueError("Invalid email address")
        return value

    @classmethod
    def from_form(cls, form: Mapping[str, Any]) -> "LoginForm":
        return cls(
            email=str(form.get("email", "")).strip(),
            password=str(form.get("password", "")),
        )


class RegisterForm(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)
    organization_name: str = Field(min_length=2, max_length=120)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not _EMAIL_RE.match(value):
            raise ValueError("Invalid email address")
        return value

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterForm":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

    @classmethod
    def from_form(cls, form: Mapping[str, Any]) -> "RegisterForm":
        return cls(
            email=str(form.get("email", "")).strip(),
            password=str(form.get("password", "")),
            confirm_password=str(form.get("confirm_password", "")),
            organization_name=str(form.get("organization_name", "")).strip(),
        )


class OrganizationForm(BaseModel):
    name: str = Field(min_length=2, max_length=120)

    @classmethod
    def from_form(cls, form: Mapping[str, Any]) -> "OrganizationForm":
        return cls(name=str(form.get("name", "")).strip())


__all__ = ["LoginForm", "RegisterForm", "OrganizationForm", "ValidationError"]
