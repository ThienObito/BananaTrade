import json

from pydantic import BaseModel, ValidationError


class StructuredOutputError(ValueError):
    """Structured JSON was invalid or did not satisfy its schema."""


def parse_structured[T: BaseModel](text: str, schema: type[T], repair_text: str | None = None) -> T:
    try:
        return schema.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        if repair_text is None:
            raise StructuredOutputError("Invalid structured output") from exc
        try:
            return schema.model_validate(json.loads(repair_text))
        except (json.JSONDecodeError, ValidationError) as repair_exc:
            raise StructuredOutputError("Invalid structured output after one repair") from repair_exc
