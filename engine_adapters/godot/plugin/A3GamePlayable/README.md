# A3GamePlayable for Godot

This adapter-owned Godot 4 add-on exposes a game-neutral UDP session boundary.
`GodotClient.runtime.sessions` sends JSON messages to the `A3GameRuntime`
autoload; generated gameplay subclasses or composes `A3GameRuntimeEntity` and
handles its `runtime_input` signal. The framework deliberately owns no movement,
combat, camera, vehicle, HUD, or game rules.

Install it with `GodotClient.plugin.install_framework()`. The public runtime
endpoint defaults to `127.0.0.1:30050` and can be changed with
`A3GAME_GODOT_RUNTIME_HOST` / `A3GAME_GODOT_RUNTIME_PORT` or the matching
`a3game/runtime_host` / `a3game/runtime_port` project settings.

Sessions default to `world_001`. A World reset removes only matching native
session records and emits `world_reset`; gameplay may use that signal for its
own World cleanup. Entity clear always removes matching native session records.
It calls `clear_a3game_entity()` only when `destroy_actor` is `true`, allowing a
caller to detach runtime control while retaining the Godot node.

Leaving erases the native controller and deactivates its Python-side binding.
The departed controller cannot send input or be revived by a heartbeat; call
`join()` to create and register a fresh controller before resuming control.
Rejoining with the same participant ID preserves its entity ID and atomically
replaces the previous native controller binding, so the old controller cannot
continue sending input. Participant-based leave targets that current binding.

`session_joined` is an entity-creation request: it is emitted only when the
entity ID is not already present in the `a3game_runtime_entity` group. A
controller replacement never emits a synthetic `session_left` followed by a
second `session_joined`; it emits
`session_reconnected(previous_session, session)` instead. A join after an
explicit leave also emits `session_reconnected` when the entity is still in
the scene tree. Use `A3GameRuntime.find_entity(entity_id)` when gameplay needs
the retained node. `session_left` means that control was detached, not that the
entity should be freed; entity destruction belongs to `clear_entity()` or
game-owned World cleanup. These rules keep one native node per persistent
entity ID across controller reconnects.
