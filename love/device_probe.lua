-- Comet Desk // read-only muOS device probe
-- Uses procfs/device-tree files only. No shell, writes, mounts or privileged actions.

local M = {}

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
    }
end

return M
