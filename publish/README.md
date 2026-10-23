# publish/ : the only way this project goes on GitHub

Everything that sends anything to GitHub goes through `publish.py`. It refuses to publish if the project would reveal something about you, contain a secret, or
contain game files. Nothing personal is stored in this folder's tracked files: your details live in `publish/local/` which git ignores.

## One-time setup
```
python publish/publish.py setup
```
1. Creates `publish/local/config.json` from `config.example.json` (already filled in on the maintainer's PC). It holds: the GitHub repo, your GitHub **no-reply** address
   (`name@users.noreply.github.com`; real e-mails are rejected), the words that must never appear in anything public (your Windows user name, folder names, e-mail
   domain), and the path of your release signing key (its contents are searched for and blocked).
2. Installs a **pre-push guard** into `.git/hooks`. After that a plain `git push` only works for the `public` branch to this repo's `main`, and for `v*` tags;
   any other push, any other remote, any deletion and any force-push is refused, and the whole public history is re-scanned first.
3. Makes this repository commit as your no-reply identity from now on.

Create the GitHub repository **empty** (no README, no licence, no .gitignore) so the first push is a clean upload.

## Publishing
```
python publish/publish.py check                  # the gate, on what is committed
python publish/publish.py snapshot -m "0.1.1"    # gate + a clean commit on the local `public` branch (nothing leaves your PC)
python publish/publish.py push                   # gate on the whole public history, then you type the repo name to confirm
python publish/publish.py release 0.1.1          # verifies dist/release/v0.1.1, then you type the tag to confirm; uploads the 5 release files
```
Your day-to-day branch (`main`) keeps all your local commits and is **never** pushed. The public branch gets one new commit per `snapshot`, created by the tool from a
tree that passed the gate, so old local commits (with old e-mails, paths or experiments) cannot leak.

## What the gate checks
* The committed tree (not your working folder) contains no file from the forbidden list: game formats (`.esm .esp .ba2 .nif .dds` ...), programs (`.exe .dll`), keys and
  certificates, logs, backups, `dist/`, `build/`, `assets/local/`, `publish/local/`.
* No private string from your config, no personal Windows path, no credential pattern (GitHub tokens, private keys, API keys, passwords), and not your actual release signing key.
* `tools/leak_scan.py` (game files, data dumps, size limits) passes on the tree.
* The working tree is clean and all tests pass.
* Every commit on `public` has only your no-reply name and e-mail, and a message free of private strings.
* For a release: `SHA256SUMS.txt` matches, the update manifest's signature verifies, the payload matches the signed manifest, the version equals the one in the published
  source, and the contents of both zips pass the same scans.

## If the gate says no
Fix the file it names (or remove the string), commit, run `check` again. Never edit the gate to get around it.

## Keep out of the repository
`publish/local/`, `dist/`, your private picture folder, and **the signing key** (`...\CapitalConvert-signing\release-private.key`): back it up somewhere private.
