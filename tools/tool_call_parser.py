import ast
import json
import re
from types import SimpleNamespace


class ToolArgumentsError(ValueError):
    pass


def is_tool_json_error(error) -> bool:
    text = str(error).lower()
    # "invalid_request_error" e "jsondecodeerror" foram removidos: eles casam com
    # qualquer erro 400 (modelo inexistente, contexto estourado, imagem não
    # suportada). O agente então dizia "JSON inválido" e escondia a causa real.
    return (
        "failed to parse tool call arguments as json" in text
        or "tool_use_failed" in text
        or "toolargumentserror" in text
    )


def failed_tool_name(error) -> str:
    generated = _failed_generation(error).lower()
    for name in (
        "write_files",
        "write_file_chunk",
        "write_file",
        "edit_file",
        "execute_file",
        "run_code_file",
        "run_terminal",
    ):
        if re.search(rf'["\']name["\']\s*:\s*["\']{name}["\']', generated):
            return name
    return ""


def parse_tool_arguments(raw: str) -> dict:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}

    candidate = raw.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 2:
            candidate = "\n".join(lines[1:-1]).strip()

    decoders = (
        lambda value: json.loads(value, strict=False),
        lambda value: json.loads(value.replace("\\\\", "\\"), strict=False),
        lambda value: json.loads(_repair_truncated_json(value), strict=False),
        lambda value: ast.literal_eval(value),
    )
    for decoder in decoders:
        try:
            parsed = decoder(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, SyntaxError, json.JSONDecodeError):
            continue

    # Fallback via regex para recuperação de escrita de código (write_file / write_file_chunk)
    path_match = re.search(r'["\']path["\']\s*:\s*["\']([^"\']+)["\']', candidate)
    if path_match:
        content_match = re.search(r'["\']content["\']\s*:\s*["\'](.*)', candidate, re.DOTALL)
        if content_match:
            val = content_match.group(1)
            val = re.sub(r'["\']\s*\}?\s*$', "", val)
            return {"path": path_match.group(1), "content": val}

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
    atingido durante um write_file com um arquivo grande).

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

    match = re.search(r'\{\s*["\']name["\']\s*:', generated)
    if not match:
        return None

    candidate = generated[match.start():]
    payload = None
    for decoder in (
        lambda text: json.loads(text, strict=False),
        lambda text: json.loads(_repair_truncated_json(text), strict=False),
        lambda text: ast.literal_eval(text),
    ):
        try:
            payload = decoder(candidate)
            if isinstance(payload, dict) and "name" in payload:
                break
        except Exception:
            continue

    if not isinstance(payload, dict):
        name_match = re.search(r'["\']name["\']\s*:\s*["\']([^"\']+)["\']', candidate)
        if name_match:
            tool_name = name_match.group(1)
            args_match = re.search(r'["\']arguments["\']\s*:\s*(\{.*)', candidate, re.DOTALL)
            if args_match:
                try:
                    args = parse_tool_arguments(args_match.group(1))
                    payload = {"name": tool_name, "arguments": args}
                except Exception:
                    pass

    if not isinstance(payload, dict):
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