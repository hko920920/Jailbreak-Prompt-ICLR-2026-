# Natural-language calibration model-side diagnostic transport

Date: 2026-08-24 (Asia/Seoul)

## Purpose

This branch exists only to make a fresh 30-item calibration capture readable for a model-side rubric diagnostic. It does not replace the frozen v2 human-annotation packet and does not contribute paper-valid labels or feasibility decisions.

## Unchanged scientific boundary

- The frozen natural-language feasibility contract, payload split, attack candidates, target model, model revision, quantization, and decoding configuration are unchanged.
- The 60-item Stage A decision packet remains unopened.
- Gate 1 evaluation 30 and Gate 2 held-out remain sealed.
- The exact causal oracle and wavelet remain closed.
- Any labels produced from this diagnostic capture are secondary diagnostics only and cannot satisfy the two-independent-human-annotator calibration gate.

## Temporary transport

The branch replaces only `security/phase1_audit_recipient_cert.pem` with a temporary certificate whose matching private key is retained outside GitHub for the duration of this diagnostic.

Certificate file SHA-256:

`69b93af07889fb3033567e935de3c885d2143e9685e67920980dc10574831647`

X.509 SHA-256 fingerprint:

`EF:EA:77:16:63:E0:A9:48:F0:87:92:FC:EB:D9:4B:57:19:F8:FC:86:DD:D1:5F:D9:DA:83:B3:2E:52:87:DB:DE`

## Allowed use

The resulting artifact may be decrypted only to inspect rubric difficulty, class balance, and likely attack signal. It must not be used to open Stage A or claim `NATURAL_LANGUAGE_CALIBRATION_GATE_PASS`.
