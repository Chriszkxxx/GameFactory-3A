extends CanvasLayer

## Presentation-only combat HUD. Gameplay state comes from ArenaDuelRuntime.

const COLOR_BLUE := Color("49c9ff")
const COLOR_RED := Color("ff4f70")
const COLOR_GOLD := Color("ffd166")
const COLOR_PANEL := Color(0.035, 0.045, 0.075, 0.94)

var _runtime: Node
var _menu_panel: Panel
var _hud_panel: Control
var _round_label: Label
var _transition_label: Label
var _pause_panel: Panel
var _end_panel: Panel
var _left_hp: ProgressBar
var _right_hp: ProgressBar
var _left_score: Label
var _right_score: Label
var _built := false
var _snapshot: Dictionary = {}
var _transition_tween: Tween


func _ready() -> void:
	_runtime = get_node_or_null("/root/ArenaDuelRuntime")
	if _runtime != null:
		if _runtime.has_signal("state_changed"):
			_runtime.state_changed.connect(_on_state_changed)
		if _runtime.has_signal("event_emitted"):
			_runtime.event_emitted.connect(_on_event_emitted)
	_build_ui()
	if _runtime != null and _runtime.has_method("get_state_snapshot"):
		sync(_runtime.get_state_snapshot())


func _on_state_changed(snapshot: Dictionary) -> void:
	sync(snapshot)


func _on_event_emitted(event_name: String, payload: Dictionary) -> void:
	match event_name:
		"fight_started": show_transition("FIGHT!", 0.55)
		"round_started": show_transition("ROUND %02d" % int(payload.get("round_number", 1)), 0.7)
		"round_ended": show_transition("ROUND COMPLETE", 0.8)


func _unhandled_input(event: InputEvent) -> void:
	if _runtime == null:
		return
	if event.is_action_pressed("pause_cancel"):
		_runtime.set_paused(not bool(_snapshot.get("paused", false)))
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("confirm_restart"):
		var state := String(_snapshot.get("match_state", "menu"))
		if state == "menu":
			_runtime.start_match()
		elif state == "match_end":
			_runtime.restart_match()
		get_viewport().set_input_as_handled()


func sync(snapshot: Dictionary) -> void:
	_snapshot = snapshot.duplicate(true)
	if not _built:
		_build_ui()
	var state := String(snapshot.get("match_state", "menu"))
	_menu_panel.visible = state == "menu"
	_hud_panel.visible = state != "menu"
	_pause_panel.visible = bool(snapshot.get("paused", false))
	_end_panel.visible = state == "match_end"
	_round_label.text = "ROUND %02d" % int(snapshot.get("round_number", 1)) if state != "menu" else ""
	_left_hp.value = float(snapshot.get("left_hp", 100))
	_right_hp.value = float(snapshot.get("right_hp", 100))
	_left_score.text = "WINS  %d" % int(snapshot.get("left_score", 0))
	_right_score.text = "WINS  %d" % int(snapshot.get("right_score", 0))


func show_transition(text: String, duration: float) -> void:
	if not _built:
		_build_ui()
	if _transition_tween != null and _transition_tween.is_valid():
		_transition_tween.kill()
	_transition_label.text = text
	_transition_label.visible = true
	_transition_tween = create_tween()
	_transition_tween.tween_interval(duration)
	_transition_tween.tween_callback(func() -> void:
		if is_instance_valid(_transition_label):
			_transition_label.visible = false
	)


