-- COMET DESK // QWASAR
-- Controller-first muOS companion. Desktop Setup retrieves the dedicated Void Desk OS
-- disk image only; it never downloads or installs the Void Desk MUX application.

local W, H = 640, 480
local pages = {
    { id = "overview", title = "OVERVIEW", subtitle = "Your handheld. Your workspace. No OS drama.", icon = "◈", accent = {0.22, 0.88, 0.94} },
    { id = "setup", title = "DESKTOP SYSTEM", subtitle = "Debian Trixie ARM64 // APT + modular desktop environments.", icon = "▣", accent = {0.62, 0.43, 0.98} },
    { id = "sessions", title = "SESSION MANAGER", subtitle = "Discover and launch installed desktop sessions.", icon = "▤", accent = {1.0, 0.72, 0.32} },
    { id = "uplink", title = "UPLINK", subtitle = "Network, wireless radios and remote services.", icon = "◎", accent = {0.24, 0.72, 1.0} },
    { id = "forge", title = "THE FORGE", subtitle = "Discover, install and manage curated Debian ARM64 software.", icon = "⚒", accent = {1.0, 0.48, 0.22} },
    { id = "tools", title = "SYSTEM TOOLS", subtitle = "Small utilities for storage and system services.", icon = "⚙", accent = {0.35, 0.90, 0.68} },
    { id = "diagnostics", title = "DIAGNOSTICS", subtitle = "Read-only checks for your device and runtime.", icon = "⌁", accent = {0.96, 0.30, 0.70} },
}

local selected, activePage = 1, 1
local carouselPosition = 1
local carouselTarget = 1
local pageChangedDirection = 1
local notice, noticeTimer = "SYSTEM READY // COMET DESK", 0
local fonts = {}
local visuals = { background = nil, atlas = nil, quads = {} }
local probe, diagnosticReport
local device = { handheld = "Unknown", soc = "Unknown", architecture = "Unknown", firmware = "Unknown", storage = {} }
local probeTimer = 0
local theme = require("theme")
local colors = theme.colors
local appRoot = os.getenv("COMET_DESK_APP_DIR") or ""
local ambientTime, pageChangedAt = 0, 0
local boot = { elapsed = 0, duration = 2.65, done = false }
local quickPanelOpen, quickPanelAge = false, 0
local gamepadHeld = {}
local keyboardHeld = { start = false, select = false }
local exitRequested = false
local selectedSlot = "tf1"
local installedSlot = nil
local desktopProfiles = {
    { id = "labwc", label = "LABWC", detail = "WAYLAND", accent = {0.22, 0.88, 0.94} },
    { id = "xfce", label = "XFCE", detail = "FULL", accent = {0.62, 0.43, 0.98} },
    { id = "lxde", label = "LXDE", detail = "LIGHTWEIGHT", accent = {1.0, 0.72, 0.32} },
    { id = "lxqt", label = "LXQT", detail = "QT DESKTOP", accent = {0.24, 0.72, 1.0} },
    { id = "icewm", label = "ICEWM", detail = "WM", accent = {0.35, 0.90, 0.68} },
    { id = "fluxbox", label = "FLUXBOX", detail = "WM", accent = {0.96, 0.30, 0.70} },
    { id = "openbox", label = "OPENBOX", detail = "WM", accent = {0.70, 0.80, 0.96} },
}
local selectedProfileIndex = 1
local selectedProfile = "labwc"
local imageDownload = { state = "NOT_INSTALLED", percent = 0, message = "Debian Trixie not installed", location = "", profile = "" }
local downloadPoll = 0
local uplinkStatus = { wifi = {}, bluetooth = {}, hotspot = {}, services = {}, tailscale = {} }
local uplinkPoll = 0
local forgeCategories = { "ALL", "CORE", "INPUT", "DESKTOP", "DEVELOPMENT", "MEDIA", "NETWORK", "UTILITIES" }
local forgeCategoryIndex, forgeSelectedIndex = 1, 1
local forgePackages, forgeSearch = {}, ""
local forgeSearchActive, forgeConfirmRemove = false, nil
local forgeStatus = { state = "IDLE", percent = 0, message = "Open THE FORGE to load the catalogue", package = "" }
local forgePoll, forgeLoaded, forgeActionBusy = 0, false, false

local function setNotice(message)
    notice = message
    noticeTimer = 3.5
end

local function setColor(c)
    love.graphics.setColor(c[1], c[2], c[3], c[4] or 1)
end

local function rounded(x, y, w, h, fill, line)
    setColor(fill)
    love.graphics.rectangle("fill", x, y, w, h, 8, 8)
    if line then
        setColor(line)
        love.graphics.setLineWidth(1)
        love.graphics.rectangle("line", x, y, w, h, 8, 8)
    end
end

local function text(value, x, y, font, color)
    love.graphics.setFont(font)
    setColor(color)
    love.graphics.print(value, x, y)
end

local function drawProgress(x, y, width, height, percent, tint)
    rounded(x, y, width, height, { 0.025, 0.035, 0.055, 1 }, colors.line)
    local filled = math.floor((width - 4) * math.max(0, math.min(100, percent)) / 100)
    if filled > 0 then
        setColor(tint)
        love.graphics.rectangle("fill", x + 2, y + 2, filled, height - 4, 3, 3)
    end
end

local function drawBackground()
    love.graphics.clear(colors.bg[1], colors.bg[2], colors.bg[3], 1)
    if visuals.background then
        love.graphics.setColor(1, 1, 1, 1)
        love.graphics.draw(visuals.background, 0, 0, 0, 2, 2)
    end
    -- A small deterministic starfield gives the industrial backdrop a little life.
    for i = 1, 18 do
        local x = (i * 83 + math.sin(ambientTime * 0.32 + i) * 10) % W
        local y = (i * 47 + ambientTime * (5 + (i % 4))) % H
        love.graphics.setColor(colors.cyan[1], colors.cyan[2], colors.cyan[3], 0.10 + (i % 3) * 0.035)
        love.graphics.circle("fill", x, y, 1)
    end
    love.graphics.setColor(0.07, 0.12, 0.18, 0.28 + 0.04 * math.sin(ambientTime * 0.5))
    for x = 0, W, 32 do love.graphics.line(x, 0, x, H) end
    for y = 0, H, 32 do love.graphics.line(0, y, W, y) end
    setColor(colors.cyan)
    love.graphics.rectangle("fill", 0, 0, W, 3)
    setColor(colors.violet)
    love.graphics.rectangle("fill", W - 112, 0, 112, 3)
end

