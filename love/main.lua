-- COMET DESK // QWASAR
-- Controller-first muOS companion. Desktop downloads use a pinned helper;
-- the app never installs downloaded MUX packages or changes host firmware.

local W, H = 640, 480
local pages = {
    { id = "overview", title = "OVERVIEW", subtitle = "Your handheld. Your workspace. No OS drama." },
    { id = "setup", title = "DESKTOP SETUP", subtitle = "Download a verified desktop manager package." },
    { id = "sessions", title = "SESSION MANAGER", subtitle = "Discover and launch installed desktop sessions." },
    { id = "tools", title = "SYSTEM TOOLS", subtitle = "Small utilities for storage and system services." },
    { id = "diagnostics", title = "DIAGNOSTICS", subtitle = "Read-only checks for your device and runtime." },
}

local selected, activePage = 1, 1
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
local download = { state = "IDLE", percent = 0, message = "Ready to download", location = "" }
local downloadPoll = 0

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
    if visuals.atlas and visuals.quads.app then
        love.graphics.setColor(1, 1, 1, 1)
        love.graphics.draw(visuals.atlas, visuals.quads.app, 22, 34, 0, 0.65, 0.65)
    end
    text("QWASAR  /  FIELD SYSTEMS", 68, 17, fonts.small, colors.muted)
    text("COMET", 68, 36, fonts.title, colors.white)
    text("DESK", 177, 42, fonts.medium, colors.cyan)
    text("MUX COMPANION  //  BUILD 0.2.0-dev", 68, 77, fonts.tiny, colors.muted)
    rounded(482, 22, 132, 42, colors.panel, colors.line)
    text("RG35XX H TARGET", 495, 28, fonts.small, colors.cyan)
    local probeStatus = device.handheld ~= "Unknown" and "LIVE PROBE OK" or "PROBE PARTIAL"
    text(probeStatus, 495, 45, fonts.tiny,
        device.handheld ~= "Unknown" and colors.green or colors.amber)
end

local function drawNavigation()
    rounded(20, 108, 190, 302, colors.panel, colors.line)
    text("NAVIGATION", 34, 122, fonts.small, colors.muted)
    for i, page in ipairs(pages) do
        local y = 151 + (i - 1) * 47
        local active = (i == selected)
        if active then
            local pulse = 0.58 + 0.20 * (0.5 + 0.5 * math.sin(ambientTime * 3.2))
            rounded(28, y - 5, 174, 39, colors.panel2,
                { colors.cyan[1], colors.cyan[2], colors.cyan[3], pulse })
            love.graphics.setColor(colors.cyan)
            love.graphics.rectangle("fill", 28, y + 5, 3, 18, 2, 2)
        end
        local pageIcon = visuals.quads[page.id]
        if visuals.atlas and pageIcon then
            love.graphics.setColor(1, 1, 1, active and 1 or 0.66)
            love.graphics.draw(visuals.atlas, pageIcon, 38, y + 2, 0, 0.38, 0.38)
        else
            text(string.format("%02d", i), 40, y + 4, fonts.small,
                active and colors.cyan or colors.muted)
        end
        text(page.title, 69, y + 4, fonts.small,
            active and colors.white or colors.muted)
    end
    text("A  SELECT     B  BACK", 34, 383, fonts.tiny, colors.muted)
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
    local page = pages[activePage]
    text(page.subtitle, 235, 127, fonts.small, colors.muted)
    rounded(230, 157, 390, 148, colors.panel, colors.line)
    text("LIVE DEVICE SNAPSHOT", 248, 174, fonts.small, colors.cyan)
    text("Handheld", 248, 202, fonts.small, colors.muted)
    text(short(device.handheld, 31), 370, 202, fonts.small, colors.white)
    text("SoC / architecture", 248, 226, fonts.small, colors.muted)
    text(short(device.soc .. " / " .. device.architecture, 34), 370, 226, fonts.tiny, colors.white)
    text("Firmware", 248, 250, fonts.small, colors.muted)
    text(short(device.firmware, 31), 370, 250, fonts.small, colors.white)
    text("RAM", 248, 274, fonts.small, colors.muted)
    text(device.memory_mb and (tostring(device.memory_mb) .. " MB") or "Unknown",
        370, 274, fonts.small, colors.white)

    rounded(230, 318, 390, 92, colors.panel, colors.line)
    text("STORAGE PRESENCE", 248, 332, fonts.small, colors.violet)
    local tf1, tf2 = storageItem("tf1"), storageItem("tf2")
    text(storageLine("TF1", tf1), 248, 356, fonts.tiny,
        tf1 and tf1.status == "MOUNTED" and colors.green or colors.amber)
    text(storageLine("TF2", tf2), 248, 374, fonts.tiny,
        tf2 and tf2.status == "MOUNTED" and colors.green or colors.muted)
    text("Free space from statvfs // read-only", 248, 392, fonts.tiny, colors.muted)
