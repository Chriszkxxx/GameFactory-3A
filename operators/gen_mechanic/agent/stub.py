"""CPU-safe Duck-Typed Agent backend for Mechanic contract tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Callable

from .contracts import (
    resolve_workspace_file,
    validate_agent_request,
    validate_agent_result,
)


class StubAgent:
    """Write deterministic fixture files and return a valid Agent result."""

    def __init__(
        self,
        files: Mapping[str, str | bytes] | None = None,
        *,
        fail: bool = False,
        message: str = "Stub Agent completed",
        warnings: Sequence[str] = (),
        errors: Sequence[str] = (),
        deleted_files: Sequence[str] = (),
        file_factory: (
            Callable[
                [Mapping[str, Any]],
                Mapping[str, str | bytes],
            ]
            | None
        ) = None,
        timeout_sec: float | None = None,
        max_turns: int | None = 8,
    ) -> None:
        self.files = dict(files or {})
        self.fail = bool(fail)
        self.message = str(message)
        self.warnings = [
            str(warning)
            for warning in warnings
        ]
        self.errors = [
            str(error)
            for error in errors
        ]
        self.deleted_files = [
            str(path)
            for path in deleted_files
        ]
        self.file_factory = file_factory
        self.timeout_sec = timeout_sec
        self.max_turns = max_turns
        self.calls: list[dict[str, Any]] = []

    def run(
        self,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        normalized = validate_agent_request(request)
        self.calls.append(normalized)
        workspace = Path(
            normalized["workspace"]
        )
        workspace.mkdir(parents=True, exist_ok=True)

        source_files = (
            dict(self.file_factory(normalized))
            if self.file_factory is not None
            else dict(self.files)
        )
        values = {
            "PROJECT_NAME": normalized["context"][
                "project_name"
            ],
            "GAMEPLAY_MODULE_NAME": normalized["context"][
                "gameplay_module_name"
            ],
            "ENGINE": normalized["context"]["engine"],
        }

        def render(value: str) -> str:
            result = str(value)
            for key, replacement in values.items():
                result = result.replace(
                    f"{{{{{key}}}}}",
                    replacement,
                )
            return result

        rendered_files = {
            render(relative_path): (
                content
                if isinstance(content, bytes)
                else render(content)
            )
            for relative_path, content in source_files.items()
        }
        file_targets = {
            relative_path: resolve_workspace_file(
                workspace,
                relative_path,
            )
            for relative_path in rendered_files
        }
        delete_targets = {
            relative_path: resolve_workspace_file(
                workspace,
                relative_path,
            )
            for relative_path in self.deleted_files
        }
        overlap = (
            set(file_targets.values())
            & set(delete_targets.values())
        )
        if overlap:
            raise ValueError(
                "Stub Agent cannot write and delete the same file"
            )

        generated_files: list[str] = []
        modified_files: list[str] = []
        for relative_path, content in rendered_files.items():
            target = file_targets[relative_path]
            existed = target.is_file()
            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            if isinstance(content, bytes):
                target.write_bytes(content)
            else:
                target.write_text(
                    str(content),
                    encoding="utf-8",
                )
            reported_path = (
                target.relative_to(workspace).as_posix()
            )
            if existed:
                modified_files.append(reported_path)
            else:
                generated_files.append(reported_path)

        deleted_files: list[str] = []
        for relative_path, target in delete_targets.items():
            if not target.is_file():
                raise FileNotFoundError(
                    f"Stub Agent delete target does not exist: "
                    f"{relative_path}"
                )
            target.unlink()
            deleted_files.append(
                target.relative_to(workspace).as_posix()
            )

        errors = list(self.errors)
        if self.fail and not errors:
            errors.append("Stub Agent configured failure")
        result = {
            "ok": not self.fail,
            "request_id": normalized["request_id"],
            "status": (
                "failed"
                if self.fail
                else "completed"
            ),
            "generated_files": generated_files,
            "modified_files": modified_files,
            "deleted_files": deleted_files,
            "diagnostics": [],
            "warnings": list(self.warnings),
            "errors": errors,
            "transcript": [
                {
                    "role": "assistant",
                    "content": self.message,
                }
            ],
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
            },
            "payload": {
                "backend": "stub",
                "mode": normalized["mode"],
                "workspace": str(workspace),
            },
        }
        return validate_agent_result(
            result,
            request_id=normalized["request_id"],
            workspace=workspace,
        )


def make_stub_mechanic_files(
    request: Mapping[str, Any],
) -> Mapping[str, str]:
    """Return deterministic source fixtures for the selected engine."""
    context = request["context"]
    engine = str(context["engine"]).strip().lower()
    if engine in {"ue", "ue5", "unreal"}:
        return {
            "project/{{PROJECT_NAME}}.uproject": (
                "{\n"
                '  "FileVersion": 3,\n'
                '  "EngineAssociation": "",\n'
                '  "Category": "AAAGameForge",\n'
                '  "Modules": [\n'
                "    {\n"
                '      "Name": "{{PROJECT_NAME}}",\n'
                '      "Type": "Runtime",\n'
                '      "LoadingPhase": "Default"\n'
                "    }\n"
                "  ],\n"
                '  "Plugins": [\n'
                "    {\n"
                '      "Name": "AAAGamePlayable",\n'
                '      "Enabled": true\n'
                "    },\n"
                "    {\n"
                '      "Name": "{{GAMEPLAY_MODULE_NAME}}",\n'
                '      "Enabled": true\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
            (
                "project/Source/{{PROJECT_NAME}}/"
                "{{PROJECT_NAME}}.Build.cs"
            ): (
                "using UnrealBuildTool;\n\n"
                "public class {{PROJECT_NAME}} : ModuleRules\n"
                "{\n"
                "    public {{PROJECT_NAME}}("
                "ReadOnlyTargetRules Target) : base(Target)\n"
                "    {\n"
                "        PCHUsage = "
                "PCHUsageMode.UseExplicitOrSharedPCHs;\n"
                "        PublicDependencyModuleNames.AddRange("
                'new[] { "Core", "CoreUObject", "Engine" });\n'
                "    }\n"
                "}\n"
            ),
            (
                "project/Source/{{PROJECT_NAME}}/"
                "{{PROJECT_NAME}}.cpp"
            ): (
                '#include "Modules/ModuleManager.h"\n\n'
                "IMPLEMENT_PRIMARY_GAME_MODULE(\n"
                "    FDefaultGameModuleImpl,\n"
                "    {{PROJECT_NAME}},\n"
                '    "{{PROJECT_NAME}}");\n'
            ),
            (
                "project/Source/{{PROJECT_NAME}}Editor.Target.cs"
            ): (
                "using UnrealBuildTool;\n\n"
                "public class {{PROJECT_NAME}}EditorTarget "
                ": TargetRules\n"
                "{\n"
                "    public {{PROJECT_NAME}}EditorTarget("
                "TargetInfo Target) : base(Target)\n"
                "    {\n"
                "        Type = TargetType.Editor;\n"
                "        DefaultBuildSettings = "
                "BuildSettingsVersion.V5;\n"
                "        ExtraModuleNames.Add("
                '"{{PROJECT_NAME}}");\n'
                "    }\n"
                "}\n"
            ),
            "project/Source/{{PROJECT_NAME}}.Target.cs": (
                "using UnrealBuildTool;\n\n"
                "public class {{PROJECT_NAME}}Target "
                ": TargetRules\n"
                "{\n"
                "    public {{PROJECT_NAME}}Target("
                "TargetInfo Target) : base(Target)\n"
                "    {\n"
                "        Type = TargetType.Game;\n"
                "        DefaultBuildSettings = "
                "BuildSettingsVersion.V5;\n"
                "        ExtraModuleNames.Add("
                '"{{PROJECT_NAME}}");\n'
                "    }\n"
                "}\n"
            ),
            (
                "generated_plugin/"
                "{{GAMEPLAY_MODULE_NAME}}.uplugin"
            ): (
                "{\n"
                '  "FileVersion": 3,\n'
                '  "Version": 1,\n'
                '  "FriendlyName": '
                '"{{GAMEPLAY_MODULE_NAME}}",\n'
                '  "EnabledByDefault": false,\n'
                '  "CanContainContent": true,\n'
                '  "Modules": [\n'
                "    {\n"
                '      "Name": "{{GAMEPLAY_MODULE_NAME}}",\n'
                '      "Type": "Runtime",\n'
                '      "LoadingPhase": "Default"\n'
                "    }\n"
                "  ],\n"
                '  "Plugins": [\n'
                "    {\n"
                '      "Name": "AAAGamePlayable",\n'
                '      "Enabled": true\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
            (
                "generated_plugin/Source/"
                "{{GAMEPLAY_MODULE_NAME}}/"
                "{{GAMEPLAY_MODULE_NAME}}.Build.cs"
            ): (
                "using UnrealBuildTool;\n\n"
                "public class {{GAMEPLAY_MODULE_NAME}} "
                ": ModuleRules\n"
                "{\n"
                "    public {{GAMEPLAY_MODULE_NAME}}("
                "ReadOnlyTargetRules Target) : base(Target)\n"
                "    {\n"
                "        PCHUsage = "
                "PCHUsageMode.UseExplicitOrSharedPCHs;\n"
                "        PublicDependencyModuleNames.AddRange("
                "new[]\n"
                "        {\n"
                '            "Core",\n'
                '            "CoreUObject",\n'
                '            "Engine",\n'
                '            "AAAGamePlayable"\n'
                "        });\n"
                "    }\n"
                "}\n"
            ),
            (
                "generated_plugin/Source/"
                "{{GAMEPLAY_MODULE_NAME}}/Private/"
                "{{GAMEPLAY_MODULE_NAME}}Module.cpp"
            ): (
                '#include "Modules/ModuleManager.h"\n\n'
                "IMPLEMENT_MODULE(\n"
                "    FDefaultModuleImpl,\n"
                "    {{GAMEPLAY_MODULE_NAME}})\n"
            ),
            (
                "generated_plugin/Source/"
                "{{GAMEPLAY_MODULE_NAME}}/Public/"
                "GeneratedMechanicContract.h"
            ): (
                "#pragma once\n\n"
                '#include "CoreMinimal.h"\n\n'
                "struct FGeneratedMechanicContract\n"
                "{\n"
                "    static FString ProjectName();\n"
                "};\n"
            ),
            (
                "generated_plugin/Source/"
                "{{GAMEPLAY_MODULE_NAME}}/Private/"
                "GeneratedMechanicContract.cpp"
            ): (
                '#include "GeneratedMechanicContract.h"\n\n'
                "FString FGeneratedMechanicContract::ProjectName()\n"
                "{\n"
                '    return TEXT("{{PROJECT_NAME}}");\n'
                "}\n"
            ),
            (
                "generated_plugin/Source/"
                "{{GAMEPLAY_MODULE_NAME}}/Private/Tests/"
                "{{GAMEPLAY_MODULE_NAME}}Tests.cpp"
            ): (
                '#include "GeneratedMechanicContract.h"\n'
                '#include "Misc/AutomationTest.h"\n\n'
                "#if WITH_DEV_AUTOMATION_TESTS\n"
                "IMPLEMENT_SIMPLE_AUTOMATION_TEST(\n"
                "    FGeneratedMechanicContractTest,\n"
                '    "AAAGame.GeneratedMechanic.Contract",\n'
                "    EAutomationTestFlags::EditorContext |\n"
                "        EAutomationTestFlags::EngineFilter)\n\n"
                "bool FGeneratedMechanicContractTest::RunTest(\n"
                "    const FString& Parameters)\n"
                "{\n"
                "    TestEqual(\n"
                '        TEXT("Generated project identifier"),\n'
                "        FGeneratedMechanicContract::ProjectName(),\n"
                '        FString(TEXT("{{PROJECT_NAME}}")));\n'
                "    return true;\n"
                "}\n"
                "#endif\n"
            ),
            "launch.cmd": (
                "@echo off\n"
                'echo Launch {{PROJECT_NAME}} with the configured engine.\n'
            ),
            "launch.sh": (
                "#!/usr/bin/env sh\n"
                'echo "Launch {{PROJECT_NAME}} with the configured engine."\n'
            ),
        }
    return {
        "project/project.json": (
            "{\n"
            '  "project_name": "{{PROJECT_NAME}}",\n'
            '  "engine": "{{ENGINE}}",\n'
            '  "gameplay_module": "{{GAMEPLAY_MODULE_NAME}}"\n'
            "}\n"
        ),
        "generated_plugin/module.json": (
            "{\n"
            '  "name": "{{GAMEPLAY_MODULE_NAME}}",\n'
            '  "engine": "{{ENGINE}}"\n'
            "}\n"
        ),
        (
            "generated_plugin/src/"
            "{{GAMEPLAY_MODULE_NAME}}.txt"
        ): "Deterministic Stub gameplay module.\n",
        (
            "generated_plugin/tests/"
            "{{GAMEPLAY_MODULE_NAME}}Tests.txt"
        ): "Deterministic Stub gameplay test source.\n",
        "launch.cmd": (
            "@echo off\n"
            'echo Launch {{PROJECT_NAME}} with the configured engine.\n'
        ),
        "launch.sh": (
            "#!/usr/bin/env sh\n"
            'echo "Launch {{PROJECT_NAME}} with the configured engine."\n'
        ),
    }