local function drawHeader()
    -- Compact identity rail: logo, build metadata and live H700 target status.
    if visuals.atlas and visuals.quads.app then
        love.graphics.setColor(1, 1, 1, 1)
        love.graphics.draw(visuals.atlas, visuals.quads.app, 22, 26, 0, 0.76, 0.76)
    end
    text("QWASAR  /  FIELD SYSTEMS", 66, 12, fonts.tiny, colors.muted)
    text("COMET", 66, 29, fonts.title, colors.white)
    text("DESK", 174, 38, fonts.medium, colors.cyan)
    text("DEBIAN APT CONTROL DECK  //  v0.6.0-dev", 67, 70, fonts.tiny, colors.muted)

    rounded(438, 17, 182, 56, colors.panel, colors.line)
    text("RG35XX H  //  H700", 451, 23, fonts.small, colors.cyan)
    local probeStatus = device.handheld ~= "Unknown" and "DEVICE LINK  ONLINE" or "DEVICE LINK  LIMITED"
    text(probeStatus, 451, 44, fonts.tiny,
        device.handheld ~= "Unknown" and colors.green or colors.amber)
    text("L1 / R1  CHANGE SECTION", 451, 59, fonts.tiny, colors.muted)
end


local function pageAccent(index)
    return pages[index or activePage].accent
end

local function curveY(x)
    local d = (x - W * 0.5) / (W * 0.5)
    return 122 + 15 * d * d
end

local function drawGlobe(cx, cy, radius, tint, alpha)
    love.graphics.setColor(tint[1], tint[2], tint[3], alpha or 1)
    love.graphics.setLineWidth(1.4)
    love.graphics.circle("line", cx, cy, radius)
    love.graphics.ellipse("line", cx, cy, radius * 0.42, radius)
    love.graphics.line(cx - radius, cy, cx + radius, cy)
    love.graphics.arc("line", "open", cx, cy, radius * 0.72, math.pi, math.pi * 2)
    love.graphics.arc("line", "open", cx, cy, radius * 0.72, 0, math.pi)
end

