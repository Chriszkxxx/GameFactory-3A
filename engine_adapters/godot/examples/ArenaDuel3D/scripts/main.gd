extends Node3D


const BLUE := Color("49c9ff")
const RED := Color("ff4f70")
const GOLD := Color("ffd166")


class Fighter:
	extends CharacterBody3D

	var health := 100
	var score := 0
	var attack_cooldown := 0.0
	var attack_pose := 0.0
	var visual: Node3D

	func configure(color: Color) -> void:
		collision_layer = 1
		collision_mask = 1
		var collision := CollisionShape3D.new()
		var shape := CapsuleShape3D.new()
		shape.radius = 0.48
		shape.height = 1.9
		collision.shape = shape
		add_child(collision)
		visual = Node3D.new()
		visual.name = "FighterVisual"
		add_child(visual)
		var body := MeshInstance3D.new()
		var body_mesh := CapsuleMesh.new()
		body_mesh.radius = 0.45
		body_mesh.height = 1.8
		body.mesh = body_mesh
		var material := StandardMaterial3D.new()
		material.albedo_color = color
		material.metallic = 0.28
		material.roughness = 0.32
		material.emission_enabled = true
		material.emission = color * 0.22
		body.material_override = material
		visual.add_child(body)
		for side in [-1.0, 1.0]:
			var glove := MeshInstance3D.new()
			glove.name = "Glove"
			var glove_mesh := SphereMesh.new()
			glove_mesh.radius = 0.22
			glove_mesh.height = 0.44
			glove.mesh = glove_mesh
			glove.position = Vector3(side * 0.62, 0.24, -0.14)
			glove.material_override = material
			visual.add_child(glove)

	func step_fighter(axis: float, opponent: Fighter, delta: float) -> void:
		attack_cooldown = maxf(0.0, attack_cooldown - delta)
		attack_pose = maxf(0.0, attack_pose - delta)
		velocity.x = move_toward(velocity.x, axis * 3.8, delta * 18.0)
		velocity.z = move_toward(velocity.z, 0.0, delta * 18.0)
		if not is_on_floor():
			velocity.y -= 22.0 * delta
		else:
			velocity.y = -0.4
		move_and_slide()
		position.x = clampf(position.x, -7.2, 7.2)
		position.z = 0.0
		var look_target := Vector3(opponent.global_position.x, global_position.y, opponent.global_position.z)
		if global_position.distance_squared_to(look_target) > 0.001:
			look_at(look_target, Vector3.UP)
		visual.scale = Vector3(1.0, 0.92, 1.18) if attack_pose > 0.0 else Vector3.ONE

	func try_attack(opponent: Fighter) -> bool:
		if health <= 0 or opponent.health <= 0 or attack_cooldown > 0.0:
			return false
		if global_position.distance_to(opponent.global_position) > 2.05:
			return false
		attack_cooldown = 0.36
		attack_pose = 0.14
		var direction := signf(opponent.global_position.x - global_position.x)
		opponent.take_hit(9, direction)
		return true

	func take_hit(damage: int, direction: float) -> void:
		health = maxi(0, health - damage)
		velocity.x += direction * 3.4


var left_fighter: Fighter
var right_fighter: Fighter
var match_camera: Camera3D
var demo_mode := true
var capture_mode := false
var elapsed := 0.0
var tick := 0
var attacks := 0
var total_damage := 0
var round_number := 1
var round_reset_timer := 0.0
var start_left := Vector3.ZERO
var start_right := Vector3.ZERO
var telemetry: Label


func _ready() -> void:
	demo_mode = not OS.get_cmdline_user_args().has("--manual")
	capture_mode = OS.get_cmdline_user_args().has("--capture")
	_build_environment()
	_build_arena()
	_build_ui()
	left_fighter = Fighter.new()
	left_fighter.name = "AzureFighter"
	left_fighter.position = Vector3(-3.2, 1.0, 0.0)
	left_fighter.configure(BLUE)
	add_child(left_fighter)
	right_fighter = Fighter.new()
	right_fighter.name = "CrimsonFighter"
	right_fighter.position = Vector3(3.2, 1.0, 0.0)
	right_fighter.configure(RED)
	add_child(right_fighter)
	start_left = left_fighter.position
	start_right = right_fighter.position
	match_camera = Camera3D.new()
	match_camera.name = "MatchOwnedCamera"
	match_camera.current = true
	match_camera.fov = 56.0
	add_child(match_camera)
	_update_camera(1.0)


func _build_environment() -> void:
	var world := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("12091f")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color("b2a0d0")
	environment.ambient_light_energy = 0.58
	world.environment = environment
	add_child(world)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-54.0, -18.0, 0.0)
	key.light_color = Color("fff0cf")
	key.light_energy = 1.4
	key.shadow_enabled = true
	add_child(key)
	for x_value in [-6.5, 6.5]:
		var rim := OmniLight3D.new()
		rim.position = Vector3(x_value, 3.8, 1.5)
		rim.light_color = BLUE if x_value < 0.0 else RED
		rim.light_energy = 6.0
		rim.omni_range = 8.0
		add_child(rim)


func _material(color: Color, emission := 0.0) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.48
	if emission > 0.0:
		material.emission_enabled = true
		material.emission = color * emission
	return material


