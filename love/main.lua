-- COMET DESK // QWASAR
-- Controller-first muOS companion. Desktop Setup retrieves the dedicated Void Desk OS
-- disk image only; it never downloads or installs the Void Desk MUX application.

local W, H = 640, 480
local pages = {
    { id = "overview", title = "OVERVIEW", subtitle = "Your handheld. Your workspace. No OS drama.", icon = "◈", accent = {0.22, 0.88, 0.94} },
    { id = "setup", title = "DESKTOP SETUP", subtitle = "Prepare and launch your XFCE environment.", icon = "▣", accent = {0.62, 0.43, 0.98} },
    { id = "sessions", title = "SESSION MANAGER", subtitle = "Discover and launch installed desktop sessions.", icon = "▤", accent = {1.0, 0.72, 0.32} },
    { id = "uplink", title = "UPLINK", subtitle = "Network, wireless radios and remote services.", icon = "◎", accent = {0.24, 0.72, 1.0} },
    { id = "tools", title = "SYSTEM TOOLS", subtitle = "Small utilities for storage and system services.", icon = "⚙", accent = {0.35, 0.90, 0.68} },
    { id = "diagnostics", title = "DIAGNOSTICS", subtitle = "Read-only checks for your device and runtime.", icon = "⌁", accent = {0.96, 0.30, 0.70} },
}

