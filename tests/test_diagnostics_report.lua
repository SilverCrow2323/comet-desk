package.path = "love/?.lua;" .. package.path
local report = require("diagnostics_report")
local device = {
    handheld = "Anbernic RG35XX H", model = "Anbernic RG35XX H\n",
    soc = "Allwinner H700", architecture = "AArch64", firmware = "muOS Andromeda 2606.0", memory_mb = 1024,
    storage = {
        tf1 = {status = "MOUNTED", mount = "/mnt/mmc", source = "/dev/mmcblk0p1", filesystem = "ext4",
            stats = {total_bytes = 64000000000, used_bytes = 1000, free_bytes = 63999999000, read_only = false}},
        tf2 = {status = "NOT DETECTED"}
    }
}
local built = report.build(device, "2026-11-26T12:00:00Z")
assert(built.schema_version == 1 and built.safety.read_only_probe == true)
assert(built.safety.filesystem_mutations_performed == false and built.storage.tf1.total_bytes == 64000000000)
assert(built.storage.tf2.status == "NOT DETECTED")
local encoded = report.encode(built)
assert(encoded:find('"product":"Comet Desk"', 1, true))
assert(encoded:find('"block_devices_written":false', 1, true))
assert(not encoded:find("/dev/mmcblk0p1", 1, true), "raw block-device source is deliberately omitted")
assert(not encoded:find("\nAnbernic", 1, true), "control characters are sanitized")
local writes = {}
local fs = {
    createDirectory = function(path) assert(path == "reports"); return true end,
    write = function(path, data) writes[path] = data; return true end,
    getInfo = function(path) return path == "reports/comet-diagnostics-20261126T120000Z.json" end
}
local saved, err = report.write(device, fs, "20261126T120000Z")
assert(saved and not err and saved == "reports/comet-diagnostics-20261126T120000Z-01.json")
assert(writes[saved] and writes[saved]:find('"schema_version":1', 1, true))
local failed, failure = report.write(device, {
    createDirectory = function() return true end,
    write = function() return false, "disk full" end
}, "20261126T120000Z")
assert(failed == nil and failure == "disk full")
print("diagnostics report tests passed")
