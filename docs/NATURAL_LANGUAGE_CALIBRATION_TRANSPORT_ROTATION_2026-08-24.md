# Natural-language calibration transport-certificate rotation

Date: 2026-08-24 (Asia/Seoul)

## Reason

The first frozen 30-item natural-language rubric-calibration packet was generated successfully, but the private key corresponding to `security/phase1_audit_recipient_cert.pem` was not available in the active research workspace or file library. The encrypted packet therefore could not be opened for the two-primary-annotator reliability study.

This commit rotates **only the encryption transport certificate**. It does not modify the scientific contract, item plan, payloads, attacks, target model, model revision, quantization, generation seed, decoding settings, annotation rubric, reliability thresholds, split boundaries, or claim boundary.

The former certificate is preserved as:

`security/phase1_audit_recipient_cert.legacy-2026-08-14.pem`

The active replacement certificate has:

- file SHA-256: `9399df24b2991b91918cb966cbed90bdaea5611a16ac8415585d7b4fbff86908`
- X.509 SHA-256 fingerprint: `1D:DA:9D:1F:80:53:9D:25:F0:3F:CF:25:7B:D7:7E:90:8D:79:FA:7D:BF:3E:B8:72:80:77:80:EB:F9:89:00:C9`
- validity: 2026-08-23 15:18:30 UTC through 2026-09-22 15:18:30 UTC

The matching private key is retained outside the public repository.

## Acceptance rule for the replacement capture

The original successful capture committed the following safe identity:

- response-set SHA-256: `915480598b864bf9f95810ef04b57bbf48598b9fb235531e7ae6671e0f982186`
- packet-order SHA-256: `d3002c8fedd46c6480c7011dffd305fb8fbb3bb250b73cff4b712111efd7154a`
- annotation-IDs SHA-256: `5f66648b48e973ad75ac47f20485c15bf3d6ba8999ee8ac6f3d2dd1faecb4980`

A replacement encrypted packet may be used for calibration annotation only if all three safe identities are byte-identical to the values above. If any identity differs, the replacement capture is not silently substituted; the discrepancy must be recorded and reviewed before annotation.

The 60-item decision packet, prior Gate 1 evaluation partition, Gate 2 held-out partition, causal oracle, and wavelet analysis remain closed.
