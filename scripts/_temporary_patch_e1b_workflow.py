from __future__ import annotations

from pathlib import Path


path = Path(".github/workflows/evaluator_panel_e1b_wildguard.yml")
text = path.read_text(encoding="utf-8")

old_identity = (
    '          test "$WILDGUARD_ACCESS_OK" = "true"\n'
    '          test "$WILDGUARD_MODEL_REVISION" = \\\n'
    '            "$(jq -r \'.model_revision\' '
    '"$SAFE_OUTPUT/wildguard_preflight.json")"\n'
)
new_identity = (
    '          test "$(jq -r \'.access_ok\' \\\n'
    '            "$SAFE_OUTPUT/wildguard_preflight.json")" = "true"\n'
    '          test "$(jq -r \'.model_revision\' \\\n'
    '            "$SAFE_OUTPUT/wildguard_preflight.json")" = \\\n'
    '            "$WILDGUARD_MODEL_REVISION"\n'
)
if old_identity not in text:
    raise SystemExit("identity-check snippet not found")
text = text.replace(old_identity, new_identity, 1)

start_marker = '          safe_text = "\\n".join(\n'
end_marker = (
    '                                  raise SystemExit('
    'f"private text leaked through {key}")\n'
)
start = text.find(start_marker)
if start < 0:
    raise SystemExit("safe verifier start not found")
end = text.find(end_marker, start)
if end < 0:
    raise SystemExit("safe verifier end not found")
end += len(end_marker)

replacement = """          safe_text = "\\n".join(
              path.read_text(encoding="utf-8")
              for path in safe.rglob("*")
              if path.is_file()
          )

          def load_safe_values(path):
              if path.suffix == ".jsonl":
                  return [
                      json.loads(line)
                      for line in path.read_text(encoding="utf-8").splitlines()
                      if line.strip()
                  ]
              return [json.loads(path.read_text(encoding="utf-8"))]

          for path in safe.rglob("*.json*"):
              for value in load_safe_values(path):
                  stack = [value]
                  while stack:
                      item = stack.pop()
                      if isinstance(item, dict):
                          leaked = forbidden_keys.intersection(item)
                          if leaked:
                              raise SystemExit(
                                  f"unsafe safe-artifact keys: {sorted(leaked)}"
                              )
                          stack.extend(item.values())
                      elif isinstance(item, list):
                          stack.extend(item)
          if private.exists():
              for path in private.rglob("*.jsonl"):
                  for line in path.read_text(encoding="utf-8").splitlines():
                      if not line.strip():
                          continue
                      row = json.loads(line)
                      for key in forbidden_keys:
                          value = row.get(key)
                          if isinstance(value, str) and len(value) >= 16:
                              if value in safe_text:
                                  raise SystemExit(
                                      f"private text leaked through {key}"
                                  )
"""
text = text[:start] + replacement + text[end:]
path.write_text(text, encoding="utf-8")
