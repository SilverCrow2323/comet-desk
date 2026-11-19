-- COMET DESK // QWASAR
-- Controller-first muOS companion. Comet owns the Debian rootfs, APT, sessions and app launch lifecycle.

local W, H = 640, 480
local pages = {
    { id = "overview", title = "OVERVIEW", subtitle = "Your handheld. Your workspace. No OS drama.", icon = "◈", accent = {0.22, 0.88, 0.94} },
    { id = "setup", title = "DESKTOP SYSTEM", subtitle = "Debian Trixie ARM64 // APT + modular desktop environments.", icon = "▣", accent = {0.62, 0.43, 0.98} },
    { id = "sessions", title = "APP DECK", subtitle = "Discover and launch installed Debian applications through Comet.", icon = "▦", accent = {1.0, 0.72, 0.32} },
    { id = "uplink", title = "UPLINK", subtitle = "Network, wireless radios and remote services.", icon = "◎", accent = {0.24, 0.72, 1.0} },
    { id = "forge", title = "THE FORGE", subtitle = "Discover, install and manage curated Debian ARM64 software.", icon = "⚒", accent = {1.0, 0.48, 0.22} },
    { id = "tools", title = "SYSTEM TOOLS", subtitle = "Live guest, storage and registry state — no simulated controls.", icon = "⚙", accent = {0.35, 0.90, 0.68} },
    { id = "diagnostics", title = "DIAGNOSTICS", subtitle = "Read-only checks for your device and runtime.", icon = "⌁", accent = {0.96, 0.30, 0.70} },
    { id = "input", title = "DESKTOP INPUT", subtitle = "Controller mouse, keyboard, click and scroll mapping.", icon = "⌖", accent = {0.30, 0.86, 0.72} },
    { id = "media", title = "MEDIA VAULT", subtitle = "IPTV, multi-source EPG and web radio. One player owner.", icon = "♫", accent = {0.96, 0.36, 0.68} },
}

local selected, activePage = 1, 1
local carouselPosition = 1
local carouselTarget = 1
local pageChangedDirection = 1
local notice, noticeTimer = "SYSTEM READY // COMET DESK", 0
local fonts = {}
local appVersion = "dev"
local visuals = { background = nil, atlas = nil, quads = {} }
local probe, diagnosticReport
local device = { handheld = "Unknown", soc = "Unknown", architecture = "Unknown", firmware = "Unknown", storage = {} }
local probeTimer = 0
local theme = require("theme")
local storageSelection = require("storage_selection")
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
local DESKTOP_CONFIG_REVISION = 2
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
local appCategories = { "ALL", "DEVELOPMENT", "GAMES", "GRAPHICS", "MEDIA", "NETWORK", "OFFICE", "SYSTEM", "UTILITIES", "FILES", "OTHER" }
local appCategoryIndex, appSelectedIndex = 1, 1
local appCatalog, appSearch = {}, ""
local appSearchActive, appCatalogLoaded = false, false
local appRegistryState, appRegistryMessage = "IDLE", "Open APP DECK to scan installed Debian applications"
local appRegistryPoll, appRegistryBusy = 0, false
local forgeCatalogRaw, forgeCatalogVersion = nil, 0
local appCatalogRaw, appCatalogVersion = nil, 0
local forgeFilterCache, forgeFilterKey = {}, ""
local appFilterCache, appFilterKey = {}, ""
local operationScreen = {
    open = false, kind = "", title = "", logPath = "", state = "IDLE",
    percent = 0, message = "", lines = {}, poll = 0, done = false,
}
local autoBootstrapChecked = false
local maybeRunAutoBootstrap
local sectionOverlayOpen = false
local sectionOverlayProgress = 0
local overlayScroll = 0
local overlayScrollLimit = 160
local inputBindingRows = {
    {key = "a", label = "A"},
    {key = "b", label = "B"},
    {key = "l1+a", label = "L1 + A"},
    {key = "l1+b", label = "L1 + B"},
    {key = "x", label = "X"},
    {key = "y", label = "Y"},
    {key = "r1+x", label = "R1 + X"},
    {key = "start", label = "START"},
    {key = "select", label = "SELECT"},
}
local inputActionChoices = {
    "enter", "escape", "mouse_left", "mouse_right", "backspace",
    "tab", "alt_tab", "super", "comet_panel", "space", "disabled",
}
local inputActionLabels = {
    enter = "ENTER", escape = "ESC", mouse_left = "LEFT CLICK",
    mouse_right = "RIGHT CLICK", backspace = "BACKSPACE",
    tab = "TAB", alt_tab = "ALT + TAB", super = "SUPER",
    comet_panel = "COMET PANEL (M)", space = "SPACE", disabled = "DISABLED",
}
local desktopInput = {
    enabled = true, pointerSpeed = 900, scrollSpeed = 9,
    deadzone = 0.18, selectedOption = 1, state = "NOT CHECKED", detail = "",
    bindings = {
        a = "enter", b = "escape", ["l1+a"] = "mouse_left",
        ["l1+b"] = "mouse_right", x = "backspace", y = "tab",
        ["r1+x"] = "alt_tab", start = "super", select = "comet_panel",
    },
}
local mediaStatus = {state = "STOPPED", kind = "", title = "", player = ""}
local mediaEpgStatus = "NOT SYNCED"
local mediaCatalog = {playlists = 0, channels = 0, radios = 0, name = "IPTV-org // ITALIA", error = ""}
local mediaItemsTV, mediaItemsRadio = {}, {}
local mediaEpgById = {}
local mediaMode, mediaSelectedIndex = "RADIO", 1
local mediaPoll, mediaHeartbeat, mediaCatalogLoaded, mediaCatalogBusy = 0, 0, false, false

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
    text("DEBIAN APT CONTROL DECK  //  v0.7.0-dev", 67, 70, fonts.tiny, colors.muted)

    rounded(438, 17, 182, 56, colors.panel, colors.line)
    text("RG35XX H  //  H700", 451, 23, fonts.small, colors.cyan)
    local probeStatus = device.handheld ~= "Unknown" and "DEVICE LINK  ONLINE" or "DEVICE LINK  LIMITED"
    text(probeStatus, 451, 44, fonts.tiny,
        device.handheld ~= "Unknown" and colors.green or colors.amber)
    text("L1 / R1 NAV  //  SELECT CONSOLE", 451, 59, fonts.tiny, colors.muted)
end


local function pageAccent(index)
    return pages[index or activePage].accent
end

local function curveY(x)
    local d = (x - W * 0.5) / (W * 0.5)
    return 139 + 10 * d * d
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

local function drawForgeMark(cx, cy, scale, tint, alpha)
    love.graphics.setColor(tint[1], tint[2], tint[3], alpha or 1)
    love.graphics.setLineWidth(2 * scale)
    -- Compact hammer + anvil mark, drawn with the renderer (no font glyphs).
    love.graphics.rectangle("line", cx - 6 * scale, cy - 8 * scale, 12 * scale, 4 * scale)
    love.graphics.line(cx, cy - 4 * scale, cx + 5 * scale, cy + 5 * scale)
    love.graphics.line(cx - 7 * scale, cy + 6 * scale, cx + 7 * scale, cy + 6 * scale)
    love.graphics.line(cx - 5 * scale, cy + 6 * scale, cx - 7 * scale, cy + 9 * scale)
    love.graphics.line(cx + 5 * scale, cy + 6 * scale, cx + 7 * scale, cy + 9 * scale)
end

local function drawFallbackMark(cx, cy, scale, tint, alpha)
    love.graphics.setColor(tint[1], tint[2], tint[3], alpha or 1)
    love.graphics.setLineWidth(1.7 * scale)
    love.graphics.circle("line", cx, cy, 6 * scale)
    love.graphics.circle("line", cx, cy, 2 * scale)
    for step = 0, 3 do
        local angle = step * math.pi * 0.5
        love.graphics.line(
            cx + math.cos(angle) * 7 * scale,
            cy + math.sin(angle) * 7 * scale,
            cx + math.cos(angle) * 9 * scale,
            cy + math.sin(angle) * 9 * scale
        )
    end
end

local function drawInputMark(cx, cy, scale, tint, alpha)
    love.graphics.setColor(tint[1], tint[2], tint[3], alpha or 1)
    love.graphics.setLineWidth(2 * scale)
    love.graphics.circle("line", cx, cy, 8 * scale)
    love.graphics.circle("line", cx, cy, 2 * scale)
    love.graphics.line(cx - 13 * scale, cy, cx - 8 * scale, cy)
    love.graphics.line(cx + 8 * scale, cy, cx + 13 * scale, cy)
    love.graphics.line(cx, cy - 13 * scale, cx, cy - 8 * scale)
    love.graphics.line(cx, cy + 8 * scale, cx, cy + 13 * scale)
end

local function drawMediaMark(cx, cy, scale, tint, alpha)
    love.graphics.setColor(tint[1], tint[2], tint[3], alpha or 1)
    love.graphics.setLineWidth(2 * scale)
    love.graphics.line(cx - 4 * scale, cy - 12 * scale, cx - 4 * scale, cy + 6 * scale)
    love.graphics.arc("line", "open", cx - 7 * scale, cy + 7 * scale, 4 * scale, 0, math.pi * 2)
    love.graphics.line(cx - 4 * scale, cy - 12 * scale, cx + 9 * scale, cy - 8 * scale)
    love.graphics.line(cx + 9 * scale, cy - 8 * scale, cx + 9 * scale, cy + 2 * scale)
    love.graphics.arc("line", "open", cx + 6 * scale, cy + 4 * scale, 4 * scale, 0, math.pi * 2)
end

local function drawPageIcon(page, x, y, scale, alpha)
    local tint = page.accent
    if page.id == "input" then
        drawInputMark(x, y, scale, tint, alpha)
    elseif page.id == "media" then
        drawMediaMark(x, y, scale, tint, alpha)
    elseif page.id == "uplink" then
        drawGlobe(x, y, 9 * scale, tint, alpha)
    elseif page.id == "forge" then
        drawForgeMark(x, y, scale, tint, alpha)
    elseif visuals.atlas and visuals.quads[page.id] then
        love.graphics.setColor(1, 1, 1, alpha or 1)
        love.graphics.draw(visuals.atlas, visuals.quads[page.id],
            x - 12 * scale, y - 12 * scale, 0, 0.50 * scale, 0.50 * scale)
    else
        drawFallbackMark(x, y, scale, tint, alpha)
    end
end

