# Synthetic paper fixtures

These original MIT-licensed fixtures contain no third-party paper or dataset.
`native.pdf` is a complete two-page PDF with a cross-reference table and a
Helvetica text layer. `scanned.pdf` contains rasterized copies of those pages
at 100 dpi, encoded as page images with no text layer. Both omit author/title
metadata. They include an equation, a small table, a multi-panel figure caption,
a result claim, conflicting training rates (0.001 and 0.01), and an incomplete
citation. Original synthetic panel curves accompany the captions; they are not
measured scientific results.

The native file was assembled from PDF objects using Python's standard library,
with vector panel curves added using the already installed pypdf library.
The scanned copy was made with the already installed Poppler renderer and
Pillow; these preparation tools are not needed to run the automated tests.

`test_extract.py` tests the external CLI using deterministic PDF-tool doubles.
It checks page coverage, OCR provenance, artifact paths, and the unchanged
pre-approval state. This proves workflow handling, not OCR recognition accuracy.
Real-tool coverage and capability limitations are recorded separately in
`docs/validation/issue-11.md`.
