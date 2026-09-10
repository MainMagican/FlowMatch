# FlowMatch Org Extraction

The Banking Circle organization deck is an input artifact, not a hand-copied
list. Extract it locally with:

```powershell
python tools/extract_org_chart.py "C:\path\Banking Circle_Org chart_July 2026.pptx" "$env:TEMP\banking-circle-org.json"
```

The extractor reads shape text, `<a:off>` coordinates, and connector endpoint
IDs. When PowerPoint does not preserve connector endpoints, it records a
proximity-derived edge separately. Do not commit the confidential deck or its
generated JSON to the repository.