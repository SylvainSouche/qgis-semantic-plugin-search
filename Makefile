# QGIS Semantic Plugin Search — repository operations.
#
# Naming convention: UpperCamelCase classes and modules, Qt style camelCase
# methods, matching the surrounding PyQt ecosystem.
# @impl 4be9-6ae4-471f-260f

.DEFAULT_GOAL := help
.PHONY: help test smoke fetch embed dist version increment clean clean-all _python _venv

PLUGIN := SemanticPluginSearch
DATA_DIR := data
BUILD_DIR := build
DIST_DIR := dist
MODEL := $(BUILD_DIR)/EmbeddingModel.npz
MODEL_ID ?= static-potion-base-8M
HF_BASE ?= https://huggingface.co/minishlab/potion-base-8M/resolve/bf8b056651a2c21b8d2565580b8569da283cab23
# System Python: python3 where it exists, else python (Cygwin, Windows).
PYTHON := $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)
# Venv Python, for the targets that need numpy (test, fetch, embed): bin/ on
# Unix and Cygwin's Python, Scripts/ for a Windows Python. Evaluated when used.
PY = $(or $(wildcard .venv/bin/python),$(wildcard .venv/Scripts/python.exe),$(wildcard .venv/Scripts/python),.venv/bin/python)
# The current version, read from metadata.txt. `make version VERSION=x.y.z`
# overrides it on the command line to set a new one.
CURRENT_VERSION := $(shell sed -n 's/^version=\(.*\)/\1/p' $(PLUGIN)/metadata.txt)
VERSION ?= $(CURRENT_VERSION)
# Model tooling kept in build/ across `make clean` (discovery-driven dev scripts).
KEEP_IN_BUILD := ddd ddd-scripts.tgz
# The changelog comment reaches tools/SetVersion.py through the environment,
# never pasted into the shell command: quotes, $ and backticks stay literal.
export COMMENT
QGIS_VERSIONS ?= 3.44 4.2
FETCH_CONNECTIONS ?= 8

help: ## Show this help and how to install the plugin
	@echo "QGIS Semantic Plugin Search $(CURRENT_VERSION)"
	@echo
	@echo "Targets:"
	@awk -F ':.*## ' '/^[a-zA-Z0-9_-]+:.*## / { printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo
	@echo "Variables (override on the command line):"
	@echo "  QGIS_VERSIONS=$(QGIS_VERSIONS)   version filter used by fetch and embed"
	@echo "  FETCH_CONNECTIONS=$(FETCH_CONNECTIONS)     parallel readme downloads"
	@echo "  ARGS=\"-k ranking\"        extra pytest arguments for 'test'"
	@echo "  VERSION=0.4.1            new version for 'version'"
	@echo "  INC=maj|min|rel          part to bump for 'increment'"
	@echo "  COMMENT=\"...\"            changelog entry for 'version' and 'increment'"
	@echo
	@echo "Install in QGIS:"
	@echo "  1. make dist"
	@echo "  2. In QGIS: Plugins > Manage and Install Plugins > Install from ZIP,"
	@echo "     and pick dist/$(PLUGIN).$(CURRENT_VERSION).zip"
	@echo "  Or copy the $(PLUGIN)/ folder into the profile plugins directory:"
	@echo "     macOS   ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/"
	@echo "     Linux   ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/"
	@echo "     Windows C:\\Users\\<you>\\AppData\\Roaming\\QGIS\\QGIS3\\profiles\\default\\python\\plugins\\"
	@echo "  3. On first open the plugin downloads the embedding model and the"
	@echo "     embeddings database for your QGIS version into <profile>/semantic-search/."

test: _venv ## Run the test suite (no QGIS needed); ARGS passes pytest options
	"$(PY)" -m pytest $(ARGS)

QGIS_APPS ?= $(wildcard /Applications/QGIS*.app /Applications/MacPorts/QGIS*.app)
# The MacPorts QGIS3 cannot be smoke tested on this machine: its Qt5
# QtWebKit fails to dlopen on macOS 26 (missing _CGLGetCurrentContext),
# so the qgis Python bindings cannot even import. Remove from the skip
# list once the MacPorts Qt5 is fixed.
QGIS_SKIP_APPS ?= /Applications/MacPorts/QGIS3.app

smoke: ## Load and run the plugin inside every installed real QGIS, headless (QGIS_APPS overrides the list)
	@status=0; \
	for app in $(QGIS_APPS); do \
		case " $(QGIS_SKIP_APPS) " in *" $$app "*) echo "==> skipping $$app"; continue;; esac; \
		echo "==> Smoke test in $$app"; \
		QGIS_APP="$$app" tools/RunQgisSmoke.sh || status=1; \
		echo; \
	done; \
	exit $$status

fetch: _venv ## Fetch the plugin catalogue and readmes into data/ (QGIS_VERSIONS selects versions)
	@command -v curl >/dev/null || { echo "curl is required"; exit 1; }
	@for v in $(QGIS_VERSIONS); do \
		echo "==> Fetching catalogue and readmes for QGIS $$v"; \
		$(PY) pipeline/FetchCatalogue.py $$v --output-dir $(DATA_DIR) --connections $(FETCH_CONNECTIONS) || exit 1; \
	done

