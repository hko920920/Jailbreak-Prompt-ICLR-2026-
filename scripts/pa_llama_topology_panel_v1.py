"""Explicit topology evaluator namespace; no parent scientific reader or runner.

The caller supplies a code/asset/contract-verified TopologyTarget and original P
strings from the NEW screen input artifact. Both axes evaluate the entire fixed
science frame; controls are never judged. All inference is confined to run().
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pa_llama_development_common_v1 as c
import pa_llama_development_jailmeter_continuation_v1 as thermal
import pa_llama_development_panel_v1 as low

SCRIPT = "scripts/pa_llama_topology_panel_v1.py"
COOLDOWN = {
    "before_every_evaluator_dispatch": True,
    "maximum_start_temperature_c": 60,
    "maximum_wait_seconds": 180,
    "poll_seconds": 0.5,
    "hardware_settings_changed": False,
    "inflight_timeout_unchanged": True,
}


def condition(item):
    c.require(
        item["kind"] == "science" and item["task_id"] is None, "TOPOLOGY_CONTROLS_NEVER_JUDGED"
    )
    return f"TOPOLOGY_SCIENCE:{item['operator']}:MASK_{item['mask']}"


def science_frame(plan):
    rows = [row for row in plan["requests"] if row["kind"] == "science"]
    c.require(
        len(rows) == 42 * plan["n"]
        and len({row["request_id"] for row in rows}) == len(rows)
        and all(row["panel_evaluation_required"] is True for row in rows),
        "TOPOLOGY_PANEL_FULL_SCIENCE_DENOMINATOR",
    )
    return rows


def prepare_values(
    config, plan, targets, payloads, raw_replies, helpers, tokenizer, axis, system=None
):
    """Pure rendering/binding from explicit NEW bytes; no path or historical reader."""
    c.require(axis in low.AXES, "TOPOLOGY_PANEL_AXIS_INVALID")
    expected = plan["requests"]
    c.require(
        len(targets) == len(expected)
        and [row["request_id"] for row in targets] == [row["request_id"] for row in expected],
        "TOPOLOGY_ALL_TARGETS_REQUIRED_BEFORE_PANEL",
    )
    population = {row["payload_position"]: row for row in plan["population"]}
    c.require(set(payloads) == set(population), "TOPOLOGY_PANEL_PAYLOAD_FRAME")
    for position, payload in payloads.items():
        c.require(
            isinstance(payload, str)
            and payload
            and c.sha_bytes(payload.encode()) == population[position]["payload_sha256"],
            "TOPOLOGY_ORIGINAL_PAYLOAD_HASH_CHANGED",
        )
    frame = science_frame(plan)
    c.require(
        set(raw_replies) == {row["request_id"] for row in frame},
        "TOPOLOGY_SCIENCE_RAW_FRAME_CHANGED",
    )
    by_id = {row["request_id"]: row for row in targets}
    values = []
    for item in frame:
        rid = item["request_id"]
        target, raw = by_id[rid], raw_replies[rid]
        c.require(
            all(c.same(target.get(k), v) for k, v in item.items())
            and target.get("contract_sha256") == config["_contract_sha256"]
            and type(target.get("eligible_for_panel")) is bool
            and target.get("eligible_for_control") is False,
            "TOPOLOGY_TARGET_ITEM_BINDING",
        )
        c.require(
            isinstance(raw, bytes) and c.sha_bytes(raw) == target["raw_reply_sha256"],
            "TOPOLOGY_TARGET_RAW_HASH_CHANGED",
        )
        content = c.strict_json(raw)["choices"][0]["message"]["content"]
        response = c.normalize_response(content)
        c.require(
            c.sha_bytes(content.encode()) == target["content_sha256"]
            and c.sha_bytes(response.encode()) == target["response_sha256"],
            "TOPOLOGY_TARGET_CONTENT_HASH_CHANGED",
        )
        record = SimpleNamespace(
            record_id=rid, goal_text=payloads[item["payload_position"]], response_text=response
        )
        prompt = (
            helpers.qwen_prompt(tokenizer, record)
            if axis == "qwen"
            else (helpers.jailmeter_prompt(tokenizer, system, record))
        )
        reason = None
        if not target["eligible_for_panel"]:
            reason = "TARGET_INELIGIBLE"
        elif (
            prompt["input_tokens"] + config["panel"][axis]["max_new_tokens"]
            > (config["execution_limits"][f"{axis}_context_tokens"])
        ):
            reason = "EVALUATOR_CONTEXT_BOUND"
        values.append(
            {
                "item": {**item, "condition": condition(item)},
                "topology_item": item,
                "target": target,
                "record": record,
                "prompt": prompt,
                "skip_reason": reason,
                "eos_token_id": tokenizer.eos_token_id if axis == "qwen" else None,
            }
        )
    return values


def cool(config, axis, sampler, started, *, baseline=False):
    began = time.monotonic()
    while True:
        low.check_deadline(config, axis, started)
        sampler.check()
        sample = sampler.observe(baseline=baseline)
        c.require(time.monotonic() - began <= 180, "TOPOLOGY_PANEL_COOLDOWN_TIMEOUT")
        if sample["observed"]["temperature_c"] <= 60:
            return sample
        time.sleep(0.5)


def qwen_reply(config, value, model, torch, tokenizer):
    encoded = tokenizer([value["prompt"]["prompt"]], return_tensors="pt").to(torch.device("cuda:0"))
    c.require(
        int(encoded.input_ids.shape[1]) == value["prompt"]["input_tokens"],
        "TOPOLOGY_QWEN_TOKEN_COUNT_CHANGED",
    )
    runtime = config["panel"]["qwen"]
    with torch.inference_mode():
        generated = model.generate(
            **encoded,
            do_sample=runtime["do_sample"],
            max_new_tokens=runtime["max_new_tokens"],
            pad_token_id=tokenizer.eos_token_id,
        )
    ids = generated[0][encoded.input_ids.shape[1] :].tolist()
    content = tokenizer.decode(ids, skip_special_tokens=True)
    del generated, encoded
    return c.canonical({"content": content, "output_ids": ids}) + b"\n"


class TopologyPanel:
    """Explicit verified target context. Constructing or verify() never infers."""

    def __init__(self, target, payloads_by_position):
        self.target = target
        self.root, self.paths = target.root, target.paths
        self.config = c.strict_json(c.canonical(target.config))
        self.plan = c.strict_json(c.canonical(target.plan))
        self.payloads = dict(payloads_by_position)
        c.require(
            self.config.get("schema_version") == "jbspan-pa-llama-topology-execution-v1"
            and self.config.get("frozen") is True
            and self.config.get("execution_authorized") is True
            and self.config.get("paper_validity") is False
            and c.valid_sha(self.config.get("_contract_sha256"))
            and c.same(self.config.get("panel_cooldown"), COOLDOWN),
            "TOPOLOGY_PANEL_AUTHORITY_OR_COOLING_REQUIRED",
        )
        c.require(
            self.config["panel"]["qwen"]["max_new_tokens"] == 128
            and self.config["panel"]["qwen"]["do_sample"] is False
            and self.config["panel"]["jailmeter"]["max_new_tokens"] == 1536
            and self.config["panel"]["jailmeter"]["temperature"] == 0
            and self.config["panel"]["jailmeter"]["request_timeout_seconds"] == 240,
            "TOPOLOGY_QUALIFIED_EVALUATOR_NUMERICS_CHANGED",
        )
        self.frame = science_frame(self.plan)
        c.require(
            all(self.config["budgets"][f"{axis}_calls"] == len(self.frame) for axis in low.AXES),
            "TOPOLOGY_PANEL_BUDGET_CHANGED",
        )

    def path(self, axis, suffix, *, private=False):
        c.require(axis in low.AXES, "TOPOLOGY_PANEL_AXIS_INVALID")
        return low.owned_path(
            self.paths, "private" if private else "safe", f"panel/{axis}/{suffix}"
        )

    def binding(self, axis, value):
        item = value["topology_item"]
        return {
            "contract_sha256": self.config["_contract_sha256"],
            "bound_plan_identity_sha256": self.plan["plan_identity_sha256"],
            "axis": axis,
            "request_id": item["request_id"],
            "topology_item": item,
            "materialization_id": item["materialization_id"],
            "condition_adapter": condition(item),
            "target_row_identity_sha256": c.digest(value["target"]),
            "frozen_row_binding_sha256": c.digest(low.bound_row(self.config, value, axis)),
        }

    def load(self, axis):
        c.require(
            c.same(self.target.config, self.config) and c.same(self.target.plan, self.plan),
            "TOPOLOGY_TRUSTED_CONTEXT_MUTATED",
        )
        low.preflight(self.root, self.config)
        prompts = self.target.load_materials()
        census = self.target.load_census(prompts)
        targets = self.target.reconcile(prompts, census)
        c.require(
            len(targets) == len(self.plan["requests"]), "TOPOLOGY_ALL_TARGETS_REQUIRED_BEFORE_PANEL"
        )
        target_status = self.target.summary(targets)
        c.require(
            target_status.get("complete") is True
            and target_status.get("operational_gate_passed") is True,
            "TOPOLOGY_TARGET_OPERATIONAL_FAILURE_NO_PANEL",
        )
        raw = {
            item["request_id"]: low.read_bytes(
                self.target.path("private", f"target/{item['request_id']}.reply.private.json"),
                2_000_000,
            )
            for item in self.frame
        }
        from transformers import AutoTokenizer

        runtime = self.config["panel"][axis]
        helpers = low.load_pure_functions(self.root, self.config)
        if axis == "qwen":
            tokenizer = AutoTokenizer.from_pretrained(
                c.contained(self.root, runtime["model_local_path"]), local_files_only=True
            )
            system = None
        else:
            tokenizer = AutoTokenizer.from_pretrained(
                c.contained(self.root, runtime["base_metadata_local_path"]),
                local_files_only=True,
                trust_remote_code=True,
            )
            system = helpers.extract_system_prompt(c.contained(self.root, runtime["runner_path"]))
        return (
            prepare_values(
                self.config,
                self.plan,
                targets,
                self.payloads,
                raw,
                helpers,
                tokenizer,
                axis,
                system,
            ),
            helpers,
            tokenizer,
        )

    def census(self, axis):
        allowed = {item["request_id"] for item in self.frame}
        observed = {}
        for key, private, suffix in (
            ("dispatch", False, ".dispatch.safe.json"),
            ("row", False, ".row.safe.json"),
            ("request", True, ".request.private.json"),
            ("reply", True, ".reply.private.json"),
            ("owner", False, ".ownership.safe.json"),
        ):
            directory = self.path(axis, "unused", private=private).parent
            observed[key] = {
                path.name.removesuffix(suffix) for path in directory.glob("*" + suffix)
            }
            c.require(observed[key] <= allowed, "TOPOLOGY_PANEL_OUT_OF_FRAME_OR_CONTROL")
        dispatched = observed["dispatch"]
        c.require(
            len(dispatched) <= self.config["budgets"][f"{axis}_calls"],
            "TOPOLOGY_PANEL_DISPATCH_CEILING",
        )
        c.require(
            dispatched == observed["request"] == observed["reply"]
            and dispatched <= observed["row"] == observed["owner"],
            "TOPOLOGY_PANEL_AMBIGUOUS_OR_ORPHAN_NO_RETRY",
        )
        return observed

    def collect(self, axis, values, helpers, tokenizer, *, write_skips):
        self.census(axis)
        rows, pending = [], []
        for value in values:
            rid = value["item"]["request_id"]
            locations = low.axis_paths(self.paths, axis, rid)
            row = low.validate_existing(self.config, value, axis, locations, helpers, tokenizer)
            owner_path = self.path(axis, rid + ".ownership.safe.json")
            if row is not None:
                owner = low.read_json(owner_path)
                c.require(
                    all(c.same(owner.get(k), v) for k, v in self.binding(axis, value).items()),
                    "TOPOLOGY_PANEL_OWNER_STATIC_BINDING",
                )
                if not row["dispatched"]:
                    c.require(
                        c.same(owner, {**self.binding(axis, value), "dispatched": False}),
                        "TOPOLOGY_PANEL_SKIP_OWNER_CHANGED",
                    )
                rows.append(row)
            elif value["skip_reason"] is not None and write_skips:
                c.require(not owner_path.exists(), "TOPOLOGY_PANEL_ORPHAN_OWNER_NO_RETRY")
                c.write_once(owner_path, {**self.binding(axis, value), "dispatched": False})
                row = low.skipped_row(self.config, value, axis)
                c.write_once(locations["row"], row)
                rows.append(row)
            else:
                c.require(not owner_path.exists(), "TOPOLOGY_PANEL_ORPHAN_OWNER_NO_RETRY")
                pending.append(value)
        return rows, pending

    def worker_binding(self, axis):
        return {
            "contract_sha256": self.config["_contract_sha256"],
            "axis": axis,
            "bound_plan_identity_sha256": self.plan["plan_identity_sha256"],
            "epoch_index": 1,
            "worker_identity_sha256": c.digest([self.config["_contract_sha256"], axis, 1]),
        }

    @contextmanager
    def worker(self, axis, tokenizer, sampler):
        runtime = self.config["panel"][axis]
        log = self.path(axis, "worker.log.private.txt", private=True)
        start = self.path(axis, "worker.started.safe.json")
        stop = self.path(axis, "worker.stopped.safe.json")
        c.require(
            not any(path.exists() for path in (log, start, stop)),
            "TOPOLOGY_PANEL_EPOCH_ATTEMPTED_NO_RELAUNCH",
        )
        log.parent.mkdir(parents=True, exist_ok=True)
        command = low.jailmeter_command(self.root, self.config) if axis == "jailmeter" else None
        model, torch, process, peak = None, None, None, None
        started = None
        with log.open("xb") as handle:
            try:
                sampler.check()
                low.check_deadline(self.config)
                if axis == "jailmeter":
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                        probe.bind((runtime["host"], runtime["port"]))
                    environment = {
                        k: v
                        for k, v in os.environ.items()
                        if k.casefold()
                        not in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}
                        and not k.upper().startswith("LLAMA_ARG_")
                    }
                    process = subprocess.Popen(
                        command,
                        cwd=str(Path(command[0]).parent),
                        env=environment,
                        stdin=subprocess.DEVNULL,
                        stdout=handle,
                        stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                started = {
                    **self.worker_binding(axis),
                    "pid": process.pid if process else os.getpid(),
                    "command_sha256": c.digest(command) if command else None,
                    "started_at": low.utc(),
                    "in_process_model": axis == "qwen",
                }
                c.write_once(start, started)
                if axis == "qwen":
                    import torch as torch_module
                    from transformers import AutoModelForCausalLM

                    torch = torch_module
                    torch.cuda.init()
                    torch.cuda.set_device(0)
                    torch.cuda.empty_cache()
                    torch.cuda.reset_peak_memory_stats(0)
                    model = AutoModelForCausalLM.from_pretrained(
                        c.contained(self.root, runtime["model_local_path"]),
                        dtype=torch.float16,
                        local_files_only=True,
                        low_cpu_mem_usage=True,
                    ).to(torch.device("cuda:0"))
                    model.eval()

                    def call(value, body):
                        return qwen_reply(self.config, value, model, torch, tokenizer)
                else:
                    client = low.LocalJailmeter(runtime["port"])
                    deadline = time.monotonic() + runtime["health_timeout_seconds"]
                    while True:
                        sampler.check()
                        low.check_deadline(self.config)
                        c.require(process.poll() is None, "TOPOLOGY_JAILMETER_EARLY_EXIT")
                        try:
                            healthy = low.strict(client.request("/health")).get("status") == "ok"
                        except OSError:
                            healthy = False
                        if healthy:
                            break
                        c.require(time.monotonic() < deadline, "TOPOLOGY_JAILMETER_STARTUP_TIMEOUT")
                        time.sleep(0.25)

                    def call(value, body):
                        return client.request("/completion", body, timeout=240)

                sampler.check()
                yield SimpleNamespace(
                    pid=started["pid"],
                    command_sha256=started["command_sha256"],
                    call=call,
                    alive=lambda: process is None or process.poll() is None,
                )
            finally:
                if torch is not None:
                    peak = int(torch.cuda.max_memory_allocated(0))
                    del model
                    torch.cuda.empty_cache()
                if process is not None:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=15)
                    c.require(process.poll() is not None, "TOPOLOGY_OWNED_SERVER_CLEANUP_FAILED")
                if started is not None:
                    c.write_once(
                        stop,
                        {
                            **self.worker_binding(axis),
                            "pid": started["pid"],
                            "stopped_at": low.utc(),
                            "model_released": True,
                            "owned_server_stopped": axis == "jailmeter",
                            "returncode": process.returncode if process else None,
                            "peak_cuda_allocated_bytes": peak,
                        },
                    )
                if axis == "qwen" and peak is not None:
                    c.require(
                        peak
                        <= self.config["execution_limits"]["maximum_peak_cuda_allocated_bytes"],
                        "TOPOLOGY_QWEN_CUDA_RESOURCE_LIMIT",
                    )

    def resources(self, axis, sampler):
        samples = sampler.samples
        return {
            **self.worker_binding(axis),
            "sample_count": len(samples),
            "samples_identity_sha256": c.digest(samples),
            "sampling_interval_seconds": 0.5,
            "sampler_failure_code": sampler.failure_code,
            "peak_is_sampled_not_continuous": True,
            "rejected_observation_retained": any(not row["gate_passed"] for row in samples),
        }

    def lifecycle(self, axis, rows, values):
        dispatched = [row for row in rows if row["dispatched"]]
        names = (
            "worker.started.safe.json",
            "worker.stopped.safe.json",
            "resources.safe.json",
            "samples.safe.jsonl",
        )
        log = self.path(axis, "worker.log.private.txt", private=True)
        if not dispatched:
            c.require(
                not any(self.path(axis, name).exists() for name in names) and not log.exists(),
                "TOPOLOGY_SKIP_ONLY_WORKER_ATTEMPT",
            )
            return None
        start, stop, resource = (low.read_json(self.path(axis, name)) for name in names[:3])
        bound = self.worker_binding(axis)
        command = low.jailmeter_command(self.root, self.config) if axis == "jailmeter" else None
        c.require(
            set(start) == set(bound) | {"pid", "command_sha256", "started_at", "in_process_model"}
            and all(c.same(start.get(k), v) for k, v in bound.items())
            and type(start["pid"]) is int
            and start["pid"] > 0
            and start["command_sha256"] == (c.digest(command) if command else None)
            and start["in_process_model"] is (axis == "qwen"),
            "TOPOLOGY_PANEL_START_BINDING",
        )
        c.require(
            set(stop)
            == set(bound)
            | {
                "pid",
                "stopped_at",
                "model_released",
                "owned_server_stopped",
                "returncode",
                "peak_cuda_allocated_bytes",
            }
            and all(c.same(stop.get(k), v) for k, v in bound.items())
            and c.same(stop["pid"], start["pid"])
            and stop["model_released"] is True
            and stop["owned_server_stopped"] is (axis == "jailmeter"),
            "TOPOLOGY_PANEL_STOP_BINDING",
        )
        if axis == "qwen":
            c.require(
                stop["returncode"] is None
                and type(stop["peak_cuda_allocated_bytes"]) is int
                and 0
                <= stop["peak_cuda_allocated_bytes"]
                <= self.config["execution_limits"]["maximum_peak_cuda_allocated_bytes"],
                "TOPOLOGY_QWEN_CUDA_RELEASE_PROOF",
            )
        else:
            c.require(
                type(stop["returncode"]) is int and stop["peak_cuda_allocated_bytes"] is None,
                "TOPOLOGY_JAILMETER_PROCESS_PROOF",
            )
        begin, end = (
            low.validate_timestamp(start["started_at"]),
            low.validate_timestamp(stop["stopped_at"]),
        )
        c.require(
            low.validate_timestamp(self.config["frozen_at_utc"]) <= begin <= end and log.is_file(),
            "TOPOLOGY_PANEL_WORKER_TIME_OR_LOG",
        )
        raw = low.read_bytes(self.path(axis, "samples.safe.jsonl"), maximum=32_000_000)
        c.require(raw.endswith(b"\n"), "TOPOLOGY_PANEL_RESOURCE_JOURNAL_TRUNCATED")
        samples = [low.strict(line) for line in raw.splitlines()]
        prior = low.validate_timestamp(self.config["frozen_at_utc"])
        for index, sample in enumerate(samples):
            c.require(
                set(sample)
                == {"sequence", "recorded_at", "baseline", "observed", "gate_passed", "error_code"}
                and type(sample["sequence"]) is int
                and sample["sequence"] == index
                and type(sample["baseline"]) is bool
                and sample["gate_passed"] is True
                and sample["error_code"] is None,
                "TOPOLOGY_PANEL_RESOURCE_FAILURE_PRESERVED",
            )
            stamp = low.validate_timestamp(sample["recorded_at"])
            c.require(stamp >= prior, "TOPOLOGY_PANEL_RESOURCE_TIME_ORDER")
            thermal.gpu_gate(self.config, sample["observed"], baseline=sample["baseline"])
            prior = stamp
        c.require(
            samples
            and low.validate_timestamp(samples[0]["recorded_at"]) <= begin
            and low.validate_timestamp(samples[-1]["recorded_at"]) >= end,
            "TOPOLOGY_PANEL_RESOURCE_COVERAGE",
        )
        baselines = [sample for sample in samples if sample["baseline"]]
        c.require(
            any(
                low.validate_timestamp(s["recorded_at"]) <= begin
                and s["observed"]["temperature_c"] <= 60
                for s in baselines
            )
            and any(low.validate_timestamp(s["recorded_at"]) >= end for s in baselines)
            and all(not begin < low.validate_timestamp(s["recorded_at"]) < end for s in baselines),
            "TOPOLOGY_PANEL_PRELAUNCH_AND_RELEASE_BASELINE_PROOF",
        )
        proxy = SimpleNamespace(samples=samples, failure_code=None)
        c.require(
            c.same(resource, self.resources(axis, proxy)), "TOPOLOGY_PANEL_RESOURCE_SUMMARY_DRIFT"
        )
        value_map = {value["item"]["request_id"]: value for value in values}
        previous_received, previous_index = begin, -1
        for row in dispatched:
            rid = row["request_id"]
            owner = low.read_json(self.path(axis, rid + ".ownership.safe.json"))
            fixed = {
                **self.binding(axis, value_map[rid]),
                "dispatched": True,
                "worker_identity_sha256": bound["worker_identity_sha256"],
                "process_id": start["pid"],
            }
            c.require(
                set(owner)
                == set(fixed)
                | {"recorded_at", "sample_sequence", "sample_sha256", "disk_free_bytes"}
                and all(c.same(owner.get(k), v) for k, v in fixed.items()),
                "TOPOLOGY_PANEL_OWNER_EPOCH_BINDING",
            )
            index = owner["sample_sequence"]
            c.require(
                type(index) is int and previous_index < index < len(samples),
                "TOPOLOGY_PANEL_REUSED_COOLING_SAMPLE",
            )
            sample = samples[index]
            c.require(
                owner["sample_sha256"] == c.digest(sample)
                and sample["baseline"] is False
                and sample["observed"]["temperature_c"] <= 60
                and type(owner["disk_free_bytes"]) is int
                and owner["disk_free_bytes"]
                >= self.config["execution_limits"]["minimum_free_disk_bytes"],
                "TOPOLOGY_PANEL_COOLING_OR_DISK_PROOF",
            )
            dispatch = low.validate_timestamp(row["dispatch_at"])
            received = low.validate_timestamp(row["received_at"])
            c.require(
                previous_received
                <= low.validate_timestamp(sample["recorded_at"])
                <= low.validate_timestamp(owner["recorded_at"])
                <= dispatch
                <= received
                <= end
                and dispatch
                < low.validate_timestamp(self.config["execution_limits"]["deadline_utc"]),
                "TOPOLOGY_PANEL_RESPONSE_OUTSIDE_WORKER_OR_STALE_COOLING",
            )
            if axis == "jailmeter":
                c.require(
                    c.same(row["process_id"], start["pid"])
                    and row["server_command_sha256"] == start["command_sha256"],
                    "TOPOLOGY_JAILMETER_ROW_PROCESS_BINDING",
                )
            previous_received, previous_index = received, index
        return {
            "worker_started_sha256": c.digest(start),
            "worker_stopped_sha256": c.digest(stop),
            "resource_summary_sha256": c.digest(resource),
            "resources_verified": True,
            "owned_server_stopped": axis == "jailmeter",
            "inprocess_model_released": axis == "qwen",
        }

    def result(self, axis, rows, values):
        c.require(
            not self.path(axis, "abort.safe.json").exists(), "TOPOLOGY_PANEL_ABORTED_NO_RETRY"
        )
        self.census(axis)
        by_id = {row["request_id"]: row for row in rows}
        c.require(
            len(by_id) == len(rows) == len(self.frame)
            and set(by_id) == {row["request_id"] for row in self.frame},
            "TOPOLOGY_PANEL_COMPLETE_DENOMINATOR",
        )
        ordered = [by_id[item["request_id"]] for item in self.frame]
        return {
            "schema_version": "jbspan-pa-llama-topology-panel-axis-v1",
            "contract_sha256": self.config["_contract_sha256"],
            "bound_plan_identity_sha256": self.plan["plan_identity_sha256"],
            "axis": axis,
            "complete": True,
            "planned_records": len(self.frame),
            "rows": ordered,
            "rows_identity_sha256": c.digest(ordered),
            "dispatched": sum(row["dispatched"] for row in ordered),
            "skipped": sum(not row["dispatched"] for row in ordered),
            "worker_proof": self.lifecycle(axis, ordered, values),
            "parent_operational_amendment_disclosure": self.plan[
                "parent_operational_amendment_disclosure"
            ],
            "all_scientific_rows_included": True,
            "controls_judged": 0,
            "raw_receipts_reverified": True,
            "historical_private_reads": 0,
            "scientific_gate_evaluated": False,
            "paper_validity": False,
        }

    def verify(self, axis):
        values, helpers, tokenizer = self.load(axis)
        rows, pending = self.collect(axis, values, helpers, tokenizer, write_skips=False)
        c.require(not pending, "TOPOLOGY_PANEL_VERIFICATION_INCOMPLETE")
        expected = self.result(axis, rows, values)
        saved = low.read_json(self.path(axis, "axis.safe.json"), maximum=32_000_000)
        c.require(c.same(saved, expected), "TOPOLOGY_PANEL_SAVED_AXIS_RECONSTRUCTION")
        return saved

    def run(self, axis):
        c.require(axis in low.AXES, "TOPOLOGY_PANEL_AXIS_INVALID")
        with self.target.operation("panel-" + axis):
            if self.path(axis, "axis.safe.json").exists():
                return self.verify(axis)
            c.require(
                not self.path(axis, "abort.safe.json").exists(), "TOPOLOGY_PANEL_ABORTED_NO_RETRY"
            )
            for name, private in (
                ("worker.log.private.txt", True),
                ("worker.started.safe.json", False),
                ("worker.stopped.safe.json", False),
                ("samples.safe.jsonl", False),
                ("resources.safe.json", False),
            ):
                c.require(
                    not self.path(axis, name, private=private).exists(),
                    "TOPOLOGY_PANEL_EPOCH_ATTEMPTED_NO_RELAUNCH",
                )
            try:
                values, helpers, tokenizer = self.load(axis)
                rows, pending = self.collect(axis, values, helpers, tokenizer, write_skips=True)
                c.require(
                    all(not row["dispatched"] for row in rows),
                    "TOPOLOGY_PANEL_PRIOR_UNCLOSED_DISPATCH",
                )
                if pending:
                    began = time.monotonic()
                    sampler = thermal.DurableSampler(
                        self.config, self.path(axis, "samples.safe.jsonl")
                    )
                    try:
                        with sampler:
                            cool(self.config, axis, sampler, began, baseline=True)
                            thermal.check_disk(self.config, self.paths)
                            with self.worker(axis, tokenizer, sampler) as worker:
                                for value in pending:
                                    sample = cool(self.config, axis, sampler, began)
                                    free = thermal.check_disk(self.config, self.paths)
                                    low.check_deadline(self.config, axis, began)
                                    sampler.check()
                                    c.require(worker.alive(), "TOPOLOGY_PANEL_WORKER_EXITED")
                                    rid = value["item"]["request_id"]
                                    owner = {
                                        **self.binding(axis, value),
                                        "dispatched": True,
                                        "worker_identity_sha256": self.worker_binding(axis)[
                                            "worker_identity_sha256"
                                        ],
                                        "process_id": worker.pid,
                                        "recorded_at": low.utc(),
                                        "sample_sequence": sample["sequence"],
                                        "sample_sha256": c.digest(sample),
                                        "disk_free_bytes": free,
                                    }
                                    c.write_once(
                                        self.path(axis, rid + ".ownership.safe.json"), owner
                                    )
                                    locations = low.axis_paths(self.paths, axis, rid)
                                    body = low.request_body(self.config, value, axis)
                                    binding = (
                                        {
                                            "process_id": worker.pid,
                                            "server_command_sha256": worker.command_sha256,
                                        }
                                        if axis == "jailmeter"
                                        else None
                                    )
                                    journal = low.reserve_dispatch(
                                        self.config, value, axis, body, locations, binding
                                    )
                                    sampler.check()
                                    started = time.monotonic()
                                    raw = worker.call(value, body)
                                    elapsed = time.monotonic() - started
                                    c.write_once(locations["reply"], raw, raw=True)
                                    c.require(
                                        worker.alive(), "TOPOLOGY_PANEL_WORKER_EXITED_AFTER_REPLY"
                                    )
                                    if axis == "qwen":
                                        reply = low.strict(raw)
                                        row = low.qwen_result(
                                            self.config,
                                            value,
                                            helpers,
                                            reply["content"],
                                            reply["output_ids"],
                                            elapsed,
                                            journal,
                                            raw,
                                        )
                                    else:
                                        row = low.jailmeter_result(
                                            self.config, value, helpers, raw, elapsed, journal
                                        )
                                    c.write_once(locations["row"], row)
                                    rows.append(row)
                                    sampler.check()
                                    low.emit(
                                        "TOPOLOGY_PANEL_PROGRESS",
                                        axis=axis,
                                        complete=len(rows),
                                        total=len(values),
                                    )
                            sampler.observe(baseline=True)
                    finally:
                        c.write_once(
                            self.path(axis, "resources.safe.json"), self.resources(axis, sampler)
                        )
                rows, absent = self.collect(axis, values, helpers, tokenizer, write_skips=False)
                c.require(not absent, "TOPOLOGY_PANEL_FINAL_REPLAY_INCOMPLETE")
                result = self.result(axis, rows, values)
                c.write_once(self.path(axis, "axis.safe.json"), result)
                return result
            except BaseException as error:
                path = self.path(axis, "abort.safe.json")
                if not path.exists():
                    c.write_once(
                        path,
                        {
                            **self.worker_binding(axis),
                            "error_code": low.safe_error_code(error),
                            "recorded_at": low.utc(),
                            "retry_ambiguous_request": False,
                            "scientific_gate_evaluated": False,
                            "private_content_included": False,
                        },
                    )
                raise
