# ICLR 2027 paper workspace

The official archive supplied by the user remains at repository root as `iclr-2027-style-files.zip`. Its extracted, unmodified style assets are under `paper/iclr2027/`.

- Source ZIP SHA-256: `0D940DFA9398AE99A18F24A85A8A683F367204B6AF6D17D2899E60A67102529E`
- Draft entry point: `paper/iclr2027/main.tex`
- Submission mode: anonymous; keep `\iclrfinalcopy` commented out.
- Initial submission limit: 9 main-text pages; references and appendices follow the official rules.
- Required before submission: final empirical results, references, AI-use statement, author/abstract registration checks, and anonymization audit.

Typical build from `paper/iclr2027/`:

```bash
latexmk -pdf main.tex
```

The draft intentionally contains visible `RESULT PENDING` markers. They prevent protocol text from being mistaken for completed empirical evidence.

