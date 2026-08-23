#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 ARTIFACT_ZIP RECIPIENT_CERT PRIVATE_KEY OUTPUT_DIR" >&2
  exit 2
fi

artifact_zip="$1"
recipient_cert="$2"
private_key="$3"
output_dir="$4"

for path in "$artifact_zip" "$recipient_cert" "$private_key"; do
  if [[ ! -f "$path" ]]; then
    echo "missing input file: $path" >&2
    exit 1
  fi
done

if [[ -e "$output_dir" ]]; then
  echo "output directory already exists: $output_dir" >&2
  exit 1
fi

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
unzip -q "$artifact_zip" -d "$work_dir/artifact"

cms_path="$work_dir/artifact/calibration_packet.cms"
if [[ ! -f "$cms_path" ]]; then
  echo "artifact does not contain calibration_packet.cms" >&2
  exit 1
fi

cert_key_hash="$(openssl x509 -in "$recipient_cert" -pubkey -noout \
  | openssl pkey -pubin -outform DER \
  | openssl sha256)"
private_key_hash="$(openssl pkey -in "$private_key" -pubout -outform DER \
  | openssl sha256)"
if [[ "$cert_key_hash" != "$private_key_hash" ]]; then
  echo "recipient certificate and private key do not match" >&2
  exit 1
fi

archive="$work_dir/private.tar.gz"
openssl cms -decrypt -binary -inform DER \
  -in "$cms_path" \
  -recip "$recipient_cert" \
  -inkey "$private_key" \
  -out "$archive"

tar -xzf "$archive" -C "$work_dir"
private_dir="$work_dir/private"
for filename in \
  annotation_packet.private.jsonl \
  annotation_key.private.jsonl \
  annotation_schema.private.json \
  randomization_seed.private.hex; do
  if [[ ! -f "$private_dir/$filename" ]]; then
    echo "decrypted packet is missing: $filename" >&2
    exit 1
  fi
done

mkdir -p "$output_dir/coordinator" \
  "$output_dir/annotator_a" \
  "$output_dir/annotator_b" \
  "$output_dir/adjudicator" \
  "$output_dir/safe"
cp "$private_dir/annotation_packet.private.jsonl" "$output_dir/coordinator/"
cp "$private_dir/annotation_key.private.jsonl" "$output_dir/coordinator/"
cp "$private_dir/randomization_seed.private.hex" "$output_dir/coordinator/"
cp "$private_dir/annotation_schema.private.json" "$output_dir/coordinator/"
cp "$private_dir/annotation_schema.private.json" "$output_dir/annotator_a/"
cp "$private_dir/annotation_schema.private.json" "$output_dir/annotator_b/"
cp "$private_dir/annotation_packet.private.jsonl" \
  "$output_dir/annotator_a/labels.jsonl"
cp "$private_dir/annotation_packet.private.jsonl" \
  "$output_dir/annotator_b/labels.jsonl"
if [[ -d "$work_dir/artifact/safe" ]]; then
  cp -R "$work_dir/artifact/safe/." "$output_dir/safe/"
fi

find "$output_dir" -type f -exec chmod 600 {} +
chmod 700 "$output_dir" "$output_dir"/*

cms_sha256="$(sha256sum "$cms_path" | cut -d' ' -f1)"
packet_sha256="$(sha256sum "$private_dir/annotation_packet.private.jsonl" | cut -d' ' -f1)"
echo "decryption complete"
echo "cms_sha256=$cms_sha256"
echo "annotation_packet_sha256=$packet_sha256"
echo "annotator A file: $output_dir/annotator_a/labels.jsonl"
echo "annotator B file: $output_dir/annotator_b/labels.jsonl"
echo "Do not give annotation_key.private.jsonl to either primary annotator."
