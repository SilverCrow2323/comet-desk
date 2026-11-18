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
local colors = {
    bg = { 0.035, 0.047, 0.075 },
    panel = { 0.065, 0.086, 0.125 },
    panel2 = { 0.085, 0.112, 0.16 },
    line = { 0.16, 0.25, 0.34 },
    cyan = { 0.22, 0.88, 0.94 },
    violet = { 0.62, 0.43, 0.98 },
    white = { 0.91, 0.95, 0.98 },
    muted = { 0.48, 0.59, 0.69 },
    amber = { 1.0, 0.72, 0.32 },
    green = { 0.35, 0.9, 0.68 },
}

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
    love.graphics.setColor(0.07, 0.12, 0.18, 0.45)
    for x = 0, W, 32 do love.graphics.line(x, 0, x, H) end
    for y = 0, H, 32 do love.graphics.line(0, y, W, y) end
    setColor(colors.cyan)
    love.graphics.rectangle("fill", 0, 0, W, 3)
    setColor(colors.violet)
    love.graphics.rectangle("fill", W - 112, 0, 112, 3)
end

local function drawHeader()
    text("QWASAR  /  FIELD SYSTEMS", 24, 17, fonts.small, colors.muted)
    text("COMET", 24, 36, fonts.title, colors.white)
    text("DESK", 133, 42, fonts.medium, colors.cyan)
    text("MUX COMPANION  //  BUILD 0.1.0-dev", 24, 77, fonts.tiny, colors.muted)
    rounded(482, 22, 132, 42, colors.panel, colors.line)
    text("RG35XX H TARGET", 495, 28, fonts.small, colors.cyan)
    text("LIVE PROBE PENDING", 495, 45, fonts.tiny, colors.amber)
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
        text(string.format("%02d", i), 40, y + 4, fonts.small, active and colors.cyan or colors.muted)
        text(page.title, 69, y + 4, fonts.small, active and colors.white or colors.muted)
    end
    text("A  SELECT     B  BACK", 34, 383, fonts.tiny, colors.muted)
end

local function drawOverview()
    local page = pages[activePage]
    text(page.subtitle, 235, 127, fonts.small, colors.muted)
    rounded(230, 157, 390, 112, colors.panel, colors.line)
    text("QUICK STATUS", 248, 174, fonts.small, colors.cyan)
    text("Host OS", 248, 205, fonts.small, colors.muted)
    text("muOS // detection pending", 370, 205, fonts.small, colors.white)
    text("Target", 248, 229, fonts.small, colors.muted)
    text("No storage selected", 370, 229, fonts.small, colors.white)

    rounded(230, 282, 390, 128, colors.panel, colors.line)
    text("FIELD NOTES", 248, 299, fonts.small, colors.violet)
    text("Comet Desk is the quick-access layer.", 248, 327, fonts.medium, colors.white)
    text("Void Desk is the workshop that taught it.", 248, 352, fonts.small, colors.muted)
    text("No writes. No hidden changes. Not yet.", 248, 376, fonts.small, colors.amber)
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
    love.graphics.setDefaultFilter("nearest", "nearest")
    fonts.tiny = love.graphics.newFont(10)
    fonts.small = love.graphics.newFont(12)
    fonts.medium = love.graphics.newFont(15)
    fonts.large = love.graphics.newFont(21)
    fonts.title = love.graphics.newFont(32)
    love.graphics.setBackgroundColor(colors.bg[1], colors.bg[2], colors.bg[3], 1)
end

function love.update(dt)
    if noticeTimer > 0 then noticeTimer = math.max(0, noticeTimer - dt) end
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
    if activePage == 1 then drawOverview() else drawModule() end
    drawFooter()
    love.graphics.pop()
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
    elseif button == "b" or button == "back" then
        love.keypressed("escape")
    end
end
