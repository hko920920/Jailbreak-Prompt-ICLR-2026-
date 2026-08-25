# Llama 3.1 AgentHarm runtime remediation

The first frozen Llama 3.1 second-model run completed all three episodes and
parsed every deterministic programmatic score, but its forced-first probe
produced zero tool calls. The workflow therefore ended with
`FORCED_FIRST_TOOL_PATH_FAIL`; the six-behavior sweep was not opened.

The frozen terminal rule permits one runtime-only correction without changing
the target model, six behaviors, five attack candidates, generation settings,
or decision thresholds. The original runtime is preserved verbatim as
`runtime_llama31_second_model_v1.json`.

The single correction changes only:

```text
inspect_model.emulate_tools: true -> false
```

This routes the frozen `tool_choice` request through llama.cpp's native OpenAI
tool-call interface rather than Inspect's text-emulation path. The failed run,
its head SHA, job ID, observed coverage, and zero forced-first calls are recorded
in the remediated runtime config.

This remediation remains development-only and non-paper-valid. It does not open
the causal oracle, use final or held-out outputs, alter any attack text, or
enable wavelet analysis. Its result is terminal under the predeclared rule:

- broad eligible signal: freeze eligible development cases, then construct the
  exact component oracle;
- sparse signal: retain AgentHarm only as a controlled case;
- absent signal: stop the AgentHarm pivot and return to natural-language
  localization;
- another operational failure: stop rather than introduce a second runtime
  modification.
