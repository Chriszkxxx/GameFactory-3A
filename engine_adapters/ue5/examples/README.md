# UE5 Reference Gameplay Plugins

These plugins are optional concrete examples built on the public
`AAAGamePlayable` contract:

| Plugin | Demonstrates |
| --- | --- |
| `ArenaFighterExample` | Character movement, light/heavy attacks, arena GameMode, HUD |
| `FPSExample` | First-person movement, hitscan fire, reload, FPS GameMode, HUD |
| `RacingExample` | Arcade vehicle movement, boost, handbrake, racing GameMode, HUD |

They are disabled by default and are never installed automatically. Generated
games should adapt the relevant patterns inside their own Gameplay Plugin,
rather than depending on or inheriting from an example plugin.

Each example owns its concrete Pawn/Character, PlayerController, GameMode, HUD,
entity factory, and runtime subsystem. `AAAGamePlayable` owns only normalized
input, session, binding, entity, and observation contracts.
