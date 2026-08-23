extends Node3D


const GREEN := Color("46d39a")
const GOLD := Color("ffd166")
const BLUE := Color("64b5ff")


class Explorer:
	extends CharacterBody3D

	var visual_anchor: Node3D

	func configure() -> void:
		collision_layer = 1
		collision_mask = 1
		floor_snap_length = 0.45
		var collision := CollisionShape3D.new()
		var shape := CapsuleShape3D.new()
		shape.radius = 0.38
		shape.height = 1.75
		collision.shape = shape
		add_child(collision)
		visual_anchor = Node3D.new()
		visual_anchor.name = "ImportedVisualAnchor"
		visual_anchor.position = Vector3(0.0, -0.88, 0.0)
		add_child(visual_anchor)


var explorer: Explorer
var follow_camera: Camera3D
var relics: Array[Area3D] = []
var route: Array[Vector3] = []
var route_cursor := 0
var demo_mode := true
var capture_mode := false
var elapsed := 0.0
var tick := 0
var camera_yaw := 0.0
var stamina := 1.0
var relics_collected := 0
var start_position := Vector3.ZERO
var imported_actor: Node3D
var imported_mesh_count := 0
var imported_skeleton_count := 0
var imported_bone_count := 0
var imported_animation_names := PackedStringArray()
var imported_animator: AnimationPlayer
var imported_animation := ""
var last_animation_position := -1.0
var animation_advanced_frames := 0
var telemetry: Label


func _ready() -> void:
	demo_mode = not OS.get_cmdline_user_args().has("--manual")
	capture_mode = OS.get_cmdline_user_args().has("--capture")
	_build_environment()
	_build_world()
	_build_ui()
	explorer = Explorer.new()
	explorer.name = "Explorer"
	explorer.position = Vector3(-4.0, 1.0, 4.0)
	explorer.configure()
	add_child(explorer)
	start_position = explorer.position
	_load_imported_actor()
	follow_camera = Camera3D.new()
	follow_camera.name = "FollowCamera"
	follow_camera.current = true
	follow_camera.fov = 62.0
	add_child(follow_camera)
	_update_camera(1.0)
	_create_relic(Vector3(-2.0, 0.75, 1.0), "SunFragment")
	_create_relic(Vector3(1.0, 0.75, -2.0), "RiverFragment")
	_create_relic(Vector3(4.0, 0.75, 1.0), "GroveFragment")
	route = [
		Vector3(-2.0, 1.0, 1.0),
		Vector3(1.0, 1.0, -2.0),
		Vector3(4.0, 1.0, 1.0),
		Vector3(-4.0, 1.0, 4.0),
	]


func _build_environment() -> void:
	var world := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("27465c")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color("b8d5cc")
	environment.ambient_light_energy = 0.72
	environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	world.environment = environment
	add_child(world)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-52.0, -28.0, 0.0)
	sun.light_color = Color("fff1c9")
	sun.light_energy = 1.35
	sun.shadow_enabled = true
	add_child(sun)


func _material(color: Color, emission := 0.0) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.74
	if emission > 0.0:
		material.emission_enabled = true
		material.emission = color * emission
	return material


func _static_box(node_name: String, size: Vector3, location: Vector3, color: Color, rotation_x := 0.0) -> void:
	var body := StaticBody3D.new()
	body.name = node_name
	body.position = location
	body.rotation_degrees.x = rotation_x
	body.collision_layer = 1
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	collision.shape = shape
	body.add_child(collision)
	var visual := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	visual.mesh = mesh
	visual.material_override = _material(color)
	body.add_child(visual)
	add_child(body)


