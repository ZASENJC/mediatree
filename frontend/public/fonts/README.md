SourceHanSansCN-Bold.woff2 is used as the bundled CJK fallback font for
browser-side ASS/SSA subtitle rendering.

It mirrors OpenList's libass-wasm strategy: keep a known CJK-capable fallback
font available at a stable static URL so libass never falls back to its bundled
Latin-only default font when a subtitle asks for missing Chinese/Japanese/Korean
fonts.
