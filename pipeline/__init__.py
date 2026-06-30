# pipeline/__init__.py
# Research pipeline package for the service business prospecting assistant.
#
# This package contains four modules:
#   - utils.py    → Shared utilities: slugify and setup_logger.
#   - research.py → Claude API research agent that generates structured brand briefs.
#   - output.py   → Merges research output into a final brief and writes it to disk.
#   - social.py   → Contact extractor; finds validated emails and Instagram links.
#   - email_validation.py → Filters fake, placeholder, and automated email addresses.
#
# Entry point: run_pipeline.py at the parent directory level.
