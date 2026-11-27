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

local unknownSnapshot = {
    storage = { tf1 = { status = "MOUNTED", stats = { read_only = nil } } },
}
assert(report.build(unknownSnapshot, "2026-11-18T20:00:00Z"):find("tf1.read_only=unknown", 1, true))
assert(output:find("tf2.status=NOT DETECTED"))
assert(output:find("device_tree_model=Anbernic RG35XX H INJECTED"))
assert(not output:find("device_tree_model=Anbernic RG35XX H\nINJECTED"))
assert(not output:find("/dev/mmcblk0p1"))
assert(not output:find("source="))
assert(output:find("privacy=No personal files"))

-- Repeated exports in the same second must not overwrite an earlier report.
local directory = os.tmpname() .. ".comet-report-test"
os.remove(directory)
assert(os.execute("mkdir -p " .. directory) == 0, "temporary report directory could not be created")
local stamp = "2026-11-24T10:48:00Z"
local first, firstErr = report.write(snapshot, directory, stamp)
assert(first, firstErr)
local firstFile = assert(io.open(first, "rb"))
local firstContents = firstFile:read("*a")
firstFile:close()

local second, secondErr = report.write(snapshot, directory, stamp)
assert(second, secondErr)
assert(first ~= second, "same-second exports must receive distinct filenames")
local preserved = assert(io.open(first, "rb"))
assert(preserved:read("*a") == firstContents, "second export overwrote the first report")
preserved:close()
local secondFile = assert(io.open(second, "rb"))
assert(secondFile:read("*a"):find("COMET DESK // DIAGNOSTIC REPORT", 1, true))
secondFile:close()

os.remove(first)
os.remove(second)

-- Existing final-name symlinks and files must not be followed or overwritten.
local outside = directory .. "/outside.txt"
local outsideFile = assert(io.open(outside, "wb"))
outsideFile:write("KEEP THIS FILE")
outsideFile:close()
local basePath = directory .. "/comet-desk-diagnostic-" .. stamp:gsub("[^0-9A-Za-z]", "") .. ".txt"
assert(os.execute("ln -s " .. outside .. " " .. basePath) == 0)
local secondCandidate = basePath:gsub("%.txt$", "-01.txt")
local reservedFile = assert(io.open(secondCandidate, "wb"))
reservedFile:write("KEEP SECOND FILE")
reservedFile:close()
local safePath, safeErr = report.write(snapshot, directory, stamp)
assert(safePath, safeErr)
assert(safePath ~= basePath and safePath ~= secondCandidate, "colliding names must be skipped")
local outsideRead = assert(io.open(outside, "rb"))
assert(outsideRead:read("*a") == "KEEP THIS FILE")
outsideRead:close()
assert(os.execute("test -L " .. basePath) == 0, "pre-existing symlink must remain untouched")
local reservedRead = assert(io.open(secondCandidate, "rb"))
assert(reservedRead:read("*a") == "KEEP SECOND FILE")
reservedRead:close()
os.remove(safePath)
os.remove(secondCandidate)
os.remove(basePath)
os.remove(outside)

assert(os.execute("rmdir " .. directory) == 0, "temporary report directory could not be removed")

print("diagnostic report tests: OK")
