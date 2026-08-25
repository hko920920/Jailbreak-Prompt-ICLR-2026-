# Terminal decision: stop the AgentHarm pivot

## Decision

The AgentHarm branch is no longer the main-paper path.

The frozen feasibility program required an analyzable population satisfying

\[
U(\text{direct}) = 0,\qquad U(\text{attacked}) = 1.
\]

That population was not obtained.

## Evidence

### Qwen2.5-7B-Instruct Q4

The frozen development matrix covered six programmatically gradable behaviors
and five attack candidates per behavior. All 36 episodes resolved, but no
direct-failure / attacked-success pair was observed. The resulting signal was
`NO_ELIGIBLE_ATTACK_SIGNAL_ACROSS_DEVELOPMENT`.

### Meta-Llama-3.1-8B-Instruct Q4

The predeclared second-model test used the same six behaviors, five candidates,
seed, and thresholds.

The initial emulated-tool runtime completed all three probe episodes but the
forced-first condition produced zero tool calls. The terminal rule authorized
one runtime-only correction. The original runtime was archived and the only
experimental change was:

```text
inspect_model.emulate_tools: true -> false
```

Under the native-tool retry, the forced-first condition again produced zero
tool calls; only two of three episodes were scored and the attacked condition
was unresolved. No matched six-behavior sweep was opened.

## Interpretation boundary

This is not evidence that AgentHarm generally lacks jailbreakable cases or that
Llama 3.1 is not susceptible to jailbreaks. The Qwen result is a negative result
for the frozen development matrix. The Llama result is an interoperability
failure after the single preauthorized remediation.

It also does not reject the causal-localization hypothesis. The exact component
oracle was never opened because an eligible successful-attack population was
not established.

## Consequence

Further AgentHarm runtime changes would violate the predeclared terminal rule
and risk turning the project into infrastructure debugging. AgentHarm may be
retained only as an engineering negative result or controlled-testbed appendix;
it is not a main empirical contribution.

The next authorized operation is:

```text
FREEZE_NATURAL_LANGUAGE_LOCALIZATION_CONTRACT
```

The restored main question is whether a successful single-turn natural-language
jailbreak depends on a compact human-readable span, a span interaction, or
distributed prompt structure. Wavelet search remains closed until an exhaustive
causal oracle has produced a real target.