func _build_world() -> void:
	_static_box("MeadowFloor", Vector3(26.0, 0.5, 24.0), Vector3(0.0, -0.25, 0.0), Color("31563e"))
	_static_box("NorthRise", Vector3(6.0, 0.5, 7.0), Vector3(6.0, 0.45, -6.0), Color("416a48"), -6.0)
	_static_box("WestRise", Vector3(5.0, 0.5, 6.0), Vector3(-7.0, 0.35, -4.0), Color("3a6244"), 5.0)
	for index in range(18):
		var tree := MeshInstance3D.new()
		tree.name = "Tree_%02d" % index
		var mesh := CylinderMesh.new()
		mesh.top_radius = 0.18
		mesh.bottom_radius = 0.34
		mesh.height = 2.0 + float(index % 3) * 0.45
		tree.mesh = mesh
		var angle := TAU * float(index) / 18.0
		tree.position = Vector3(cos(angle) * (8.0 + float(index % 2) * 2.0), mesh.height * 0.5, sin(angle) * (7.0 + float(index % 3)))
		tree.material_override = _material(Color("254b34"))
		add_child(tree)


func _build_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var title := Label.new()
	title.position = Vector2(28.0, 20.0)
	title.text = "RPG EXPLORER // THE THREE FRAGMENTS"
	title.add_theme_color_override("font_color", GOLD)
	title.add_theme_font_size_override("font_size", 22)
	layer.add_child(title)
	telemetry = Label.new()
	telemetry.position = Vector2(28.0, 54.0)
	telemetry.add_theme_color_override("font_color", Color.WHITE)
	telemetry.add_theme_font_size_override("font_size", 17)
	layer.add_child(telemetry)
	var controls := Label.new()
	controls.position = Vector2(28.0, 504.0)
	controls.text = "WASD camera-relative move  •  arrows orbit  •  Shift sprint  •  collect 3 relics"
	controls.add_theme_color_override("font_color", Color("d0e5d7"))
	controls.add_theme_font_size_override("font_size", 14)
	layer.add_child(controls)


func _load_imported_actor() -> void:
	var packed := load("res://assets/reference_actor.gltf") as PackedScene
	if packed == null:
		return
	imported_actor = packed.instantiate()
	imported_actor.name = "ImportedReferenceActor"
	imported_actor.scale = Vector3.ONE * 1.25
	explorer.visual_anchor.add_child(imported_actor)
	imported_mesh_count = imported_actor.find_children("*", "MeshInstance3D", true, false).size()
	var skeletons := imported_actor.find_children("*", "Skeleton3D", true, false)
	imported_skeleton_count = skeletons.size()
	for skeleton_node in skeletons:
		var skeleton := skeleton_node as Skeleton3D
		imported_bone_count += skeleton.get_bone_count()
	var animators := imported_actor.find_children("*", "AnimationPlayer", true, false)
	for animator_node in animators:
		var animator := animator_node as AnimationPlayer
		for animation_name in animator.get_animation_list():
			if not imported_animation_names.has(animation_name):
				imported_animation_names.append(animation_name)
			if imported_animation.is_empty() and String(animation_name).to_lower().contains("walk"):
				imported_animator = animator
				imported_animation = animation_name
	if imported_animator != null and not imported_animation.is_empty():
		var animation := imported_animator.get_animation(imported_animation)
		animation.loop_mode = Animation.LOOP_LINEAR
		imported_animator.play(imported_animation)


func _create_relic(location: Vector3, node_name: String) -> void:
	var relic := Area3D.new()
	relic.name = node_name
	relic.position = location
	relic.collision_layer = 2
	relic.collision_mask = 1
	var collision := CollisionShape3D.new()
	var shape := SphereShape3D.new()
	shape.radius = 0.62
	collision.shape = shape
	relic.add_child(collision)
	var visual := MeshInstance3D.new()
	var mesh := PrismMesh.new()
	mesh.size = Vector3(0.55, 1.0, 0.55)
	visual.mesh = mesh
	visual.material_override = _material(BLUE if relics.size() % 2 == 0 else GOLD, 1.8)
	relic.add_child(visual)
	relic.body_entered.connect(_on_relic_body_entered.bind(relic))
	add_child(relic)
	relics.append(relic)


