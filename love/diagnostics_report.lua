-- Read-only Comet Desk diagnostic report exporter.
-- The filesystem adapter is injected so the data contract can be tested without LÖVE.
local M = {}
local function clean(value, limit)
    if type(value) ~= "string" then return nil end
    value = value:gsub("[%z\1-\31\127]", " "):gsub("%s+", " ")
    value = value:sub(1, limit or 160)
    if value == "" then return nil end
    return value
end
local function finite_number(value)
    return type(value) == "number" and value == value and value ~= math.huge and value ~= -math.huge
end
local function storage_record(item)
    if type(item) ~= "table" then return {status = "NOT DETECTED"} end
    local record = {status = clean(item.status, 32) or "UNKNOWN", mount_point = clean(item.mount, 96), filesystem = clean(item.filesystem, 32)}
    if type(item.stats) == "table" then
        for _, key in ipairs({"total_bytes", "used_bytes", "free_bytes"}) do
            if finite_number(item.stats[key]) and item.stats[key] >= 0 then record[key] = math.floor(item.stats[key]) end
        end
        if type(item.stats.read_only) == "boolean" then record.read_only = item.stats.read_only end
    end
    return record
end
function M.build(device, timestamp)
    device = type(device) == "table" and device or {}
    local storage = type(device.storage) == "table" and device.storage or {}
    return {
        schema_version = 1, product = "Comet Desk",
        generated_at_utc = clean(timestamp, 40) or os.date("!%Y-%m-%dT%H:%M:%SZ"),
        device = {
            handheld = clean(device.handheld, 96) or "Unknown",
            model = clean(device.model, 128) or "Unknown",
            soc = clean(device.soc, 96) or "Unknown",
            architecture = clean(device.architecture, 32) or "Unknown",
            firmware = clean(device.firmware, 96) or "Unknown",
            memory_mb = finite_number(device.memory_mb) and math.max(0, math.floor(device.memory_mb)) or nil,
        },
        storage = {tf1 = storage_record(storage.tf1), tf2 = storage_record(storage.tf2)},
        safety = {read_only_probe = true, filesystem_mutations_performed = false,
            mounts_changed = false, block_devices_written = false},
        notes = "Diagnostic snapshot only. Unknown values are not inferred.",
    }
end
local function json_escape(value)
    local escaped = value:gsub('[%z\1-\31\127\\"]', function(char)
        local escapes = {['"'] = '\\"', ['\\'] = '\\\\', ['\b'] = '\\b',
            ['\f'] = '\\f', ['\n'] = '\\n', ['\r'] = '\\r', ['\t'] = '\\t'}
        return escapes[char] or string.format("\\u%04x", string.byte(char))
    end)
    return '"' .. escaped .. '"'
end
local function is_array(value)
    local count, maximum = 0, 0
    for key in pairs(value) do
        if type(key) ~= "number" or key < 1 or key % 1 ~= 0 then return false end
        count = count + 1
        if key > maximum then maximum = key end
    end
    return count > 0 and count == maximum
end
local function encode(value)
    local kind = type(value)
    if kind == "nil" then return "null" end
    if kind == "boolean" then return value and "true" or "false" end
    if kind == "number" then return finite_number(value) and tostring(value) or "null" end
    if kind == "string" then return json_escape(value) end
    if kind ~= "table" then return "null" end
    local parts = {}
    if is_array(value) then
        for i = 1, #value do parts[#parts + 1] = encode(value[i]) end
        return "[" .. table.concat(parts, ",") .. "]"
    end
    local keys = {}
    for key in pairs(value) do if type(key) == "string" then keys[#keys + 1] = key end end
    table.sort(keys)
    for _, key in ipairs(keys) do parts[#parts + 1] = json_escape(key) .. ":" .. encode(value[key]) end
    return "{" .. table.concat(parts, ",") .. "}"
end
function M.encode(value) return encode(value) .. "\n" end
function M.write(device, filesystem, timestamp)
    if type(filesystem) ~= "table" or type(filesystem.createDirectory) ~= "function" or type(filesystem.write) ~= "function" then
        return nil, "Filesystem export API is unavailable."
    end
    local safe_stamp = clean(timestamp, 40) or os.date("!%Y%m%dT%H%M%SZ")
    safe_stamp = safe_stamp:gsub("[^%wT%-]", "")
    local directory = "reports"
    local ok, message = filesystem.createDirectory(directory)
    if ok == false then return nil, message or "Could not create reports directory." end
    local path = directory .. "/comet-diagnostics-" .. safe_stamp .. ".json"
    local written, write_error = filesystem.write(path, M.encode(M.build(device, timestamp)))
    if not written then return nil, write_error or "Could not write diagnostic report." end
    return path
end
return M
