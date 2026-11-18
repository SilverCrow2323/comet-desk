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

function M.write(device, destination)
    if type(destination) ~= "string" or destination == "" then
        return nil, "report destination is unavailable"
    end
    local stamp = os.date("!%Y%m%dT%H%M%SZ")
    local path = destination .. "/comet-desk-diagnostic-" .. stamp .. ".txt"
    local file, err = io.open(path, "wb")
    if not file then return nil, err or "cannot open report file" end
    local ok, writeErr = file:write(M.build(device))
    local closeOk, closeErr = file:close()
    if not ok then return nil, writeErr or "cannot write report" end
    if closeOk == nil then return nil, closeErr or "cannot close report" end
    return path
end

return M
