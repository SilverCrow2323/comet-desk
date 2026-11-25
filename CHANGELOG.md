# Changelog

## Unreleased

- Fixed Linux `statvfs` read-only detection in the LÖVE device probe without relying on an optional LuaJIT global bit library.
- Preserve an Unknown read-only state when the flag is unavailable instead of falsely reporting the filesystem as writable.
- Added Lua 5.1 regression coverage and included it in CI.