local function drawNavigation()
    local active = pageAccent(selected)
    local points = {}
    for x = 10, W - 10, 4 do
        points[#points + 1] = x
        points[#points + 1] = curveY(x)
    end

    -- The fascia is a real curved structure, not a single decorative stroke.
    love.graphics.setColor(0.006, 0.012, 0.024, 0.98)
    love.graphics.setLineWidth(68)
    love.graphics.line(points)
    love.graphics.setColor(0.10, 0.16, 0.24, 1)
    love.graphics.setLineWidth(2.4)
    love.graphics.line(points)

    -- Two parallel guide rails and short cross ties make the tab travel path visible.
    local upper, lower = {}, {}
    for x = 10, W - 10, 4 do
        upper[#upper + 1] = x; upper[#upper + 1] = curveY(x) - 34
        lower[#lower + 1] = x; lower[#lower + 1] = curveY(x) + 34
    end
    love.graphics.setColor(0.36, 0.48, 0.62, 0.95)
    love.graphics.setLineWidth(2)
    love.graphics.line(upper)
    love.graphics.line(lower)
    love.graphics.setColor(active[1], active[2], active[3], 0.55)
    love.graphics.setLineWidth(1)
    love.graphics.line(upper)
    love.graphics.line(lower)
    for x = 28, W - 28, 26 do
        local y = curveY(x)
        love.graphics.setColor(0.42, 0.54, 0.67, 0.7)
        love.graphics.setLineWidth(1)
        love.graphics.line(x, y - 32, x, y + 32)
    end

    local labels = {
        overview = "HOME", setup = "DESKTOP", sessions = "APPS",
        uplink = "UPLINK", forge = "FORGE", tools = "TOOLS",
        diagnostics = "DIAG", input = "INPUT", media = "MEDIA",
    }
    for offset = -2, 2 do
        local raw = carouselTarget + offset
        local index = ((raw - 1) % #pages) + 1
        local x = W * 0.5 + (raw - carouselPosition) * 112
        if x > -68 and x < W + 68 then
            local page = pages[index]
            local distance = math.abs(x - W * 0.5) / 210
            local isActive = index == selected
            local scale = isActive and 1 or math.max(0.82, 0.96 - distance * 0.08)
            local w, h = 102 * scale, 52 * scale
            local px = x - w / 2
            local py = curveY(x) - h / 2 - 4
            local tint = page.accent
            local alpha = isActive and 1 or math.max(0.5, 0.88 - distance * 0.15)

            rounded(px, py, w, h, isActive and colors.panel2 or colors.panel,
                {tint[1], tint[2], tint[3], (isActive and 1 or 0.55) * alpha})
            if isActive then
                love.graphics.setColor(tint[1], tint[2], tint[3],
                    0.18 + 0.12 * math.sin(ambientTime * 4.2))
                love.graphics.rectangle("fill", px + 5, py + h - 4, w - 10, 2, 1, 1)
                love.graphics.setColor(tint[1], tint[2], tint[3], 0.20)
                love.graphics.rectangle("fill", px + 2, py + 2, w - 4, h - 4, 6, 6)
            end

            -- Icon and label have reserved columns: they cannot collide at 640x480.
            drawPageIcon(page, px + 20 * scale, py + h * 0.5, 1.0 * scale, alpha)
            text(labels[page.id] or page.title, px + 39 * scale, py + 18 * scale,
                fonts.tiny, {colors.white[1], colors.white[2], colors.white[3], alpha})
        end
    end

    text(pages[activePage].title, 22, 80, fonts.medium, pageAccent(activePage))
    text(string.format("%02d  /  %02d", activePage, #pages), 558, 82, fonts.tiny, colors.muted)
    for i = 1, #pages do
        local x = 264 + (i - 1) * 19
        love.graphics.setColor(active[1], active[2], active[3], i == selected and 1 or 0.25)
        love.graphics.circle("fill", x, 173, i == selected and 3.5 or 2)
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

local function normalizeSelectedSlot(notify)
    local nextSlot, changed = storageSelection.normalize(selectedSlot, storageUsable)
    if changed then
        selectedSlot = nextSlot
        if notify then
            setNotice(nextSlot == "tf1"
                and "TF2 NOT AVAILABLE // USING TF1"
                or "TF1 NOT AVAILABLE // USING TF2")
        end
    end
    return changed
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
    local desktopEngine, engineColor = "NOT INSTALLED", colors.amber
    if imageDownload.state == "READY" then
        local profile = imageDownload.profile ~= "" and imageDownload.profile or selectedProfile
        desktopEngine = profile == "labwc" and "LABWC / WAYLAND" or (profile:upper() .. " / X11")
        engineColor = colors.green
    elseif imageDownload.state ~= "NOT_INSTALLED" then
        desktopEngine = imageDownload.state
        engineColor = (imageDownload.state == "FAILED" or imageDownload.state == "CLEANUP_REQUIRED")
            and colors.amber or colors.violet
    end
    text(short(desktopEngine, 28), 413, 293, fonts.small, engineColor)

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
        text((selectedSlot == slot and "> " or "  ") .. label, x, 382, fonts.tiny,
            selectedSlot == slot and colors.cyan or colors.muted)
        text(state, x + 48, 382, fonts.tiny, usable and colors.green or colors.amber)
    end
    slotLabel("TF1", "tf1", 34)
    slotLabel("TF2", "tf2", 214)
    text("LEFT / RIGHT  SELECT STORAGE SLOT", 34, 402, fonts.tiny, colors.muted)
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

local function openOperationScreen(kind, title, logPath, message, state)
    operationScreen.open = true
    operationScreen.kind = kind
    operationScreen.title = title
    operationScreen.logPath = logPath
    operationScreen.message = message or "Starting operation..."
    operationScreen.state = state or "STARTING"
    operationScreen.percent = 0
    operationScreen.lines = {}
    operationScreen.poll = 0
    operationScreen.done = false
end

local function updateOperationScreen(kind, state, percent, message, done)
    if operationScreen.kind ~= kind then return end
    operationScreen.state = state or operationScreen.state
    operationScreen.percent = math.max(0, math.min(100, tonumber(percent) or operationScreen.percent))
    if message and message ~= "" then operationScreen.message = message end
    if done ~= nil then operationScreen.done = done end
end

local function refreshOperationLog()
    if not operationScreen.open or operationScreen.logPath == "" then return end
    local stream = io.open(operationScreen.logPath, "rb")
    if not stream then return end
    local size = stream:seek("end") or 0
    stream:seek("set", math.max(0, size - 8192))
    local content = stream:read("*a") or ""
    stream:close()
    local lines = {}
    for line in (content .. "\n"):gmatch("(.-)\n") do
        line = line:gsub("\27%[[%d;?]*[%a]", "")
        line = line:gsub("[%z\1-\8\11\12\14-\31]", " ")
        line = line:gsub("%s+", " "):match("^%s*(.-)%s*$") or ""
        if line ~= "" then
            lines[#lines + 1] = line
            if #lines > 9 then table.remove(lines, 1) end
        end
    end
    operationScreen.lines = lines
end

local function queueForgeAction(action, packageName)
    if appRoot == "" then setNotice("COMET APP RUNNER PATH UNAVAILABLE"); return end
    local slot = installedSlot or selectedSlot
    if not installedSlot then setNotice("INSTALL DEBIAN TRIXIE IN DESKTOP SYSTEM FIRST"); return end
    if forgeActionBusy then
        openOperationScreen("FORGE", "THE FORGE // " .. string.upper(forgeStatus.state),
            appRoot .. "/data/forge-apt.log", forgeStatus.message, forgeStatus.state)
        operationScreen.percent = forgeStatus.percent or 0
        setNotice("REOPENED THE ACTIVE APT CONSOLE")
        return
    end
    local function quote(value) return "'" .. tostring(value):gsub("'", "'\\''") .. "'" end
    local script = appRoot .. "/service/forge_apt.py"
    if action ~= "catalog" then os.remove(appRoot .. "/data/forge-operation.status") end
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
        if action ~= "catalog" then
            openOperationScreen("FORGE", "THE FORGE // " .. string.upper(action),
                appRoot .. "/data/forge-apt.log",
                string.upper(action) .. " // " .. (packageName or "DEBIAN INDEXES"),
                string.upper(action))
        end
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
        local raw = catalog:read("*a") or ""
        catalog:close()
        if raw ~= forgeCatalogRaw then
            forgeCatalogRaw = raw
            forgeCatalogVersion = forgeCatalogVersion + 1
            local rows = {}
            for line in (raw .. "\n"):gmatch("(.-)\n") do
                local category, packageName, title, summary, installed, available, size, tag =
                    line:match("^PKG|([^|]*)|([^|]*)|([^|]*)|([^|]*)|([^|]*)|([^|]*)|([^|]*)|([^|]*)$")
                if packageName then rows[#rows + 1] = {
                    category = category, package = packageName, title = title, summary = summary,
                    installed = installed == "1", available = available == "1", size = size, tag = tag,
                } end
            end
            forgePackages = rows
        end
    end
    local status = io.open(appRoot .. "/data/forge-operation.status", "r")
    if status then
        local line = status:read("*l"); status:close()
        local state, percent, message, packageName = line and line:match("^([^|]+)|(%d+)|([^|]*)|(.*)$")
        if state then
            local previousState = forgeStatus.state
            forgeStatus.state = state; forgeStatus.percent = tonumber(percent) or 0
            forgeStatus.message = message; forgeStatus.package = packageName or ""
            forgeActionBusy = state == "INSTALLING" or state == "REMOVING" or state == "UPDATING"
            if operationScreen.kind == "FORGE" then
                local finished = state == "DONE" or state == "REFRESHED"
                    or state == "FAILED" or state == "CLEANUP_REQUIRED" or state == "BUSY"
                updateOperationScreen("FORGE", state, tonumber(percent) or 0,
                    message or "", finished)
            end
            if state == "DONE" and previousState ~= "DONE" then
                appCatalogLoaded = false
            end
        end
    end
end

local function forgeFilteredPackages()
    local key = tostring(forgeCatalogVersion) .. ":" .. tostring(forgeCategoryIndex) .. ":" .. forgeSearch
    if key == forgeFilterKey then return forgeFilterCache end
    local category = forgeCategories[forgeCategoryIndex]
    local query = forgeSearch:lower()
    local rows = {}
    for _, item in ipairs(forgePackages) do
        local categoryMatch = category == "ALL" or item.category == category
        local textMatch = query == "" or item.title:lower():find(query, 1, true)
            or item.package:lower():find(query, 1, true) or item.summary:lower():find(query, 1, true)
        if categoryMatch and textMatch then rows[#rows + 1] = item end
    end
    forgeFilterKey, forgeFilterCache = key, rows
    return forgeFilterCache
end

local function queueAppCatalog()
    if appRoot == "" then
        setNotice("COMET APP RUNNER PATH UNAVAILABLE")
        return
    end
    if not installedSlot then
        setNotice("INSTALL DEBIAN TRIXIE IN DESKTOP SYSTEM FIRST")
        return
    end
    if appRegistryBusy then
        openOperationScreen("APP DECK", "APP DECK // INDEXING",
            appRoot .. "/data/app-registry.log",
            appRegistryMessage, appRegistryState)
        setNotice("REOPENED THE APP DECK SCAN CONSOLE")
        return
    end
    local function quote(value) return "'" .. tostring(value):gsub("'", "'\\''") .. "'" end
    local script = appRoot .. "/service/app_registry.py"
    os.remove(appRoot .. "/data/app-registry.status")
    local command = "cd " .. quote(appRoot) .. " && python3 " .. quote(script)
        .. " catalog --slot " .. installedSlot
        .. " --app-dir " .. quote(appRoot)
        .. " >> " .. quote(appRoot .. "/data/app-registry.log") .. " 2>&1 &"
    local result = os.execute(command)
    if result == 0 or result == true then
        appRegistryState = "SCANNING"
        appRegistryMessage = "Discovering installed Debian applications"
        appRegistryBusy = true
        openOperationScreen("APP DECK", "APP DECK // INDEXING",
            appRoot .. "/data/app-registry.log",
            "Discovering installed Debian applications", "SCANNING")
        setNotice("APP DECK // SCANNING DEBIAN")
    else
        appRegistryState = "FAILED"
        appRegistryMessage = "Could not start the app registry worker"
        setNotice("APP REGISTRY WORKER COULD NOT START")
    end
end

local function readAppFiles()
    if appRoot == "" then return end
    local catalog = io.open(appRoot .. "/data/app-catalog.txt", "r")
    if catalog then
        local raw = catalog:read("*a") or ""
        catalog:close()
        if raw ~= appCatalogRaw then
            appCatalogRaw = raw
            appCatalogVersion = appCatalogVersion + 1
            local rows = {}
            for line in (raw .. "\n"):gmatch("(.-)\n") do
                local id, name, category, icon, executable =
                    line:match("^APP|([^|]*)|([^|]*)|([^|]*)|([^|]*)|([^|]*)$")
                if id then
                    rows[#rows + 1] = {
                        id = id, name = name, category = category,
                        icon = icon, executable = executable,
                    }
                end
            end
            appCatalog = rows
            if appSelectedIndex > #appCatalog then appSelectedIndex = math.max(1, #appCatalog) end
        end
    end
    local status = io.open(appRoot .. "/data/app-registry.status", "r")
    if status then
        local line = status:read("*l")
        status:close()
        local state, message = line and line:match("^([^|]+)|(.*)$")
        if state then
            local previousState = appRegistryState
            appRegistryState, appRegistryMessage = state, message or ""
            appRegistryBusy = state == "SCANNING"
            if operationScreen.kind == "APP DECK" then
                local finished = state == "READY" or state == "FAILED" or state == "CLEANUP_REQUIRED"
                updateOperationScreen("APP DECK", state, state == "READY" and 100 or 0,
                    message or "", finished)
            end
            if state == "READY" and previousState ~= "READY" then
                setNotice("APP DECK // " .. tostring(#appCatalog) .. " APPS")
            elseif state == "FAILED" and previousState ~= "FAILED" then
                setNotice("APP DECK SCAN FAILED // CHECK LOG")
            end
        end
    end
end

local function filteredApps()
    local key = tostring(appCatalogVersion) .. ":" .. tostring(appCategoryIndex) .. ":" .. appSearch
    if key == appFilterKey then return appFilterCache end
    local category = appCategories[appCategoryIndex]
    local query = appSearch:lower()
    local rows = {}
    for _, item in ipairs(appCatalog) do
        local categoryMatch = category == "ALL" or item.category == category
        local textMatch = query == "" or item.name:lower():find(query, 1, true)
            or item.id:lower():find(query, 1, true)
            or item.executable:lower():find(query, 1, true)
        if categoryMatch and textMatch then rows[#rows + 1] = item end
    end
    appFilterKey, appFilterCache = key, rows
    return appFilterCache
end

local function cycleAppCategory(direction)
    appCategoryIndex = ((appCategoryIndex - 1 + direction) % #appCategories) + 1
    appSelectedIndex = 1
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

local function drawAppDeck()
    local tint = pages[activePage].accent
    text("COMET APPLICATION REGISTRY  /  DEBIAN Trixie ARM64", 24, 180, fonts.small, colors.muted)
    rounded(20, 201, 600, 214, colors.panel, { tint[1], tint[2], tint[3], 0.75 })
    local category = appCategories[appCategoryIndex]
    rounded(28, 211, 86, 25, colors.panel2, tint)
    text(category, 35, 216, fonts.tiny, colors.white)
    text("INSTALLED APPS  /  " .. tostring(#appCatalog), 127, 216, fonts.tiny, tint)
    text(appRegistryBusy and "SCANNING..." or appRegistryState, 490, 216, fonts.tiny,
        appRegistryBusy and colors.amber or (appRegistryState == "READY" and colors.green or colors.muted))

    local rows = filteredApps()
    if appSelectedIndex > #rows then appSelectedIndex = math.max(1, #rows) end
    rounded(27, 246, 245, 151, colors.panel2, colors.line)
    local first = math.max(1, math.min(appSelectedIndex - 1, math.max(1, #rows - 3)))
    for visible = 1, 4 do
        local index = first + visible - 1
        local item = rows[index]
        if item then
            local y = 255 + (visible - 1) * 34
            local active = index == appSelectedIndex
            if active then rounded(34, y - 3, 230, 30, colors.bg, tint) end
            local glyph = item.category == "DEVELOPMENT" and "DEV"
                or (item.category == "MEDIA" and "MED" or (item.category == "NETWORK" and "NET" or "APP"))
            text(glyph, 42, y + 3, fonts.tiny, active and tint or colors.violet)
            text(short(item.name, 18), 80, y + 3, fonts.small, active and colors.white or colors.muted)
        end
    end

    rounded(281, 246, 326, 151, colors.panel2, colors.line)
    local chosen = rows[appSelectedIndex]
    if chosen then
        text(short(chosen.name, 28), 296, 255, fonts.medium, colors.white)
        text(chosen.id, 296, 281, fonts.tiny, tint)
        text(chosen.category .. "  /  DEBIAN APPLICATION", 296, 302, fonts.tiny, colors.muted)
        text("EXECUTABLE", 296, 330, fonts.tiny, colors.muted)
        text(short(chosen.executable, 42), 296, 348, fonts.small, colors.white)
        text("A  LAUNCH WITH " .. selectedProfile:upper(), 296, 379, fonts.tiny, tint)
    elseif not installedSlot then
        text("DEBIAN NOT READY", 296, 270, fonts.medium, colors.amber)
        text("Install the Debian system first.", 296, 305, fonts.small, colors.muted)
    elseif appRegistryBusy then
        text("BUILDING APP REGISTRY", 296, 270, fonts.medium, colors.cyan)
        text(short(appRegistryMessage, 38), 296, 305, fonts.small, colors.muted)
    else
        text("NO APPLICATIONS FOUND", 296, 270, fonts.medium, colors.amber)
        text("Install GUI packages in THE FORGE, then refresh.", 296, 305, fonts.small, colors.muted)
    end
    text("L / R CATEGORY   UP / DOWN APP   A LAUNCH   Y REFRESH", 29, 402, fonts.tiny, colors.muted)
    if appSearch ~= "" then
        text("SEARCH: " .. short(appSearch, 20), 438, 402, fonts.tiny, tint)
    else
        text("/ SEARCH", 548, 402, fonts.tiny, tint)
    end
end

local function drawSystemTools()
    text("COMET // SYSTEM CONTROL AND ENVIRONMENT STATUS", 24, 180, fonts.small, colors.muted)
    rounded(20, 201, 600, 214, colors.panel, colors.line)
    local guestState, guestColor = "NOT INSTALLED", colors.amber
    if imageDownload.state == "READY" then
        guestState, guestColor = "DEBIAN 13 / TRIXIE READY", colors.green
    elseif imageDownload.state ~= "NOT_INSTALLED" then
        guestState = imageDownload.state
        guestColor = (imageDownload.state == "FAILED" or imageDownload.state == "CLEANUP_REQUIRED")
            and colors.amber or colors.violet
    end
    local forgeLabel = not installedSlot and "LOCKED // DEBIAN NOT READY"
        or (forgeLoaded and (forgeStatus.state == "IDLE" and "IDLE // NO TASK" or forgeStatus.state)
            or "NOT CHECKED")
    local appLabel = not installedSlot and "LOCKED // DEBIAN NOT READY"
        or (appCatalogLoaded and (tostring(#appCatalog) .. " DISCOVERED // " .. appRegistryState)
            or "NOT SCANNED")
    local rows = {
        { "GUEST OS", guestState, guestColor },
        { "ARCHITECTURE", (device.architecture or "UNKNOWN"):upper() .. " // SHARED MUOS KERNEL", colors.white },
        { "STORAGE", installedSlot and installedSlot:upper() or "NOT CONFIGURED", installedSlot and colors.green or colors.amber },
        { "DESKTOP PROFILE", imageDownload.state == "READY" and (imageDownload.profile or selectedProfile):upper()
            or (imageDownload.state == "NOT_INSTALLED" and "NOT INSTALLED" or imageDownload.state), colors.violet },
        { "APT / FORGE", forgeLabel, installedSlot and colors.green or colors.amber },
        { "APPLICATION REGISTRY", appLabel, colors.cyan },
    }
    for i, item in ipairs(rows) do
        local y = 220 + (i - 1) * 27
        text(item[1], 40, y, fonts.tiny, colors.muted)
        text(short(item[2], 48), 214, y - 2, fonts.small, item[3])
    end
    setColor(colors.line)
    love.graphics.line(40, 385, 600, 385)
    text("Y  REFRESH APPLICATION REGISTRY", 40, 393, fonts.tiny, colors.cyan)
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

local function drawSectionStructure(x, y, w, h, page, alpha)
    local tint = page.accent
    alpha = alpha or 1
    rounded(x, y, w, h, colors.panel,
        {tint[1], tint[2], tint[3], 0.72 * alpha})
    love.graphics.setColor(tint[1], tint[2], tint[3], 0.80 * alpha)
    love.graphics.setLineWidth(2)

    -- Every section gets its own frame language, not merely a different colour.
    if page.id == "overview" then
        love.graphics.arc("line", "open", x + 22, y + 22, 13, math.pi, math.pi * 1.5)
        love.graphics.arc("line", "open", x + w - 22, y + h - 22, 13, 0, math.pi * 0.5)
        love.graphics.line(x + 38, y + 5, x + w - 38, y + 5)
    elseif page.id == "setup" then
        love.graphics.line(x + 5, y + 24, x + 5, y + 5, x + 24, y + 5)
        love.graphics.line(x + w - 24, y + h - 5, x + w - 5, y + h - 5, x + w - 5, y + h - 24)
        love.graphics.line(x + 18, y + h - 5, x + 38, y + h - 5)
    elseif page.id == "sessions" then
        love.graphics.rectangle("line", x + 7, y + 7, w - 14, h - 14, 4, 4)
        love.graphics.line(x + 18, y + 5, x + 86, y + 5)
        love.graphics.line(x + w - 86, y + h - 5, x + w - 18, y + h - 5)
    elseif page.id == "uplink" then
        love.graphics.arc("line", "open", x + 52, y + h - 4, 26, math.pi, math.pi * 2)
        love.graphics.arc("line", "open", x + 52, y + h - 4, 14, math.pi, math.pi * 2)
        love.graphics.line(x + 96, y + 5, x + w - 18, y + 5)
    elseif page.id == "forge" then
        for i = 0, 3 do
            love.graphics.line(x + w - 94 + i * 20, y + 5, x + w - 114 + i * 20, y + 25)
            love.graphics.line(x + 8 + i * 18, y + h - 5, x + 26 + i * 18, y + h - 23)
        end
    elseif page.id == "tools" then
        for i = 0, 3 do
            love.graphics.rectangle("line", x + 14 + i * 9, y + 5, 4, 4)
            love.graphics.rectangle("line", x + w - 18 - i * 9, y + h - 9, 4, 4)
        end
        love.graphics.line(x + 5, y + 30, x + 5, y + h - 30)
    else
        love.graphics.circle("line", x + w - 28, y + 28, 13)
        love.graphics.circle("line", x + w - 28, y + 28, 7)
        love.graphics.line(x + 5, y + 18, x + 20, y + 18)
        love.graphics.line(x + 5, y + 25, x + 13, y + 25)
        love.graphics.line(x + w - 20, y + h - 18, x + w - 5, y + h - 18)
    end
end

local function drawMetricCard(x, y, w, label, value, detail, tint)
    rounded(x, y, w, 76, colors.panel2, colors.line)
    text(short(label, 22), x + 12, y + 8, fonts.tiny, colors.muted)
    text(short(value, 20), x + 12, y + 28, fonts.medium, colors.white)
    text(short(detail, 24), x + 12, y + 54, fonts.tiny, tint or colors.muted)
end

local function desktopInputPath()
    return appRoot ~= "" and (appRoot .. "/data/desktop-input.json") or ""
end

local function readDesktopInputConfig()
    local path = desktopInputPath()
    if path == "" then return end
    local stream = io.open(path, "r")
    if not stream then return end
    local raw = stream:read("*a") or ""
    stream:close()
    local function number(key, fallback)
        return tonumber(raw:match('"' .. key .. '"%s*:%s*([%d%.]+)')) or fallback
    end
    desktopInput.pointerSpeed = math.max(200, math.min(2200, number("pointer_speed", 900)))
    desktopInput.scrollSpeed = math.max(2, math.min(24, number("scroll_speed", 9)))
    desktopInput.deadzone = math.max(0.08, math.min(0.42, number("deadzone", 0.18)))
    desktopInput.enabled = not raw:match('"enabled"%s*:%s*false')
    for _, row in ipairs(inputBindingRows) do
        local keyPattern = row.key:gsub("([^%w])", "%%%1")
        local value = raw:match('"' .. keyPattern .. '"%s*:%s*"([^"]+)"')
        if value then desktopInput.bindings[row.key] = value end
    end
end

local function writeDesktopInputConfig()
    if appRoot == "" then return end
    local path = desktopInputPath()
    local stream = io.open(path .. ".tmp", "w")
    if not stream then setNotice("COULD NOT SAVE DESKTOP INPUT PROFILE"); return end
    local b = desktopInput.bindings
    stream:write(string.format(
        '{\n  "schema_version": 1,\n  "enabled": %s,\n  "device": "auto",\n'
        .. '  "pointer_speed": %d,\n  "scroll_speed": %d,\n  "deadzone": %.2f,\n'
        .. '  "acceleration": 1.65,\n  "bindings": {\n'
        .. '    "a": "%s", "b": "%s", "l1+a": "%s",\n'
        .. '    "l1+b": "%s", "x": "%s", "y": "%s",\n'
        .. '    "r1+x": "%s", "start": "%s", "select": "%s"\n'
        .. '  }\n}\n',
        desktopInput.enabled and "true" or "false",
        desktopInput.pointerSpeed, desktopInput.scrollSpeed, desktopInput.deadzone,
        b.a, b.b, b["l1+a"], b["l1+b"], b.x, b.y, b["r1+x"], b.start, b.select
    ))
    stream:close()
    if not os.rename(path .. ".tmp", path) then
        os.remove(path .. ".tmp")
        setNotice("COULD NOT COMMIT DESKTOP INPUT PROFILE")
        return
    end
    setNotice("DESKTOP INPUT PROFILE SAVED // NEXT SESSION")
end

local function adjustDesktopInput(direction)
    local option = desktopInput.selectedOption
    if option == 1 then
        desktopInput.pointerSpeed = math.max(200, math.min(2200,
            desktopInput.pointerSpeed + direction * 100))
    elseif option == 2 then
        desktopInput.scrollSpeed = math.max(2, math.min(24,
            desktopInput.scrollSpeed + direction))
    elseif option == 3 then
        desktopInput.deadzone = math.max(0.08, math.min(0.42,
            math.floor((desktopInput.deadzone + direction * 0.02) * 100 + 0.5) / 100))
    elseif option == 4 then
        desktopInput.enabled = not desktopInput.enabled
    else
        local row = inputBindingRows[option - 4]
        if row then
            local current = desktopInput.bindings[row.key] or "disabled"
            local index = 1
            for i, action in ipairs(inputActionChoices) do
                if action == current then index = i; break end
            end
            index = ((index - 1 + direction) % #inputActionChoices) + 1
            desktopInput.bindings[row.key] = inputActionChoices[index]
        end
    end
    writeDesktopInputConfig()
end

local function resetDesktopInput()
    desktopInput.enabled = true
    desktopInput.pointerSpeed = 900
    desktopInput.scrollSpeed = 9
    desktopInput.deadzone = 0.18
    desktopInput.bindings = {
        a = "enter", b = "escape", ["l1+a"] = "mouse_left",
        ["l1+b"] = "mouse_right", x = "backspace", y = "tab",
        ["r1+x"] = "alt_tab", start = "super", select = "comet_panel",
    }
    desktopInput.selectedOption = 1
    writeDesktopInputConfig()
    setNotice("DESKTOP INPUT // DEFAULT MAP RESTORED")
end

local function readDesktopInputStatus()
    if appRoot == "" then return end
    local stream = io.open(appRoot .. "/data/desktop-input.status", "r")
    if not stream then return end
    local line = stream:read("*l") or ""
    stream:close()
    local state, detail = line:match("^([^|]+)|?(.*)$")
    if state then desktopInput.state = state; desktopInput.detail = detail or "" end
end

local function shellQuoteMedia(value)
    return "'" .. tostring(value):gsub("'", "'\\''") .. "'"
end

local function queueMediaTask(action, extra)
    if appRoot == "" then setNotice("COMET MEDIA SERVICE PATH UNAVAILABLE"); return end
    local script = appRoot .. "/service/media_vault.py"
    local command = "cd " .. shellQuoteMedia(appRoot) .. " && python3 "
        .. shellQuoteMedia(script) .. " " .. action .. " --app-dir "
        .. shellQuoteMedia(appRoot) .. (extra and (" " .. extra) or "")
        .. " >> " .. shellQuoteMedia(appRoot .. "/data/media-vault.log") .. " 2>&1 &"
    local result = os.execute(command)
    if result == 0 or result == true then
        setNotice("MEDIA VAULT // " .. action:upper())
    else
        setNotice("COULD NOT START MEDIA VAULT TASK")
    end
end

local function readMediaStatus()
    if appRoot == "" then return end
    local stream = io.open(appRoot .. "/data/media-player.status", "r")
    if not stream then return end
    local line = stream:read("*l") or ""
    stream:close()
    local state, kind, title, player = line:match("^([^|]*)|([^|]*)|([^|]*)|(.*)$")
    if state then mediaStatus = {state = state, kind = kind, title = title, player = player} end
end

local function readMediaCatalog()
    if appRoot == "" then return end
    local stream = io.open(appRoot .. "/data/media-vault.catalog", "r")
    if not stream then return end
    local raw = stream:read("*a") or ""
    stream:close()
    local radios, channels = {}, {}
    local function fields(line)
        local out = {}
        for value in (line .. "|"):gmatch("(.-)|") do out[#out + 1] = value end
        return out
    end
    for line in (raw .. "\n"):gmatch("(.-)\n") do
        local f = fields(line)
        if f[1] == "META" then
            mediaCatalog.playlists = tonumber(f[2]) or 0
            mediaCatalog.channels = tonumber(f[3]) or 0
            mediaCatalog.radios = tonumber(f[4]) or 0
            mediaCatalog.name = f[5] or "IPTV LIBRARY"
            mediaCatalog.error = f[6] or ""
        elseif f[1] == "RADIO" then
            radios[#radios + 1] = {id = f[2], name = f[3], genre = f[4],
                url = f[5], favorite = f[6] == "1"}
        elseif f[1] == "TV" then
            channels[#channels + 1] = {id = f[2], name = f[3], group = f[4],
                url = f[5], tvgId = f[6], favorite = f[7] == "1"}
        end
    end
    mediaItemsRadio, mediaItemsTV = radios, channels
    mediaEpgById = {}
    local epgCatalog = io.open(appRoot .. "/data/media-vault.epg", "r")
    if epgCatalog then
        for row in (epgCatalog:read("*a") .. "\n"):gmatch("(.-)\n") do
            local id, current, following = row:match("^EPG|([^|]*)|([^|]*)|(.*)$")
            if id then mediaEpgById[id] = {current = current, next = following} end
        end
        epgCatalog:close()
    end
    mediaCatalogLoaded, mediaCatalogBusy = true, false
    local epg = io.open(appRoot .. "/data/media-epg.status", "r")
    if epg then
        local state, ok, failed = (epg:read("*l") or ""):match("^([^|]+)|(%d+)|(%d+)")
        epg:close()
        if state then mediaEpgStatus = state .. "  //  " .. ok .. " OK / " .. failed .. " ERRORS" end
    end
    local rows = mediaMode == "RADIO" and radios or channels
    if mediaSelectedIndex > #rows then mediaSelectedIndex = math.max(1, #rows) end
end

local function queueMediaCatalogue(force)
    if mediaCatalogBusy or appRoot == "" then return end
    mediaCatalogBusy = true
    queueMediaTask(force and "catalogue" or "init", force and "--force" or nil)
end

local function queueMediaRadio(item)
    if not item then return end
    queueMediaTask("play-radio", "--query " .. shellQuoteMedia(item.id))
end

local function queueMediaFavourite(item)
    if not item then return end
    local kind = mediaMode:lower()
    queueMediaTask("toggle-favourite", "--kind " .. kind
        .. " --query " .. shellQuoteMedia(item.id))
end

local function queueMediaRefresh()
    queueMediaCatalogue(true)
    queueMediaTask("refresh-epg")
end

local function queueMediaStop()
    queueMediaTask("stop")
end

local function queueMediaToggle()
    if mediaStatus.state == "PLAYING" or mediaStatus.state == "PAUSED" then
        queueMediaTask("toggle")
    else
        setNotice("NO MEDIA STREAM IS PLAYING")
    end
end

local function queueMediaTV(item)
    if appRoot == "" or not item then return end
    local function jsonQuote(value)
        value = tostring(value or ""):gsub("\\", "\\\\"):gsub('"', '\\"')
            :gsub("\n", "\\n"):gsub("\r", "")
        return '"' .. value .. '"'
    end
    local path = appRoot .. "/data/media-session.request"
    local temporary = path .. ".tmp"
    local stream = io.open(temporary, "w")
    if not stream then setNotice("COULD NOT CREATE TV PLAY REQUEST"); return end
    stream:write('{"kind":"tv","url":', jsonQuote(item.url),
        ',"title":', jsonQuote(item.name), '}\n')
    stream:close()
    if not os.rename(temporary, path) then
        os.remove(temporary)
        setNotice("COULD NOT QUEUE TV PLAYBACK")
        return
    end
    setNotice("MEDIA VAULT // HANDING DISPLAY TO IPTV PLAYER")
    love.event.quit()
end

local function heartbeatMedia()
    if appRoot == "" then return end
    local stream = io.open(appRoot .. "/data/media-player.heartbeat", "a")
    if stream then stream:write(tostring(os.time()), "\n"); stream:close() end
end

local function drawSectionWidget()
    local page = pages[activePage]
    local tint = page.accent
    drawSectionStructure(20, 184, 600, 232, page, 1)
    text("SECTION SNAPSHOT", 36, 196, fonts.tiny, tint)
    text(short(page.subtitle, 76), 36, 218, fonts.small, colors.muted)

    local a, b, c = {}, {}, {}
    local lowerLine, lowerDetail = "", ""
    if page.id == "overview" then
        a = {"DEVICE", device.handheld or "Unknown", "RG35XX / HANDHELD"}
        b = {"SOC / ARCH", short(device.soc or "Unknown", 14), device.architecture or "Unknown"}
        c = {"MEMORY", device.memory_mb and (tostring(device.memory_mb) .. " MB") or "Unknown", device.firmware or "muOS"}
        lowerLine = storageLine("TF1", storageItem("tf1"))
        lowerDetail = storageLine("TF2", storageItem("tf2"))
    elseif page.id == "setup" then
        local state = imageDownload.state == "NOT_INSTALLED" and "NOT INSTALLED" or imageDownload.state
        a = {"DEBIAN GUEST", state, short(imageDownload.message, 22)}
        b = {"DESKTOP PROFILE", selectedProfile:upper(), "SELECTED ENVIRONMENT"}
        c = {"TARGET STORAGE", selectedSlot:upper(), installedSlot and ("INSTALLED: " .. installedSlot:upper()) or "NO ROOTFS YET"}
        lowerLine = "DEBIAN TRIXIE ARM64  //  ONE ROOTFS  //  APT INSIDE THE GUEST"
        lowerDetail = imageDownload.message or "Select a profile and open the section to install"
    elseif page.id == "sessions" then
        local chosen = filteredApps()[appSelectedIndex]
        a = {"APPLICATIONS", tostring(#appCatalog), appRegistryState or "NOT SCANNED"}
        b = {"SELECTED APP", chosen and short(chosen.name, 18) or "NONE", chosen and chosen.category or "OPEN APP DECK"}
        c = {"DESKTOP", selectedProfile:upper(), installedSlot and installedSlot:upper() or "DEBIAN NOT READY"}
        lowerLine = "APP DECK  //  VALIDATED GUI APPLICATIONS ONLY"
        lowerDetail = appRegistryMessage or "Open the section to browse the installed application registry"
    elseif page.id == "uplink" then
        local wifi, hot, bt = uplinkStatus.wifi or {}, uplinkStatus.hotspot or {}, uplinkStatus.bluetooth or {}
        a = {"WI-FI", wifi.connected and short(wifi.ssid or "CONNECTED", 18) or "OFFLINE", wifi.ip or "NO ADDRESS"}
        b = {"HOTSPOT", hot.active and short(hot.ssid or "ACTIVE", 18) or "INACTIVE", hot.interface or "NO AP INTERFACE"}
        c = {"BLUETOOTH", bt.powered and "POWERED ON" or "POWERED OFF", tostring(bt.devices or 0) .. " PAIRED / SEEN"}
        local ts = uplinkStatus.tailscale or {}
        lowerLine = "MUOS SERVICES  //  SSH " .. ((uplinkStatus.services or {}).ssh and "ON" or "OFF")
            .. "  //  SFTP " .. ((uplinkStatus.services or {}).sftp and "ON" or "OFF")
        lowerDetail = "TAILSCALE  //  " .. (ts.installed and (ts.backend or "INSTALLED") or "NOT INSTALLED")
    elseif page.id == "forge" then
        local rows = forgeFilteredPackages()
        local chosen = rows[forgeSelectedIndex]
        local installed = 0
        for _, item in ipairs(rows) do if item.installed then installed = installed + 1 end end
        a = {"CATALOGUE", tostring(#rows) .. " PACKAGES", forgeLoaded and "INDEX READY" or "NOT LOADED"}
        b = {"INSTALLED", tostring(installed), "IN CURRENT FILTER"}
        c = {"APT OPERATION", forgeStatus.state or "IDLE", short(forgeStatus.message, 22)}
        lowerLine = chosen and ("SELECTED  //  " .. short(chosen.title, 52)) or "THE FORGE  //  CURATED DEBIAN ARM64 PACKAGES"
        lowerDetail = "A INSTALL  /  X REMOVE  /  Y REFRESH INDEX"
    elseif page.id == "input" then
        a = {"CONTROLLER", desktopInput.enabled and "BRIDGE ON" or "BRIDGE OFF", desktopInput.state}
        b = {"POINTER", tostring(desktopInput.pointerSpeed), "PIXELS / SECOND"}
        c = {"SCROLL", tostring(desktopInput.scrollSpeed), "STEPS / SECOND"}
        lowerLine = "L-STICK POINTER  //  A ENTER  //  B ESC  //  L1+A / L1+B MOUSE"
        lowerDetail = "R-STICK SCROLL  //  D-PAD ARROWS  //  R1+X ALT+TAB  //  SELECT M-PANEL"
    elseif page.id == "media" then
        a = {"PLAYLISTS", tostring(mediaCatalog.playlists), mediaCatalog.name}
        b = {"TV CHANNELS", tostring(mediaCatalog.channels), "M3U / M3U8"}
        c = {"WEB RADIO", tostring(mediaCatalog.radios), mediaStatus.state .. " // " .. mediaStatus.kind}
        lowerLine = "NOW PLAYING  //  " .. (mediaStatus.title ~= "" and short(mediaStatus.title, 56) or "NOTHING")
        lowerDetail = "NOW PLAYING / RADIO  //  Y FAVOURITE  //  START REFRESHES EPG"
    elseif page.id == "tools" then
        local guest = imageDownload.state == "READY" and "DEBIAN 13 READY"
            or (imageDownload.state == "NOT_INSTALLED" and "NOT INSTALLED" or imageDownload.state)
        a = {"GUEST OS", guest, installedSlot and installedSlot:upper() or "NO STORAGE"}
        b = {"ARCHITECTURE", device.architecture or "Unknown", "SHARED MUOS KERNEL"}
        c = {"APP REGISTRY", appCatalogLoaded and tostring(#appCatalog) .. " APPS" or "NOT SCANNED", appRegistryState or "IDLE"}
        lowerLine = "APT / THE FORGE  //  " .. (forgeStatus.state or "IDLE")
        lowerDetail = "System state is read-only here; use DESKTOP SYSTEM and THE FORGE for actions"
    else
        a = {"HANDHELD", device.handheld or "Unknown", device.firmware or "muOS"}
        b = {"SOC / ARCH", device.soc or "Unknown", device.architecture or "Unknown"}
        c = {"MEMORY", device.memory_mb and (tostring(device.memory_mb) .. " MB") or "Unknown", "DEVICE SNAPSHOT"}
        lowerLine = storageLine("TF1", storageItem("tf1"))
        lowerDetail = storageLine("TF2", storageItem("tf2"))
    end

    drawMetricCard(36, 253, 178, a[1], a[2], a[3], tint)
    drawMetricCard(231, 253, 178, b[1], b[2], b[3], tint)
    drawMetricCard(426, 253, 178, c[1], c[2], c[3], tint)
    if page.id == "setup" then
        drawProgress(38, 355, 564, 12, imageDownload.percent or 0, tint)
        text(short(lowerLine, 82), 38, 375, fonts.tiny, colors.white)
        text(short(lowerDetail, 82), 38, 394, fonts.tiny,
            imageDownload.state == "FAILED" and colors.amber or colors.muted)
    else
        text(short(lowerLine, 82), 38, 356, fonts.tiny, colors.white)
        text(short(lowerDetail, 82), 38, 380, fonts.tiny, colors.muted)
    end
    text("A  OPEN SECTION", 492, 196, fonts.tiny, tint)
end

local function drawDesktopInput()
    local page, tint = pages[activePage], pages[activePage].accent
    drawSectionStructure(20, 183, 600, 232, page, 1)
    text("COMET INPUT BRIDGE  //  HOST uinput", 36, 196, fonts.small, tint)
    text("One virtual keyboard + mouse. No guest-side Python/Pygame dependency.",
        36, 218, fonts.tiny, colors.muted)
    text("BRIDGE  //  " .. desktopInput.state .. "  " .. short(desktopInput.detail, 36),
        390, 218, fonts.tiny,
        desktopInput.state == "READY" and colors.green or colors.muted)
    local fixedRows = {
        {"LEFT STICK", "MOUSE POINTER"}, {"RIGHT STICK", "SCROLL"},
        {"D-PAD", "ARROW KEYS"},
    }
    for i, item in ipairs(fixedRows) do
        text(item[1], 38, 241 + (i - 1) * 18, fonts.tiny, colors.muted)
        text(item[2], 130, 241 + (i - 1) * 18, fonts.tiny, colors.white)
    end
    local function bindingText(value)
        return inputActionLabels[value] or string.upper(value or "DISABLED")
    end
    for i, row in ipairs(inputBindingRows) do
        local column = i <= 5 and 0 or 1
        local slot = i <= 5 and i or i - 5
        local x, y = 38 + column * 284, 298 + (slot - 1) * 18
        local option = i + 4
        if desktopInput.selectedOption == option then
            rounded(x - 4, y - 2, 270, 18, colors.panel2,
                {tint[1], tint[2], tint[3], 0.9})
        end
        text(row.label, x + 4, y, fonts.tiny, colors.muted)
        text(bindingText(desktopInput.bindings[row.key]), x + 90, y, fonts.tiny,
            desktopInput.selectedOption == option and colors.white or tint)
    end
    love.graphics.setColor(tint[1], tint[2], tint[3], 0.55)
    love.graphics.line(36, 390, 604, 390)
    local options = {
        {"POINTER", tostring(desktopInput.pointerSpeed) .. " px/s"},
        {"SCROLL", tostring(desktopInput.scrollSpeed) .. " steps/s"},
        {"DEADZONE", string.format("%.2f", desktopInput.deadzone)},
        {"BRIDGE", desktopInput.enabled and "ON" or "OFF"},
    }
    for i, item in ipairs(options) do
        local column = (i - 1) % 2
        local row = math.floor((i - 1) / 2)
        local x, y = 38 + column * 282, 397 + row * 17
        if desktopInput.selectedOption == i then
            rounded(x - 4, y - 2, 268, 17, colors.panel2,
                {tint[1], tint[2], tint[3], 0.9})
        end
        text(item[1], x + 4, y, fonts.tiny, colors.muted)
        text(item[2], x + 100, y, fonts.tiny,
            desktopInput.selectedOption == i and colors.white or tint)
    end
end

local function selectedMediaRows()
    return mediaMode == "RADIO" and mediaItemsRadio or mediaItemsTV
end

local function drawMediaVault()
    local page, tint = pages[activePage], pages[activePage].accent
    drawSectionStructure(20, 183, 600, 232, page, 1)
    text("MEDIA VAULT  //  IPTV + BROADCAST AUDIO", 36, 196, fonts.small, tint)
    local modeX = mediaMode == "RADIO" and 38 or 130
    rounded(modeX, 218, 82, 23, colors.panel2, {tint[1], tint[2], tint[3], 0.9})
    text("TV", 59, 222, fonts.tiny, mediaMode == "TV" and colors.white or colors.muted)
    text("RADIO", 144, 222, fonts.tiny, mediaMode == "RADIO" and colors.white or colors.muted)
    text(mediaMode == "RADIO" and "WEB RADIO PRESETS / FAVOURITES"
        or short(mediaCatalog.name, 34), 234, 222, fonts.tiny, colors.muted)

    local rows = selectedMediaRows()
    local count = #rows
    if mediaSelectedIndex > count then mediaSelectedIndex = math.max(1, count) end
    rounded(34, 248, 260, 148, colors.panel2, colors.line)
    local first = math.max(1, math.min(mediaSelectedIndex - 2, math.max(1, count - 5)))
    for visible = 1, 6 do
        local index = first + visible - 1
        local item = rows[index]
        if item then
            local y = 255 + (visible - 1) * 22
            if index == mediaSelectedIndex then
                rounded(40, y - 2, 246, 20, colors.bg, {tint[1], tint[2], tint[3], 0.8})
            end
            text(short(item.name, 28) .. (item.favorite and " ★" or ""), 48, y,
                fonts.tiny, index == mediaSelectedIndex and colors.white or colors.muted)
        end
    end
    rounded(306, 248, 296, 148, colors.panel2, colors.line)
    local chosen = rows[mediaSelectedIndex]
    if chosen then
        text(short(chosen.name, 31), 320, 259, fonts.medium, colors.white)
        if mediaMode == "RADIO" then
            text(short(chosen.genre, 36), 320, 284, fonts.tiny, tint)
            text("WEB RADIO STREAM", 320, 306, fonts.tiny, colors.muted)
            text("A  PLAY SELECTED", 320, 331, fonts.small, tint)
            text("Y  " .. (chosen.favorite and "UNFAVOURITE" or "FAVOURITE") .. "   X STOP",
                320, 354, fonts.tiny, colors.amber)
        else
            local epg = mediaEpgById[chosen.id] or {}
            text(short(chosen.group, 36), 320, 281, fonts.tiny, tint)
            text("NOW  " .. short(epg.current or "NO EPG DATA", 34), 320, 303,
                fonts.tiny, colors.white)
            text("NEXT " .. short(epg.next or "NOT AVAILABLE", 34), 320, 324,
                fonts.tiny, colors.muted)
            text("A  PLAY IPTV", 320, 350, fonts.small, tint)
            text("Y  " .. (chosen.favorite and "UNFAV" or "FAV") .. "   X STOP",
                320, 373, fonts.tiny, colors.amber)
        end
    else
        text("NO ITEMS IN THIS VIEW", 320, 270, fonts.small, colors.amber)
        text("Refresh the catalogue or select RADIO.", 320, 298, fonts.tiny, colors.muted)
    end
    text("LIBRARY  //  " .. mediaCatalog.playlists .. " PLAYLISTS  ·  "
        .. mediaCatalog.channels .. " TV  ·  " .. mediaCatalog.radios .. " RADIO",
        38, 375, fonts.tiny, colors.white)
    text("NOW  //  " .. mediaStatus.state .. "  "
        .. short(mediaStatus.title ~= "" and mediaStatus.title or "NOT PLAYING", 48),
        38, 393, fonts.tiny,
        mediaStatus.state == "PLAYING" and colors.green or colors.muted)
    if mediaCatalog.error ~= "" then
        text(short(mediaCatalog.error, 76), 38, 408, fonts.tiny, colors.amber)
    else
        text("EPG  //  " .. short(mediaEpgStatus, 58), 38, 408, fonts.tiny,
            mediaEpgStatus:find("READY", 1, true) and colors.green or colors.muted)
    end
end

local function drawPageContent()
    if activePage == 8 then drawDesktopInput()
    elseif activePage == 9 then drawMediaVault()
    elseif activePage == 1 then drawOverview()
    elseif activePage == 2 then drawSetup()
    elseif activePage == 3 then drawAppDeck()
    elseif activePage == 4 then drawUplink()
    elseif activePage == 5 then drawForge()
    elseif activePage == 6 then drawSystemTools()
    elseif activePage == 7 then drawDiagnostics()
    else drawModule() end
end

local function drawLegendItem(x, key, label, tint)
    rounded(x, 434, 34, 22, colors.panel2, {tint[1], tint[2], tint[3], 0.9})
    love.graphics.setFont(fonts.tiny)
    setColor(colors.white)
    love.graphics.printf(key, x, 438, 34, "center")
    text(label, x + 41, 438, fonts.tiny, colors.muted)
end

local function drawSectionOverlay()
    if sectionOverlayProgress <= 0.01 then return end
    local p = math.max(0, math.min(1, sectionOverlayProgress))
    local t = 1 - math.pow(1 - p, 3)
    love.graphics.setColor(0.002, 0.006, 0.014, 0.72 * t)
    love.graphics.rectangle("fill", 0, 0, W, H)

    local x = 20 - 12 * t
    local y = 184 - 108 * t
    local w = 600 + 24 * t
    local h = 232 + 156 * t
    local page = pages[activePage]
    drawSectionStructure(x, y, w, h, page, t)

    if p > 0.72 then
        drawPageIcon(page, 34, 98, 0.9, 1)
        text(page.title, 58, 82, fonts.medium, page.accent)
        text(short(page.subtitle, 78), 58, 105, fonts.tiny, colors.muted)
        love.graphics.setColor(page.accent[1], page.accent[2], page.accent[3], 0.72)
        love.graphics.setLineWidth(1)
        love.graphics.line(24, 124, 616, 124)

        love.graphics.setScissor(16, 128, 608, 290)
        love.graphics.push()
        love.graphics.translate(0, -overlayScroll * t)
        drawPageContent()
        love.graphics.pop()
        love.graphics.setScissor()

        love.graphics.setColor(page.accent[1], page.accent[2], page.accent[3], 0.7)
        love.graphics.line(18, 425, 622, 425)
        if page.id == "setup" then
            drawLegendItem(20, "↑↓", "PROFILE", page.accent)
            drawLegendItem(175, "←→", "TF SLOT", page.accent)
            drawLegendItem(330, "A", "INSTALL / LAUNCH", page.accent)
            drawLegendItem(485, "B", "CLOSE", page.accent)
        elseif page.id == "sessions" then
            drawLegendItem(20, "↑↓", "APP", page.accent)
            drawLegendItem(175, "←→", "CATEGORY", page.accent)
            drawLegendItem(330, "A", "LAUNCH", page.accent)
            drawLegendItem(485, "B", "CLOSE", page.accent)
        elseif page.id == "forge" then
            drawLegendItem(20, "↑↓", "PACKAGE", page.accent)
            drawLegendItem(175, "←→", "CATEGORY", page.accent)
            drawLegendItem(330, "A/X/Y", "APT", page.accent)
            drawLegendItem(485, "B", "CLOSE", page.accent)
        elseif page.id == "input" then
            drawLegendItem(20, "↑↓", "OPTION", page.accent)
            drawLegendItem(175, "←→", "ADJUST", page.accent)
            drawLegendItem(330, "Y", "RESET", page.accent)
            drawLegendItem(485, "B", "CLOSE", page.accent)
        elseif page.id == "media" then
            drawLegendItem(20, "↑↓", "ITEM", page.accent)
            drawLegendItem(175, "←→", "TV / RADIO", page.accent)
            drawLegendItem(330, "A/Y", "PLAY / FAV", page.accent)
            drawLegendItem(485, "X", "STOP", page.accent)
        elseif page.id == "diagnostics" then
            drawLegendItem(20, "Y", "EXPORT", page.accent)
            drawLegendItem(175, "B", "CLOSE", page.accent)
            drawLegendItem(330, "L1/R1", "SECTION", page.accent)
            drawLegendItem(485, "SEL", "CONSOLE", page.accent)
        else
            drawLegendItem(20, "A", "ACTION", page.accent)
            drawLegendItem(175, "B", "CLOSE", page.accent)
            drawLegendItem(330, "↑↓", "SCROLL", page.accent)
            drawLegendItem(485, "SEL", "CONSOLE", page.accent)
        end
    end
end

local function scrollSectionOverlay(direction)
    overlayScroll = math.max(0, math.min(overlayScrollLimit, overlayScroll + direction * 26))
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
    text(short(label, 48), 24, 439, fonts.tiny, noticeTimer > 0 and colors.cyan or colors.muted)
    text("A OPEN  /  SELECT LOG", 430, 439, fonts.tiny, colors.muted)
    text("v" .. appVersion, 594, 439, fonts.tiny, colors.muted)
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
    text("NOW PLAYING  //  " .. short(mediaStatus.title ~= "" and mediaStatus.title or "NOTHING",
        38), x + 24, y + 104, fonts.small, colors.white)
    text("MEDIA  " .. mediaStatus.state .. "  //  "
        .. (mediaStatus.kind ~= "" and mediaStatus.kind:upper() or "IDLE"),
        x + 24, y + 131, fonts.tiny,
        mediaStatus.state == "PLAYING" and colors.green or colors.muted)
    text("DEBIAN  " .. imageDownload.state .. "  //  "
        .. string.format("%d%%", imageDownload.percent or 0), x + 24, y + 158,
        fonts.tiny, colors.violet)
    text("A  PAUSE / RESUME     X  STOP     Y  MEDIA VAULT", x + 24, y + 204,
        fonts.small, colors.white)
    text("M  CLOSE PANEL   //   START + SELECT  EXIT COMET", x + 24, y + 232,
        fonts.tiny, colors.amber)
    text("Radio stays in the frontend; IPTV uses the full-screen player handoff.", x + 24, y + 258,
        fonts.tiny, colors.muted)
end

function love.load()
    local versionContent = love.filesystem.read("version.txt")
    local bundledVersion = versionContent and versionContent:match("(%S+)")
    if bundledVersion then appVersion = bundledVersion end
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
            normalizeSelectedSlot(false)
        end
    end
    readDesktopInputConfig()
    readDesktopInputStatus()
    readMediaStatus()
    readMediaCatalog()
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
    if operationScreen.kind == "DESKTOP" then
        local finished = state == "READY" or state == "FAILED"
            or state == "CLEANUP_REQUIRED" or state == "BUSY"
        updateOperationScreen("DESKTOP", state, imageDownload.percent, message or "", finished)
    end
    if location and location:find("/mnt/mmc/", 1, true) then
        installedSlot = "tf1"
    elseif location and location:find("/mnt/sdcard/", 1, true) then
        installedSlot = "tf2"
    end
    if state == "READY" and (previousState ~= "READY" or previousProfile ~= imageDownload.profile or previousSlot ~= installedSlot) then
        forgeLoaded = false
        appCatalogLoaded = false
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
    local overlayTarget = sectionOverlayOpen and 1 or 0
    sectionOverlayProgress = sectionOverlayProgress
        + (overlayTarget - sectionOverlayProgress) * math.min(1, dt * 10)
    if math.abs(overlayTarget - sectionOverlayProgress) < 0.002 then
        sectionOverlayProgress = overlayTarget
    end
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

    mediaHeartbeat = mediaHeartbeat + dt
    if mediaHeartbeat >= 1 then
        mediaHeartbeat = 0
        heartbeatMedia()
    end
    mediaPoll = mediaPoll + dt
    if mediaPoll >= 0.5 then
        mediaPoll = 0
        readMediaStatus()
        readMediaCatalog()
        readDesktopInputStatus()
    end
    if activePage == 9 and not mediaCatalogLoaded and not mediaCatalogBusy then
        queueMediaCatalogue(false)
    end

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
    appRegistryPoll = appRegistryPoll + dt
    if appRegistryPoll >= 0.5 then
        appRegistryPoll = 0
        readAppFiles()
    end
    probeTimer = probeTimer + dt
    if probe and probeTimer >= 10 then
        probeTimer = 0
        local success, snapshot = pcall(probe.read)
        if success and snapshot then
            device = snapshot
            normalizeSelectedSlot(true)
        end
    end
    if boot.done and maybeRunAutoBootstrap then maybeRunAutoBootstrap() end
    if operationScreen.open then
        operationScreen.poll = operationScreen.poll + dt
        if operationScreen.poll >= 0.35 then
            operationScreen.poll = 0
            refreshOperationLog()
        end
    end
end

local function drawOperationScreen()
    love.graphics.clear(0.006, 0.009, 0.013, 1)
    setColor(colors.cyan)
    love.graphics.rectangle("fill", 0, 0, W, 3)
    setColor(colors.green)
    love.graphics.rectangle("fill", 20, 24, 4, 42)
    text("COMET DESK  //  SYSTEM CONSOLE", 34, 22, fonts.tiny, colors.muted)
    text(short(operationScreen.title, 42), 34, 42, fonts.medium, colors.white)
    text(operationScreen.state, 500, 28, fonts.tiny,
        operationScreen.state == "FAILED" and colors.amber or colors.green)
    rounded(20, 82, 600, 288, {0.008, 0.014, 0.018, 1}, colors.line)
    text("ROOT TASK  /  LIVE OUTPUT", 36, 96, fonts.tiny, colors.cyan)
    setColor({0.10, 0.22, 0.18, 0.55})
    love.graphics.line(36, 119, 604, 119)
    local rows = operationScreen.lines or {}
    local first = math.max(1, #rows - 8)
    local shown = 0
    for index = first, #rows do
        shown = shown + 1
        text("> " .. short(rows[index], 78), 38, 130 + (shown - 1) * 24,
            fonts.tiny, colors.green)
    end
    if shown == 0 then
        text("> " .. short(operationScreen.message, 76), 38, 136, fonts.small, colors.green)
        text("> Waiting for the bootstrap worker...", 38, 165, fonts.tiny, colors.muted)
    end
    love.graphics.line(36, 344, 604, 344)
    text(short(operationScreen.message, 74), 28, 382, fonts.small, colors.white)
    drawProgress(28, 410, 584, 14, operationScreen.percent, colors.cyan)
    if operationScreen.percent == 0 and not operationScreen.done then
        local pulseX = 30 + (ambientTime * 150) % 480
        setColor(colors.cyan)
        love.graphics.rectangle("fill", pulseX, 412, 92, 10, 3, 3)
    end
    text(string.format("%d%%", operationScreen.percent), 28, 432, fonts.tiny, colors.cyan)
    local action = operationScreen.done and "SELECT / A  CLOSE CONSOLE"
        or "SELECT / B  HIDE CONSOLE  //  TASK CONTINUES"
    text(action, 270, 432, fonts.tiny, colors.muted)
    if operationScreen.done then
        local resultLine = operationScreen.state == "FAILED"
            and "TASK FAILED // CHECK THE LOG ABOVE"
            or (operationScreen.state == "CLEANUP_REQUIRED"
                and "TASK FINISHED // CHECK MOUNT CLEANUP"
                or "TASK FINISHED // COMET DESK READY")
        text(resultLine,
            28, 456, fonts.tiny,
            operationScreen.state == "FAILED" and colors.amber or colors.green)
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

    if operationScreen.open then
        drawOperationScreen()
        love.graphics.pop()
        return
    end

    drawBackground()
    drawHeader()
    drawNavigation()
    if activePage == 3 and not appCatalogLoaded then
        if installedSlot then queueAppCatalog() end
        appCatalogLoaded = true
    end
    if activePage == 4 and not uplinkStatus.loaded then
        queueUplinkAction("status")
        uplinkStatus.loaded = true
    end
    if activePage == 5 and not forgeLoaded then
        if installedSlot then queueForgeAction("catalog") end
        forgeLoaded = true
    end

    drawSectionWidget()
    drawFooter()
    drawQuickPanel()
    drawSectionOverlay()
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
    sectionOverlayOpen = false
    overlayScroll = 0
    pageChangedDirection = direction
    pageChangedAt = ambientTime
    setNotice("TAB // " .. pages[activePage].title)
end

local function activate()
    activePage = selected
    if sectionOverlayOpen then return end
    sectionOverlayOpen = true
    overlayScroll = 0
    pageChangedAt = ambientTime
    setNotice(pages[activePage].title .. " // SECTION OPEN")
end



local function shellQuote(value)
    return "'" .. tostring(value):gsub("'", "'\\''") .. "'"
end

local function cycleDesktopProfile(direction)
    selectedProfileIndex = ((selectedProfileIndex - 1 + direction) % #desktopProfiles) + 1
    selectedProfile = desktopProfiles[selectedProfileIndex].id
    setNotice("DESKTOP PROFILE // " .. selectedProfile:upper())
end

local function desktopConfigReady()
    if appRoot == "" then return false end
    local stream = io.open(appRoot .. "/data/desktop-config-revision", "r")
    if not stream then return false end
    local revision = tonumber(stream:read("*l") or "")
    stream:close()
    return revision == DESKTOP_CONFIG_REVISION
end

local function debianOperationBusy()
    if appRoot == "" then return nil end
    local statusPath = appRoot .. "/data/debian-lock.status"
    os.remove(statusPath)
    local script = appRoot .. "/service/desktop_environment.py"
    local command = "cd " .. shellQuote(appRoot) .. " && python3 "
        .. shellQuote(script) .. " check --slot " .. selectedSlot
        .. " --profile " .. selectedProfile
        .. " --app-dir " .. shellQuote(appRoot)
        .. " >/dev/null 2>&1"
    local result = os.execute(command)
    local stream = io.open(statusPath, "r")
    if not stream then return nil end
    local state = stream:read("*l")
    stream:close()
    os.remove(statusPath)
    if state == "BUSY" then return true end
    if state == "IDLE" and (result == 0 or result == true) then return false end
    return nil
end

local function clearStaleDesktopStatus()
    os.remove(appRoot .. "/data/desktop-environment.status")
    if imageDownload.state ~= "READY" then
        imageDownload.state = "FAILED"
        imageDownload.percent = 0
        imageDownload.message = "Recovered stale setup state; no Debian worker owns the system lock"
    end
end

local function startDesktopEnvironment()
    if appRoot == "" then
        setNotice("COMET DESK APP RUNNER PATH UNAVAILABLE")
        return
    end
    local busy = debianOperationBusy()
    if busy == nil then
        setNotice("COULD NOT VERIFY DEBIAN WORKER LOCK // CHECK LOG")
        return
    elseif busy then
        openOperationScreen("DESKTOP", "DEBIAN SYSTEM // BUSY",
            appRoot .. "/data/desktop-environment.log",
            "Another Comet Debian/APT worker still owns the shared system lock",
            imageDownload.state)
        setNotice("A REAL DEBIAN OPERATION IS STILL RUNNING")
        return
    end

    local runningStates = {
        STARTING = true, RUNNING = true, APT_UPDATE = true,
        INSTALLING_PROFILE = true, DOWNLOADING_ROOTFS = true,
        DOWNLOADING_TEMPLATE = true, EXPANDING_IMAGE = true,
        PREPARING_ROOTFS = true, EXTRACTING_ROOTFS = true,
    }
    if runningStates[imageDownload.state] then
        clearStaleDesktopStatus()
        setNotice("RECOVERED STALE DEBIAN STATUS // RETRYING")
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
        and desktopConfigReady()
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
    os.remove(appRoot .. "/data/desktop-environment.status")
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
        openOperationScreen("DESKTOP", "DEBIAN TRIXIE // BOOTSTRAP",
            appRoot .. "/data/desktop-environment.log",
            "Preparing Debian GNU/Linux 13 ARM64", "STARTING")
        setNotice("DEBIAN APT SETUP // " .. selectedProfile:upper())
    else
        setNotice("COULD NOT START DEBIAN ENVIRONMENT MANAGER")
    end
end

maybeRunAutoBootstrap = function()
    if autoBootstrapChecked or not boot.done then return end
    autoBootstrapChecked = true
    if appRoot == "" then return end
    local busy = debianOperationBusy()
    if busy == nil then
        activePage, selected, carouselTarget = 2, 2, 2
        setNotice("COULD NOT VERIFY DEBIAN WORKER LOCK // CHECK LOG")
        return
    elseif busy then
        openOperationScreen("DESKTOP", "DEBIAN TRIXIE // RESUME",
            appRoot .. "/data/desktop-environment.log",
            imageDownload.message, imageDownload.state)
        return
    end
    local runningStates = {
        STARTING = true, RUNNING = true, DOWNLOADING_TEMPLATE = true,
        PREPARING_ROOTFS = true, DOWNLOADING_ROOTFS = true,
        EXTRACTING_ROOTFS = true, APT_UPDATE = true,
        INSTALLING_PROFILE = true, EXPANDING_IMAGE = true,
    }
    if imageDownload.state == "READY" and desktopConfigReady() then return end
    if runningStates[imageDownload.state] then
        clearStaleDesktopStatus()
    end

    local roots = {
        tf1 = "/mnt/mmc/MUOS/CometDesk/Desktop/.comet-debian-ready",
        tf2 = "/mnt/sdcard/MUOS/CometDesk/Desktop/.comet-debian-ready",
    }
    local preferred = nil
    local minimum = 9 * 1024 * 1024 * 1024
    local function hasSpace(slot)
        local item = storageItem(slot)
        return storageUsable(slot) and item.stats.free_bytes >= minimum
    end
    for _, slot in ipairs({"tf1", "tf2"}) do
        local marker = io.open(roots[slot], "r")
        if marker then
            marker:close()
            if hasSpace(slot) then preferred = slot; break end
        end
    end
    if not preferred then
        if hasSpace(selectedSlot) then
            preferred = selectedSlot
        else
            local other = selectedSlot == "tf1" and "tf2" or "tf1"
            if hasSpace(other) then preferred = other end
        end
    end
    if not preferred then
        activePage, selected, carouselTarget = 2, 2, 2
        setNotice("BOOTSTRAP NEEDS A WRITABLE CARD WITH 9 GB FREE")
        return
    end

    selectedSlot = preferred
    activePage, selected, carouselTarget = 2, 2, 2
    pageChangedAt = ambientTime
    selectedProfileIndex, selectedProfile = 1, "labwc"
    startDesktopEnvironment()
end

local function startDesktopApplication(appId)
    if not appId or appId == "" then
        setNotice("SELECT AN INSTALLED APPLICATION")
        return
    end
    if appRoot == "" then
        setNotice("COMET APP RUNNER PATH UNAVAILABLE")
        return
    end
    if not installedSlot or imageDownload.state ~= "READY" then
        setNotice("DEBIAN TRIXIE MUST BE READY BEFORE APP LAUNCH")
        return
    end
    if not desktopConfigReady() then
        setNotice("UPDATE DESKTOP SYSTEM BEFORE APP LAUNCH")
        return
    end
    if selectedProfile ~= imageDownload.profile then
        setNotice("INSTALL THE SELECTED DESKTOP PROFILE FIRST")
        return
    end
    local request = appRoot .. "/data/desktop-session.request"
    local temporary = request .. ".tmp"
    os.remove(temporary)
    local stream = io.open(temporary, "w")
    if not stream then
        setNotice("COULD NOT CREATE APP SESSION REQUEST")
        return
    end
    stream:write(installedSlot, "\n", selectedProfile, "\n", appId, "\n")
    stream:close()
    if not os.rename(temporary, request) then
        os.remove(temporary)
        setNotice("COULD NOT QUEUE APPLICATION SESSION")
        return
    end
    setNotice("COMET // LAUNCHING " .. appId:upper())
    love.event.quit()
end

local function toggleQuickPanel()
    quickPanelOpen = not quickPanelOpen
    quickPanelAge = 0
end

local function toggleOperationScreen()
    if operationScreen.kind == "" and appRoot ~= "" then
        local statusPath = appRoot .. "/data/desktop-environment.status"
        local status = io.open(statusPath, "r")
        if status then
            local line = status:read("*l") or ""
            status:close()
            local state, percent, message =
                line:match("^([^|]+)|(%d+)|([^|]*)|([^|]*)|(.*)$")
            if state then
                openOperationScreen("DESKTOP", "DEBIAN TRIXIE // TASK",
                    appRoot .. "/data/desktop-environment.log", message, state)
                operationScreen.percent = tonumber(percent) or 0
                operationScreen.done = state == "READY" or state == "FAILED"
                    or state == "CLEANUP_REQUIRED" or state == "BUSY"
            end
        end
        if operationScreen.kind == "" then
            local logPath = appRoot .. "/data/desktop-environment.log"
            local log = io.open(logPath, "rb")
            if log then
                log:close()
                openOperationScreen("DESKTOP", "DEBIAN TRIXIE // CONSOLE",
                    logPath, "Latest Debian bootstrap output", imageDownload.state)
            end
        end
    end
    if operationScreen.kind == "" then
        setNotice("NO DESKTOP / APT TASK CONSOLE AVAILABLE")
        return
    end
    operationScreen.open = not operationScreen.open
    if operationScreen.open then
        refreshOperationLog()
        setNotice("TASK CONSOLE SHOWN")
    else
        setNotice("CONSOLE HIDDEN // TASK CONTINUES")
    end
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
    if key == "f9" then
        keyboardHeld.start = true
        maybeExitKeyboard()
        return
    end
    if key == "f8" then
        keyboardHeld.select = true
        if keyboardHeld.start then
            maybeExitKeyboard()
        else
            toggleOperationScreen()
        end
        return
    end
    if operationScreen.open then
        if key == "escape" or key == "backspace" or key == "x" or key == "b" then
            operationScreen.open = false
            setNotice(operationScreen.done and "SYSTEM TASK CLOSED"
                or "TASK CONTINUES IN BACKGROUND")
        end
        return
    end
    if key == "m" then toggleQuickPanel(); return end
    if quickPanelOpen then
        if key == "escape" or key == "backspace" or key == "b" then
            toggleQuickPanel()
        elseif key == "return" or key == "space" then
            queueMediaToggle()
        elseif key == "x" then
            queueMediaStop()
        elseif key == "y" then
            toggleQuickPanel()
            selected, activePage, carouselTarget = 9, 9, 9
            activate()
        end
        return
    end

    if forgeSearchActive or appSearchActive then
        if key == "escape" then
            forgeSearchActive, appSearchActive = false, false
        elseif key == "backspace" then
            if forgeSearchActive then forgeSearch = forgeSearch:sub(1, math.max(0, #forgeSearch - 1)) end
            if appSearchActive then appSearch = appSearch:sub(1, math.max(0, #appSearch - 1)) end
        end
        return
    end
    if key == "pageup" and sectionOverlayOpen then scrollSectionOverlay(-1); return end
    if key == "pagedown" and sectionOverlayOpen then scrollSectionOverlay(1); return end
    if key == "left" then
        if not sectionOverlayOpen then return end
        if activePage == 2 then selectedSlot = "tf1"; normalizeSelectedSlot(true)
        elseif activePage == 3 then cycleAppCategory(-1)
        elseif activePage == 5 then cycleForgeCategory(-1)
        elseif activePage == 8 then adjustDesktopInput(-1)
        elseif activePage == 9 then
            mediaMode = mediaMode == "RADIO" and "TV" or "RADIO"
            mediaSelectedIndex = 1
        end
    elseif key == "right" or key == "d" then
        if not sectionOverlayOpen then return end
        if activePage == 2 then selectedSlot = "tf2"; normalizeSelectedSlot(true)
        elseif activePage == 3 then cycleAppCategory(1)
        elseif activePage == 5 then cycleForgeCategory(1)
        elseif activePage == 8 then adjustDesktopInput(1)
        elseif activePage == 9 then
            mediaMode = mediaMode == "RADIO" and "TV" or "RADIO"
            mediaSelectedIndex = 1
        end
    elseif key == "up" or key == "w" then
        if not sectionOverlayOpen then return end
        if activePage == 2 then cycleDesktopProfile(-1)
        elseif activePage == 3 then appSelectedIndex = math.max(1, appSelectedIndex - 1)
        elseif activePage == 5 then forgeSelectedIndex = math.max(1, forgeSelectedIndex - 1)
        elseif activePage == 8 then desktopInput.selectedOption = math.max(1, desktopInput.selectedOption - 1)
        elseif activePage == 9 then mediaSelectedIndex = math.max(1, mediaSelectedIndex - 1)
        else scrollSectionOverlay(-1) end
    elseif key == "down" or key == "s" then
        if not sectionOverlayOpen then return end
        if activePage == 2 then cycleDesktopProfile(1)
        elseif activePage == 3 then appSelectedIndex = math.min(#filteredApps(), appSelectedIndex + 1)
        elseif activePage == 5 then forgeSelectedIndex = math.min(#forgeFilteredPackages(), forgeSelectedIndex + 1)
        elseif activePage == 8 then desktopInput.selectedOption = math.min(13, desktopInput.selectedOption + 1)
        elseif activePage == 9 then mediaSelectedIndex = math.min(#selectedMediaRows(), mediaSelectedIndex + 1)
        else scrollSectionOverlay(1) end
    elseif key == "/" and sectionOverlayOpen and activePage == 5 then
        forgeSearchActive = true
        setNotice("THE FORGE SEARCH // TYPE TO FILTER")
    elseif key == "/" and sectionOverlayOpen and activePage == 3 then
        appSearchActive = true
        setNotice("APP DECK SEARCH // TYPE TO FILTER")
    elseif key == "a" or key == "return" or key == "space" or key == "z" or key == "i" then
        if not sectionOverlayOpen then
            activate()
            return
        end
        if activePage == 2 then
            startDesktopEnvironment()
        elseif activePage == 8 then
            adjustDesktopInput(1)
        elseif activePage == 9 then
            local item = selectedMediaRows()[mediaSelectedIndex]
            if item then
                if mediaMode == "RADIO" then queueMediaRadio(item) else queueMediaTV(item) end
            end
        elseif activePage == 3 then
            local item = filteredApps()[appSelectedIndex]
            if item then startDesktopApplication(item.id) end
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
        else
            setNotice(pages[activePage].title .. " // NO PRIMARY ACTION")
        end
    elseif key == "y" and sectionOverlayOpen and activePage == 8 then
        resetDesktopInput()
    elseif key == "y" and sectionOverlayOpen and activePage == 9 then
        queueMediaFavourite(selectedMediaRows()[mediaSelectedIndex])
    elseif key == "r" and sectionOverlayOpen and activePage == 9 then
        queueMediaRefresh()
    elseif key == "x" and sectionOverlayOpen and activePage == 9 then
        queueMediaStop()
    elseif key == "r" and sectionOverlayOpen and activePage == 5 then
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
    elseif key == "y" and sectionOverlayOpen and activePage == 3 then
        appCatalogLoaded = false
        queueAppCatalog()
        appCatalogLoaded = true
    elseif key == "y" and sectionOverlayOpen and activePage == 5 then
        queueForgeAction("update")
    elseif key == "y" and sectionOverlayOpen and activePage == 6 then
        queueAppCatalog()
    elseif (key == "e" or key == "y") and sectionOverlayOpen then
        exportDiagnostics()
    elseif key == "escape" or key == "x" or key == "b" or key == "backspace" then
        if sectionOverlayOpen then
            sectionOverlayOpen = false
            overlayScroll = 0
            setNotice("SECTION CLOSED")
        else
            setNotice("COMET DESK // READY")
        end
    end
end



function love.textinput(value)
    if not sectionOverlayOpen then return end
    if activePage == 5 and forgeSearchActive then
        if #forgeSearch < 40 then forgeSearch = forgeSearch .. value end
    elseif activePage == 3 and appSearchActive then
        if #appSearch < 40 then appSearch = appSearch .. value end
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

    -- SELECT is a dedicated show/hide switch for the live download/APT console.
    if button == "select" or button == "back" then
        toggleOperationScreen()
        return
    end
    if operationScreen.open then
        if button == "b" or (operationScreen.done and button == "a") then
            operationScreen.open = false
            setNotice(operationScreen.done and "SYSTEM TASK CLOSED"
                or "TASK CONTINUES IN BACKGROUND")
        end
        return
    end
    if button == "guide" then
        toggleQuickPanel()
        return
    end
    if quickPanelOpen then
        if button == "b" then
            toggleQuickPanel()
        elseif button == "a" then
            queueMediaToggle()
        elseif button == "x" then
            queueMediaStop()
        elseif button == "y" then
            toggleQuickPanel()
            selected, activePage, carouselTarget = 9, 9, 9
            sectionOverlayOpen = true
            sectionOverlayProgress = 0
            overlayScroll = 0
        end
        return
    end
    if button == "leftshoulder" then
        cyclePage(-1)
        return
    elseif button == "rightshoulder" then
        cyclePage(1)
        return
    elseif button == "b" then
        if sectionOverlayOpen then
            sectionOverlayOpen = false
            overlayScroll = 0
            setNotice("SECTION CLOSED")
        end
        return
    end

    if button == "dpup" then
        if not sectionOverlayOpen then return end
        if activePage == 2 then cycleDesktopProfile(-1)
        elseif activePage == 3 then appSelectedIndex = math.max(1, appSelectedIndex - 1)
        elseif activePage == 5 then forgeSelectedIndex = math.max(1, forgeSelectedIndex - 1)
        elseif activePage == 8 then desktopInput.selectedOption = math.max(1, desktopInput.selectedOption - 1)
        elseif activePage == 9 then mediaSelectedIndex = math.max(1, mediaSelectedIndex - 1)
        else scrollSectionOverlay(-1) end
    elseif button == "dpdown" then
        if not sectionOverlayOpen then return end
        if activePage == 2 then cycleDesktopProfile(1)
        elseif activePage == 3 then appSelectedIndex = math.min(#filteredApps(), appSelectedIndex + 1)
        elseif activePage == 5 then forgeSelectedIndex = math.min(#forgeFilteredPackages(), forgeSelectedIndex + 1)
        elseif activePage == 8 then desktopInput.selectedOption = math.min(13, desktopInput.selectedOption + 1)
        elseif activePage == 9 then mediaSelectedIndex = math.min(#selectedMediaRows(), mediaSelectedIndex + 1)
        else scrollSectionOverlay(1) end
    elseif button == "dpleft" and sectionOverlayOpen and activePage == 2 then
        selectedSlot = "tf1"
        normalizeSelectedSlot(true)
    elseif button == "dpright" and sectionOverlayOpen and activePage == 2 then
        selectedSlot = "tf2"
        normalizeSelectedSlot(true)
    elseif button == "dpleft" and sectionOverlayOpen and activePage == 3 then
        cycleAppCategory(-1)
    elseif button == "dpright" and sectionOverlayOpen and activePage == 3 then
        cycleAppCategory(1)
    elseif button == "dpleft" and sectionOverlayOpen and activePage == 5 then
        cycleForgeCategory(-1)
    elseif button == "dpright" and sectionOverlayOpen and activePage == 5 then
        cycleForgeCategory(1)
    elseif button == "dpleft" and sectionOverlayOpen and activePage == 8 then
        adjustDesktopInput(-1)
    elseif button == "dpright" and sectionOverlayOpen and activePage == 8 then
        adjustDesktopInput(1)
    elseif button == "dpleft" and sectionOverlayOpen and activePage == 9 then
        mediaMode = mediaMode == "RADIO" and "TV" or "RADIO"
        mediaSelectedIndex = 1
    elseif button == "dpright" and sectionOverlayOpen and activePage == 9 then
        mediaMode = mediaMode == "RADIO" and "TV" or "RADIO"
        mediaSelectedIndex = 1
    elseif button == "a" then
        if not sectionOverlayOpen then
            activate()
            return
        end
        if activePage == 2 then
            startDesktopEnvironment()
        elseif activePage == 8 then
            adjustDesktopInput(1)
        elseif activePage == 9 then
            local item = selectedMediaRows()[mediaSelectedIndex]
            if item then
                if mediaMode == "RADIO" then queueMediaRadio(item) else queueMediaTV(item) end
            end
        elseif activePage == 3 then
            local item = filteredApps()[appSelectedIndex]
            if item then startDesktopApplication(item.id) end
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
        else
            setNotice(pages[activePage].title .. " // NO PRIMARY ACTION")
        end
    elseif button == "x" and sectionOverlayOpen and activePage == 5 then
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
    elseif button == "y" and sectionOverlayOpen and activePage == 8 then
        resetDesktopInput()
    elseif button == "y" and sectionOverlayOpen and activePage == 9 then
        queueMediaFavourite(selectedMediaRows()[mediaSelectedIndex])
    elseif button == "start" and sectionOverlayOpen and activePage == 9 then
        queueMediaRefresh()
    elseif button == "x" and sectionOverlayOpen and activePage == 9 then
        queueMediaStop()
    elseif button == "y" and sectionOverlayOpen and activePage == 3 then
        appCatalogLoaded = false
        queueAppCatalog()
        appCatalogLoaded = true
    elseif button == "y" and sectionOverlayOpen and activePage == 5 then
        queueForgeAction("update")
    elseif button == "y" and sectionOverlayOpen and activePage == 6 then
        queueAppCatalog()
    elseif button == "y" and sectionOverlayOpen then
        exportDiagnostics()
    end
end



function love.gamepadreleased(joystick, button)
    local held = gamepadHeld[joystick]
    if not held then return end
    if button == "start" then held.start = false end
    if button == "back" or button == "select" then held.select = false end
end

function love.wheelmoved(x, y)
    if sectionOverlayOpen then scrollSectionOverlay(y > 0 and -1 or 1) end
end
