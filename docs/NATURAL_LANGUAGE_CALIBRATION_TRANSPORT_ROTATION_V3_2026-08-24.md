# Natural-language calibration transport rotation v3

Date: 2026-08-24 (Asia/Seoul)

## Reason

The active v2 calibration capture was frozen before annotation and the repository records that no primary or adjudicated labels had been observed. The corresponding decrypted offline annotator packages are not available in the active execution workspace, so they cannot be scored or used to continue the frozen protocol here.

This commit rotates only the CMS transport certificate before any v3 labels are observed. It does not alter the scientific contract, safe item plan, payloads, attack assignments, target model or revision, quantization, generation configuration, annotation rubric, reliability thresholds, split boundaries, causal-oracle boundary, or wavelet boundary.

The v2 certificate remains identifiable by its repository blob SHA `114a29698910321b047e77bed0c313f38dc2850d`. The active v3 certificate has:

- file SHA-256: `7e8a4ebf64572415869d8b976c6b861c1ba8dfb8ba410f3d25bce25194f77150`
- X.509 SHA-256 fingerprint: `08:E0:F9:68:E5:C1:97:92:96:E3:06:D4:7E:27:F5:3C:86:FA:1D:4F:01:C8:CF:30:AC:32:D2:21:D5:C6:02:63`
- public-key SHA-256: `54b6ea5502d8f1db5e68298aad85da4ca15d257d11f52849031256b4c9c86a19`
- validity: 2026-08-23 17:19:30 UTC through 2026-10-07 17:19:30 UTC

The matching private key is retained only in the active secure execution workspace and is not committed.

## Frozen handling rule

1. Run the existing 30-item calibration workflow under the unchanged scientific contract.
2. Before opening any raw response or annotation packet, commit the safe v3 capture identities from the workflow artifact.
3. Only then decrypt the packet and collect two complete blinded primary label passes.
4. Compute raw agreement and Cohen's kappa under the unchangd thresholds.
5. Route only disagreements or `UNCERTAIN` items to a separate adjudication pass.
6. Keep the 60-item Stage A decision packet, Gate 1 evaluation 30, Gate 2 held-out, exact causal oracle, and wavelet closed unless the calibration gate passes.
