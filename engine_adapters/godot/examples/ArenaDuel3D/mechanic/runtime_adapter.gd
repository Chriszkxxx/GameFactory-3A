extends Node

## Public bridge between the mechanic scene and the optional UI module.
## The UI never reaches into fighters or arena nodes directly.

signal state_changed(snapshot: Dictionary)
signal event_emitted(event_name: String, payload: Dictionary)

var _game: Node = null


func _ready() -> void:
	call_deferred("_bind_current_scene")


func _bind_current_scene() -> void:
	var scene := get_tree().current_scene
	if scene != null and scene.has_method("get_runtime_snapshot"):
		bind_game(scene)


func bind_game(game: Node) -> void:
	if _game == game:
		return
	_game = game
	if _game.has_signal("state_changed"):
		_game.state_changed.connect(_on_game_state_changed)
	if _game.has_signal("event_emitted"):
		_game.event_emitted.connect(_on_game_event_emitted)
	_on_game_state_changed(_game.get_runtime_snapshot())


func _on_game_state_changed(snapshot: Dictionary) -> void:
	state_changed.emit(snapshot)


func _on_game_event_emitted(event_name: String, payload: Dictionary) -> void:
	event_emitted.emit(event_name, payload)


func get_state_snapshot() -> Dictionary:
	return _game.get_runtime_snapshot() if _game != null else {}


func handle_runtime_command(command_name: String, payload: Dictionary = {}) -> Dictionary:
	if _game == null or not _game.has_method("handle_runtime_command"):
		return {"ok": false, "error": "game_not_bound", "command": command_name}
	return _game.handle_runtime_command(command_name, payload)


func start_match() -> Dictionary:
	return handle_runtime_command("start_match")


func restart_match() -> Dictionary:
	return handle_runtime_command("restart_match")


func set_paused(value: bool) -> Dictionary:
	return handle_runtime_command("set_paused", {"paused": value})


func apply_input(input_state: Dictionary, fighter: String = "p1") -> Dictionary:
	return handle_runtime_command("apply_input", {"input_state": input_state, "fighter": fighter})
