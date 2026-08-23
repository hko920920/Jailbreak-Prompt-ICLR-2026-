# Natural-language calibration transport rotation and active-capture freeze

Date: 2026-08-24 (Asia/Seoul)

## Transport failure and certificate rotation

The first frozen 30-item rubric-calibration packet was generated successfully, but the private key corresponding to the original `security/phase1_audit_recipient_cert.pem` was unavailable in the active research workspace and file library. The first encrypted packet could not be opened and received no human labels.

Only the encryption transport certificate was rotated. The scientific contract, safe item plan, payloads, attacks, target model and revision, quantization, generation seed and decoding configuration, annotation rubric, reliability thresholds, split boundaries, and claim boundary were not changed. The former certificate remains preserved at:

`security/phase1_audit_recipient_cert.legacy-2026-08-14.pem`

The active replacement certificate has:

- file SHA-256: `9399df24b2991b91918cb966cbed90bdaea5611a16ac8415585d7b4fbff86908`
- X.509 SHA-256 fingerprint: `1D:DA:9D:1F:80:53:9D:25:F0:3F:CF:25:7B:D7:7E:90:8D:79:FA:7D:BF:3E:B8:72:80:77:80:EB:F9:89:00:C9`
- validity: 2026-08-23 15:18:30 UTC through 2026-09-22 15:18:30 UTC

The matching private key is retained outside the public repository.

## Correction to the initial transport-only acceptance note

The initial note proposed requiring the replacement capture's response-set, annotation-ID, and packet-order hashes to equal the abandoned packet. That test was reviewed before any annotation labels were created and found to be invalid for two reasons:

1. `annotation_ids_sha256` and `packet_order_sha256` are intentionally derived from a fresh private 256-bit randomization seed on every packet build. Equality across captures is therefore neither expected nor scientifically meaningful.
2. The target-generation contract uses temperature `0.6`. The replacement is a new stochastic capture under the same frozen model, inputs, attack assignments, seed field, and decoding parameters; it is not claimed to reproduce inaccessible response bytes from the abandoned encrypted packet.

This correction does not relax an outcome threshold and was made before any primary or adjudicated labels were observed. The original packet remains abandoned and unopenable rather than being selectively compared at the response level.

## Active v2 packet frozen before annotation

The replacement workflow completed successfully:

- workflow run: `32648286046`
- artifact: `9495782653`
- artifact digest: `sha256:5054b3463b2a5f6471c8d037fcfac776a08cb4f39ed66e09572b8d8d59850db7`
- source commit: `7541d608acae9ffa60621ba7954b69e099154c0c`

The 30 safe inputs are byte-identical to the first capture:

- `safe_inputs_sha256`: `77c39445eab4d7fef18668d1f055c0dba187674e4b5643bef5f9015abaa999f0`
- contract identity: `5388f918c3781ac09770b9613e73cd9e5971475d29886e8c60ac9aedf96ebe06`
- plan identity: `156ca37ecc826b25de1cd75c35ecde2feb5730f18a1dc54f91407505498ff261`

The active packet identities, frozen before annotation, are:

- response-set SHA-256: `3b0e604f02cd9fb1636c1661ee0cc617f97595d32cb5f4a88f6971621bf61e49`
- randomization-seed commitment: `38a953a18598a158bdad6f913219e72fd4beb30cef136519a0cf0a110a3ffa81`
- annotation-IDs SHA-256: `32c90dd0f175d2f98e7acbe9bdc88d7f861bcbc4ad85d1b2d64239db1cc31a29`
- packet-order SHA-256: `83df6f466fce2f8e6db6283c13e16281dcc319dedeb0029d102a58fdcdb7a31a`

The machine-readable record is:

`data/natural_language_localization/feasibility_v1/calibration_capture_v2.safe.json`

## Remaining boundary

The active packet may now be distributed to two independent blinded primary annotators. The 60-item decision packet, prior Gate 1 evaluation partition, Gate 2 held-out partition, exact causal oracle, and wavelet analysis remain closed until the calibration reliability gate passes unchanged:

- raw agreement at least `0.80`;
- Cohen's kappa at least `0.60`.
