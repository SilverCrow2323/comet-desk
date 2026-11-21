-- Comet Desk // storage target selection policy
local M = {}

-- Keep the user's selected mounted target. If it disappears or becomes
-- unusable, prefer TF1; use TF2 only when TF1 is not usable.
function M.normalize(selected, isUsable)
    if type(isUsable) ~= "function" then
        error("isUsable must be a function")
    end
    if selected ~= "tf1" and selected ~= "tf2" then
        selected = "tf1"
    end
    if isUsable(selected) then
        return selected, false
    end
    if isUsable("tf1") then
        return "tf1", selected ~= "tf1"
    end
    if isUsable("tf2") then
        return "tf2", selected ~= "tf2"
    end
    return selected, false
end

return M
