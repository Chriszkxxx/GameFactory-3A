extends Node3D


const CYAN := Color("43e8ff")
const ORANGE := Color("ff9b42")
const MAGENTA := Color("ff4f9a")


class FpsPlayer:
	extends CharacterBody3D

	var camera: Camera3D

	func configure() -> void:
		collision_layer = 1
		collision_mask = 1
		var collision := CollisionShape3D.new()
		var shape := CapsuleShape3D.new()
		shape.radius = 0.36
		shape.height = 1.8
		collision.shape = shape
		add_child(collision)
		camera = Camera3D.new()
		camera.name = "PlayerCamera"
		camera.position = Vector3(0.0, 0.68, 0.0)
		camera.fov = 72.0
		camera.current = true
		add_child(camera)


class Target:
	extends StaticBody3D

	var health := 2
	var visual: MeshInstance3D

	func configure(color: Color) -> void:
		collision_layer = 2
		collision_mask = 0
		var collision := CollisionShape3D.new()
		var shape := CapsuleShape3D.new()
		shape.radius = 0.48
		shape.height = 1.8
		collision.shape = shape
		add_child(collision)
		visual = MeshInstance3D.new()
		var mesh := CapsuleMesh.new()
		mesh.radius = 0.48
		mesh.height = 1.8
		visual.mesh = mesh
		var material := StandardMaterial3D.new()
		material.albedo_color = color
		material.metallic = 0.35
		material.roughness = 0.28
		material.emission_enabled = true
		material.emission = color * 0.3
		visual.material_override = material
		add_child(visual)

	func take_hit() -> bool:
		if health <= 0:
			return false
		health -= 1
		visual.scale = Vector3.ONE * (0.45 if health == 0 else 0.82)
		return true


var player: FpsPlayer
var targets: Array[Target] = []
var demo_mode := true
var capture_mode := false
var elapsed := 0.0
var tick := 0
var shots_fired := 0
var shots_hit := 0
var ammo := 6
var reloads := 0
var fire_cooldown := 0.0
var reload_timer := 0.0
var target_cursor := 0
var start_position := Vector3.ZERO
var telemetry: Label


func _ready() -> void:
	demo_mode = not OS.get_cmdline_user_args().has("--manual")
	capture_mode = OS.get_cmdline_user_args().has("--capture")
	_build_environment()
	_build_arena()
	_build_ui()
	player = FpsPlayer.new()
	player.name = "FpsPlayer"
	player.position = Vector3(0.0, 1.0, 7.0)
	player.configure()
	add_child(player)
	start_position = player.position
	for index in range(6):
		var target := Target.new()
		target.name = "Target_%02d" % index
		target.position = Vector3(-5.0 + float(index % 3) * 5.0, 1.0, -7.5 - float(index / 3) * 4.0)
		target.configure(CYAN if index % 2 == 0 else MAGENTA)
		add_child(target)
		targets.append(target)


func _build_environment() -> void:
	var world := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("07101d")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color("809bc5")
	environment.ambient_light_energy = 0.62
	world.environment = environment
	add_child(world)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-55.0, -32.0, 0.0)
	sun.light_color = Color("ffe8c2")
	sun.light_energy = 1.35
	sun.shadow_enabled = true
	add_child(sun)


func _material(color: Color, emission := 0.0) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.58
	material.metallic = 0.18
	if emission > 0.0:
		material.emission_enabled = true
		material.emission = color * emission
	return material


func _static_box(node_name: String, size: Vector3, location: Vector3, color: Color) -> void:
	var body := StaticBody3D.new()
	body.name = node_name
	body.position = location
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


func _build_arena() -> void:
	_static_box("Floor", Vector3(22.0, 0.5, 30.0), Vector3(0.0, -0.25, -3.0), Color("1a2740"))
	_static_box("BackWall", Vector3(22.0, 4.0, 0.5), Vector3(0.0, 2.0, -17.5), Color("24385d"))
	_static_box("LeftWall", Vector3(0.5, 3.0, 30.0), Vector3(-11.0, 1.5, -3.0), Color("17233a"))
	_static_box("RightWall", Vector3(0.5, 3.0, 30.0), Vector3(11.0, 1.5, -3.0), Color("17233a"))
	for index in range(12):
		var strip := MeshInstance3D.new()
		var mesh := BoxMesh.new()
		mesh.size = Vector3(0.08, 0.02, 23.0)
		strip.mesh = mesh
		strip.position = Vector3(-9.0 + float(index) * 1.65, 0.02, -4.0)
		strip.material_override = _material(CYAN if index % 2 == 0 else MAGENTA, 1.4)
		add_child(strip)


