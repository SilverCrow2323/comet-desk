# Changelog

## Unreleased

- Fixed Linux `statvfs` read-only detection in the LÖVE device probe without relying on an optional LuaJIT global bit library.
- Preserve an Unknown read-only state when the flag is unavailable instead of falsely reporting the filesystem as writable.
- Added Lua 5.1 regression coverage and included it in CI.

- Reserve final diagnostic filenames with exclusive creation, skipping existing files and symlinks instead of relying on a check-then-rename sequence that could overwrite a concurrent export.
- Added regression coverage for colliding final names and symlink targets.
