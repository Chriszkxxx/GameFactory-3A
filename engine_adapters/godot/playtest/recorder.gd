extends SceneTree

var _output_dir = ""
var _fps = 15
var _duration = 10.0

func _initialize() -> void:
	var args = OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--scenario":
			var f = FileAccess.open(args[i + 1], FileAccess.READ)
			if f:
				var data = JSON.parse_string(f.get_as_text())
				if data:
					_fps = int(data.get("fps", 15))
					_duration = float(data.get("duration", 10.0))
		elif args[i] == "--output":
			_output_dir = args[i + 1]
	if _output_dir == "":
		print("RECORDER_ERROR: no --output")
		quit(1)
		return
	call_deferred("_run")

func _run() -> void:
	var main_scene = load("res://scenes/main.tscn")
	if main_scene == null:
		print("RECORDER_ERROR: main scene not found")
		quit(1)
		return
	var game = main_scene.instantiate()
	root.add_child(game)
	
	for _i in range(30):
		await physics_frame
	
	# Enable AI on both fighters
	game.ai_enabled = true
	game.p1_ai_enabled = true
	
	# Start match
	game.start_match()
	
	for _i in range(90):
		await physics_frame
	
	var frame_count = 0
	var capture_interval = int(60.0 / _fps)
	var capture_index = 0
	var dt = 1.0 / 60.0
	
	while frame_count < int(_duration * 60):
		# Manually drive the game's physics to ensure it runs
		if game.has_method("_physics_process"):
			game._physics_process(dt)
		
		# Manually drive fighters to ensure movement
		if game.p1 and game.p1_ai_enabled and game.p1_ai_controller:
			var p1_input = game.p1_ai_controller.think(dt, game.p1, game.p2)
			game.p1.set_input_state(p1_input)
			game.p1.physics_step(dt)
		if game.p2 and game.ai_enabled and game.ai_controller:
			var p2_input = game.ai_controller.think(dt, game.p2, game.p1)
			game.p2.set_input_state(p2_input)
			game.p2.physics_step(dt)
		
		await physics_frame
		frame_count += 1
		
		if frame_count % capture_interval == 0:
			var img = root.get_viewport().get_texture().get_image()
			if img:
				capture_index += 1
				var path = _output_dir + "/f%05d.png" % capture_index
				img.save_png(path)
	
	print("RECORD_COMPLETE frames=", capture_index)
	quit(0)
