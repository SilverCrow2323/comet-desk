local storage = dofile("love/storage_selection.lua")

local function availability(tf1, tf2)
    return function(slot)
        if slot == "tf1" then return tf1 end
        if slot == "tf2" then return tf2 end
        return false
    end
end

local slot, changed = storage.normalize("tf2", availability(true, false))
assert(slot == "tf1" and changed, "missing TF2 must fall back to TF1")

slot, changed = storage.normalize("tf1", availability(true, true))
assert(slot == "tf1" and not changed, "TF1 remains the default when both cards exist")

slot, changed = storage.normalize("tf1", availability(false, true))
assert(slot == "tf2" and changed, "TF2 is used when TF1 is unavailable")

slot, changed = storage.normalize("tf2", availability(true, true))
assert(slot == "tf2" and not changed, "keep a manually selected usable TF2")

slot, changed = storage.normalize("tf2", availability(false, false))
assert(slot == "tf2" and not changed, "do not invent a usable target")
