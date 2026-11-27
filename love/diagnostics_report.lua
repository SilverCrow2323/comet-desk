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
            local readOnly = stats.read_only
            out = out .. line(label .. ".read_only", readOnly == nil and "unknown" or (readOnly and "yes" or "no"))
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

local function reserveReportPath(destination, stamp)
    local stem = destination .. "/comet-desk-diagnostic-" .. stamp
    for suffix = 0, 9999 do
        local path = suffix == 0 and (stem .. ".txt")
            or (stem .. "-" .. string.format("%02d", suffix) .. ".txt")
        -- Reserve the final name exclusively. This avoids the check-then-rename
        -- race in which os.rename could replace a report created by another process.
        local file, err = io.open(path, "wbx")
        if file then return path, file end
        if not exists(path) then
            return nil, nil, err or "cannot reserve report destination"
        end
    end
    return nil, nil, "report filename space is exhausted"
end

function M.write(device, destination, timestamp)
    if type(destination) ~= "string" or destination == "" then
        return nil, "report destination is unavailable"
    end
    local generated = timestamp or os.date("!%Y-%m-%dT%H:%M:%SZ")
    local stamp = generated:gsub("[^0-9A-Za-z]", "")
    local path, file, err = reserveReportPath(destination, stamp)
    if not file then return nil, err or "cannot reserve report" end
    local ok, writeErr = file:write(M.build(device, generated))
    local closeOk, closeErr = file:close()
    if not ok then
        os.remove(path)
        return nil, writeErr or "cannot write report"
    end
    if closeOk == nil then
        os.remove(path)
        return nil, closeErr or "cannot close report"
    end
    return path
end

return M
