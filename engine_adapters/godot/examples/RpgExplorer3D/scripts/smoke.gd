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
	for _frame in range(180):
		await physics_frame
	var first: Dictionary = game.smoke_snapshot()
	for _frame in range(270):
		await physics_frame
	var second: Dictionary = game.smoke_snapshot()
	if int(second.get("tick", 0)) <= int(first.get("tick", 0)):
		_fail("physics tick did not advance")
		return
	if not bool(second.get("follow_camera_owned_by_world", false)):
		_fail("third-person follow camera is not world-owned")
		return
	if float(second.get("distance", 0.0)) < 2.0:
		_fail("explorer did not traverse the world")
		return
	if int(second.get("relics", 0)) != 3 or int(second.get("collected", 0)) != 3:
		_fail("quest pickup loop did not complete")
		return
	if int(second.get("imported_meshes", 0)) < 1:
		_fail("glTF mesh was not natively instantiated")
		return
	if int(second.get("imported_skeletons", 0)) < 1 or int(second.get("imported_bones", 0)) < 1:
		_fail("glTF skin did not import as a nonempty Skeleton3D")
		return
	var animation_names: Array = second.get("animations", [])
	if not animation_names.has("Walk") or String(second.get("playing_animation", "")) != "Walk":
		_fail("glTF Walk animation was not imported and selected")
		return
	if int(second.get("animation_advanced_frames", 0)) < 30:
		_fail("imported bone animation did not advance")
		return
	print("A3GAME_SMOKE_OK ", JSON.stringify(second))
	quit(0)


func _fail(message: String) -> void:
	push_error("A3GAME_SMOKE_FAIL: " + message)
	quit(1)
