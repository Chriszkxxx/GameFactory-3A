# Optional pinned bone maps

Do **not** check in Mixamo/MoMask → Puppeteer maps for a generic character.

Puppeteer joint names (`joint0…N`) are per-mesh prediction order, so a full
bone map is only valid for the single rig it was generated against. The
pipeline default is `mapping_auto`.

Drop a JSON here only when you deliberately re-animate the **same** rig and
have verified `pinned_mapping_fits_rig(name, that_rig.txt)`. Prefer passing
`mapping_path` on the task for one-off maps.
