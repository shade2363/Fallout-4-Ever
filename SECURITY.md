# Security policy

## What matters most here
* **Updates are signed.** The program only installs an update whose manifest is signed with the project's key (the public key is `builder/update_key.py`) and whose size and SHA-256
  match the signed manifest. Anything that weakens that is a security bug.
* **Downloads are pinned.** The two third-party tools are downloaded from fixed official URLs and refused unless their SHA-256 matches `builder/tools.lock.json`.
* **The uninstall must only remove what the install placed** (`installed-files.txt`).
* **The release must never contain game files, credentials or personal data** (checked by `tools/leak_scan.py` and the `publish/` gate).

## Reporting a vulnerability
Please **do not** open a public issue for a security problem. Use GitHub's private reporting: the **Security** tab of this repository, then **Report a vulnerability**.
Include the version (shown top right in the window), what you did, and what happened. You will get an answer as soon as the maintainers can; please allow some days.

## Supported versions
Only the latest release receives fixes.

## Verifying a download
Every release lists `SHA256SUMS.txt`. Compare it with the file you downloaded (`certutil -hashfile CapitalConvert-x.y.z.zip SHA256` in a command window). The program itself is not
code-signed yet, so Windows SmartScreen may show a warning; the hash comparison is how you know the file is the one the maintainers built.
