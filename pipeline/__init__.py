# pipeline/__init__.py
# Research pipeline package for the service business prospecting assistant.
#
# This package contains five modules:
#   - utils.py    → Shared utilities: slugify and setup_logger.
#   - research.py → Claude API research agent that generates structured brand briefs.
#   - output.py   → Merges research output into a final brief and writes it to disk.
#   - social.py   → Social media URL extractor; finds Instagram links from business websites.
#   - address.py  → Address parser for Street, City, State, and ZIP sheet fields.
#
# Entry point: run_pipeline.py at the parent directory level.