func _build_arena() -> void:
	var floor := StaticBody3D.new()
	floor.name = "ArenaFloor"
	floor.position.y = -0.25
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(17.0, 0.5, 8.0)
	collision.shape = shape
	floor.add_child(collision)
	var visual := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = shape.size
	visual.mesh = mesh
	visual.material_override = _material(Color("261b37"))
	floor.add_child(visual)
	add_child(floor)
	for index in range(9):
		var marker := MeshInstance3D.new()
		var marker_mesh := BoxMesh.new()
		marker_mesh.size = Vector3(0.08, 0.025, 7.2)
		marker.mesh = marker_mesh
		marker.position = Vector3(-7.2 + float(index) * 1.8, 0.02, 0.0)
		marker.material_override = _material(GOLD if index == 4 else Color("67437f"), 1.0 if index == 4 else 0.2)
		add_child(marker)


func _build_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var title := Label.new()
	title.position = Vector2(30.0, 20.0)
	title.text = "ARENA DUEL // MATCH-OWNED CAMERA"
	title.add_theme_color_override("font_color", GOLD)
	title.add_theme_font_size_override("font_size", 22)
	layer.add_child(title)
	telemetry = Label.new()
	telemetry.position = Vector2(30.0, 54.0)
	telemetry.add_theme_font_size_override("font_size", 18)
	telemetry.add_theme_color_override("font_color", Color.WHITE)
	layer.add_child(telemetry)
	var controls := Label.new()
	controls.position = Vector2(30.0, 504.0)
	controls.text = "A/D move on opponent axis  •  Space attack  •  camera belongs to the match"
	controls.add_theme_color_override("font_color", Color("c4afd9"))
	controls.add_theme_font_size_override("font_size", 14)
	layer.add_child(controls)


func _physics_process(delta: float) -> void:
	tick += 1
	elapsed += delta
	if round_reset_timer > 0.0:
		round_reset_timer = maxf(0.0, round_reset_timer - delta)
		if round_reset_timer == 0.0:
			_reset_round()
		_update_camera(delta)
		_update_ui()
		return
	var left_axis := signf(right_fighter.position.x - left_fighter.position.x)
	if not demo_mode:
		left_axis = float(Input.is_key_pressed(KEY_D)) - float(Input.is_key_pressed(KEY_A))
	var right_axis := signf(left_fighter.position.x - right_fighter.position.x)
	left_fighter.step_fighter(left_axis, right_fighter, delta)
	right_fighter.step_fighter(right_axis, left_fighter, delta)
	if demo_mode or Input.is_key_pressed(KEY_SPACE):
		_record_attack(left_fighter, right_fighter)
	_record_attack(right_fighter, left_fighter)
	if left_fighter.health == 0 or right_fighter.health == 0:
		if left_fighter.health > right_fighter.health:
			left_fighter.score += 1
		else:
			right_fighter.score += 1
		round_reset_timer = 0.7
	_update_camera(delta)
	_update_ui()
	if capture_mode and elapsed > 18.0:
		get_tree().quit()


func _record_attack(attacker: Fighter, defender: Fighter) -> void:
	var health_before := defender.health
	if attacker.try_attack(defender):
		attacks += 1
		total_damage += health_before - defender.health


func _reset_round() -> void:
	round_number += 1
	left_fighter.health = 100
	right_fighter.health = 100
	left_fighter.position = Vector3(-3.2, 1.0, 0.0)
	right_fighter.position = Vector3(3.2, 1.0, 0.0)
	left_fighter.velocity = Vector3.ZERO
	right_fighter.velocity = Vector3.ZERO
	left_fighter.attack_cooldown = 0.0
	right_fighter.attack_cooldown = 0.0


func _update_camera(delta: float) -> void:
	var midpoint := (left_fighter.global_position + right_fighter.global_position) * 0.5
	var separation := left_fighter.global_position.distance_to(right_fighter.global_position)
	var desired := midpoint + Vector3(0.0, 4.8, 7.5 + separation * 0.28)
	match_camera.global_position = match_camera.global_position.lerp(desired, minf(1.0, delta * 6.0))
	match_camera.look_at(midpoint + Vector3.UP * 0.45, Vector3.UP)


func _update_ui() -> void:
	telemetry.text = "ROUND %02d   AZURE %03d HP [%d]   CRIMSON %03d HP [%d]   ATTACKS %03d" % [
		round_number,
		left_fighter.health,
		left_fighter.score,
		right_fighter.health,
		right_fighter.score,
		attacks,
	]


func smoke_snapshot() -> Dictionary:
	return {
		"game": "arena_duel_3d",
		"tick": tick,
		"left": [left_fighter.position.x, left_fighter.position.y, left_fighter.position.z],
		"right": [right_fighter.position.x, right_fighter.position.y, right_fighter.position.z],
		"left_start_distance": left_fighter.position.distance_to(start_left),
		"right_start_distance": right_fighter.position.distance_to(start_right),
		"match_camera_owned": match_camera.get_parent() == self,
		"fighter_camera_count": left_fighter.find_children("*", "Camera3D", true, false).size() + right_fighter.find_children("*", "Camera3D", true, false).size(),
		"attacks": attacks,
		"damage": total_damage,
		"round": round_number,
	}
