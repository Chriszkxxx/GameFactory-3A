# Godot examples

These project-local add-ons are read-only architecture references for generated
Godot gameplay and UI. They demonstrate the required `plugin.cfg` boundary and
depend only on the public `A3GamePlayable` runtime add-on. They are not copied as
base projects and are never runtime dependencies of generated output.

`MinimalExample/` contains one deliberately game-neutral add-on skeleton and a
small native test source showing the `run_test()` contract consumed by
`GodotClient.testing`.
