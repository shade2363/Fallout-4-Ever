"""Release identity.  Bump VERSION for every release (semantic versioning: MAJOR.MINOR.PATCH)."""
VERSION = '0.2.0'
UPDATE_REPO = 'shade2363/Fallout-4-Ever'          # GitHub Releases of this repo are the update source
STEPS_REV = 3       # bump ONLY when the built-in steps (builder/steps.py) change what they produce: it re-runs the stages that use them (a normal release does NOT)
