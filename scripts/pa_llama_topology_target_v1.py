"""Explicit-base topology target worker; no historical reader, judge or scientific gate.

The root loader owns frozen-contract/asset verification. Preparation accepts only
bytes of the NEW screen input artifact, in memory. Execution uses independent
topology receipts and only pinned low-level server/resource/parser helpers.
"""

from __future__ import annotations

import math
import os
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

import pa_llama_development_common_v1 as c
import pa_llama_development_target_v1 as low
import pa_llama_topology_plan_v1 as p

RUNNER = "scripts/pa_llama_topology_target_v1.py"
SAFE_ROOT = "data/natural_language_localization/pa_llama_topology_v1"
PRIVATE_ROOT = "artifacts/pa_llama_topology_v1/private"
SCHEMA = "jbspan-pa-llama-topology-execution-v1"
COOLDOWN = {
    "before_every_target_dispatch": True,
    "maximum_start_temperature_c": 60,
    "maximum_wait_seconds": 180,
    "poll_seconds": 0.5,
    "hardware_settings_changed": False,
    "inflight_timeout_unchanged": True,
}
MAX_JSON_BYTES = 32_000_000


def read_json(path):
    c.require(
        path.is_file() and 0 < path.stat().st_size <= MAX_JSON_BYTES,
        "TOPOLOGY_JSON_MISSING_OR_OVERSIZED",
    )
    return c.strict_json(path.read_bytes())


def prepare_materials(plan, source_context, screen_inputs_raw, screen_input_receipt, renderer):
    """Pure: verify NEW input bytes and materialize every certified position, no reader."""
    p.validate_plan(plan, **source_context)
    c.require(plan["materializations_bound"] is False, "UNBOUND_PROSPECTIVE_PLAN_REQUIRED")
    config, inventory = p.validate_inputs(
        source_context["screen_contract_raw"], source_context["inventory_raw"]
    )
    config = {**config, "_contract_sha256": p.SCREEN_SHA256}
    c.require(
        isinstance(screen_inputs_raw, bytes) and len(screen_inputs_raw) <= 2_000_000,
        "NEW_SCREEN_INPUT_BYTES_REQUIRED",
    )
    c.require(
        c.same(screen_input_receipt, low.input_receipt(config, inventory, screen_inputs_raw)),
        "NEW_SCREEN_INPUT_RECEIPT_MISMATCH",
    )
    wrapper = c.strict_json(screen_inputs_raw)
    c.require(
        isinstance(wrapper, dict)
        and set(wrapper) == {"rows"}
        and isinstance(wrapper["rows"], list)
        and len(wrapper["rows"]) == 90,
        "NEW_SCREEN_INPUT_FRAME_NOT_90",
    )
    attacked = {}
    for row, source in zip(wrapper["rows"], inventory["rows"], strict=True):
        c.require(
            isinstance(row, dict) and set(row) == low.INPUT_KEYS,
            "NEW_SCREEN_INPUT_EXTRA_OR_MISSING_FIELD",
        )
        c.require(
            all(
                c.same(row.get(key), source[key])
                for key in ("payload_position", "condition", "payload_sha256", "prompt_sha256")
            )
            and row["source_private_record_sha256"] == source["private_source"]["sha256"],
            "NEW_SCREEN_INPUT_SOURCE_BINDING_CHANGED",
        )
        payload, prompt = row["payload"], row["prompt"]
        c.require(
            isinstance(payload, str)
            and payload
            and isinstance(prompt, str)
            and prompt
            and c.sha_bytes(payload.encode()) == row["payload_sha256"]
            and c.sha_bytes(prompt.encode()) == row["prompt_sha256"]
            and len(prompt.encode()) == source["prompt_utf8_bytes"],
            "NEW_SCREEN_INPUT_CONTENT_CHANGED",
        )
        c.require(
            prompt.count(payload) == 1 and (row["condition"] != "DIRECT" or prompt == payload),
            "NEW_SCREEN_INPUT_PAYLOAD_PARTITION_CHANGED",
        )
        if row["condition"] == "ATTACKED_H4RM3L":
            attacked[row["payload_position"]] = row
    safe_rows, private_rows = [], []
    identities = []
    for source in plan["population"]:
        row = attacked[source["payload_position"]]
        anchor = {
            key: source[key]
            for key in (
                "payload_sha256",
                "prompt_sha256",
                "unit_manifest_sha256",
                "fragment_manifest_sha256",
            )
        }
        bundle = renderer.prepare_bound_bundle(
            row["payload"], row["prompt"], anchor, source["payload_position"]
        )
        c.require(
            c.same(bundle.get("source_identity"), anchor)
            and bundle.get("execution_authorized") is False
            and c.same(bundle.get("model_calls"), 0),
            "RENDERER_AUTHORITY_OR_ANCHOR_CHANGED",
        )
        safe_rows.extend(bundle["safe_rows"])
        private_rows.extend(bundle["private_rows"])
        identities.append({"payload_position": source["payload_position"], **anchor})
    bound = p.bind_materializations(plan, safe_rows, c.digest(identities), **source_context)
    c.require(len(private_rows) == 48 * plan["n"], "ALL48_PRIVATE_RENDERER_ROWS_REQUIRED")
    private_map = {}
    for row in private_rows:
        c.require(
            isinstance(row, dict)
            and set(row) == {"payload_position", "mask", "operator", "kind", "task_id", "prompt"},
            "PRIVATE_RENDERER_ROW_SCHEMA_CHANGED",
        )
        key = c.digest(p.materialization_key(row))
        c.require(key not in private_map, "PRIVATE_RENDERER_DUPLICATE_KEY")
        private_map[key] = row
    for row in safe_rows:
        key = c.digest(p.materialization_key(row))
        c.require(
            key in private_map
            and isinstance(private_map[key]["prompt"], str)
            and c.sha_bytes(private_map[key]["prompt"].encode()) == row["prompt_sha256"]
            and len(private_map[key]["prompt"].encode()) == row["prompt_utf8_bytes"],
            "PRIVATE_RENDERER_SAFE_BINDING_CHANGED",
        )
    rows = [
        {
            "materialization_id": item["materialization_id"],
            "prompt": private_map[c.digest(p.materialization_key(item))]["prompt"],
        }
        for item in bound["bound_materializations"]
    ]
    return {
        "bound_plan": bound,
        "private_materializations": {"rows": rows},
        "new_screen_input_sha256": c.sha_bytes(screen_inputs_raw),
        "historical_private_reads": 0,
        "model_calls": 0,
        "execution_authorized": False,
    }