func _build_ui() -> void:
	if _built:
		return
	_built = true
	_menu_panel = Panel.new()
	_menu_panel.name = "MainMenu"
	var menu_size := Vector2(470, 300)
	_menu_panel.set_anchors_preset(Control.PRESET_CENTER)
	_menu_panel.position = -menu_size * 0.5
	_menu_panel.size = menu_size
	_menu_panel.add_theme_stylebox_override("panel", _panel_style(COLOR_PANEL))
	add_child(_menu_panel)

	var title := _label("ARENA DUEL", 34, COLOR_GOLD, HORIZONTAL_ALIGNMENT_CENTER)
	title.position = Vector2(0, 32)
	title.size = Vector2(menu_size.x, 48)
	_menu_panel.add_child(title)
	var subtitle := _label("SECOND-PERSON FIGHTING REFERENCE", 14, Color(0.76, 0.78, 0.88), HORIZONTAL_ALIGNMENT_CENTER)
	subtitle.position = Vector2(0, 86)
	subtitle.size = Vector2(menu_size.x, 24)
	_menu_panel.add_child(subtitle)
	var controls := _label("ENTER  START MATCH\n\nA / D  MOVE      SPACE  ATTACK\nESC  PAUSE", 15, Color(0.86, 0.87, 0.94), HORIZONTAL_ALIGNMENT_CENTER)
	controls.position = Vector2(0, 130)
	controls.size = Vector2(menu_size.x, 120)
	_menu_panel.add_child(controls)

	_hud_panel = Control.new()
	_hud_panel.name = "FightHUD"
	_hud_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	_hud_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_hud_panel)

	var left_name := _label("AZURE", 18, COLOR_BLUE, HORIZONTAL_ALIGNMENT_LEFT)
	left_name.position = Vector2(32, 26)
	left_name.size = Vector2(220, 24)
	_hud_panel.add_child(left_name)
	_left_hp = _bar(Vector2(32, 56), Vector2(320, 18), COLOR_BLUE)
	_hud_panel.add_child(_left_hp)
	_left_score = _label("WINS  0", 12, Color(0.68, 0.72, 0.84), HORIZONTAL_ALIGNMENT_LEFT)
	_left_score.position = Vector2(32, 82)
	_left_score.size = Vector2(180, 20)
	_hud_panel.add_child(_left_score)

	var right_name := _label("CRIMSON", 18, COLOR_RED, HORIZONTAL_ALIGNMENT_RIGHT)
	right_name.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	right_name.position = Vector2(-252, 26)
	right_name.size = Vector2(220, 24)
	_hud_panel.add_child(right_name)
	_right_hp = _bar(Vector2.ZERO, Vector2(320, 18), COLOR_RED)
	_right_hp.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_right_hp.position = Vector2(-352, 56)
	_hud_panel.add_child(_right_hp)
	_right_score = _label("WINS  0", 12, Color(0.68, 0.72, 0.84), HORIZONTAL_ALIGNMENT_RIGHT)
	_right_score.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_right_score.position = Vector2(-252, 82)
	_right_score.size = Vector2(220, 20)
	_hud_panel.add_child(_right_score)

	_round_label = _label("", 20, Color(0.92, 0.93, 0.98), HORIZONTAL_ALIGNMENT_CENTER)
	_round_label.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_round_label.position = Vector2(-100, 28)
	_round_label.size = Vector2(200, 30)
	_hud_panel.add_child(_round_label)
	_transition_label = _label("", 44, Color(1.0, 0.94, 0.78), HORIZONTAL_ALIGNMENT_CENTER)
	_transition_label.set_anchors_preset(Control.PRESET_CENTER)
	_transition_label.position = Vector2(-300, -42)
	_transition_label.size = Vector2(600, 84)
	_transition_label.visible = false
	_hud_panel.add_child(_transition_label)

	_end_panel = Panel.new()
	_end_panel.name = "MatchEnd"
	_end_panel.set_anchors_preset(Control.PRESET_CENTER)
	_end_panel.position = Vector2(-210, -100)
	_end_panel.size = Vector2(420, 200)
	_end_panel.add_theme_stylebox_override("panel", _panel_style(COLOR_PANEL))
	_end_panel.visible = false
	add_child(_end_panel)
	var end_label := _label("MATCH COMPLETE", 26, COLOR_GOLD, HORIZONTAL_ALIGNMENT_CENTER)
	end_label.position = Vector2(0, 42)
	end_label.size = Vector2(420, 36)
	_end_panel.add_child(end_label)
	var end_hint := _label("ENTER  RESTART", 15, Color(0.8, 0.82, 0.9), HORIZONTAL_ALIGNMENT_CENTER)
	end_hint.position = Vector2(0, 132)
	end_hint.size = Vector2(420, 24)
	_end_panel.add_child(end_hint)

	_pause_panel = Panel.new()
	_pause_panel.name = "PauseOverlay"
	_pause_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	_pause_panel.add_theme_stylebox_override("panel", _panel_style(Color(0.0, 0.0, 0.0, 0.7)))
	_pause_panel.visible = false
	add_child(_pause_panel)
	var pause_label := _label("PAUSED\nESC  RESUME", 24, Color(0.92, 0.93, 0.98), HORIZONTAL_ALIGNMENT_CENTER)
	pause_label.set_anchors_preset(Control.PRESET_CENTER)
	pause_label.position = Vector2(-180, -38)
	pause_label.size = Vector2(360, 76)
	_pause_panel.add_child(pause_label)


func _label(text: String, font_size: int, color: Color, alignment: int) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.horizontal_alignment = alignment
	return label


func _bar(pos: Vector2, bar_size: Vector2, color: Color) -> ProgressBar:
	var bar := ProgressBar.new()
	bar.position = pos
	bar.size = bar_size
	bar.min_value = 0
	bar.max_value = 100
	bar.value = 100
	bar.show_percentage = false
	bar.add_theme_stylebox_override("background", _bar_style(Color(0.08, 0.09, 0.14, 0.9)))
	bar.add_theme_stylebox_override("fill", _bar_style(color))
	return bar


func _panel_style(color: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.border_color = Color(0.38, 0.42, 0.56, 0.6)
	style.set_border_width_all(1)
	style.set_corner_radius_all(6)
	return style


func _bar_style(color: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(3)
	return style
