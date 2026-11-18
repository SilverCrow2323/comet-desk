-- COMET DESK // QWASAR
-- Lightweight LÖVE shell. This prototype is intentionally read-only:
-- no installer, shell execution, or filesystem mutation is connected.

local W, H = 640, 480
local pages = {
    { id = "overview", title = "OVERVIEW", subtitle = "Your handheld. Your workspace. No OS drama." },
    { id = "setup", title = "DESKTOP SETUP", subtitle = "Prepare a desktop environment on a separate target." },
    { id = "sessions", title = "SESSION MANAGER", subtitle = "Discover and launch installed desktop sessions." },
    { id = "tools", title = "SYSTEM TOOLS", subtitle = "Small utilities for storage and system services." },
    { id = "diagnostics", title = "DIAGNOSTICS", subtitle = "Read-only checks for your device and runtime." },
}

local selected = 1
local activePage = 1
local notice = "SYSTEM READY // PROTOTYPE MODE"
local noticeTimer = 0
local fonts = {}
local visuals = { background = nil, atlas = nil, quads = {} }
local probe = nil
local diagnosticReport = nil
local device = { handheld = "Unknown", soc = "Unknown", architecture = "Unknown", firmware = "Unknown", storage = {} }
local probeTimer = 0
local theme = require("theme")
local colors = theme.colors

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

local function drawBackground()
    love.graphics.clear(colors.bg[1], colors.bg[2], colors.bg[3], 1)
    if visuals.background then
        love.graphics.setColor(1, 1, 1, 1)
        love.graphics.draw(visuals.background, 0, 0, 0, 2, 2)
    end
    love.graphics.setColor(0.07, 0.12, 0.18, 0.32)
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
    text("MUX COMPANION  //  BUILD 0.1.0-dev", 68, 77, fonts.tiny, colors.muted)
    rounded(482, 22, 132, 42, colors.panel, colors.line)
    text("RG35XX H TARGET", 495, 28, fonts.small, colors.cyan)
    local probeStatus = device.handheld ~= "Unknown" and "LIVE PROBE OK" or "PROBE PARTIAL"
    text(probeStatus, 495, 45, fonts.tiny, device.handheld ~= "Unknown" and colors.green or colors.amber)
end

local function drawNavigation()
    rounded(20, 108, 190, 302, colors.panel, colors.line)
    text("NAVIGATION", 34, 122, fonts.small, colors.muted)
    for i, page in ipairs(pages) do
        local y = 151 + (i - 1) * 47
        local active = (i == selected)
        if active then
            rounded(28, y - 5, 174, 39, colors.panel2, { colors.cyan[1], colors.cyan[2], colors.cyan[3], 0.8 })
            love.graphics.setColor(colors.cyan)
            love.graphics.rectangle("fill", 28, y + 5, 3, 18, 2, 2)
        end
        local pageIcon = visuals.quads[page.id]
        if visuals.atlas and pageIcon then
            love.graphics.setColor(1, 1, 1, active and 1 or 0.66)
            love.graphics.draw(visuals.atlas, pageIcon, 38, y + 2, 0, 0.38, 0.38)
        else
            text(string.format("%02d", i), 40, y + 4, fonts.small, active and colors.cyan or colors.muted)
        end
        text(page.title, 69, y + 4, fonts.small, active and colors.white or colors.muted)
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

local function storageLine(label, item)
    if not item or item.status ~= "MOUNTED" then
        return label .. "  NOT DETECTED"
    end
    local stats = item.stats
    if not stats then return label .. "  MOUNTED // SPACE N/A" end
    local access = stats.read_only and "RO" or "RW"
    return string.format("%s  %s FREE / %s  %s", label, formatBytes(stats.free_bytes), formatBytes(stats.total_bytes), access)
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
    text(device.memory_mb and (tostring(device.memory_mb) .. " MB") or "Unknown", 370, 274, fonts.small, colors.white)

    rounded(230, 318, 390, 92, colors.panel, colors.line)
    text("STORAGE PRESENCE", 248, 332, fonts.small, colors.violet)
    local tf1 = device.storage and device.storage.tf1 or nil
    local tf2 = device.storage and device.storage.tf2 or nil
    text(storageLine("TF1", tf1), 248, 356, fonts.tiny, tf1 and tf1.status == "MOUNTED" and colors.green or colors.amber)
    text(storageLine("TF2", tf2), 248, 374, fonts.tiny, tf2 and tf2.status == "MOUNTED" and colors.green or colors.muted)
    text("Free space from statvfs // read-only", 248, 392, fonts.tiny, colors.muted)
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
    local tf1 = device.storage and device.storage.tf1 or {}
    local tf2 = device.storage and device.storage.tf2 or {}
    text(storageLine("TF1", tf1) .. "  [" .. short(tf1.filesystem, 8) .. "]", 248, 375, fonts.tiny, colors.white)
    text(storageLine("TF2", tf2) .. "  [" .. short(tf2.filesystem, 8) .. "]", 248, 392, fonts.tiny, colors.white)
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

local function drawFooter()
    setColor(colors.line)
    love.graphics.line(20, 425, 620, 425)
    local label = notice
    if noticeTimer <= 0 then label = "QWASAR ECOSYSTEM  //  VOID DESK EXPERIENCE, COMET-SIZED" end
    text(label, 24, 441, fonts.tiny, noticeTimer > 0 and colors.cyan or colors.muted)
    text("v0.1.0", 574, 441, fonts.tiny, colors.muted)
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
        if success and snapshot then device = snapshot end
    end
end

function love.update(dt)
    if noticeTimer > 0 then noticeTimer = math.max(0, noticeTimer - dt) end
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
    drawBackground()
    drawHeader()
    drawNavigation()
    if activePage == 1 then drawOverview()
    elseif activePage == 5 then drawDiagnostics()
    else drawModule() end
    drawFooter()
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
    if activePage == 1 then
        setNotice("OVERVIEW // READ-ONLY")
    else
        setNotice(pages[activePage].title .. " // COMING SOON")
    end
end

function love.keypressed(key)
    if key == "up" or key == "w" then
        selected = ((selected - 2) % #pages) + 1
    elseif key == "down" or key == "s" then
        selected = (selected % #pages) + 1
    elseif key == "return" or key == "space" or key == "z" then
        activate()
    elseif key == "e" or key == "y" then
        exportDiagnostics()
    elseif key == "escape" or key == "x" or key == "backspace" then
        activePage = 1
        selected = 1
        setNotice("RETURNED TO OVERVIEW")
    end
end

function love.gamepadpressed(_, button)
    if button == "dpup" or button == "leftshoulder" then
        love.keypressed("up")
    elseif button == "dpdown" or button == "rightshoulder" then
        love.keypressed("down")
    elseif button == "a" or button == "start" then
        activate()
    elseif button == "y" then
        exportDiagnostics()
    elseif button == "b" or button == "back" then
        love.keypressed("escape")
    end
end
