"""The two languages the site supports. One definition shared by errors, schemas and models."""

from enum import StrEnum


class Locale(StrEnum):
    ES = "es"
    EN = "en"
