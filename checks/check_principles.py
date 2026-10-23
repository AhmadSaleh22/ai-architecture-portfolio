"""Fails the build if the system settings or the ADRs break ShopCo's principles."""
import glob, json, re, sys

errors = []
cfg = json.load(open("config/shopco.json"))
country = cfg["data"]["country"]

# P1: every offer is checked for profit; losing ones go to an admin
if not cfg["offers"]["profit_check"]:
    errors.append("P1: profit check is off")
if cfg["offers"]["losing_offers"] != "admin_approval":
    errors.append("P1: losing offers must go to an admin")

# P3: monthly message limit, enforced in code
if cfg["messages"]["monthly_limit_per_customer"] > 2:
    errors.append("P3: message limit is above 2 a month")
if cfg["messages"]["enforced_by"] != "code":
    errors.append("P3: message limit must be enforced in code")

# Data stays in the country (ADR 0002, 0004)
if cfg["llm"]["provider_region"] != country:
    errors.append("ADR 0002: LLM runs outside " + country)
if cfg["vector_store"]["region"] != country:
    errors.append("ADR 0004: vectors stored outside " + country)

# Every ADR has options, a decision and a revisit condition
for path in sorted(glob.glob("adr/[0-9]*.md")):
    if path.startswith("adr/0000") or path.startswith("adr/0001"):
        continue
    text = open(path).read()
    for section in ["## Options", "## Decision", "## Revisit if"]:
        if section not in text:
            errors.append(f"{path}: missing '{section}'")

if errors:
    print("Guardrail failed:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("Guardrail passed")