local selected, activePage = 1, 1
local carouselPosition = 1
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
local imageDownload = { state = "NOT_INSTALLED", percent = 0, message = "XFCE environment not installed", location = "" }
local downloadPoll = 0
local uplinkStatus = { wifi = {}, bluetooth = {}, hotspot = {}, services = {}, tailscale = {} }
local uplinkPoll = 0

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
    text("MUX CONTROL DECK  //  v0.3.0-dev", 67, 70, fonts.tiny, colors.muted)

    rounded(438, 17, 182, 56, colors.panel, colors.line)
    text("RG35XX H  //  H700", 451, 25, fonts.small, colors.cyan)
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
        local raw = carouselPosition + offset
        local index = ((math.floor(raw + 0.5) - 1) % #pages) + 1
        local fraction = raw - math.floor(raw)
        local x = W * 0.5 + offset * 108 - fraction * 108
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
            text(page.icon, px + 9, py + 10, fonts.medium, {tint[1], tint[2], tint[3], alpha})
            local label = page.id == "setup" and "DESKTOP" or page.title:gsub("SESSION MANAGER", "SESSIONS"):gsub("SYSTEM TOOLS", "TOOLS")
            text(label, px + 30, py + 15, fonts.tiny, {colors.white[1], colors.white[2], colors.white[3], alpha})
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
    text(pages[activePage].subtitle, 24, 158, fonts.small, colors.muted)
    rounded(20, 183, 600, 232, colors.panel, colors.line)

    text("VOID DESK  /  XFCE ENVIRONMENT", 38, 199, fonts.small, colors.cyan)
    text("Ubuntu Base 24.04 ARM64", 38, 222, fonts.medium, colors.white)
    text("XFCE + Xorg tuned for the RG35XX H framebuffer", 38, 246, fonts.tiny, colors.muted)
    text("Comet downloads, prepares, mounts and launches this environment.", 38, 263, fonts.tiny, colors.muted)

    text("INSTALL TARGET", 38, 292, fonts.tiny, colors.violet)
    local function targetCard(slot, x, label)
        local item = storageItem(slot)
        local usable = storageUsable(slot)
        local active = selectedSlot == slot
        rounded(x, 309, 162, 52, active and colors.panel2 or colors.bg,
            active and colors.cyan or colors.line)
        text(label, x + 12, 316, fonts.small, active and colors.white or colors.muted)
        local state = item and item.status == "MOUNTED" and item.stats
            and (item.stats.read_only and "READ ONLY" or formatBytes(item.stats.free_bytes) .. " FREE")
            or "NOT DETECTED"
        text(state, x + 12, 338, fonts.tiny, usable and colors.green or colors.amber)
    end
    targetCard("tf1", 38, "TF1  /  LEFT")
    targetCard("tf2", 210, "TF2  /  RIGHT")

    rounded(391, 197, 211, 201, colors.panel2, colors.line)
    text("DESKTOP CONTROL", 408, 213, fonts.small, colors.violet)
    local stateColor = colors.cyan
    if imageDownload.state == "READY" then stateColor = colors.green
    elseif imageDownload.state == "FAILED" or imageDownload.state == "CLEANUP_REQUIRED" then
        stateColor = colors.amber
    elseif imageDownload.state ~= "NOT_INSTALLED" then
        stateColor = colors.violet
    end
    local statusLabel = imageDownload.state
    if imageDownload.state == "READY" and installedSlot and installedSlot ~= selectedSlot then
        statusLabel = "INSTALLED ON " .. installedSlot:upper()
        stateColor = colors.amber
    end
    text(statusLabel, 408, 244, fonts.medium, stateColor)
    text(short(imageDownload.message, 29), 408, 271, fonts.tiny, colors.white)
    drawProgress(408, 294, 175, 12, imageDownload.percent, stateColor)
    text(string.format("%d%%  COMPLETE", imageDownload.percent), 408, 316, fonts.tiny, colors.muted)
    if imageDownload.state == "READY" and installedSlot == selectedSlot then
        text("A  LAUNCH XFCE", 408, 349, fonts.small, colors.green)
        text("B  RETURN TO COMET", 408, 370, fonts.tiny, colors.muted)
    elseif imageDownload.state == "READY" and installedSlot then
        text("A  INSTALL ON " .. selectedSlot:upper(), 408, 349, fonts.small, colors.cyan)
        text("Current image: " .. installedSlot:upper(), 408, 370, fonts.tiny, colors.muted)
    elseif imageDownload.state == "INSTALLING_XFCE" or imageDownload.state == "DOWNLOADING_ROOTFS"
        or imageDownload.state == "DOWNLOADING_TEMPLATE" or imageDownload.state == "EXPANDING_IMAGE"
        or imageDownload.state == "PREPARING_ROOTFS" or imageDownload.state == "EXTRACTING_ROOTFS" then
        text("BUILDING  //  KEEP POWER ON", 408, 349, fonts.tiny, colors.violet)
        text("Comet is working in the background", 408, 370, fonts.tiny, colors.muted)
    elseif imageDownload.state == "FAILED" then
        text("CHECK DESKTOP LOG", 408, 349, fonts.tiny, colors.amber)
        text("Retry with A after review", 408, 370, fonts.tiny, colors.muted)
    else
        text("A  INSTALL XFCE", 408, 349, fonts.small, colors.cyan)
        text("LEFT / RIGHT  SELECT CARD", 408, 370, fonts.tiny, colors.muted)
    end
end


local function queueUplinkAction(action)
    if appRoot == "" then setNotice("COMET APP PATH UNAVAILABLE"); return end
    local script = appRoot .. "/service/uplink_status.py"
    local command = "cd " .. shellQuote(appRoot) .. " && python3 " .. shellQuote(script)
        .. " " .. shellQuote(appRoot) .. " " .. action
        .. " >> " .. shellQuote(appRoot .. "/data/uplink.log") .. " 2>&1 &"
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
    text(ts.installed and (tostring(ts.peers or 0) .. " PEERS  ·  " .. (ts.ip or "NO TAILNET IP"))
        or "A  INSTALL RT:TAILSCALE-M", 38, 394, fonts.tiny, ts.installed and colors.white or tint)
    text(ts.installed and "Y  REFRESH" or "Y  REFRESH", 506, 394, fonts.tiny, colors.muted)
    if uplinkStatus.error then text(short(uplinkStatus.error, 72), 38, 410, fonts.tiny, colors.amber) end
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
    text(label, 24, 441, fonts.tiny, noticeTimer > 0 and colors.cyan or colors.muted)
    text("v0.4.0", 574, 441, fonts.tiny, colors.muted)
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
    text("VOID DESK OS IMAGE  //  " .. imageDownload.state, x + 24, y + 104, fonts.small, colors.violet)
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
    fonts.tiny = loadFont(theme.fonts.telemetry, 10, 10)
    fonts.small = loadFont(theme.fonts.interface, 12, 12)
    fonts.medium = loadFont(theme.fonts.display, 15, 15)
    fonts.large = loadFont(theme.fonts.display, 21, 21)
    fonts.title = loadFont(theme.fonts.display, 32, 32)

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
    local state, percent, message, location = line and line:match("^([^|]+)|(%d+)|([^|]*)|(.*)$")
    if not state then return end
    imageDownload.state = state
    imageDownload.percent = tonumber(percent) or 0
    imageDownload.message = message
    imageDownload.location = location or ""
    if location and location:find("/mnt/mmc/", 1, true) then
        installedSlot = "tf1"
    elseif location and location:find("/mnt/sdcard/", 1, true) then
        installedSlot = "tf2"
    end
    if state == "READY" and imageDownload._notice ~= "READY" then
        setNotice("XFCE ENVIRONMENT READY // A TO LAUNCH")
    elseif state == "RUNNING" and imageDownload._notice ~= "RUNNING" then
        setNotice("VOID DESK XFCE SESSION RUNNING")
    elseif state == "FAILED" and imageDownload._notice ~= "FAILED" then
        setNotice("DESKTOP SETUP FAILED // CHECK MESSAGE")
    elseif state == "CLEANUP_REQUIRED" then
        setNotice("DESKTOP MOUNT CLEANUP NEEDS ATTENTION")
    end
    imageDownload._notice = state
end

function love.update(dt)
    ambientTime = ambientTime + dt
    local delta = selected - carouselPosition
    if delta > #pages / 2 then delta = delta - #pages end
    if delta < -#pages / 2 then delta = delta + #pages end
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
    local transition = math.min(1, math.max(0, (ambientTime - pageChangedAt) / 0.34))
    love.graphics.push()
    love.graphics.translate((1 - transition) * 26 * pageChangedDirection, (1 - transition) * 5)
    local accent = pageAccent(activePage)
    love.graphics.setColor(accent[1], accent[2], accent[3], 0.82)
    love.graphics.rectangle("fill", 20, 202, 3, 212, 1, 1)
    if activePage == 1 then drawOverview()
    elseif activePage == 2 then drawSetup()
    elseif activePage == 4 then drawUplink()
    elseif activePage == 6 then drawDiagnostics()
    else drawModule() end
    love.graphics.pop()
    drawFooter()
    drawQuickPanel()
    love.graphics.pop()
end

local function exportDiagnostics()
    if activePage ~= 6 then
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

local function startDesktopEnvironment()
    if imageDownload.state == "STARTING" or imageDownload.state == "RUNNING"
        or imageDownload.state == "DOWNLOADING_TEMPLATE"
        or imageDownload.state == "DOWNLOADING_ROOTFS"
        or imageDownload.state == "EXPANDING_IMAGE"
        or imageDownload.state == "PREPARING_ROOTFS"
        or imageDownload.state == "EXTRACTING_ROOTFS"
        or imageDownload.state == "INSTALLING_XFCE" then
        setNotice("DESKTOP SETUP IS ALREADY RUNNING")
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
    if imageDownload.state == "READY" and installedSlot == selectedSlot then
        local request = appRoot .. "/data/desktop-session.request"
        local temporary = request .. ".tmp"
        local stream = io.open(temporary, "w")
        if not stream then
            setNotice("COULD NOT CREATE DESKTOP SESSION REQUEST")
            return
        end
        stream:write(selectedSlot, "\n")
        stream:close()
        if not os.rename(temporary, request) then
            os.remove(temporary)
            setNotice("COULD NOT QUEUE DESKTOP SESSION")
            return
        end
        setNotice("COMET DESK HANDING OFF TO ITS XFCE SESSION")
        love.event.quit()
        return
    end
    local script = appRoot .. "/service/desktop_environment.py"
    local command = "cd " .. shellQuote(appRoot) .. " && python3 "
        .. shellQuote(script) .. " setup --slot " .. selectedSlot
        .. " --app-dir " .. shellQuote(appRoot)
        .. " >> " .. shellQuote(appRoot .. "/data/desktop-environment.log")
        .. " 2>&1 &"
    local result = os.execute(command)
    if result == 0 or result == true then
        imageDownload.state = "STARTING"
        imageDownload.percent = 0
        imageDownload.message = "Comet Desk is preparing its own XFCE image"
        setNotice("XFCE SETUP STARTED // " .. selectedSlot:upper())
    else
        setNotice("COULD NOT START INTERNAL DESKTOP SETUP")
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
    if quickPanelOpen then
        if key == "escape" or key == "backspace" then toggleQuickPanel() end
        return
    end

    if key == "up" or key == "w" then
        selected = ((selected - 2) % #pages) + 1
    elseif key == "down" or key == "s" then
        selected = (selected % #pages) + 1
    elseif key == "left" or key == "a" then
        if activePage == 2 then selectedSlot = "tf1" end
    elseif key == "right" or key == "d" then
        if activePage == 2 then selectedSlot = "tf2" end
    elseif key == "return" or key == "space" or key == "z" then
        if activePage == 2 then startDesktopEnvironment() else activate() end
    elseif key == "e" or key == "y" then
        exportDiagnostics()
    elseif key == "escape" or key == "x" or key == "backspace" then
        activePage = 1
        selected = 1
        pageChangedAt = ambientTime
        setNotice("RETURNED TO OVERVIEW")
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
        love.keypressed("up")
    elseif button == "dpdown" then
        love.keypressed("down")
    elseif button == "leftshoulder" then
        cyclePage(-1)
    elseif button == "rightshoulder" then
        cyclePage(1)
    elseif button == "dpleft" and activePage == 2 then
        selectedSlot = "tf1"
    elseif button == "dpright" and activePage == 2 then
        selectedSlot = "tf2"
    elseif button == "a" then
        if activePage == 2 then startDesktopEnvironment() else activate() end
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
