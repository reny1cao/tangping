PY ?= python3

all: fonts docs

fonts:
	$(PY) sources/build.py

docs: fonts
	$(PY) research/export_sources.py
	$(PY) scripts/build_docs.py

check: fonts
	$(PY) scripts/check.py

media: fonts
	$(PY) scripts/make_images.py
	$(PY) scripts/make_video.py

.PHONY: all fonts docs check media