def request_for(config, item, prompt):
    c.require(isinstance(prompt, str) and prompt, "TOPOLOGY_PROMPT_REQUIRED")
    return {
        "model": config["model"]["alias"],
        "stream": False,
        "messages": [{"role": "user", "content": prompt}],
        **item["generation"],
    }


def parse_reply(config, item, raw, expected_prompt_tokens):
    if item["kind"] == "science":
        parsed = low.parse_reply(config, raw, expected_prompt_tokens)
        return {**parsed, "eligible_for_control": False}
    c.require(item["kind"] == "control", "TOPOLOGY_REQUEST_KIND_INVALID")
    value = c.strict_json(raw)
    c.require(
        isinstance(value, dict) and value.get("model") == config["model"]["alias"],
        "REPLY_MODEL_MISMATCH",
    )
    choices = value.get("choices")
    c.require(
        isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict),
        "REPLY_CHOICES_INVALID",
    )
    choice = choices[0]
    c.require(c.same(choice.get("index"), 0), "REPLY_CHOICE_INDEX_INVALID")
    message = choice.get("message")
    c.require(
        isinstance(message, dict)
        and message.get("role") == "assistant"
        and not any(
            message.get(key)
            for key in ("tool_calls", "function_call", "refusal", "reasoning_content")
        ),
        "REPLY_ROLE_OR_CHANNEL_INVALID",
    )
    content, finish, usage = message.get("content"), choice.get("finish_reason"), value.get("usage")
    c.require(
        isinstance(content, str) and finish in {"stop", "length"}, "REPLY_CONTENT_OR_FINISH_INVALID"
    )
    c.require(
        isinstance(usage, dict)
        and all(
            type(usage.get(key)) is int and usage[key] >= 0
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        ),
        "REPLY_USAGE_INVALID",
    )
    c.require(
        usage["prompt_tokens"] == expected_prompt_tokens,
        "NATIVE_CENSUS_USAGE_MISMATCH_NO_SILENT_TRUNCATION",
    )
    c.require(
        0 < usage["prompt_tokens"] <= 4048
        and usage["completion_tokens"] <= 48
        and usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
        and usage["total_tokens"] <= 4096,
        "REPLY_TOKEN_BUDGET_VIOLATION",
    )
    c.require(not content or usage["completion_tokens"] > 0, "NONEMPTY_REPLY_ZERO_TOKENS")
    normalized = c.normalize_response(content)
    reason = (
        "TRUNCATED_UNKNOWN" if finish == "length" else ("EMPTY_UNKNOWN" if not normalized else None)
    )
    return {
        "content_sha256": c.sha_bytes(content.encode()),
        "response_sha256": c.sha_bytes(normalized.encode()),
        "raw_reply_sha256": c.sha_bytes(raw),
        "finish_reason": finish,
        "usage": {
            key: usage[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        },
        "eligible_for_panel": False,
        "eligible_for_control": reason is None,
        "ineligible_reason": reason,
        "completion_cap_reached": usage["completion_tokens"] == 48,
        "request_max_tokens": 48,
    }


class TopologyTarget:
    """Root must validate raw contract SHA, all assets and complete code closure first."""

    def __init__(self, root, config, bound_plan, source_context, *, helper=None):
        p.validate_plan(bound_plan, **source_context)
        c.require(bound_plan["materializations_bound"] is True, "BOUND_TOPOLOGY_PLAN_REQUIRED")
        c.require(
            config.get("schema_version") == SCHEMA
            and config.get("frozen") is True
            and config.get("execution_authorized") is True
            and config.get("paper_validity") is False
            and p.valid_sha(config.get("_contract_sha256")),
            "TOPOLOGY_AUTHORITY_REQUIRED",
        )
        c.require(
            config.get("parent_screen_contract_sha256") == p.SCREEN_SHA256
            and config.get("bound_plan_identity_sha256") == bound_plan["plan_identity_sha256"]
            and c.same(config.get("budgets"), bound_plan["budgets"])
            and c.same(config.get("cooldown"), COOLDOWN)
            and c.same(config.get("execution_limits"), bound_plan["execution_limits"]),
            "TOPOLOGY_CONTRACT_PLAN_OR_OPERATIONAL_POLICY_CHANGED",
        )
        c.require(
            c.digest(
                {key: config[key] for key in ("model", "runtime", "server", "panel", "software")}
            )
            == bound_plan["prospective_runtime_identity_sha256"],
            "TOPOLOGY_INHERITED_RUNTIME_IDENTITY_CHANGED",
        )
        c.require(
            c.same(config.get("paths"), {"safe_root": SAFE_ROOT, "private_root": PRIVATE_ROOT}),
            "TOPOLOGY_NEW_NAMESPACE_REQUIRED",
        )
        self.root = Path(root).resolve()
        self.config = c.strict_json(c.canonical(config))
        self.plan = c.strict_json(c.canonical(bound_plan))
        self.paths = {
            kind: c.contained(self.root, prefix + "/" + config["_contract_sha256"])
            for kind, prefix in (("safe", SAFE_ROOT), ("private", PRIVATE_ROOT))
        }
        if os.name == "nt":
            self.paths = {
                kind: path if str(path).startswith("\\\\?\\") else Path("\\\\?\\" + str(path))
                for kind, path in self.paths.items()
            }
        self.helper = helper if helper is not None else low.helper_for(self.root, config)
        self.items = {row["request_id"]: row for row in self.plan["requests"]}
        self.materials = {
            row["materialization_id"]: row for row in self.plan["bound_materializations"]
        }
        self._validated_config_sha256 = c.digest(self.config)
        self._validated_plan_sha256 = c.digest(self.plan)

    def assert_unchanged(self):
        c.require(
            c.digest(self.config) == self._validated_config_sha256
            and c.digest(self.plan) == self._validated_plan_sha256
            and c.same(list(self.items.values()), self.plan["requests"])
            and c.same(list(self.materials.values()), self.plan["bound_materializations"]),
            "POSTVALIDATION_CONTRACT_OR_PLAN_MUTATION",
        )

    def path(self, kind, relative):
        return c.contained(self.paths[kind], relative)

    def read(self, kind, relative):
        return read_json(self.path(kind, relative))

    def write(self, kind, relative, value, *, raw=False):
        c.write_once(self.path(kind, relative), value, raw=raw)

    def reservation(self):
        path = c.contained(self.root, SAFE_ROOT + "/experiment-reservation.safe.json")
        expected = {
            "contract_sha256": self.config["_contract_sha256"],
            "bound_plan_identity_sha256": self.plan["plan_identity_sha256"],
            "budgets": self.plan["budgets"],
            "historical_private_reads_allowed": False,
            "ambiguous_dispatch_retry_allowed": False,
        }
        if path.exists():
            c.require(c.same(read_json(path), expected), "ANOTHER_TOPOLOGY_EXPERIMENT_RESERVED")
        else:
            c.write_once(path, expected)

    @contextmanager
    def operation(self, name):
        self.assert_unchanged()
        c.require(
            not any(
                self.path("safe", f"{prior}-aborted.safe.json").exists()
                for prior in {"stage", "census", "generate", name}
            ),
            "PRIOR_ABORTED_OPERATION_REQUIRES_SEPARATE_AMENDMENT",
        )
        self.reservation()
        lock = self.path("safe", "target-operation.lock.safe.json")
        c.write_once(
            lock,
            {
                "pid": os.getpid(),
                "operation": name,
                "contract_sha256": self.config["_contract_sha256"],
            },
        )
        try:
            yield
        except BaseException as error:
            abort = self.path("safe", f"{name}-aborted.safe.json")
            if not abort.exists():
                c.write_once(
                    abort,
                    {
                        "contract_sha256": self.config["_contract_sha256"],
                        "operation": name,
                        "error_code": low.safe_error_code(error),
                        "scientific_gate_evaluated": False,
                    },
                )
            raise
        finally:
            lock.unlink()

    def stage(self, materials):
        with self.operation("stage"):
            c.require(
                c.same(materials.get("bound_plan"), self.plan)
                and materials.get("historical_private_reads") == 0
                and materials.get("model_calls") == 0
                and materials.get("execution_authorized") is False,
                "PREPARED_MATERIAL_SCOPE_CHANGED",
            )
            wrapper = materials["private_materializations"]
            self.validate_private(wrapper)
            raw = c.canonical(wrapper) + b"\n"
            receipt = {
                "contract_sha256": self.config["_contract_sha256"],
                "bound_plan_identity_sha256": self.plan["plan_identity_sha256"],
                "private_materializations_sha256": c.sha_bytes(raw),
                "new_screen_input_sha256": materials["new_screen_input_sha256"],
                "materializations": len(self.materials),
                "historical_private_reads": 0,
                "new_model_calls": 0,
            }
            self.write("private", "materializations.private.json", raw, raw=True)
            self.write("safe", "materializations.safe.json", receipt)
            return receipt

    def validate_private(self, wrapper):
        c.require(
            isinstance(wrapper, dict)
            and set(wrapper) == {"rows"}
            and isinstance(wrapper["rows"], list)
            and len(wrapper["rows"]) == len(self.materials),
            "PRIVATE_MATERIAL_FRAME_INVALID",
        )
        rows = wrapper["rows"]
        c.require(
            [row.get("materialization_id") for row in rows] == list(self.materials),
            "PRIVATE_MATERIAL_ORDER_OR_IDS_CHANGED",
        )
        for row in rows:
            c.require(
                set(row) == {"materialization_id", "prompt"}
                and isinstance(row["prompt"], str)
                and row["prompt"],
                "PRIVATE_MATERIAL_SCHEMA_CHANGED",
            )
            safe = self.materials[row["materialization_id"]]["renderer_row"]
            c.require(
                c.sha_bytes(row["prompt"].encode()) == safe["prompt_sha256"]
                and len(row["prompt"].encode()) == safe["prompt_utf8_bytes"],
                "PRIVATE_MATERIAL_HASH_CHANGED",
            )
        return {row["materialization_id"]: row["prompt"] for row in rows}

    def load_materials(self):
        raw = self.path("private", "materializations.private.json").read_bytes()
        receipt = self.read("safe", "materializations.safe.json")
        c.require(
            receipt.get("contract_sha256") == self.config["_contract_sha256"]
            and receipt.get("bound_plan_identity_sha256") == self.plan["plan_identity_sha256"]
            and receipt.get("private_materializations_sha256") == c.sha_bytes(raw)
            and c.same(receipt.get("materializations"), len(self.materials))
            and p.valid_sha(receipt.get("new_screen_input_sha256"))
            and c.same(receipt.get("historical_private_reads"), 0)
            and c.same(receipt.get("new_model_calls"), 0),
            "MATERIAL_RECEIPT_CHANGED",
        )
        return self.validate_private(c.strict_json(raw))

    def epoch(self):
        return low.next_epoch(self.paths)

    @contextmanager
    def server(self, epoch):
        low.check_deadline(self.config)
        low.record_prelaunch(self.root, self.config, self.paths, epoch)
        safe, private = low.epoch_paths(self.paths, epoch)
        private.mkdir(parents=True, exist_ok=False)
        with self.helper.owned_server(
            self.root, self.config, private, safe, 1, self.config["_contract_sha256"]
        ) as owned:
            yield owned
        low.verify_epoch(self.config, self.paths, epoch, self.helper, self.root)

    def identity(self, process, client, epoch, relative, context):
        def observe(value):
            self.write(
                "safe",
                relative,
                {
                    "contract_sha256": self.config["_contract_sha256"],
                    "epoch_index": epoch,
                    **context,
                    **value,
                },
            )

        return self.helper.check_identity(process, client, self.config, observe)

    def metadata_post(self, item, stage, body, process, client, epoch):
        c.require(item["stage"] == stage, "METADATA_STAGE_CHANGED")
        low.check_deadline(self.config)
        c.require(process.poll() is None, "METADATA_OWNED_PROCESS_EXITED")
        mid = item["metadata_request_id"]
        stem = f"metadata/{mid}"
        self.write("private", stem + ".request.private.json", body)
        journal = {
            **item,
            "contract_sha256": self.config["_contract_sha256"],
            "epoch_index": epoch,
            "process_id": process.pid,
            "request_sha256": c.digest(body),
            "dispatch_at": self.helper.utc_now(),
        }
        self.write("safe", stem + ".dispatch.safe.json", journal)
        started = time.monotonic()
        raw = low.metadata_request(client, self.config, item["route"], body)
        self.write("private", stem + ".reply.private.json", raw, raw=True)
        c.require(process.poll() is None, "METADATA_OWNED_PROCESS_EXITED_AFTER_DISPATCH")
        row = {
            **journal,
            "raw_reply_sha256": c.sha_bytes(raw),
            "received_at": self.helper.utc_now(),
            "latency_seconds": time.monotonic() - started,
        }
        self.write("safe", stem + ".row.safe.json", row)
        return raw

    def parse_census(self, material, replies):
        rendered = c.strict_json(replies[0])
        c.require(
            isinstance(rendered, dict)
            and isinstance(rendered.get("prompt"), str)
            and rendered["prompt"],
            "TEMPLATE_RENDER_INVALID",
        )
        tokens = []
        for raw in replies[1:]:
            value = c.strict_json(raw)
            values = value.get("tokens") if isinstance(value, dict) else None
            c.require(
                isinstance(values, list)
                and values
                and all(type(value) is int and value >= 0 for value in values),
                "TOKENIZATION_REPLY_INVALID",
            )
            tokens.append(values)
        plain, native = map(len, tokens)
        limit = self.plan["metadata_field_contract"][material["kind"]]["native_prompt_tokens_max"]
        return {
            "materialization_id": material["materialization_id"],
            "kind": material["kind"],
            "prompt_sha256": material["renderer_row"]["prompt_sha256"],
            "input_tokens": plain,
            "native_prompt_tokens": native,
            "template_overhead_tokens": native - plain,
            "rendered_prompt_sha256": c.sha_bytes(rendered["prompt"].encode()),
            "native_token_ids_sha256": c.digest(tokens[1]),
            "context_budget_passed": plain <= 3456 and native <= limit and native - plain <= 128,
            "metadata_reply_sha256": [c.sha_bytes(raw) for raw in replies],
        }

    def census(self):
        prompts = self.load_materials()
        with self.operation("census"):
            existing = self.path("safe", "census.safe.json")
            if existing.exists():
                return self.load_census(prompts)
            self.write(
                "safe",
                "census-started.safe.json",
                {
                    "contract_sha256": self.config["_contract_sha256"],
                    "metadata_post_ceiling": self.plan["budgets"]["metadata_post_calls"],
                    "target_generations": 0,
                },
            )
            epoch, rows = self.epoch(), []
            metadata = self.plan["metadata_requests"]
            with self.server(epoch) as (process, client, _):
                props = client.get("/props")
                c.require(
                    c.same(props.get("default_generation_settings", {}).get("n_ctx"), 4096),
                    "SERVED_CONTEXT_NOT_4096",
                )
                for index, material in enumerate(self.materials.values()):
                    mid = material["materialization_id"]
                    self.identity(
                        process,
                        client,
                        epoch,
                        f"census/{mid}.tpl.safe.json",
                        {"materialization_id": mid},
                    )
                    item = next(
                        row for row in self.plan["requests"] if row["materialization_id"] == mid
                    )
                    request = request_for(self.config, item, prompts[mid])
                    tasks = metadata[3 * index : 3 * index + 3]
                    replies = [
                        self.metadata_post(
                            tasks[0], "apply_template", request, process, client, epoch
                        )
                    ]
                    rendered = c.strict_json(replies[0])
                    c.require(
                        isinstance(rendered, dict)
                        and isinstance(rendered.get("prompt"), str)
                        and rendered["prompt"],
                        "TEMPLATE_RENDER_INVALID",
                    )
                    for task, text in zip(
                        tasks[1:], (prompts[mid], rendered["prompt"]), strict=True
                    ):
                        body = {
                            "content": text,
                            "add_special": True,
                            "parse_special": True,
                            "with_pieces": False,
                        }
                        replies.append(
                            self.metadata_post(task, task["stage"], body, process, client, epoch)
                        )
                    row = {
                        **self.parse_census(material, replies),
                        "epoch_index": epoch,
                        "process_id": process.pid,
                        "served_chat_template_sha256": self.config["runtime"][
                            "served_chat_template_sha256"
                        ],
                    }
                    self.write("safe", f"census/{mid}.row.safe.json", row)
                    rows.append(row)
            result = {
                "contract_sha256": self.config["_contract_sha256"],
                "bound_plan_identity_sha256": self.plan["plan_identity_sha256"],
                "epoch_index": epoch,
                "rows": rows,
                "rows_sha256": c.digest(rows),
                "metadata_post_requests": len(metadata),
                "target_generations": 0,
                "all_inputs_within_context": all(row["context_budget_passed"] for row in rows),
            }
            self.write("safe", "census.safe.json", result)
            return self.load_census(prompts)

    def global_check(self, kind):
        c.require(kind in {"metadata", "target"}, "RECEIPT_NAMESPACE_INVALID")
        expected = (
            {row["metadata_request_id"] for row in self.plan["metadata_requests"]}
            if kind == "metadata"
            else set(self.items)
        )
        directory = self.path("safe", kind)
        files = list(directory.glob("*.dispatch.safe.json")) if directory.exists() else []
        observed = {path.name.removesuffix(".dispatch.safe.json") for path in files}
        c.require(
            observed <= expected and len(observed) <= len(expected),
            "GLOBAL_TOPOLOGY_CEILING_OR_FRAME_VIOLATION",
        )
        suffixes = [
            ("safe", ".row.safe.json"),
            ("private", ".reply.private.json"),
            ("private", ".request.private.json"),
        ]
        if kind == "target":
            suffixes += [("safe", ".tpl.safe.json"), ("safe", ".cooldown.safe.json")]
        for area, suffix in suffixes:
            directory = self.path(area, kind)
            paths = list(directory.glob("*" + suffix)) if directory.exists() else []
            ids = {path.name.removesuffix(suffix) for path in paths}
            c.require(ids <= observed, "ORPHAN_TOPOLOGY_ARTIFACT_REQUIRES_AUDIT")
        return observed

    def verify_times(self, epoch, journal, row):
        c.require(
            type(row.get("latency_seconds")) in (int, float)
            and math.isfinite(row["latency_seconds"])
            and row["latency_seconds"] >= 0,
            "RECEIPT_LATENCY_INVALID",
        )
        c.require(
            low.parse_utc(epoch["started_at"])
            <= low.parse_utc(journal.get("dispatch_at"))
            <= low.parse_utc(row.get("received_at"))
            <= low.parse_utc(epoch["stopped_at"]),
            "RECEIPT_TIMESTAMP_ORDER_INVALID",
        )
        c.require(
            low.parse_utc(journal["dispatch_at"])
            < low.parse_utc(self.config["execution_limits"]["deadline_utc"]),
            "RECEIPT_DISPATCH_NOT_BEFORE_AUTHORIZED_DEADLINE",
        )

    def load_census(self, prompts=None):
        prompts = prompts if prompts is not None else self.load_materials()
        result = self.read("safe", "census.safe.json")
        c.require(
            set(result)
            == {
                "contract_sha256",
                "bound_plan_identity_sha256",
                "epoch_index",
                "rows",
                "rows_sha256",
                "metadata_post_requests",
                "target_generations",
                "all_inputs_within_context",
            }
            and result["contract_sha256"] == self.config["_contract_sha256"]
            and result["bound_plan_identity_sha256"] == self.plan["plan_identity_sha256"]
            and c.same(result["metadata_post_requests"], len(self.plan["metadata_requests"]))
            and c.same(result["target_generations"], 0)
            and result["all_inputs_within_context"] is True
            and isinstance(result["rows"], list)
            and len(result["rows"]) == len(self.materials)
            and c.digest(result["rows"]) == result["rows_sha256"],
            "CENSUS_NOT_COMPLETE_OR_CONTEXT_FAILED",
        )
        c.require(
            len(self.global_check("metadata")) == len(self.plan["metadata_requests"]),
            "CENSUS_GLOBAL_RECEIPT_SET_INCOMPLETE",
        )
        epoch = low.verify_epoch(
            self.config, self.paths, result["epoch_index"], self.helper, self.root
        )
        verified = []
        previous_received = low.parse_utc(epoch["started_at"])
        for index, material in enumerate(self.materials.values()):
            mid = material["materialization_id"]
            tasks = self.plan["metadata_requests"][3 * index : 3 * index + 3]
            item = next(row for row in self.plan["requests"] if row["materialization_id"] == mid)
            replies = []
            for task in tasks:
                stem = f"metadata/{task['metadata_request_id']}"
                journal = self.read("safe", stem + ".dispatch.safe.json")
                row = self.read("safe", stem + ".row.safe.json")
                if task["stage"] == "apply_template":
                    body = request_for(self.config, item, prompts[mid])
                else:
                    text = (
                        prompts[mid]
                        if task["stage"] == "raw_tokens"
                        else c.strict_json(replies[0])["prompt"]
                    )
                    body = {
                        "content": text,
                        "add_special": True,
                        "parse_special": True,
                        "with_pieces": False,
                    }
                expected = {
                    **task,
                    "contract_sha256": self.config["_contract_sha256"],
                    "epoch_index": result["epoch_index"],
                    "process_id": epoch["pid"],
                    "request_sha256": c.digest(body),
                }
                c.require(
                    set(journal) == set(expected) | {"dispatch_at"}
                    and all(c.same(journal.get(key), value) for key, value in expected.items())
                    and c.same(self.read("private", stem + ".request.private.json"), body),
                    "CENSUS_REQUEST_JOURNAL_CHANGED",
                )
                raw_path = self.path("private", stem + ".reply.private.json")
                c.require(
                    raw_path.is_file() and raw_path.stat().st_size <= low.MAX_REPLY_BYTES,
                    "METADATA_RECEIPT_MISSING_OR_OVERSIZED",
                )
                raw = raw_path.read_bytes()
                expected = {**journal, "raw_reply_sha256": c.sha_bytes(raw)}
                c.require(
                    set(row) == set(expected) | {"received_at", "latency_seconds"}
                    and all(c.same(row.get(key), value) for key, value in expected.items()),
                    "CENSUS_RAW_REPLY_BINDING_CHANGED",
                )
                self.verify_times(epoch, journal, row)
                c.require(
                    previous_received <= low.parse_utc(journal["dispatch_at"]),
                    "METADATA_RECEIPTS_NOT_IN_FROZEN_PLAN_TIME_ORDER",
                )
                previous_received = low.parse_utc(row["received_at"])
                replies.append(raw)
            self.helper.verify_template_observation(
                self.config,
                self.config["_contract_sha256"],
                self.path("safe", f"census/{mid}.tpl.safe.json"),
                {
                    "materialization_id": mid,
                    "epoch_index": result["epoch_index"],
                    "process_id": epoch["pid"],
                },
            )
            row = {
                **self.parse_census(material, replies),
                "epoch_index": result["epoch_index"],
                "process_id": epoch["pid"],
                "served_chat_template_sha256": self.config["runtime"][
                    "served_chat_template_sha256"
                ],
            }
            c.require(
                row["context_budget_passed"] is True
                and c.same(row, result["rows"][index])
                and c.same(row, self.read("safe", f"census/{mid}.row.safe.json")),
                "CENSUS_ROW_NOT_RECONSTRUCTED",
            )
            verified.append(row)
        return result

    def cooldown(self, item, epoch):
        started, samples = time.monotonic(), []
        rid = item["request_id"]
        passed = False
        try:
            while True:
                low.check_deadline(self.config)
                sample = {**low.gpu_sample(), "disk_free_bytes": shutil.disk_usage(self.root).free}
                samples.append(sample)
                low.validate_resource_sample(sample, baseline=False)
                elapsed = time.monotonic() - started
                c.require(elapsed <= 180, "TARGET_COOLDOWN_TIMEOUT")
                if sample["gpu_temperature_c"] <= 60:
                    passed = True
                    break
                if len(samples) % 20 == 0:
                    self.helper.emit(
                        "TOPOLOGY_TARGET_COOLDOWN",
                        request_id=rid,
                        sampled_temperature_c=sample["gpu_temperature_c"],
                    )
                time.sleep(0.5)
        finally:
            receipt = {
                "contract_sha256": self.config["_contract_sha256"],
                "request_id": rid,
                "epoch_index": epoch,
                "policy": COOLDOWN,
                "samples": samples,
                "cooldown_passed": passed,
                "wait_seconds": elapsed if passed else time.monotonic() - started,
                "measurement": "PREDISPATCH_SNAPSHOTS_NOT_CONTINUOUS_PEAK",
            }
            self.write("safe", f"target/{rid}.cooldown.safe.json", receipt)
        return receipt

    def verify_cooldown(self, item, epoch, journal, previous_received):
        receipt = self.read("safe", f"target/{item['request_id']}.cooldown.safe.json")
        c.require(
            set(receipt)
            == {
                "contract_sha256",
                "request_id",
                "epoch_index",
                "policy",
                "samples",
                "cooldown_passed",
                "wait_seconds",
                "measurement",
            }
            and receipt["contract_sha256"] == self.config["_contract_sha256"]
            and receipt["request_id"] == item["request_id"]
            and c.same(receipt["epoch_index"], journal["epoch_index"])
            and c.same(receipt["policy"], COOLDOWN)
            and receipt["cooldown_passed"] is True
            and receipt["measurement"] == "PREDISPATCH_SNAPSHOTS_NOT_CONTINUOUS_PEAK"
            and isinstance(receipt["samples"], list)
            and receipt["samples"]
            and c.digest(receipt) == journal.get("cooldown_receipt_sha256"),
            "COOLDOWN_RECEIPT_BINDING_INVALID",
        )
        c.require(
            type(receipt["wait_seconds"]) in (int, float)
            and math.isfinite(receipt["wait_seconds"])
            and 0 <= receipt["wait_seconds"] <= 180,
            "COOLDOWN_WAIT_EVIDENCE_INVALID",
        )
        prior = low.parse_utc(epoch["started_at"])
        c.require(
            previous_received <= low.parse_utc(receipt["samples"][0]["sampled_at"]),
            "COOLDOWN_SAMPLE_NOT_FRESH_AFTER_PREVIOUS_REQUEST",
        )
        for index, sample in enumerate(receipt["samples"]):
            low.validate_resource_sample(sample, baseline=False)
            stamp = low.parse_utc(sample["sampled_at"])
            c.require(
                prior <= stamp <= low.parse_utc(journal["dispatch_at"]),
                "COOLDOWN_SAMPLE_TIMESTAMP_INVALID",
            )
            prior = stamp
            c.require(
                index == len(receipt["samples"]) - 1 or sample["gpu_temperature_c"] > 60,
                "COOLDOWN_CONTINUED_AFTER_ACCEPTED_SAMPLE",
            )
        c.require(
            receipt["samples"][-1]["gpu_temperature_c"] <= 60,
            "COOLDOWN_REQUIRED_BEFORE_EVERY_DISPATCH",
        )
        return receipt

    def dispatch(self, item, prompt, census_row, process, client, epoch):
        rid = item["request_id"]
        cooldown = self.cooldown(item, epoch)
        properties = self.identity(
            process, client, epoch, f"target/{rid}.tpl.safe.json", {"request_id": rid}
        )
        low.check_deadline(self.config)
        request = request_for(self.config, item, prompt)
        self.write("private", f"target/{rid}.request.private.json", request)
        journal = {
            **item,
            "contract_sha256": self.config["_contract_sha256"],
            "request_sha256": c.digest(request),
            "epoch_index": epoch,
            "process_id": process.pid,
            "dispatch_at": self.helper.utc_now(),
            "cooldown_receipt_sha256": c.digest(cooldown),
            "census_row_sha256": c.digest(census_row),
            "served_chat_template_sha256": properties["served_chat_template_sha256"],
        }
        self.write("safe", f"target/{rid}.dispatch.safe.json", journal)
        started = time.monotonic()
        raw = client.request(
            "/v1/chat/completions",
            request,
            timeout=self.config["server"]["request_timeout_seconds"],
        )
        self.write("private", f"target/{rid}.reply.private.json", raw, raw=True)
        c.require(process.poll() is None, "OWNED_SERVER_EXITED_AFTER_DISPATCH")
        parsed = parse_reply(self.config, item, raw, census_row["native_prompt_tokens"])
        row = {
            **journal,
            **parsed,
            "latency_seconds": time.monotonic() - started,
            "received_at": self.helper.utc_now(),
        }
        self.write("safe", f"target/{rid}.row.safe.json", row)
        self.helper.emit(
            "TOPOLOGY_TARGET_RECORDED",
            ordinal=item["ordinal"],
            kind=item["kind"],
            finish_reason=row["finish_reason"],
            eligible_for_panel=row["eligible_for_panel"],
            eligible_for_control=row["eligible_for_control"],
        )
        return row

    def reconcile(self, prompts, census):
        self.assert_unchanged()
        observed = self.global_check("target")
        census_map = {row["materialization_id"]: row for row in census["rows"]}
        complete, missing, epochs = [], False, {}
        census_epoch = low.verify_epoch(
            self.config, self.paths, census["epoch_index"], self.helper, self.root
        )
        previous_received = low.parse_utc(census_epoch["stopped_at"])
        previous_epoch_stopped = previous_received
        previous_epoch = census["epoch_index"]
        for item in self.plan["requests"]:
            rid = item["request_id"]
            if rid not in observed:
                missing = True
                continue
            c.require(not missing, "TARGET_DISPATCHES_NOT_COMPLETE_PLAN_PREFIX")
            stem = f"target/{rid}"
            c.require(
                self.path("safe", stem + ".row.safe.json").is_file()
                and self.path("private", stem + ".reply.private.json").is_file(),
                "AMBIGUOUS_OR_UNFINALIZED_DISPATCH_NO_RETRY",
            )
            journal, row = (
                self.read("safe", stem + suffix)
                for suffix in (".dispatch.safe.json", ".row.safe.json")
            )
            epoch_index = journal.get("epoch_index")
            c.require(type(epoch_index) is int and epoch_index > 0, "TARGET_EPOCH_INDEX_INVALID")
            if epoch_index not in epochs:
                epochs[epoch_index] = low.verify_epoch(
                    self.config, self.paths, epoch_index, self.helper, self.root
                )
            epoch = epochs[epoch_index]
            c.require(
                epoch_index >= previous_epoch
                and epoch_index > census["epoch_index"]
                and previous_received <= low.parse_utc(journal["dispatch_at"]),
                "TARGET_RECEIPTS_NOT_IN_FROZEN_PLAN_TIME_ORDER",
            )
            if epoch_index != previous_epoch:
                c.require(
                    previous_epoch_stopped <= low.parse_utc(epoch["started_at"]),
                    "TARGET_OWNED_EPOCHS_OVERLAP_OR_OUT_OF_ORDER",
                )
            mid = item["materialization_id"]
            request = request_for(self.config, item, prompts[mid])
            expected = {
                **item,
                "contract_sha256": self.config["_contract_sha256"],
                "request_sha256": c.digest(request),
                "epoch_index": epoch_index,
                "process_id": epoch["pid"],
                "census_row_sha256": c.digest(census_map[mid]),
                "served_chat_template_sha256": self.config["runtime"][
                    "served_chat_template_sha256"
                ],
            }
            c.require(
                set(journal) == set(expected) | {"dispatch_at", "cooldown_receipt_sha256"}
                and all(c.same(journal.get(key), value) for key, value in expected.items())
                and c.same(self.read("private", stem + ".request.private.json"), request),
                "TARGET_JOURNAL_REQUEST_CENSUS_BINDING_CHANGED",
            )
            self.verify_cooldown(item, epoch, journal, previous_received)
            self.helper.verify_template_observation(
                self.config,
                self.config["_contract_sha256"],
                self.path("safe", stem + ".tpl.safe.json"),
                {"request_id": rid, "epoch_index": epoch_index, "process_id": epoch["pid"]},
            )
            raw_path = self.path("private", stem + ".reply.private.json")
            c.require(raw_path.stat().st_size <= low.MAX_REPLY_BYTES, "TARGET_REPLY_OVERSIZED")
            parsed = parse_reply(
                self.config, item, raw_path.read_bytes(), census_map[mid]["native_prompt_tokens"]
            )
            expected = {**journal, **parsed}
            c.require(
                set(row) == set(expected) | {"latency_seconds", "received_at"}
                and all(c.same(row.get(key), value) for key, value in expected.items()),
                "TARGET_ROW_NOT_RECONSTRUCTED_FROM_RAW_RECEIPT",
            )
            self.verify_times(epoch, journal, row)
            previous_received = low.parse_utc(row["received_at"])
            previous_epoch = epoch_index
            previous_epoch_stopped = low.parse_utc(epoch["stopped_at"])
            complete.append(row)
        c.require(len(complete) == len(observed), "UNRECONCILED_GLOBAL_TARGET_DISPATCH")
        return complete

    def summary(self, rows):
        prior_failures = [
            name
            for name in ("stage", "census", "generate")
            if self.path("safe", f"{name}-aborted.safe.json").exists()
        ]
        return {
            "contract_sha256": self.config["_contract_sha256"],
            "bound_plan_identity_sha256": self.plan["plan_identity_sha256"],
            "target_records": len(rows),
            "planned_target_records": len(self.items),
            "complete": len(rows) == len(self.items),
            "science_records": sum(row["kind"] == "science" for row in rows),
            "control_records": sum(row["kind"] == "control" for row in rows),
            "science_eligible_for_panel": sum(row["eligible_for_panel"] for row in rows),
            "controls_eligible_for_measurement": sum(row["eligible_for_control"] for row in rows),
            "target_rows_sha256": c.digest(rows),
            "scientific_gate_evaluated": False,
            "paper_validity": False,
            "historical_private_reads": 0,
            "prior_operation_failures": prior_failures,
            "operational_gate_passed": len(rows) == len(self.items) and not prior_failures,
        }

    def status(self):
        self.assert_unchanged()
        prompts = self.load_materials()
        census = self.load_census(prompts)
        return self.summary(self.reconcile(prompts, census))

    def generate(self):
        prompts = self.load_materials()
        census = self.load_census(prompts)
        with self.operation("generate"):
            complete = self.reconcile(prompts, census)
            pending = self.plan["requests"][len(complete) :]
            c.require(
                len(complete) + len(pending) == self.plan["budgets"]["total_target_calls"],
                "TOPOLOGY_GLOBAL_TARGET_CEILING_CHANGED",
            )
            if pending:
                epoch = self.epoch()
                census_map = {row["materialization_id"]: row for row in census["rows"]}
                with self.server(epoch) as (process, client, _):
                    for item in pending:
                        mid = item["materialization_id"]
                        complete.append(
                            self.dispatch(
                                item, prompts[mid], census_map[mid], process, client, epoch
                            )
                        )
            result = self.summary(self.reconcile(prompts, census))
            path = self.path("safe", "targets.safe.json")
            if path.exists():
                c.require(c.same(read_json(path), result), "TARGET_FINAL_RECEIPT_CHANGED")
            else:
                c.write_once(path, result)
            return result