embed: _venv $(MODEL) ## Embed the fetched plugins into per universe databases; fetches first if needed
	@for v in $(QGIS_VERSIONS); do \
		u=$$(echo $$v | cut -d. -f1); \
		xml=$(DATA_DIR)/plugins-$$v.xml; \
		readmes=$(DATA_DIR)/plugins-$$v; \
		if [ ! -f "$$xml" ] || [ ! -d "$$readmes" ]; then \
			echo "==> Data for QGIS $$v missing; fetching first"; \
			$(MAKE) --no-print-directory fetch QGIS_VERSIONS=$$v || exit 1; \
		fi; \
		echo "==> Building embeddings for QGIS $$v (universe $$u)"; \
		$(PY) pipeline/BuildEmbeddings.py \
			--catalogue $$xml \
			--readmes $$readmes \
			--readme-urls $(DATA_DIR)/readme-urls-$$v.json \
			--model $(MODEL) \
			--universe $$u \
			--output $(BUILD_DIR)/Embeddings-$$u.sqlite \
			--catalogue-source "https://plugins.qgis.org/plugins/plugins.xml?qgis=$$v" || exit 1; \
	done
	@echo "==> Databases:"; ls -lh $(BUILD_DIR)/Embeddings-*.sqlite

# @impl 4be9-6ae4-4ed4-e450
dist: _python ## Check, then package the plugin as dist/<plugin>.<version>.zip (no venv needed)
	@test -n "$(CURRENT_VERSION)" || { echo "Cannot read the version from $(PLUGIN)/metadata.txt"; exit 1; }
	@"$(PYTHON)" tools/PackageCheck.py
	@command -v zip >/dev/null || { echo "zip is required"; exit 1; }
	@mkdir -p $(DIST_DIR)
	@rm -f $(DIST_DIR)/$(PLUGIN).$(CURRENT_VERSION).zip
	@zip -rq $(DIST_DIR)/$(PLUGIN).$(CURRENT_VERSION).zip $(PLUGIN) \
		-x "*__pycache__*" -x "*.pyc" -x "*.DS_Store"
	@echo "==> Packaged $(DIST_DIR)/$(PLUGIN).$(CURRENT_VERSION).zip"
	@ls -lh $(DIST_DIR)/$(PLUGIN).$(CURRENT_VERSION).zip

version: _python ## Set the plugin version: make version VERSION=0.4.1 COMMENT="What changed"
	@test "$(origin VERSION)" = "command line" || { echo "Usage: make version VERSION=x.y.z [COMMENT=\"...\"] (current: $(CURRENT_VERSION))"; exit 1; }
	@"$(PYTHON)" tools/SetVersion.py --set $(VERSION) --comment "$$COMMENT"

increment: _python ## Bump the plugin version: make increment INC=maj|min|rel COMMENT="What changed"
	@test -n "$(INC)" || { echo "Usage: make increment INC=maj|min|rel [COMMENT=\"...\"] (current: $(CURRENT_VERSION))"; exit 1; }
	@"$(PYTHON)" tools/SetVersion.py --increment $(INC) --comment "$$COMMENT"

clean: ## Remove generated files (build/ except the model tooling, dist/, caches); keeps data/ and .venv/
	@if [ -d $(BUILD_DIR) ]; then \
		find $(BUILD_DIR) -mindepth 1 -maxdepth 1 $(foreach keep,$(KEEP_IN_BUILD),! -name $(keep)) -exec rm -rf {} +; \
	fi
	@rm -rf $(DIST_DIR) .pytest_cache .ruff_cache
	@find . -path ./.venv -prune -o -type d -name '__pycache__' -exec rm -rf {} +
	@find . -path ./.venv -prune -o -type f -name '*.pyc' -exec rm -f {} +
	@echo "==> Removed build, dist and caches (kept $(DATA_DIR)/, .venv/ and $(BUILD_DIR)/ddd)"

clean-all: ## Remove everything clean removes, plus data/ (fetched plugins data) and .venv/
	@$(MAKE) --no-print-directory clean
	@rm -rf $(DATA_DIR) .venv
	@echo "==> Also removed $(DATA_DIR)/ and .venv/ (everything is regenerated by fetch, embed and test)"

$(MODEL): pipeline/ConvertStaticModel.py | _venv
	@command -v curl >/dev/null || { echo "curl is required"; exit 1; }
	@mkdir -p $(BUILD_DIR)/model-src
	@echo "==> Downloading the static model (MIT licensed, commercial use allowed)"
	curl -fsSL --retry 3 $(HF_BASE)/model.safetensors -o $(BUILD_DIR)/model-src/model.safetensors
	curl -fsSL --retry 3 $(HF_BASE)/tokenizer.json -o $(BUILD_DIR)/model-src/tokenizer.json
	$(PY) pipeline/ConvertStaticModel.py \
		--model-dir $(BUILD_DIR)/model-src \
		--model-id $(MODEL_ID) \
		--source-model "minishlab/potion-base-8M" \
		--license-note "MIT (potion-base-8M), distilled from all-MiniLM-L6-v2 (Apache-2.0); commercial use allowed" \
		--output $(MODEL)

_python:
	@test -n "$(PYTHON)" || { echo "Python 3 is required (python3 or python on the PATH)"; exit 1; }

_venv: _python
	@test -x "$(PY)" || { \
		echo "==> Creating .venv with numpy and pytest"; \
		"$(PYTHON)" -m venv .venv && \
		if [ -x .venv/bin/python ]; then venv=.venv/bin/python; else venv=.venv/Scripts/python; fi && \
		"$$venv" -m pip install --quiet numpy pytest; }
