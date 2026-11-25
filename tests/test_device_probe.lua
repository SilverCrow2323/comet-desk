package.path = "love/?.lua;" .. package.path

local probe = require("device_probe")

assert(probe._isReadOnlyFlag(0) == false, "clear ST_RDONLY flag must be writable")
assert(probe._isReadOnlyFlag(1) == true, "ST_RDONLY bit must be detected")
assert(probe._isReadOnlyFlag(3) == true, "ST_RDONLY must be detected with other flags present")
assert(probe._isReadOnlyFlag(2) == false, "unrelated statvfs flags must not imply read-only")
assert(probe._isReadOnlyFlag(nil) == nil, "missing flags must remain unknown")

print("device probe read-only flag tests: OK")