func _build_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var title := Label.new()
	title.position = Vector2(28.0, 22.0)
	title.text = "FPS ARENA // CAMERA = ENTITY"
	title.add_theme_color_override("font_color", CYAN)
	title.add_theme_font_size_override("font_size", 22)
	layer.add_child(title)
	telemetry = Label.new()
	telemetry.position = Vector2(28.0, 54.0)
	telemetry.add_theme_color_override("font_color", ORANGE)
	telemetry.add_theme_font_size_override("font_size", 17)
	layer.add_child(telemetry)
	var crosshair := Label.new()
	crosshair.text = "+"
	crosshair.position = Vector2(470.0, 251.0)
	crosshair.add_theme_color_override("font_color", Color.WHITE)
	crosshair.add_theme_font_size_override("font_size", 30)
	layer.add_child(crosshair)
	var controls := Label.new()
	controls.position = Vector2(28.0, 504.0)
	controls.text = "WASD move  •  arrows turn  •  Space fires  •  R reloads"
	controls.add_theme_color_override("font_color", Color("a8bbd8"))
	controls.add_theme_font_size_override("font_size", 14)
	layer.add_child(controls)


func _physics_process(delta: float) -> void:
	tick += 1
	elapsed += delta
	fire_cooldown = maxf(0.0, fire_cooldown - delta)
	if reload_timer > 0.0:
		reload_timer = maxf(0.0, reload_timer - delta)
		if reload_timer == 0.0:
			ammo = 6
	_drive_player(delta)
	if demo_mode:
		var target := _current_live_target()
		if target != null:
			player.camera.look_at(target.global_position, Vector3.UP)
		if fire_cooldown == 0.0 and reload_timer == 0.0:
			_fire()
	else:
		if Input.is_key_pressed(KEY_SPACE) and fire_cooldown == 0.0:
			_fire()
		if Input.is_key_pressed(KEY_R) and reload_timer == 0.0 and ammo < 6:
			_start_reload()
	_update_ui()
	if capture_mode and elapsed > 18.0:
		get_tree().quit()


func _drive_player(delta: float) -> void:
	var input_vector := Vector2.ZERO
	if demo_mode:
		input_vector = Vector2(sin(elapsed * 1.15), 0.18)
	else:
		input_vector = Vector2(
			float(Input.is_key_pressed(KEY_D)) - float(Input.is_key_pressed(KEY_A)),
			float(Input.is_key_pressed(KEY_S)) - float(Input.is_key_pressed(KEY_W))
		)
		var turn := float(Input.is_key_pressed(KEY_LEFT)) - float(Input.is_key_pressed(KEY_RIGHT))
		player.rotation.y += turn * delta * 1.8
	var forward := -player.global_transform.basis.z
	var right := player.global_transform.basis.x
	var direction := (right * input_vector.x + forward * -input_vector.y).normalized()
	player.velocity.x = move_toward(player.velocity.x, direction.x * 4.2, delta * 18.0)
	player.velocity.z = move_toward(player.velocity.z, direction.z * 4.2, delta * 18.0)
	if not player.is_on_floor():
		player.velocity.y -= 20.0 * delta
	else:
		player.velocity.y = -0.4
	player.move_and_slide()
	player.position.x = clampf(player.position.x, -8.5, 8.5)
	player.position.z = clampf(player.position.z, 1.5, 10.0)


func _current_live_target() -> Target:
	for offset in range(targets.size()):
		var index := (target_cursor + offset) % targets.size()
		if targets[index].health > 0:
			target_cursor = index
			return targets[index]
	for target in targets:
		target.health = 2
		target.visual.scale = Vector3.ONE
	target_cursor = 0
	return targets[0]


func _fire() -> void:
	if reload_timer > 0.0:
		return
	if ammo <= 0:
		_start_reload()
		return
	ammo -= 1
	shots_fired += 1
	fire_cooldown = 0.22
	var target := _current_live_target()
	if demo_mode and target != null:
		player.camera.look_at(target.global_position, Vector3.UP)
	var origin := player.camera.global_position
	var destination := origin - player.camera.global_transform.basis.z * 80.0
	var query := PhysicsRayQueryParameters3D.create(origin, destination, 2)
	query.exclude = [player.get_rid()]
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	var collider: Object = hit.get("collider")
	if collider is Target and collider.take_hit():
		shots_hit += 1
		if collider.health == 0:
			target_cursor = (targets.find(collider) + 1) % targets.size()


func _start_reload() -> void:
	if reload_timer > 0.0 or ammo == 6:
		return
	reload_timer = 0.75
	reloads += 1


func _update_ui() -> void:
	var live := 0
	for target in targets:
		live += int(target.health > 0)
	telemetry.text = "AMMO %02d/06   SHOTS %03d   HITS %03d   TARGETS %d/6%s" % [
		ammo,
		shots_fired,
		shots_hit,
		live,
		"   RELOADING" if reload_timer > 0.0 else "",
	]


func smoke_snapshot() -> Dictionary:
	return {
		"game": "fps_arena_3d",
		"tick": tick,
		"player": [player.position.x, player.position.y, player.position.z],
		"distance": player.position.distance_to(start_position),
		"camera_owned_by_player": player.camera.get_parent() == player,
		"targets": targets.size(),
		"shots": shots_fired,
		"hits": shots_hit,
		"reloads": reloads,
	}
