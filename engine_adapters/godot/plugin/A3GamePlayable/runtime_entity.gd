class_name A3GameRuntimeEntity
extends Node3D


signal runtime_input(input_state: Dictionary)

@export var a3game_entity_id := ""


func _ready() -> void:
	add_to_group("a3game_runtime_entity")


func apply_a3game_input(input_state: Dictionary) -> void:
	runtime_input.emit(input_state)


func clear_a3game_entity() -> void:
	queue_free()
