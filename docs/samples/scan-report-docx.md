# Sample DOCX output (base64)

The OCR preview for the Vietnamese political report is stored as
`scan-report.docx.b64` so it can live in the repository without binary-file
restrictions. To inspect the actual DOCX, decode the base64 payload:

```bash
base64 --decode docs/samples/scan-report.docx.b64 > scan-report.docx
```

Open the resulting `scan-report.docx` file in any word processor to review the
layout and recognized text.
