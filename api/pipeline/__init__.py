"""Analysis pipeline.

Stages:
  1. ingest    -- fetch candidate studies from PubMed for a product/ingredient
  2. extract   -- pull structured features out of titles + abstracts
  3. quality   -- per-study quality score (rubric-based, with ML hook)
  4. claims    -- derive candidate marketed claims from the literature
  5. alignment -- per-(claim, study) supports/contradicts/unrelated classifier
  6. aggregate -- combine into a product-level verdict with evidence grades

The orchestrator is `pipeline.run.analyze_product`.
"""

PIPELINE_VERSION = "0.1.0"
