# Run and build it yourself

## Run from source
```
python -m pip install pillow cryptography pywinauto
python builder/capital_builder.py            # opens the window
python builder/capital_builder.py detect     # prints what it found
python builder/capital_builder.py plan       # lists the stages
python builder/capital_builder.py build --workdir D:\work --yes
```
You need Python 3.10 or newer (3.12 is what the release is built with) with Tk (the standard Windows installer includes it).
`tools/run-from-source.bat` does the same as the first line.

## Run the tests
```
python -m unittest discover -s tests -v
python tools/leak_scan.py            # the release gate on the repository
python tools/verify_manifest.py      # SYNC-MANIFEST.json describes the payload (after editing a payload file: --update)
```
The command line of the program is documented by `python builder/capital_builder.py --help`.
The tests need no game. `tools/smoke_exe.py` additionally needs Fallout 3 and Fallout 4 installed (read-only) and tests the packaged exe.

## Build the packaged program
```
python -m pip install pyinstaller
python builder/make_exe.py --zip      # dist/CapitalConvert/ and dist/CapitalConvert.zip
python tools/smoke_exe.py             # run the packaged exe in a fresh work folder
powershell -ExecutionPolicy Bypass -File tools/sandbox_install_test.ps1 -Work <finished work folder>   # install/uninstall into a throw-away folder
```

## Make a signed release (maintainer)
```
python tools/make_keys.py                                  # once: creates your signing key outside the repo and writes the public key into builder/update_key.py
python tools/release.py --version X.Y.Z --notes-file notes.txt --save-compat save-safe
```
The private key must never be committed or shared. Publishing goes through `publish/publish.py`, see [publish/README.md](../publish/README.md) and [RELEASE-CHECKLIST.md](RELEASE-CHECKLIST.md).

## Layout
See [ARCHITECTURE.md](ARCHITECTURE.md).
