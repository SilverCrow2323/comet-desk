-- Comet Desk // privacy-conscious diagnostic report export
-- Only called after an explicit user action. No file crawling or shell commands.

local M = {}

local function clean(value, limit)
    if value == nil then return "Unknown" end
    local result = tostring(value):gsub("[%c]", " ")
    result = result:gsub("%s+", " ")
    if #result > (limit or 120) then
        result = result:sub(1, (limit or 120) - 3) .. "..."
    end
    return result
end

local function line(key, value)
    return key .. "=" .. clean(value) .. "\n"
end

local function storageLines(label, item)
    item = item or {}
    local out = ""
    out = out .. line(label .. ".status", item.status or "NOT DETECTED")
    if item.status == "MOUNTED" then
        out = out .. line(label .. ".mount", item.mount)
        out = out .. line(label .. ".filesystem", item.filesystem)
        local stats = item.stats
        if stats then
            out = out .. line(label .. ".total_bytes", stats.total_bytes)
            out = out .. line(label .. ".used_bytes", stats.used_bytes)
            out = out .. line(label .. ".free_bytes", stats.free_bytes)
            out = out .. line(label .. ".read_only", stats.read_only and "yes" or "no")
        else
            out = out .. line(label .. ".space_stats", "unavailable")
        end
    end
    return out
end

local function exists(path)
    local file = io.open(path, "rb")
    if not file then return false end
    file:close()
    return true
end

local function nextReportPath(destination, stamp)
    local stem = destination .. "/comet-desk-diagnostic-" .. stamp
    local path = stem .. ".txt"
    local suffix = 1
    while exists(path) do
        path = stem .. "-" .. string.format("%02d", suffix) .. ".txt"
        suffix = suffix + 1
    end
    return path
end

function M.build(device, timestamp)
    device = device or {}
    local storage = device.storage or {}
    local out = "COMET DESK // DIAGNOSTIC REPORT\n"
    out = out .. "format_version=1\n"
    out = out .. line("generated_utc", timestamp or os.date("!%Y-%m-%dT%H:%M:%SZ"))
    out = out .. line("handheld", device.handheld)
    out = out .. line("device_tree_model", device.model)
    out = out .. line("soc", device.soc)
    out = out .. line("architecture", device.architecture)
    out = out .. line("memory_mb", device.memory_mb)
    out = out .. line("firmware", device.firmware)
    out = out .. line("storage_stats_available", device.storage_stats_available and "yes" or "no")
    out = out .. storageLines("tf1", storage.tf1)
    out = out .. storageLines("tf2", storage.tf2)
    out = out .. "\nprivacy=No personal files, account identifiers, Wi-Fi details or device serials are collected.\n"
    return out
end

function M.write(device, destination, timestamp)
    if type(destination) ~= "string" or destination == "" then
        return nil, "report destination is unavailable"
    end
    local stamp = timestamp or os.date("!%Y%m%dT%H%M%SZ")
    local path = nextReportPath(destination, stamp)
    local temporary = path .. ".tmp"
    local file, err = io.open(temporary, "wb")
    if not file then return nil, err or "cannot open report" end
    local ok, writeErr = file:write(M.build(device))
    local closeOk, closeErr = file:close()
    if not ok then
        os.remove(temporary)
        return nil, writeErr or "cannot write report"
    end
    if closeOk == nil then
        os.remove(temporary)
        return nil, closeErr or "cannot close report"
    end
    local renamed, renameErr = os.rename(temporary, path)
    if not renamed then
        os.remove(temporary)
        return nil, renameErr or "cannot publish report"
    end
    return path
end

return M