func _physics_process(delta: float) -> void:
	tick += 1
	elapsed += delta
	var desired := Vector3.ZERO
	var sprinting := false
	if demo_mode:
		var target := route[route_cursor]
		desired = target - explorer.position
		desired.y = 0.0
		if desired.length() < 0.55:
			route_cursor = (route_cursor + 1) % route.size()
		sprinting = stamina > 0.15
		camera_yaw = sin(elapsed * 0.24) * 0.42
	else:
		camera_yaw += (float(Input.is_key_pressed(KEY_LEFT)) - float(Input.is_key_pressed(KEY_RIGHT))) * delta * 1.35
		var input_vector := Vector2(
			float(Input.is_key_pressed(KEY_D)) - float(Input.is_key_pressed(KEY_A)),
			float(Input.is_key_pressed(KEY_S)) - float(Input.is_key_pressed(KEY_W))
		)
		var camera_forward := Vector3(-sin(camera_yaw), 0.0, -cos(camera_yaw))
		var camera_right := Vector3(cos(camera_yaw), 0.0, -sin(camera_yaw))
		desired = camera_right * input_vector.x + camera_forward * -input_vector.y
		sprinting = Input.is_key_pressed(KEY_SHIFT) and desired.length_squared() > 0.01 and stamina > 0.05
	if desired.length_squared() > 1.0:
		desired = desired.normalized()
	var speed := 5.2 if sprinting else 3.2
	explorer.velocity.x = move_toward(explorer.velocity.x, desired.x * speed, delta * 16.0)
	explorer.velocity.z = move_toward(explorer.velocity.z, desired.z * speed, delta * 16.0)
	if not explorer.is_on_floor():
		explorer.velocity.y -= 22.0 * delta
	else:
		explorer.velocity.y = -0.45
	explorer.move_and_slide()
	if desired.length_squared() > 0.02:
		explorer.rotation.y = lerp_angle(explorer.rotation.y, atan2(-desired.x, -desired.z), minf(1.0, delta * 8.0))
	stamina = clampf(stamina + (-0.23 if sprinting else 0.16) * delta, 0.0, 1.0)
	_update_imported_motion()
	_update_camera(delta)
	for index in range(relics.size()):
		if relics[index].visible:
			relics[index].rotation.y += delta * (1.2 + float(index) * 0.18)
	_update_ui()
	if capture_mode and elapsed > 18.0:
		get_tree().quit()


func _update_imported_motion() -> void:
	if imported_animator == null or imported_animation.is_empty():
		return
	if not imported_animator.is_playing():
		imported_animator.play(imported_animation)
	var position := imported_animator.current_animation_position
	if last_animation_position >= 0.0 and not is_equal_approx(position, last_animation_position):
		animation_advanced_frames += 1
	last_animation_position = position


func _update_camera(delta: float) -> void:
	var focus := explorer.global_position + Vector3.UP * 0.85
	var desired := focus + Vector3(sin(camera_yaw) * 6.2, 3.6, cos(camera_yaw) * 6.2)
	follow_camera.global_position = follow_camera.global_position.lerp(desired, minf(1.0, delta * 5.0))
	follow_camera.look_at(focus, Vector3.UP)


func _on_relic_body_entered(body: Node3D, relic: Area3D) -> void:
	if body != explorer or not relic.visible:
		return
	relics_collected += 1
	relic.visible = false
	relic.set_deferred("monitoring", false)


func _update_ui() -> void:
	telemetry.text = "QUEST %d/3%s   STAMINA %03d   IMPORT mesh=%d skeleton=%d bones=%d motion=%s" % [
		relics_collected,
		" COMPLETE" if relics_collected == 3 else "",
		int(stamina * 100.0),
		imported_mesh_count,
		imported_skeleton_count,
		imported_bone_count,
		imported_animation if not imported_animation.is_empty() else "MISSING",
	]


func smoke_snapshot() -> Dictionary:
	return {
		"game": "rpg_explorer_3d",
		"tick": tick,
		"player": [explorer.position.x, explorer.position.y, explorer.position.z],
		"distance": explorer.position.distance_to(start_position),
		"follow_camera_owned_by_world": follow_camera.get_parent() == self,
		"relics": relics.size(),
		"collected": relics_collected,
		"imported_meshes": imported_mesh_count,
		"imported_skeletons": imported_skeleton_count,
		"imported_bones": imported_bone_count,
		"animations": Array(imported_animation_names),
		"playing_animation": imported_animation,
		"animation_advanced_frames": animation_advanced_frames,
	}