end

local function drawSetup()
    text(pages[activePage].subtitle, 235, 127, fonts.small, colors.muted)
    rounded(230, 157, 390, 253, colors.panel, colors.line)
    text("VOID DESK // DESKTOP INSTALLER", 248, 174, fonts.small, colors.cyan)
    text("Stable release  v10.2.0", 248, 197, fonts.medium, colors.white)
    text("Download the official muOS package into ARCHIVE.", 248, 222, fonts.tiny, colors.muted)
    text("DESTINATION SLOT", 248, 247, fonts.tiny, colors.violet)

    local function targetCard(slot, x, label)
        local item = storageItem(slot)
        local usable = storageUsable(slot)
        local active = selectedSlot == slot
        rounded(x, 266, 166, 49, active and colors.panel2 or colors.bg,
            active and colors.cyan or colors.line)
        text(label, x + 12, 273, fonts.small, active and colors.white or colors.muted)
        local state = item and item.status == "MOUNTED" and item.stats
            and (item.stats.read_only and "READ ONLY" or formatBytes(item.stats.free_bytes) .. " FREE")
            or "NOT DETECTED"
        text(state, x + 12, 292, fonts.tiny, usable and colors.green or colors.amber)
    end
    targetCard("tf1", 248, "TF1  /  LEFT")
    targetCard("tf2", 424, "TF2  /  RIGHT")

    local stateColor = colors.cyan
    if download.state == "DONE" then stateColor = colors.green
    elseif download.state == "FAILED" then stateColor = colors.amber
    elseif download.state == "DOWNLOADING" or download.state == "CHECKING" then stateColor = colors.violet end
    text("DOWNLOAD STATUS  //  " .. download.state, 248, 329, fonts.tiny, stateColor)
    text(short(download.message, 48), 248, 346, fonts.tiny, colors.white)
    drawProgress(248, 365, 354, 12, download.percent, stateColor)
    if download.state == "DONE" then
        text("NEXT: Applications  >  Archive Manager", 248, 387, fonts.tiny, colors.green)
    else
        text("A / ENTER  DOWNLOAD     LEFT / RIGHT  TARGET", 248, 387, fonts.tiny, colors.cyan)
    end
end

local function drawDiagnostics()
    text(pages[activePage].subtitle, 235, 127, fonts.small, colors.muted)
    rounded(230, 157, 390, 253, colors.panel, colors.line)
    text("DEVICE IDENTITY", 248, 174, fonts.small, colors.cyan)
    local rows = {
        { "Handheld", device.handheld },
        { "SoC", device.soc },
        { "Architecture", device.architecture },
        { "RAM", device.memory_mb and (tostring(device.memory_mb) .. " MB") or "Unknown" },
        { "Firmware", device.firmware },
    }
    for i, item in ipairs(rows) do
        local y = 202 + (i - 1) * 29
        text(item[1], 248, y, fonts.small, colors.muted)
        text(short(item[2], 34), 370, y, fonts.small, colors.white)
    end
    text("STORAGE MOUNTS", 248, 351, fonts.small, colors.violet)
    local tf1, tf2 = storageItem("tf1") or {}, storageItem("tf2") or {}
    text(storageLine("TF1", tf1) .. "  [" .. short(tf1.filesystem, 8) .. "]",
        248, 375, fonts.tiny, colors.white)
    text(storageLine("TF2", tf2) .. "  [" .. short(tf2.filesystem, 8) .. "]",
        248, 392, fonts.tiny, colors.white)
    text("Y / E  EXPORT PRIVACY-SAFE REPORT", 248, 402, fonts.tiny, colors.cyan)
end

