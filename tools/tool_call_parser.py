import ast
import json
import re
from types import SimpleNamespace


class ToolArgumentsError(ValueError):
    pass


def is_tool_json_error(error) -> bool:
    text = str(error).lower()
    return (
        "failed to parse tool call arguments as json" in text
        or "tool_use_failed" in text
        or "invalid_request_error" in text
    )


def failed_tool_name(error) -> str:
    generated = _failed_generation(error).lower()
    for name in (
        "write_file_chunk",
        "write_file",
        "edit_file",
        "execute_file",
    ):
        if f'"name": "{name}"' in generated or f'"name":"{name}"' in generated:
            return name
    return ""


def parse_tool_arguments(raw: str) -> dict:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}

    candidate = raw.strip()
    decoders = (
        lambda value: json.loads(value),
        lambda value: json.loads(value.replace("\\\\", "\\")),
        lambda value: ast.literal_eval(value),
    )
    for decoder in decoders:
        try:
            parsed = decoder(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, SyntaxError, json.JSONDecodeError):
            continue

    raise ToolArgumentsError("Argumentos da ferramenta não formam um objeto JSON válido.")


def _failed_generation(error) -> str:
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        value = body.get("failed_generation")
        if isinstance(value, str):
            return value

    text = str(error)
    match = re.search(r"failed_generation['\"]\s*:\s*(['\"])(.*?)\1", text, re.DOTALL)
    if not match:
        return ""

    try:
        value = ast.literal_eval(match.group(0).split(":", 1)[1].strip())
        return value if isinstance(value, str) else ""
    except (ValueError, SyntaxError):
        return match.group(2)


def _repair_truncated_json(text: str) -> str:
    """
    Fecha aspas e chaves/colchetes deixados abertos quando a geração do
    modelo é cortada no meio do conteúdo (ex.: max_completion_tokens
    atingido durante um write_file_chunk com um arquivo grande).

    Não tenta validar semântica, apenas devolver algo parseável por
    json.loads contendo o máximo de conteúdo real possível.
    """

    text = text.rstrip()
    in_string = False
    escape = False
    stack = []

    for char in text:
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char in "{[":
                stack.append(char)
            elif char in "}]":
                if stack:
                    stack.pop()

    repaired = text

    if in_string:
        repaired += '"'

    while stack:
        opener = stack.pop()
        repaired += "}" if opener == "{" else "]"

    return repaired


def recover_tool_call(error):
    generated = _failed_generation(error)
    if not generated:
        return None

    marker = generated.find("{\"name\"")
    if marker < 0:
        marker = generated.find("{\'name\'")
    if marker < 0:
        return None

    candidate = generated[marker:]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        try:
            payload = json.loads(_repair_truncated_json(candidate))
        except (ValueError, json.JSONDecodeError):
            return None

    name = payload.get("name")
    arguments = payload.get("arguments", {})
    if not isinstance(name, str):
        return None

    try:
        arguments = parse_tool_arguments(arguments)
    except ToolArgumentsError:
        return None

    return SimpleNamespace(
        id="recovered-tool-call",
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments, ensure_ascii=False),
        ),
    )