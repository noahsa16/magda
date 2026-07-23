#!/usr/bin/env bash
# Einmaliges Setup auf einem frischen RunPod-Pod (PyTorch-Template, Linux + CUDA).
#
# Ablauf:
#   1. Auf dem Pod:  git clone <repo> && cd magda
#   2.               bash scripts/setup_runpod.sh
#   3. Daten hochschieben (R2, siehe unten) oder per scp nach data/labeled/
#   4.               python scripts/04_train.py layoutxlm
#
# Das RunPod-PyTorch-Image bringt torch + CUDA schon mit – deshalb wird torch
# hier NICHT neu installiert (das würde nur die CUDA-Version zerschießen).

set -euo pipefail

echo "== Python-Abhängigkeiten (ohne torch, das liefert das Pod-Image) =="
grep -vE "^torch$" requirements.txt > /tmp/req_ohne_torch.txt
pip install -r /tmp/req_ohne_torch.txt

echo "== detectron2 (Quellcode-Build, auf Linux+CUDA unproblematisch) =="
pip install --no-build-isolation "git+https://github.com/facebookresearch/detectron2.git"

echo "== Smoke-Test: lädt LayoutXLM komplett? =="
python - <<'EOF'
import torch
from transformers import AutoTokenizer, LayoutLMv2ForTokenClassification

tok = AutoTokenizer.from_pretrained("microsoft/layoutxlm-base")
model = LayoutLMv2ForTokenClassification.from_pretrained("microsoft/layoutxlm-base", num_labels=15)
print("LayoutXLM ok |", sum(p.numel() for p in model.parameters()) // 1_000_000, "M Parameter")
print("CUDA:", torch.cuda.is_available(), "|", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "-")
EOF

cat <<'EOF'

== Fertig. Nächste Schritte ==

Daten vom Mac auf den Pod, Variante A – direkt per scp:
    scp -r data/labeled data/images data/splits root@<pod-ip>:/workspace/magda/data/

Variante B – über Cloudflare R2 (S3-kompatibel, aws-cli):
    # lokal:  aws s3 sync data/labeled  s3://<bucket>/magda/labeled  --endpoint-url https://<account-id>.r2.cloudflarestorage.com
    # Pod:    aws s3 sync s3://<bucket>/magda/labeled  data/labeled  --endpoint-url https://<account-id>.r2.cloudflarestorage.com
    # (Credentials via AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY aus dem R2-Dashboard)

Training:
    python scripts/04_train.py layoutxlm
    python scripts/05_evaluate.py layoutxlm

Checkpoint zurücksichern (R2 oder scp), bevor der Pod gestoppt wird –
/workspace überlebt nur bei Volumes, sonst ist alles weg:
    aws s3 sync checkpoints/layoutxlm/best s3://<bucket>/magda/checkpoints/layoutxlm --endpoint-url ...
EOF