local function drawNavigation()
    local active = pageAccent(selected)
    local points = {}
    for x = 12, W - 12, 4 do points[#points + 1] = x; points[#points + 1] = curveY(x) end
    love.graphics.setColor(0.015, 0.025, 0.043, 0.96)
    love.graphics.setLineWidth(22); love.graphics.line(points)
    love.graphics.setColor(0.16, 0.23, 0.32, 0.95)
    love.graphics.setLineWidth(1.5); love.graphics.line(points)
    love.graphics.setColor(active[1], active[2], active[3], 0.34)
    love.graphics.setLineWidth(2.2); love.graphics.line(points)
    for offset = -2, 2 do
        local raw = carouselTarget + offset
        local index = ((raw - 1) % #pages) + 1
        local x = W * 0.5 + (raw - carouselPosition) * 108
        if x > -65 and x < W + 65 then
            local page = pages[index]
            local distance = math.abs(x - W * 0.5) / 216
            local y = curveY(x) - 17
            local isActive = math.abs(x - W * 0.5) < 48
            local scale = isActive and 1 or (0.84 - distance * 0.06)
            local w, h = 92 * scale, 43 * scale
            local px, py = x - w / 2, y - h / 2
            local tint = page.accent
            local alpha = isActive and 1 or math.max(0.42, 0.84 - distance * 0.16)
            rounded(px, py, w, h, isActive and colors.panel2 or colors.panel,
                {tint[1], tint[2], tint[3], (isActive and 0.95 or 0.35) * alpha})
            if isActive then
                love.graphics.setColor(tint[1], tint[2], tint[3], 0.16 + 0.08 * math.sin(ambientTime * 4))
                love.graphics.rectangle("fill", px + 3, py + h - 4, w - 6, 2, 1, 1)
            end
            if page.id == "uplink" then
                drawGlobe(px + 18, py + h / 2, 8 * scale, tint, alpha)
            elseif visuals.atlas and visuals.quads[page.id] then
                love.graphics.setColor(1, 1, 1, alpha)
                love.graphics.draw(visuals.atlas, visuals.quads[page.id], px + 8, py + 9, 0, 0.52 * scale, 0.52 * scale)
            else
                text(page.icon, px + 9, py + 10, fonts.medium, {tint[1], tint[2], tint[3], alpha})
            end
            local labels = { overview = "HOME", setup = "SYSTEM", sessions = "SESS",
                uplink = "UPLINK", forge = "FORGE", tools = "TOOLS", diagnostics = "DIAG" }
            text(labels[page.id] or page.title, px + 30, py + 15, fonts.tiny,
                {colors.white[1], colors.white[2], colors.white[3], alpha})
        end
    end
    text(pages[activePage].title, 22, 82, fonts.medium, active)
    text(string.format("%02d  /  %02d", activePage, #pages), 555, 84, fonts.tiny, colors.muted)
    for i = 1, #pages do
        local x = 294 + (i - 1) * 11
        love.graphics.setColor(active[1], active[2], active[3], i == selected and 1 or 0.22)
        love.graphics.circle("fill", x, 165, i == selected and 3 or 1.5)
    end
end

local function short(value, limit)
    value = tostring(value or "Unknown")
    if #value > limit then return value:sub(1, limit - 3) .. "..." end
    return value
end

local function formatBytes(value)
    if not value then return "n/a" end
    local gib = value / 1073741824
    if gib >= 10 then return string.format("%.1f GB", gib) end
    if gib >= 1 then return string.format("%.2f GB", gib) end
    return string.format("%.0f MB", value / 1048576)
end

local function storageItem(slot)
    return device.storage and device.storage[slot] or nil
end

local function storageUsable(slot)
    local item = storageItem(slot)
    return item and item.status == "MOUNTED" and item.stats
        and not item.stats.read_only and item.stats.free_bytes
end

local function storageLine(label, item)
    if not item or item.status ~= "MOUNTED" then
        return label .. "  NOT DETECTED"
    end
    local stats = item.stats
    if not stats then return label .. "  MOUNTED // SPACE N/A" end
    local access = stats.read_only and "RO" or "RW"
    return string.format("%s  %s FREE / %s  %s", label,
        formatBytes(stats.free_bytes), formatBytes(stats.total_bytes), access)
end

local function drawOverview()
    text(pages[activePage].subtitle, 24, 158, fonts.small, colors.muted)

    rounded(20, 183, 365, 147, colors.panel, colors.line)
    text("LIVE DEVICE SNAPSHOT", 38, 198, fonts.small, colors.cyan)
    text("HANDHELD", 38, 229, fonts.tiny, colors.muted)
    text(short(device.handheld, 28), 164, 226, fonts.small, colors.white)
    text("SOC / ARCH", 38, 253, fonts.tiny, colors.muted)
    text(short(device.soc .. " / " .. device.architecture, 32), 164, 250, fonts.small, colors.white)
    text("FIRMWARE", 38, 277, fonts.tiny, colors.muted)
    text(short(device.firmware, 30), 164, 274, fonts.small, colors.white)
    text("MEMORY", 38, 301, fonts.tiny, colors.muted)
    text(device.memory_mb and (tostring(device.memory_mb) .. " MB") or "Unknown",
        164, 298, fonts.small, colors.white)

    rounded(395, 183, 225, 147, colors.panel, colors.line)
    text("COMET STATUS", 413, 198, fonts.small, colors.violet)
    text("APP / RUNTIME", 413, 229, fonts.tiny, colors.muted)
    text("LÖVE 11.5  //  ARM64", 413, 246, fonts.small, colors.white)
    text("DESKTOP ENGINE", 413, 276, fonts.tiny, colors.muted)
    text("XFCE  //  XORG", 413, 293, fonts.small, colors.green)

    rounded(20, 343, 600, 72, colors.panel, colors.line)
    text("STORAGE  //  LIVE MOUNT STATE", 38, 355, fonts.small, colors.cyan)
    local tf1, tf2 = storageItem("tf1"), storageItem("tf2")
    text(storageLine("TF1", tf1), 38, 379, fonts.tiny,
        tf1 and tf1.status == "MOUNTED" and colors.green or colors.amber)
    text(storageLine("TF2", tf2), 335, 379, fonts.tiny,
        tf2 and tf2.status == "MOUNTED" and colors.green or colors.muted)
end


local function drawSetup()
    local tint = pages[activePage].accent
    text(pages[activePage].subtitle, 24, 180, fonts.small, colors.muted)
    rounded(20, 203, 600, 212, colors.panel, {tint[1], tint[2], tint[3], 0.75})

    text("DEBIAN GNU/LINUX 13  //  TRIXIE ARM64", 34, 214, fonts.medium, colors.white)
    text("APT SYSTEM  /  ONE ROOTFS  /  COMET-MANAGED SOFTWARE", 34, 239, fonts.tiny, colors.cyan)
    text("DESKTOP ENVIRONMENTS", 34, 265, fonts.small, colors.violet)
    for i, profile in ipairs(desktopProfiles) do
        local col = (i - 1) % 4
        local row = math.floor((i - 1) / 4)
        local x, y = 34 + col * 83, 287 + row * 39
        local active = i == selectedProfileIndex
        local accent = profile.accent
        rounded(x, y, 78, 34, active and colors.panel2 or colors.bg, active and accent or colors.line)
        text(profile.label, x + 7, y + 4, fonts.tiny, active and colors.white or colors.muted)
        text(profile.detail, x + 7, y + 19, fonts.tiny, active and accent or colors.muted)
    end

    rounded(376, 260, 228, 142, colors.panel2, colors.line)
    text("DEBIAN / APT STATUS", 391, 272, fonts.small, colors.cyan)
    local stateColor = colors.cyan
    if imageDownload.state == "READY" and installedSlot == selectedSlot and imageDownload.profile == selectedProfile then
        stateColor = colors.green
    elseif imageDownload.state == "FAILED" or imageDownload.state == "CLEANUP_REQUIRED" then
        stateColor = colors.amber
    elseif imageDownload.state ~= "NOT_INSTALLED" then
        stateColor = colors.violet
    end
    local stateLabel = imageDownload.state
    if imageDownload.state == "READY" then stateLabel = "DEBIAN READY / " .. (imageDownload.profile or "APT"):upper() end
    text(short(stateLabel, 24), 391, 299, fonts.medium, stateColor)
    text(short(imageDownload.message, 28), 391, 324, fonts.tiny, colors.white)
    drawProgress(391, 349, 196, 10, imageDownload.percent, stateColor)
    text(string.format("%d%% COMPLETE", imageDownload.percent), 391, 363, fonts.tiny, colors.muted)

    local function slotLabel(label, slot, x)
        local item = storageItem(slot)
        local usable = storageUsable(slot)
        local state = item and item.status == "MOUNTED" and item.stats
            and (item.stats.read_only and "READ ONLY" or formatBytes(item.stats.free_bytes) .. " FREE")
            or "NOT DETECTED"
        text(label, x, 382, fonts.tiny, selectedSlot == slot and colors.cyan or colors.muted)
        text(state, x + 34, 382, fonts.tiny, usable and colors.green or colors.amber)
    end
    slotLabel("TF1", "tf1", 34)
    slotLabel("TF2", "tf2", 214)
    local ready = imageDownload.state == "READY" and installedSlot == selectedSlot and imageDownload.profile == selectedProfile
    text(ready and ("A  LAUNCH " .. selectedProfile:upper()) or ("A  INSTALL " .. selectedProfile:upper()),
        391, 383, fonts.small, ready and colors.green or tint)
end

local function queueUplinkAction(action)
    if appRoot == "" then setNotice("COMET APP PATH UNAVAILABLE"); return end
    local script = appRoot .. "/service/uplink_status.py"
    local function quote(value) return "'" .. tostring(value):gsub("'", "'\\''") .. "'" end
    local command = "cd " .. quote(appRoot) .. " && python3 " .. quote(script)
        .. " " .. quote(appRoot) .. " " .. action
        .. " >> " .. quote(appRoot .. "/data/uplink.log") .. " 2>&1 &"
    local result = os.execute(command)
    if result == 0 or result == true then
        setNotice(action == "install" and "INSTALLING RT:TAILSCALE-M // VERIFIED RELEASE" or "REFRESHING UPLINK TELEMETRY")
    else
        setNotice("COULD NOT START UPLINK TASK")
    end
end

local function readUplinkStatus()
    if appRoot == "" then return end
    local stream = io.open(appRoot .. "/data/uplink.status", "r")
    if not stream then return end
    local line = stream:read("*l")
    stream:close()
    if not line then return end
    local fields = {}
    for value in (line .. "|"):gmatch("(.-)|") do fields[#fields + 1] = value end
    if fields[1] == "ERROR" then uplinkStatus.error = fields[2]; return end
    if #fields < 19 then return end
    local yes = function(v) return v == "1" end
    uplinkStatus.wifi = {connected = yes(fields[1]), ssid = fields[2], ip = fields[3]}
    uplinkStatus.hotspot = {active = yes(fields[4]), ssid = fields[5], interface = fields[6]}
    uplinkStatus.bluetooth = {powered = yes(fields[7]), devices = tonumber(fields[8]) or 0}
    uplinkStatus.services = {
        dns = yes(fields[9]), dashboard = yes(fields[10]), ssh = yes(fields[11]),
        sftp = yes(fields[12]), terminal = yes(fields[13]), syncthing = yes(fields[14])
    }
    uplinkStatus.tailscale = {
        installed = yes(fields[15]), online = yes(fields[16]), backend = fields[17],
        peers = tonumber(fields[18]) or 0, ip = fields[19]
    }
end

local function drawUplink()
    local tint = pages[activePage].accent
    text(pages[activePage].subtitle, 24, 180, fonts.small, colors.muted)
    rounded(20, 205, 600, 210, colors.panel, {tint[1], tint[2], tint[3], 0.7})
    text("WIRELESS // REMOTE ACCESS", 38, 220, fonts.small, tint)
    local wifi, bt, hot, ts = uplinkStatus.wifi or {}, uplinkStatus.bluetooth or {}, uplinkStatus.hotspot or {}, uplinkStatus.tailscale or {}
    local function stateColor(on) return on and colors.green or colors.muted end
    rounded(38, 248, 174, 66, colors.panel2, colors.line)
    text("WI-FI", 50, 258, fonts.tiny, colors.muted)
    text(wifi.connected and short(wifi.ssid or "CONNECTED", 19) or "OFFLINE", 50, 276, fonts.medium, stateColor(wifi.connected))
    text(wifi.ip or "NO ADDRESS", 50, 298, fonts.tiny, colors.muted)
    rounded(223, 248, 174, 66, colors.panel2, colors.line)
    text("HOTSPOT", 235, 258, fonts.tiny, colors.muted)
    text(hot.active and short(hot.ssid or "ACTIVE", 18) or "INACTIVE", 235, 276, fonts.medium, stateColor(hot.active))
    text(hot.interface or "NO AP INTERFACE", 235, 298, fonts.tiny, colors.muted)
    rounded(408, 248, 174, 66, colors.panel2, colors.line)
    text("BLUETOOTH", 420, 258, fonts.tiny, colors.muted)
    text(bt.powered and "POWERED ON" or "POWERED OFF", 420, 276, fonts.medium, stateColor(bt.powered))
    text(tostring(bt.devices or 0) .. " PAIRED / SEEN", 420, 298, fonts.tiny, colors.muted)
    text("MUOS WEB SERVICES", 38, 329, fonts.tiny, tint)
    local sv = uplinkStatus.services or {}
    text("DNS " .. (sv.dns and "●" or "○") .. "   DASH " .. (sv.dashboard and "●" or "○")
        .. "   SSH " .. (sv.ssh and "●" or "○") .. "   SFTP " .. (sv.sftp and "●" or "○")
        .. "   TERM " .. (sv.terminal and "●" or "○") .. "   SYNC " .. (sv.syncthing and "●" or "○"),
        38, 346, fonts.tiny, colors.white)
    text("TAILSCALE // " .. (ts.installed and (ts.backend or "INSTALLED") or "NOT INSTALLED"),
        38, 373, fonts.small, ts.online and colors.green or colors.muted)
    local tailAction = not ts.installed and "A  INSTALL RT:TAILSCALE-M"
        or (not ts.online and "A  START / REPAIR RT SERVICE" or "A  REFRESH RT STATUS")
    text(ts.installed and (tostring(ts.peers or 0) .. " PEERS  ·  " .. (ts.ip or "NO TAILNET IP"))
        or tailAction, 38, 394, fonts.tiny, ts.installed and colors.white or tint)
    if ts.installed and not ts.online then text(tailAction, 38, 410, fonts.tiny, tint) end
    text(ts.installed and "Y  REFRESH" or "Y  REFRESH", 506, 394, fonts.tiny, colors.muted)
    if uplinkStatus.error then text(short(uplinkStatus.error, 72), 38, 410, fonts.tiny, colors.amber) end
end

local function queueForgeAction(action, packageName)
    if appRoot == "" then setNotice("COMET APP RUNNER PATH UNAVAILABLE"); return end
    local slot = installedSlot or selectedSlot
    if not installedSlot then setNotice("INSTALL DEBIAN TRIXIE IN DESKTOP SYSTEM FIRST"); return end
    if forgeActionBusy then setNotice("THE FORGE IS ALREADY RUNNING AN APT OPERATION"); return end
    local function quote(value) return "'" .. tostring(value):gsub("'", "'\\''") .. "'" end
    local script = appRoot .. "/service/forge_apt.py"
    local command = "cd " .. quote(appRoot) .. " && python3 " .. quote(script)
        .. " " .. action .. " --slot " .. slot
        .. (packageName and (" --package " .. quote(packageName)) or "")
        .. " --app-dir " .. quote(appRoot)
        .. " >> " .. quote(appRoot .. "/data/forge-apt.log") .. " 2>&1 &"
    local result = os.execute(command)
    if result == 0 or result == true then
        forgeStatus.state = action == "catalog" and "LOADING" or string.upper(action)
        forgeStatus.percent = 0
        forgeStatus.message = action == "catalog" and "Loading curated APT catalogue" or
            (string.upper(action) .. " // " .. (packageName or "DEBIAN INDEXES"))
        forgeStatus.package = packageName or ""
        forgeActionBusy = action ~= "catalog"
        setNotice("THE FORGE // " .. string.upper(action))
    else
        forgeStatus.state = "FAILED"; forgeStatus.message = "Could not start APT worker"
        setNotice("THE FORGE WORKER COULD NOT START")
    end
end

local function readForgeFiles()
    if appRoot == "" then return end
    local catalog = io.open(appRoot .. "/data/forge-catalog.txt", "r")
    if catalog then
        local rows = {}
        for line in catalog:lines() do
            local category, packageName, title, summary, installed, available, size, tag =
                line:match("^PKG|([^|]*)|([^|]*)|([^|]*)|([^|]*)|([^|]*)|([^|]*)|([^|]*)|([^|]*)$")
            if packageName then rows[#rows + 1] = {
                category = category, package = packageName, title = title, summary = summary,
                installed = installed == "1", available = available == "1", size = size, tag = tag,
            } end
        end
        catalog:close(); forgePackages = rows
    end
    local status = io.open(appRoot .. "/data/forge-operation.status", "r")
    if status then
        local line = status:read("*l"); status:close()
        local state, percent, message, packageName = line and line:match("^([^|]+)|(%d+)|([^|]*)|(.*)$")
        if state then
            forgeStatus.state = state; forgeStatus.percent = tonumber(percent) or 0
            forgeStatus.message = message; forgeStatus.package = packageName or ""
            forgeActionBusy = state == "INSTALLING" or state == "REMOVING" or state == "UPDATING"
        end
    end
end

local function forgeFilteredPackages()
    local category = forgeCategories[forgeCategoryIndex]
    local query = forgeSearch:lower()
    local rows = {}
    for _, item in ipairs(forgePackages) do
        local categoryMatch = category == "ALL" or item.category == category
        local textMatch = query == "" or item.title:lower():find(query, 1, true)
            or item.package:lower():find(query, 1, true) or item.summary:lower():find(query, 1, true)
        if categoryMatch and textMatch then rows[#rows + 1] = item end
    end
    return rows
end

local function cycleForgeCategory(direction)
    forgeCategoryIndex = ((forgeCategoryIndex - 1 + direction) % #forgeCategories) + 1
    forgeSelectedIndex = 1; forgeConfirmRemove = nil
end

local function drawForge()
    local tint = pages[activePage].accent
    text("DEBIAN TRIXIE  /  ARM64 SOFTWARE CENTRE", 24, 180, fonts.small, colors.muted)
    rounded(20, 201, 600, 214, colors.panel, {tint[1], tint[2], tint[3], 0.75})
    local labels = { "ALL", "H700 CORE", "INPUT", "DESKTOP", "DEV", "MEDIA", "NET", "TOOLS" }
    for i, label in ipairs(labels) do
        local x = 26 + (i - 1) * 73
        local active = forgeCategoryIndex == i
        rounded(x, 211, 68, 25, active and colors.panel2 or colors.bg, active and tint or colors.line)
        text(label, x + 5, 216, fonts.tiny, active and colors.white or colors.muted)
    end
    local rows = forgeFilteredPackages()
    if forgeSelectedIndex > #rows then forgeSelectedIndex = math.max(1, #rows) end
    rounded(27, 246, 245, 151, colors.panel2, colors.line)
    text("CURATED SOFTWARE  /  " .. tostring(#rows), 39, 252, fonts.tiny, tint)
    local first = math.max(1, math.min(forgeSelectedIndex - 1, math.max(1, #rows - 3)))
    for visible = 1, 4 do
        local index = first + visible - 1
        local item = rows[index]
        if item then
            local y = 271 + (visible - 1) * 29
            local active = index == forgeSelectedIndex
            if active then rounded(34, y - 2, 230, 27, colors.bg, item.available and tint or colors.amber) end
            local marker = item.installed and "[x] " or (item.available and "[ ] " or "[-] ")
            text(marker .. short(item.title, 20), 42, y, fonts.small,
                active and colors.white or (item.available and colors.muted or colors.amber))
        end
    end
    rounded(281, 246, 326, 151, colors.panel2, colors.line)
    local chosen = rows[forgeSelectedIndex]
    if chosen then
        text(short(chosen.title, 29), 296, 255, fonts.medium, colors.white)
        text(chosen.package, 296, 281, fonts.small, tint)
        if forgeActionBusy then
            drawProgress(296, 296, 294, 7, forgeStatus.percent, tint)
        elseif forgeStatus.state ~= "IDLE" then
            text(short(forgeStatus.message, 38), 296, 296, fonts.tiny, colors.muted)
        end
        love.graphics.setFont(fonts.tiny); setColor(colors.muted)
        love.graphics.printf(short(chosen.summary, 96), 296, 307, 294, "left")
        local stateText = chosen.installed and "INSTALLED" or (chosen.available and "AVAILABLE" or chosen.tag)
        text(stateText .. "  /  " .. (chosen.size ~= "" and chosen.size or "SIZE N/A"),
            296, 365, fonts.tiny, chosen.installed and colors.green or (chosen.available and colors.cyan or colors.amber))
        if chosen.package == "input-leap" then
            text("UPSTREAM BUILD NOT PACKAGED FOR TRIXIE", 296, 383, fonts.tiny, colors.amber)
        elseif forgeConfirmRemove == chosen.package then
            text("PRESS X AGAIN TO CONFIRM REMOVE", 296, 383, fonts.tiny, colors.amber)
        elseif chosen.installed then
            text("X  REMOVE   /   A  DETAILS", 296, 383, fonts.tiny, colors.amber)
        elseif chosen.available then
            text("A  INSTALL PACKAGE", 296, 383, fonts.small, tint)
        else
            text("NOT IN DEBIAN ARM64 REPOSITORY", 296, 383, fonts.tiny, colors.amber)
        end
    else
        text(installedSlot and "NO MATCHES" or "DEBIAN NOT READY", 296, 270, fonts.medium, colors.amber)
        text(installedSlot and "Change category or clear search." or "Install the base system from DESKTOP SYSTEM.",
            296, 306, fonts.small, colors.muted)
        if not installedSlot then
            text("APT CATALOGUE LOCKED UNTIL BASE INSTALL", 296, 344, fonts.tiny, colors.amber)
        end
    end
    text("LEFT / RIGHT CATEGORY   UP / DOWN PACKAGE   Y REFRESH", 29, 402, fonts.tiny, colors.muted)
    if forgeSearch ~= "" then text("SEARCH: " .. short(forgeSearch, 22), 425, 402, fonts.tiny, tint)
    else text("/ SEARCH", 526, 402, fonts.tiny, tint) end
end

local function drawDiagnostics()
    text(pages[activePage].subtitle, 24, 158, fonts.small, colors.muted)
    rounded(20, 183, 600, 232, colors.panel, colors.line)
    text("DEVICE IDENTITY", 38, 199, fonts.small, colors.cyan)
    local rows = {
        { "HANDHELD", device.handheld },
        { "SOC", device.soc },
        { "ARCHITECTURE", device.architecture },
        { "RAM", device.memory_mb and (tostring(device.memory_mb) .. " MB") or "Unknown" },
        { "FIRMWARE", device.firmware },
    }
    for i, item in ipairs(rows) do
        local y = 226 + (i - 1) * 24
        text(item[1], 38, y, fonts.tiny, colors.muted)
        text(short(item[2], 34), 190, y - 2, fonts.small, colors.white)
    end
    setColor(colors.line)
    love.graphics.line(38, 352, 602, 352)
    text("STORAGE MOUNTS", 38, 365, fonts.small, colors.violet)
    local tf1, tf2 = storageItem("tf1") or {}, storageItem("tf2") or {}
    text(storageLine("TF1", tf1) .. "  [" .. short(tf1.filesystem, 7) .. "]",
        38, 388, fonts.tiny, colors.white)
    text(storageLine("TF2", tf2) .. "  [" .. short(tf2.filesystem, 7) .. "]",
        330, 388, fonts.tiny, colors.white)
    text("Y / E  EXPORT PRIVACY-SAFE REPORT", 414, 402, fonts.tiny, colors.cyan)
end


local function drawModule()
    local page = pages[activePage]
    text(page.subtitle, 24, 158, fonts.small, colors.muted)
    rounded(20, 183, 600, 232, colors.panel, colors.line)
    text(page.title, 42, 207, fonts.medium, colors.cyan)
    text("MODULE STATUS", 42, 248, fonts.tiny, colors.muted)
    text("NOT IMPLEMENTED", 42, 272, fonts.large, colors.amber)
    text("This section is a roadmap entry, not a decorative fake control.", 42, 310, fonts.small, colors.white)
    text("Comet Desk will expose only actions that are wired to a verified backend.", 42, 335, fonts.tiny, colors.muted)
    rounded(42, 365, 556, 30, colors.panel2, colors.line)
    text("FEATURE SLOT  //  AVAILABLE IN A LATER VERIFIED BUILD", 58, 374, fonts.tiny, colors.violet)
end


local function drawBoot()
    drawBackground()
    local reveal = math.min(1, boot.elapsed / 0.85)
    local offset = (1 - reveal) * 18
    local pulse = 0.5 + 0.5 * math.sin(ambientTime * 4.2)
    rounded(84, 76 + offset, 472, 328, colors.panel,
        { colors.cyan[1], colors.cyan[2], colors.cyan[3], 0.45 + pulse * 0.35 })
    if visuals.atlas and visuals.quads.app then
        love.graphics.setColor(1, 1, 1, reveal)
        love.graphics.draw(visuals.atlas, visuals.quads.app, 270, 108 + offset, 0, 2, 2)
    end
    text("QWASAR  /  FIELD SYSTEMS", 240, 226 + offset, fonts.small, colors.muted)
    text("COMET", 242, 246 + offset, fonts.title, colors.white)
    text("DESK", 353, 253 + offset, fonts.medium, colors.cyan)
    text("MEGASTRUCTURE DESKTOP COMPANION", 187, 294 + offset, fonts.tiny, colors.muted)
    local progress = math.min(100, boot.elapsed / boot.duration * 100)
    drawProgress(142, 338 + offset, 356, 13, progress, colors.cyan)
    local label = boot.elapsed < 0.85 and "INITIALIZING VISUAL SYSTEM"
        or (boot.elapsed < 1.65 and "CHECKING DEVICE PROFILE" or "PREPARING CONTROL DECK")
    text(label, 210, 365 + offset, fonts.tiny, colors.cyan)
    text("PRESS A / ENTER TO SKIP", 237, 386 + offset, fonts.tiny, colors.muted)
end

local function drawFooter()
    setColor(colors.line)
    love.graphics.line(20, 425, 620, 425)
    local label = notice
    if noticeTimer <= 0 then label = "QWASAR ECOSYSTEM  //  VOID DESK EXPERIENCE, COMET-SIZED" end
    text(short(label, 64), 24, 439, fonts.tiny, noticeTimer > 0 and colors.cyan or colors.muted)
    text("v0.6.0", 574, 439, fonts.tiny, colors.muted)
end

local function drawQuickPanel()
    if not quickPanelOpen then return end
    local reveal = math.min(1, quickPanelAge / 0.16)
    local x, y = 62 + (1 - reveal) * 18, 92 + (1 - reveal) * 8
    love.graphics.setColor(0.008, 0.012, 0.022, 0.76 * reveal)
    love.graphics.rectangle("fill", 0, 0, W, H)
    rounded(x, y, 516, 296, colors.panel,
        { colors.cyan[1], colors.cyan[2], colors.cyan[3], 0.75 * reveal })
    text("COMET  //  QUICK OVERLAY", x + 24, y + 22, fonts.medium, colors.cyan)
    text("CONTROL DECK", x + 24, y + 53, fonts.large, colors.white)
    text("DEBIAN TRIXIE // " .. imageDownload.state, x + 24, y + 104, fonts.small, colors.violet)
    text(short(imageDownload.message, 54), x + 24, y + 127, fonts.tiny, colors.muted)
    drawProgress(x + 24, y + 153, 468, 12, imageDownload.percent, colors.cyan)
    text("M  CLOSE OVERLAY", x + 24, y + 204, fonts.small, colors.white)
    text("START + SELECT  EXIT COMET DESK", x + 24, y + 232, fonts.tiny, colors.amber)
    text("Quick panel // QWASAR control surface", x + 24, y + 258, fonts.tiny, colors.muted)
end

function love.load()
    love.graphics.setDefaultFilter("linear", "linear")
    local function loadFont(path, size, fallback)
        if path == "builtin" then return love.graphics.newFont(size) end
        local ok, font = pcall(love.graphics.newFont, path, size)
        if ok then return font end
        return love.graphics.newFont(fallback or size)
    end
    -- 640x480 handheld-safe typography: status labels remain readable at
    -- native resolution instead of relying on a desktop-sized display.
    fonts.tiny = loadFont(theme.fonts.telemetry, 13, 13)
    fonts.small = loadFont(theme.fonts.interface, 15, 15)
    fonts.medium = loadFont(theme.fonts.display, 18, 18)
    fonts.large = loadFont(theme.fonts.display, 23, 23)
    fonts.title = loadFont(theme.fonts.display, 34, 34)

    local function loadImage(path)
        local ok, image = pcall(love.graphics.newImage, path)
        if ok then return image end
        return nil
    end
    visuals.background = loadImage("assets/backgrounds/comet-dashboard-640x480.png")
    visuals.atlas = loadImage("assets/icons/comet-desk-atlas.png")
    if visuals.atlas then
        local names = { "app", "overview", "setup", "sessions", "tools", "diagnostics" }
        for index, name in ipairs(names) do
            visuals.quads[name] = love.graphics.newQuad((index - 1) * 48, 0, 48, 48, 288, 48)
        end
    end
    love.graphics.setBackgroundColor(colors.bg[1], colors.bg[2], colors.bg[3], 1)

    local ok, module = pcall(require, "device_probe")
    if ok then probe = module end
    local reportOK, reportModule = pcall(require, "diagnostics_report")
    if reportOK then diagnosticReport = reportModule end
    if probe then
        local success, snapshot = pcall(probe.read)
        if success and snapshot then
            device = snapshot
            if not storageUsable(selectedSlot) and storageUsable("tf1") then
                selectedSlot = "tf1"
            elseif not storageUsable(selectedSlot) and storageUsable("tf2") then
                selectedSlot = "tf2"
            end
        end
    end
end

local function readImageDownloadStatus()
    if appRoot == "" then return end
    local statusFile = io.open(appRoot .. "/data/desktop-environment.status", "r")
    if not statusFile then return end
    local line = statusFile:read("*l")
    statusFile:close()
    local state, percent, message, location, profile =
        line and line:match("^([^|]+)|(%d+)|([^|]*)|([^|]*)|(.*)$")
    if not state then return end
    local previousState, previousProfile, previousSlot =
        imageDownload.state, imageDownload.profile, installedSlot
    imageDownload.state = state
    imageDownload.percent = tonumber(percent) or 0
    imageDownload.message = message
    imageDownload.location = location or ""
    imageDownload.profile = profile or ""
    if location and location:find("/mnt/mmc/", 1, true) then
        installedSlot = "tf1"
    elseif location and location:find("/mnt/sdcard/", 1, true) then
        installedSlot = "tf2"
    end
    if state == "READY" and (previousState ~= "READY" or previousProfile ~= imageDownload.profile or previousSlot ~= installedSlot) then
        forgeLoaded = false
        setNotice("DEBIAN TRIXIE READY // " .. (imageDownload.profile or "APT"))
    elseif state == "RUNNING" and imageDownload._notice ~= "RUNNING:" .. imageDownload.profile then
        setNotice("DESKTOP SESSION // " .. (imageDownload.profile or ""):upper())
    elseif state == "FAILED" and imageDownload._notice ~= "FAILED" then
        setNotice("DESKTOP SETUP FAILED // CHECK MESSAGE")
    elseif state == "CLEANUP_REQUIRED" then
        setNotice("DESKTOP MOUNT CLEANUP NEEDS ATTENTION")
    end
    imageDownload._notice = state == "READY" and ("READY:" .. imageDownload.profile)
        or (state == "RUNNING" and ("RUNNING:" .. imageDownload.profile) or state)
end

function love.update(dt)
    ambientTime = ambientTime + dt
    local delta = carouselTarget - carouselPosition
    carouselPosition = carouselPosition + delta * math.min(1, dt * 9.5)
    if not boot.done then
        boot.elapsed = math.min(boot.duration, boot.elapsed + dt)
        if boot.elapsed >= boot.duration then
            boot.done = true
            pageChangedAt = ambientTime
            setNotice("SYSTEM READY // COMET DESK")
        end
    end
    if quickPanelOpen then quickPanelAge = quickPanelAge + dt end
    if noticeTimer > 0 then noticeTimer = math.max(0, noticeTimer - dt) end

    downloadPoll = downloadPoll + dt
    if downloadPoll >= 0.25 then
        downloadPoll = 0
        readImageDownloadStatus()
    end

    uplinkPoll = uplinkPoll + dt
    if uplinkPoll >= 2 then
        uplinkPoll = 0
        readUplinkStatus()
    end
    forgePoll = forgePoll + dt
    if forgePoll >= 0.5 then
        forgePoll = 0
        readForgeFiles()
    end
    probeTimer = probeTimer + dt
    if probe and probeTimer >= 10 then
        probeTimer = 0
        local success, snapshot = pcall(probe.read)
        if success and snapshot then device = snapshot end
    end
end

function love.draw()
    local ww, wh = love.graphics.getDimensions()
    local scale = math.min(ww / W, wh / H)
    love.graphics.push()
    love.graphics.translate((ww - W * scale) / 2, (wh - H * scale) / 2)
    love.graphics.scale(scale, scale)

    if not boot.done then
        drawBoot()
        love.graphics.pop()
        return
    end

    drawBackground()
    drawHeader()
    drawNavigation()
    if activePage == 4 and not uplinkStatus.loaded then
        queueUplinkAction("status")
        uplinkStatus.loaded = true
    end
    if activePage == 5 and not forgeLoaded then
        if installedSlot then queueForgeAction("catalog") end
        forgeLoaded = true
    end
    local transition = math.min(1, math.max(0, (ambientTime - pageChangedAt) / 0.34))
    love.graphics.push()
    love.graphics.translate((1 - transition) * 26 * pageChangedDirection, (1 - transition) * 5)
    local accent = pageAccent(activePage)
    love.graphics.setColor(accent[1], accent[2], accent[3], 0.82)
    love.graphics.rectangle("fill", 20, 202, 3, 212, 1, 1)
    love.graphics.setScissor(18, 176, 604, 244)
    if activePage == 1 then drawOverview()
    elseif activePage == 2 then drawSetup()
    elseif activePage == 4 then drawUplink()
    elseif activePage == 5 then drawForge()
    elseif activePage == 7 then drawDiagnostics()
    else drawModule() end
    love.graphics.setScissor()
    love.graphics.pop()
    drawFooter()
    drawQuickPanel()
    love.graphics.pop()
end

local function exportDiagnostics()
    if activePage ~= 7 then
        setNotice("OPEN DIAGNOSTICS TO EXPORT")
        return
    end
    if not diagnosticReport then
        setNotice("REPORT MODULE UNAVAILABLE")
        return
    end
    local destination = os.getenv("COMET_DESK_APP_DIR")
    if destination and destination ~= "" then
        destination = destination .. "/data"
    else
        local created = love.filesystem.createDirectory("diagnostics")
        if not created then
            setNotice("REPORT DIRECTORY UNAVAILABLE")
            return
        end
        destination = love.filesystem.getSaveDirectory() .. "/diagnostics"
    end
    local path, err = diagnosticReport.write(device, destination)
    if path then
        setNotice("REPORT SAVED // " .. path:match("([^/]+)$"))
    else
        setNotice("REPORT FAILED // " .. short(err, 42))
    end
end

local function cyclePage(direction)
    selected = ((selected - 1 + direction) % #pages) + 1
    carouselTarget = carouselTarget + direction
    activePage = selected
    pageChangedDirection = direction
    pageChangedAt = ambientTime
    setNotice("TAB // " .. pages[activePage].title)
end

local function activate()
    activePage = selected
    pageChangedAt = ambientTime
    if activePage == 1 then
        setNotice("OVERVIEW // READ-ONLY")
    elseif activePage == 2 then
        setNotice("VOID DESK OS // DEBIAN ARM64 + LABWC")
    else
        setNotice(pages[activePage].title .. " // COMING SOON")
    end
end

local function shellQuote(value)
    return "'" .. tostring(value):gsub("'", "'\\''") .. "'"
end

local function cycleDesktopProfile(direction)
    selectedProfileIndex = ((selectedProfileIndex - 1 + direction) % #desktopProfiles) + 1
    selectedProfile = desktopProfiles[selectedProfileIndex].id
    setNotice("DESKTOP PROFILE // " .. selectedProfile:upper())
end

local function startDesktopEnvironment()
    if imageDownload.state == "STARTING" or imageDownload.state == "RUNNING"
        or imageDownload.state == "APT_UPDATE" or imageDownload.state == "INSTALLING_PROFILE"
        or imageDownload.state == "DOWNLOADING_ROOTFS" or imageDownload.state == "DOWNLOADING_TEMPLATE"
        or imageDownload.state == "EXPANDING_IMAGE" or imageDownload.state == "PREPARING_ROOTFS"
        or imageDownload.state == "EXTRACTING_ROOTFS" then
        setNotice("DEBIAN SETUP IS ALREADY RUNNING")
        return
    end
    if appRoot == "" then
        setNotice("COMET DESK APP RUNNER PATH UNAVAILABLE")
        return
    end
    local item = storageItem(selectedSlot)
    if not item or item.status ~= "MOUNTED" then
        setNotice(selectedSlot:upper() .. " NOT DETECTED")
        return
    end
    if not item.stats or item.stats.read_only or not item.stats.free_bytes then
        setNotice(selectedSlot:upper() .. " NOT WRITABLE OR SPACE UNKNOWN")
        return
    end
    local installedHere = imageDownload.state == "READY"
        and installedSlot == selectedSlot and imageDownload.profile == selectedProfile
    if installedHere then
        local request = appRoot .. "/data/desktop-session.request"
        local temporary = request .. ".tmp"
        local stream = io.open(temporary, "w")
        if not stream then
            setNotice("COULD NOT CREATE DESKTOP SESSION REQUEST")
            return
        end
        stream:write(selectedSlot, "\n", selectedProfile, "\n")
        stream:close()
        if not os.rename(temporary, request) then
            os.remove(temporary)
            setNotice("COULD NOT QUEUE DESKTOP SESSION")
            return
        end
        setNotice("COMET STARTING " .. selectedProfile:upper())
        love.event.quit()
        return
    end
    local script = appRoot .. "/service/desktop_environment.py"
    local command = "cd " .. shellQuote(appRoot) .. " && python3 "
        .. shellQuote(script) .. " setup --slot " .. selectedSlot
        .. " --profile " .. selectedProfile
        .. " --app-dir " .. shellQuote(appRoot)
        .. " >> " .. shellQuote(appRoot .. "/data/desktop-environment.log")
        .. " 2>&1 &"
    local result = os.execute(command)
    if result == 0 or result == true then
        imageDownload.state = "STARTING"
        imageDownload.percent = 0
        imageDownload.profile = selectedProfile
        imageDownload.message = "Preparing Debian Trixie // " .. selectedProfile
        setNotice("DEBIAN APT SETUP // " .. selectedProfile:upper())
    else
        setNotice("COULD NOT START DEBIAN ENVIRONMENT MANAGER")
    end
end

local function toggleQuickPanel()
    quickPanelOpen = not quickPanelOpen
    quickPanelAge = 0
end

local function maybeExitKeyboard()
    if keyboardHeld.start and keyboardHeld.select and not exitRequested then
        exitRequested = true
        love.event.quit()
    end
end

function love.keypressed(key)
    if not boot.done then
        boot.done = true
        pageChangedAt = ambientTime
        setNotice("SYSTEM READY // COMET DESK")
        return
    end
    if key == "f9" then keyboardHeld.start = true; maybeExitKeyboard(); return end
    if key == "pageup" then cyclePage(-1); return end
    if key == "pagedown" then cyclePage(1); return end
    if key == "f8" then keyboardHeld.select = true; maybeExitKeyboard(); return end
    if key == "m" then toggleQuickPanel(); return end
    if activePage == 5 and forgeSearchActive then
        if key == "escape" then forgeSearchActive = false
        elseif key == "backspace" then forgeSearch = forgeSearch:sub(1, math.max(0, #forgeSearch - 1)) end
        return
    end
    if quickPanelOpen then
        if key == "escape" or key == "backspace" then toggleQuickPanel() end
        return
    end

    if key == "/" and activePage == 5 then
        forgeSearchActive = true
        setNotice("THE FORGE SEARCH // TYPE TO FILTER")
    elseif key == "up" or key == "w" then
        if activePage == 2 then cycleDesktopProfile(-1)
        elseif activePage == 5 then forgeSelectedIndex = math.max(1, forgeSelectedIndex - 1)
        else cyclePage(-1) end
    elseif key == "down" or key == "s" then
        if activePage == 2 then cycleDesktopProfile(1)
        elseif activePage == 5 then forgeSelectedIndex = math.min(#forgeFilteredPackages(), forgeSelectedIndex + 1)
        else cyclePage(1) end
    elseif key == "left" or key == "a" then
        if activePage == 2 then selectedSlot = "tf1"
        elseif activePage == 5 then cycleForgeCategory(-1) end
    elseif key == "right" or key == "d" then
        if activePage == 2 then selectedSlot = "tf2"
        elseif activePage == 5 then cycleForgeCategory(1) end
    elseif key == "return" or key == "space" or key == "z" or key == "i" then
        if activePage == 2 then startDesktopEnvironment()
        elseif activePage == 5 then
            local item = forgeFilteredPackages()[forgeSelectedIndex]
            if item and item.available and not item.installed then queueForgeAction("install", item.package)
            elseif item and item.installed then setNotice(item.title .. " IS ALREADY INSTALLED") end
        elseif activePage == 4 then
            if uplinkStatus.tailscale and uplinkStatus.tailscale.installed then
                queueUplinkAction(uplinkStatus.tailscale.online and "status" or "start")
            else
                queueUplinkAction("install")
            end
        else activate() end
    elseif key == "r" and activePage == 5 then
        local item = forgeFilteredPackages()[forgeSelectedIndex]
        if item and item.installed then
            if forgeConfirmRemove == item.package then
                queueForgeAction("remove", item.package)
                forgeConfirmRemove = nil
            else
                forgeConfirmRemove = item.package
                setNotice("PRESS R AGAIN TO REMOVE " .. item.package)
            end
        end
    elseif key == "y" and activePage == 5 then
        queueForgeAction("update")
    elseif key == "e" or key == "y" then
        exportDiagnostics()
    elseif key == "escape" or key == "x" or key == "backspace" then
        activePage = 1
        selected = 1
        carouselTarget = 1
        pageChangedDirection = 1
        pageChangedAt = ambientTime
        setNotice("RETURNED TO OVERVIEW")
    end
end

function love.textinput(value)
    if activePage == 5 and forgeSearchActive then
        if #forgeSearch < 40 then forgeSearch = forgeSearch .. value end
    end
end

function love.keyreleased(key)
    if key == "f9" then keyboardHeld.start = false end
    if key == "f8" then keyboardHeld.select = false end
end

function love.gamepadpressed(joystick, button)
    gamepadHeld[joystick] = gamepadHeld[joystick] or {}
    if button == "start" then gamepadHeld[joystick].start = true end
    if button == "back" or button == "select" then gamepadHeld[joystick].select = true end
    if gamepadHeld[joystick].start and gamepadHeld[joystick].select and not exitRequested then
        exitRequested = true
        love.event.quit()
        return
    end
    if not boot.done then
        boot.done = true
        pageChangedAt = ambientTime
        setNotice("SYSTEM READY // COMET DESK")
        return
    end
    if button == "guide" then
        toggleQuickPanel()
        return
    end
    if quickPanelOpen then
        if button == "b" or button == "back" then toggleQuickPanel() end
        return
    end

    if button == "dpup" then
        if activePage == 2 then cycleDesktopProfile(-1)
        elseif activePage == 5 then forgeSelectedIndex = math.max(1, forgeSelectedIndex - 1)
        else love.keypressed("up") end
    elseif button == "dpdown" then
        if activePage == 2 then cycleDesktopProfile(1)
        elseif activePage == 5 then forgeSelectedIndex = math.min(#forgeFilteredPackages(), forgeSelectedIndex + 1)
        else love.keypressed("down") end
    elseif button == "leftshoulder" then
        cyclePage(-1)
    elseif button == "rightshoulder" then
        cyclePage(1)
    elseif button == "dpleft" and activePage == 2 then
        selectedSlot = "tf1"
    elseif button == "dpright" and activePage == 2 then
        selectedSlot = "tf2"
    elseif button == "dpleft" and activePage == 5 then
        cycleForgeCategory(-1)
    elseif button == "dpright" and activePage == 5 then
        cycleForgeCategory(1)
    elseif button == "a" then
        if activePage == 2 then
            startDesktopEnvironment()
        elseif activePage == 5 then
            local item = forgeFilteredPackages()[forgeSelectedIndex]
            if item and item.available and not item.installed then queueForgeAction("install", item.package)
            elseif item and item.installed then setNotice(item.title .. " IS ALREADY INSTALLED") end
        else
            activate()
        end
    elseif button == "x" and activePage == 5 then
        local item = forgeFilteredPackages()[forgeSelectedIndex]
        if item and item.installed then
            if forgeConfirmRemove == item.package then
                queueForgeAction("remove", item.package)
                forgeConfirmRemove = nil
            else
                forgeConfirmRemove = item.package
                setNotice("PRESS X AGAIN TO REMOVE " .. item.package)
            end
        end
    elseif button == "y" and activePage == 5 then
        queueForgeAction("update")
    elseif button == "y" then
        exportDiagnostics()
    elseif button == "b" or button == "back" then
        love.keypressed("escape")
    end
end

function love.gamepadreleased(joystick, button)
    local held = gamepadHeld[joystick]
    if not held then return end
    if button == "start" then held.start = false end
    if button == "back" or button == "select" then held.select = false end
end
