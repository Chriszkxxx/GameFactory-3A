# AAAGameForge Unity Example Plugins

These are **educational reference implementations** that demonstrate how to
build fully functional gameplay on top of the `A3GameRuntime` Unity
framework. They are not skeletons or stubs — every script contains real,
testable game logic.

## Examples

| Example | Genre | Demonstrates |
| --- | --- | --- |
| `ArenaFighterExample` | Melee arena combat | Health, attacks, range-based hit detection, AI opponent |
| `FPSExample` | First-person shooter mechanic | CharacterController movement/collision, jump, door interaction, environment collision, enemy pursuit, hitscan combat, restart |
| `FPSUIExample` | FPS presentation | HUD, crosshair, health/ammo/kill/timer state, damage/hit feedback, restart interaction |
| `RacingExample` | Arcade racing | Checkpoint-based lap counting, vehicle movement |

## Key Properties

- **Gameplay and presentation are separate.** Gameplay examples reference
  `A3GameRuntime`; optional UI examples reference the public gameplay assembly.
- **All gameplay scripts are MonoBehaviours** with complete, working logic.
- **Every example ships with NUnit EditMode tests** that create real
  `GameObject`s and verify behavioral invariants (damage, death, lap counting).
- **Each example includes a `mechanic_contract.json`** using the
  `aaagameforge.mechanic_contract.v1` schema, documenting the behavioral
  invariants the implementation must satisfy.

## Directory Layout

```
examples/
├── README.md                           ← you are here
├── ArenaFighterExample/
│   ├── package.json
│   ├── ArenaFighterExample.asmdef
│   ├── Scripts/
│   │   ├── ArenaFighterController.cs
│   │   ├── ArenaFighterCombat.cs
│   │   ├── ArenaFighterAI.cs
│   │   └── ArenaFighterGameMode.cs
│   ├── mechanic_contract.json
│   └── Tests/
│       ├── ArenaFighterExample.Tests.asmdef
│       └── ArenaFighterTests.cs
├── FPSExample/
│   ├── package.json
│   ├── FPSExample.asmdef
│   ├── Scripts/
│   │   ├── FPSGameRuntimeAdapter.cs
│   │   ├── FPSGameState.cs
│   │   ├── FPSPlayerController.cs
│   │   ├── FPSEnemy.cs
│   │   ├── FPSEnemySpawner.cs
│   │   ├── FPSWeapon.cs
│   │   └── FPSDoor.cs
│   ├── mechanic_contract.json
│   └── Tests/
│       ├── FPSExample.Tests.asmdef
│       └── FPSTests.cs
├── FPSUIExample/
│   ├── package.json
│   ├── FPSUIExample.asmdef
│   ├── Scripts/
│   │   └── FPSArenaHUD.cs
│   └── Tests/
│       ├── FPSUIExample.Tests.asmdef
│       └── FPSArenaHUDTests.cs
└── RacingExample/
    ├── package.json
    ├── RacingExample.asmdef
    ├── Scripts/
    │   ├── RacingVehicleController.cs
    │   ├── RacingCheckpoint.cs
    │   ├── RacingLapCounter.cs
    │   └── RacingGameMode.cs
    ├── mechanic_contract.json
    └── Tests/
        ├── RacingExample.Tests.asmdef
        └── RacingTests.cs
```

## Running the Tests

1. Open the Unity project that includes the `A3GameRuntime` package.
2. Import the desired example folder(s) into the project.
3. Open **Window → General → Test Runner**.
4. Select the **EditMode** tab and click **Run All**.

All tests are EditMode tests that instantiate `GameObject`s programmatically,
so no scene setup is required.

## Relationship to A3GameRuntime

Each example depends on the `A3GameRuntime` assembly for:

- Entity identity and observation (`A3GameRuntimeEntityComponent`,
  `IA3GameControllableEntity`, `A3GameEntitySnapshot`)
- Runtime coordination (`A3GameRuntimeSubsystem`)
- Locomotion and control-mode enums (`A3GameLocomotionState`,
  `A3GameControlMode`)

The examples never modify `A3GameRuntime`; they consume its public API.

> **Note:** These examples are disabled by default and are never installed
> automatically. Generated games should adapt the relevant patterns inside
> their own gameplay code rather than depending on or inheriting from an
> example.
