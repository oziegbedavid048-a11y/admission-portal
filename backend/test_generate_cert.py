"""Test script to generate and preview the new partnership certificate."""

import os
import sys

# Ensure backend directory is in python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from apps.partners.certificate import build_partnership_certificate_raw

pdf_bytes = build_partnership_certificate_raw(
    agent_name="Holland International",
    partner_code="GAB-84920",
    org_name="Apply Gabstep",
    signatory_name="Stephen Oziegbe.O",
    signatory_title="Chief Executive Officer",
)

output_path = os.path.join(backend_dir, "test_certificate.pdf")
with open(output_path, "wb") as f:
    f.write(pdf_bytes)

print(f"Generated {len(pdf_bytes)} bytes at {output_path}")
