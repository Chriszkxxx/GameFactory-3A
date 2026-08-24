extends SceneTree


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		_fail("main.tscn did not load as PackedScene")
		return
	var game := packed.instantiate()
	root.add_child(game)
	for _frame in range(120):
		await physics_frame
	var first: Dictionary = game.smoke_snapshot()
	for _frame in range(150):
		await physics_frame
	var second: Dictionary = game.smoke_snapshot()
	if int(second.get("tick", 0)) <= int(first.get("tick", 0)):
		_fail("physics tick did not advance")
		return
	if not bool(second.get("camera_owned_by_player", false)):
		_fail("first-person camera is not owned by the player")
		return
	if float(second.get("distance", 0.0)) < 0.5:
		_fail("player did not move through the arena")
		return
	if int(second.get("targets", 0)) != 6:
		_fail("target range was not constructed")
		return
	if int(second.get("shots", 0)) < 6 or int(second.get("hits", 0)) < 4:
		_fail("camera hitscan did not damage live targets")
		return
	if int(second.get("reloads", 0)) < 1:
		_fail("magazine reload state was not exercised")
		return
	print("A3GAME_SMOKE_OK ", JSON.stringify(second))
	quit(0)


func _fail(message: String) -> void:
	push_error("A3GAME_SMOKE_FAIL: " + message)
	quit(1)
