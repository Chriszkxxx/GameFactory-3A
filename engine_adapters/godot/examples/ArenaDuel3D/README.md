# Arena Duel 3D

A second-person combat reference matching Three.js `arena-fighter-example`:
the match owns a camera that frames both fighters, neither fighter may steer it,
and locomotion/facing stay locked to the opponent axis. The project adds live
character collision, attack windows, cooldowns, health, knockback, round reset,
score HUD, deterministic AI-versus-AI validation, and manual A/D/space control.

```bash
godot4 --headless --path . --import
godot4 --headless --path . --script res://scripts/smoke.gd
godot4 --path . -- --manual
```

The reviewer demonstration path is
`my_code/AAAGameForge/test_data/outputs/game505/godot/`.
