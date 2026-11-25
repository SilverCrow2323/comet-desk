-- Comet Desk // read-only muOS device probe
-- Uses procfs/device-tree and read-only statvfs calls. No shell or writes.

local M = {}
local ffiOK, ffi = pcall(require, "ffi")

if ffiOK then
    pcall(ffi.cdef, [[
        struct statvfs {
            unsigned long f_bsize;
            unsigned long f_frsize;
            unsigned long f_blocks;
            unsigned long f_bfree;
            unsigned long f_bavail;
            unsigned long f_files;
            unsigned long f_ffree;
            unsigned long f_favail;
            unsigned long f_fsid;
            unsigned long f_flag;
            unsigned long f_namemax;
            int __f_spare[6];
        };
        int statvfs(const char *path, struct statvfs *buf);
    ]])
end

local function readFile(path)
    local file = io.open(path, "rb")
    if not file then return nil end
    local value = file:read("*a")
    file:close()
    if not value then return nil end
    value = value:gsub("%z", ""):gsub("^%s+", ""):gsub("%s+$", "")
    if value == "" then return nil end
    return value
end

local function firstFile(paths)
    for _, path in ipairs(paths) do
        local value = readFile(path)
        if value then return value, path end
    end
    return nil, nil
end

local function readMemory()
    local value = readFile("/proc/meminfo")
    if not value then return nil end
    local kb = tonumber(value:match("MemTotal:%s+(%d+)"))
    if not kb then return nil end
    return math.floor(kb / 1024 + 0.5)
end

local function readOnlyFlag(flags)
    local value = tonumber(flags)
    if value == nil then return nil end
    -- Linux/POSIX ST_RDONLY is bit 0; do not depend on an optional global bit table.
    return math.floor(value) % 2 == 1
end

local function filesystemStats(path)
    if not ffiOK then return nil end
    local ok, result = pcall(function()
        local stats = ffi.new("struct statvfs[1]")
        if ffi.C.statvfs(path, stats) ~= 0 then return nil end
        local item = stats[0]
        local unit = tonumber(item.f_frsize)
        if not unit or unit == 0 then unit = tonumber(item.f_bsize) end
        if not unit or unit == 0 then return nil end
        local total = tonumber(item.f_blocks) * unit
        local free = tonumber(item.f_bavail) * unit
        local used = (tonumber(item.f_blocks) - tonumber(item.f_bfree)) * unit
        return {
            total_bytes = total,
            used_bytes = used,
            free_bytes = free,
            read_only = readOnlyFlag(item.f_flag),
        }
    end)
    if ok then return result end
    return nil
end

local function readStorage()
    local mounts = readFile("/proc/mounts")
    local found = {
        tf1 = { label = "TF1", mount = "/mnt/mmc", status = "NOT DETECTED" },
        tf2 = { label = "TF2", mount = "/mnt/sdcard", status = "NOT DETECTED" },
    }
    if not mounts then return found end

    for line in mounts:gmatch("[^\n]+") do
        local source, mountpoint, filesystem = line:match("^(%S+)%s+(%S+)%s+(%S+)")
        if source and mountpoint then
            for _, key in ipairs({ "tf1", "tf2" }) do
                local item = found[key]
                if mountpoint == item.mount then
                    item.status = "MOUNTED"
                    item.source = source
                    item.filesystem = filesystem or "Unknown"
                    item.stats = filesystemStats(mountpoint)
                end
            end
        end
    end
    return found
end

function M.read()
    local model = firstFile({
        "/proc/device-tree/model",
        "/sys/firmware/devicetree/base/model",
    })
    local compatible = readFile("/proc/device-tree/compatible")
        or readFile("/sys/firmware/devicetree/base/compatible")
        or ""
    local arch = (jit and jit.arch) or "Unknown"
    if arch == "arm64" then arch = "AArch64" end

    local firmware = firstFile({
        "/opt/muos/config/system/version",
        "/opt/muos/config/system/release",
        "/opt/muos/config/version",
    })

    local soc = "Unknown"
    if compatible:find("sun50i%-h700") or compatible:find("allwinner,sun50i%-h700") then
        soc = "Allwinner H700"
    elseif compatible:find("sun50i") then
        soc = "Allwinner sun50i family"
    end

    local handheld = "Unknown"
    if model then
        if model:lower():find("rg35xx%-h") or model:lower():find("rg35xx h") then
            handheld = "Anbernic RG35XX H"
        else
            handheld = model:gsub("[\r\n]+", " ")
        end
    end

    return {
        handheld = handheld,
        model = model or "Unknown",
        soc = soc,
        architecture = arch,
        memory_mb = readMemory(),
        firmware = firmware or "Unknown",
        storage = readStorage(),
        storage_stats_available = ffiOK,
    }
end

M._isReadOnlyFlag = readOnlyFlag

return M
