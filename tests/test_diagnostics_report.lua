package.path = "love/?.lua;" .. package.path

local report = require("diagnostics_report")
local snapshot = {
    handheld = "Anbernic RG35XX H",
    model = "Anbernic RG35XX H\nINJECTED",
    soc = "Allwinner H700",
    architecture = "AArch64",
    memory_mb = 1024,
    firmware = "muOS Andromeda",
    storage_stats_available = true,
    storage = {
        tf1 = {
            status = "MOUNTED",
            mount = "/mnt/mmc",
            filesystem = "exfat",
            source = "/dev/mmcblk0p1",
            stats = {
                total_bytes = 64000000000,
                used_bytes = 12000000000,
                free_bytes = 52000000000,
                read_only = false,
            },
        },
        tf2 = { status = "NOT DETECTED" },
    },
}

local output = report.build(snapshot, "2026-11-18T20:00:00Z")
assert(output:find("generated_utc=2026%-11%-18T20:00:00Z"))
assert(output:find("handheld=Anbernic RG35XX H"))
assert(output:find("tf1.filesystem=exfat"))
assert(output:find("tf1.total_bytes=64000000000"))
assert(output:find("tf1.read_only=no"))
assert(output:find("tf2.status=NOT DETECTED"))
assert(not output:find("device_tree_model=Anbernic RG35XX H\\nINJECTED"))
assert(not output:find("/dev/mmcblk0p1"))
assert(not output:find("source="))
assert(output:find("privacy=No personal files"))

print("diagnostic report tests: OK")