local function drawModule()
    local page = pages[activePage]
    text(page.subtitle, 235, 127, fonts.small, colors.muted)
    rounded(230, 157, 390, 172, colors.panel, colors.line)
    text(page.title, 250, 178, fonts.medium, colors.white)
    text("MODULE STATUS", 250, 220, fonts.tiny, colors.muted)
    text("NOT IMPLEMENTED", 250, 243, fonts.large, colors.amber)
    text("This panel is a roadmap entry, not a fake control.", 250, 282, fonts.tiny, colors.muted)
    rounded(230, 343, 390, 67, colors.panel2, colors.line)
    text("Available in a later verified build.", 250, 367, fonts.small, colors.cyan)
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
    text("v0.2.0", 574, 441, fonts.tiny, colors.muted)
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
    text("DESKTOP PACKAGE  //  " .. download.state, x + 24, y + 104, fonts.small, colors.violet)
    text(short(download.message, 54), x + 24, y + 127, fonts.tiny, colors.muted)
    drawProgress(x + 24, y + 153, 468, 12, download.percent, colors.cyan)
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

local function readDownloadStatus()
    if appRoot == "" then return end
    local statusFile = io.open(appRoot .. "/data/desktop-download.status", "r")
    if not statusFile then return end
    local line = statusFile:read("*l")
    statusFile:close()
    local state, percent, message, location = line and line:match("^([^|]+)|(%d+)|([^|]*)|(.*)$")
    if not state then return end
    download.state = state
    download.percent = tonumber(percent) or 0
    download.message = message
    download.location = location or ""
    if state == "DONE" and download._notice ~= "DONE" then
        setNotice("DESKTOP PACKAGE VERIFIED // ARCHIVE MANAGER NEXT")
    elseif state == "FAILED" and download._notice ~= "FAILED" then
        setNotice("DOWNLOAD FAILED // CHECK MESSAGE")
    end
    download._notice = state
end

function love.update(dt)
    ambientTime = ambientTime + dt
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
        readDownloadStatus()
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
    local transition = math.min(1, math.max(0, (ambientTime - pageChangedAt) / 0.22))
    love.graphics.push()
    love.graphics.translate((1 - transition) * 13, 0)
    if activePage == 1 then drawOverview()
    elseif activePage == 2 then drawSetup()
    elseif activePage == 5 then drawDiagnostics()
    else drawModule() end
    love.graphics.pop()
    drawFooter()
    drawQuickPanel()
    love.graphics.pop()
end

local function exportDiagnostics()
    if activePage ~= 5 then
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

local function activate()
    activePage = selected
    pageChangedAt = ambientTime
    if activePage == 1 then
        setNotice("OVERVIEW // READ-ONLY")
    elseif activePage == 2 then
        setNotice("DESKTOP SETUP // VERIFIED DOWNLOAD")
    else
        setNotice(pages[activePage].title .. " // COMING SOON")
    end
end

local function shellQuote(value)
    return "'" .. tostring(value):gsub("'", "'\\''") .. "'"
end

local function startDesktopDownload()
    if download.state == "STARTING" or download.state == "CHECKING"
        or download.state == "DOWNLOADING" then
        setNotice("DOWNLOAD ALREADY RUNNING")
        return
    end
    if appRoot == "" then
        setNotice("DOWNLOAD REQUIRES THE MUOS APP RUNNER")
        return
    end
    local item = storageItem(selectedSlot)
    if not item or item.status ~= "MOUNTED" then
        setNotice(selectedSlot:upper() .. " NOT DETECTED")
        return
    end
    if not item.stats or item.stats.read_only then
        setNotice(selectedSlot:upper() .. " NOT WRITABLE OR SPACE UNKNOWN")
        return
    end
    local pythonCheck = os.execute("command -v python3 >/dev/null 2>&1")
    if pythonCheck ~= 0 and pythonCheck ~= true then
        setNotice("PYTHON 3 NOT AVAILABLE ON HOST")
        return
    end
    local script = appRoot .. "/service/desktop_download.py"
    local command = "cd " .. shellQuote(appRoot) .. " && python3 "
        .. shellQuote(script) .. " --slot " .. selectedSlot
        .. " >/dev/null 2>&1 &"
    local result = os.execute(command)
    if result == 0 or result == true then
        download.state = "STARTING"
        download.percent = 0
        download.message = "Starting checksum-verified download"
        setNotice("DOWNLOAD STARTED // " .. selectedSlot:upper() .. "/ARCHIVE")
    else
        setNotice("COULD NOT START DOWNLOAD HELPER")
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
        if activePage == 2 then startDesktopDownload() else activate() end
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

    if button == "dpup" or button == "leftshoulder" then
        love.keypressed("up")
    elseif button == "dpdown" or button == "rightshoulder" then
        love.keypressed("down")
    elseif button == "dpleft" and activePage == 2 then
        selectedSlot = "tf1"
    elseif button == "dpright" and activePage == 2 then
        selectedSlot = "tf2"
    elseif button == "a" then
        if activePage == 2 then startDesktopDownload() else activate() end
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
