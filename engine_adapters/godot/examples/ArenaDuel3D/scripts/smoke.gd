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
	for _frame in range(180):
		await physics_frame
	var second: Dictionary = game.smoke_snapshot()
	if int(second.get("tick", 0)) <= int(first.get("tick", 0)):
		_fail("physics tick did not advance")
		return
	if not bool(second.get("match_camera_owned", false)) or int(second.get("fighter_camera_count", -1)) != 0:
		_fail("second-person camera is not exclusively match-owned")
		return
	if float(second.get("left_start_distance", 0.0)) < 0.5 or float(second.get("right_start_distance", 0.0)) < 0.5:
		_fail("fighters did not traverse the opponent axis")
		return
	if int(second.get("attacks", 0)) < 4 or int(second.get("damage", 0)) < 30:
		_fail("attack windows did not produce combat damage")
		return
	print("A3GAME_SMOKE_OK ", JSON.stringify(second))
	quit(0)


func _fail(message: String) -> void:
	push_error("A3GAME_SMOKE_FAIL: " + message)
	quit(1)
