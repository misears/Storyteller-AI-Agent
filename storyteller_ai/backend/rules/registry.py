"""Validated discovery of bundled and local ruleset/setting packs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Generic, TypeVar

import yaml
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from ..models.ruleset import Ruleset, SettingPack
from ..services.app_paths import get_app_root, get_data_dir


PackModel = TypeVar("PackModel", Ruleset, SettingPack)


@dataclass(frozen=True)
class PackIssue:
    kind: str
    path: str
    error: str


@dataclass(frozen=True)
class PackEntry(Generic[PackModel]):
    value: PackModel | None
    path: Path
    source: str
    error: str | None = None

    @property
    def valid(self) -> bool:
        return self.value is not None and self.error is None


class PackRegistry(Generic[PackModel]):
    def __init__(
        self, model: type[PackModel], manifest_name: str,
        roots: list[tuple[str, Path]], schema_name: str | None = None,
    ):
        self.model = model
        self.manifest_name = manifest_name
        self.roots = roots
        self.schema_name = schema_name
        self.entries: list[PackEntry[PackModel]] = []
        self.refresh()

    def refresh(self) -> None:
        self.entries = []
        seen: set[tuple[str, str]] = set()
        for source, root in self.roots:
            if not root.exists():
                continue
            for pack_dir in sorted(path for path in root.iterdir() if path.is_dir()):
                entry = self._load(pack_dir, source)
                if entry.value is not None:
                    key = (entry.value.id, entry.value.version)
                    if key in seen:
                        continue
                    seen.add(key)
                self.entries.append(entry)

    def list(self, include_invalid: bool = False) -> list[PackEntry[PackModel]]:
        if include_invalid:
            return list(self.entries)
        return [entry for entry in self.entries if entry.valid]

    def get(self, pack_id: str, version: str | None = None) -> PackModel | None:
        for entry in self.entries:
            if not entry.valid or entry.value.id != pack_id:
                continue
            if version is None or entry.value.version == version:
                return entry.value
        return None

    def issues(self) -> list[PackIssue]:
        return [PackIssue(self.model.__name__, str(entry.path), entry.error)
                for entry in self.entries if entry.error is not None]

    def _load(self, pack_dir: Path, source: str) -> PackEntry[PackModel]:
        manifest_path = pack_dir / self.manifest_name
        try:
            manifest = _read_yaml(manifest_path)
            if manifest.get("id") != pack_dir.name:
                raise ValueError("manifest id must match its directory name")
            if self.schema_name is not None:
                schema_path = pack_dir / self.schema_name
                schema = _read_json(schema_path)
                Draft202012Validator.check_schema(schema)
                manifest["sheet_schema"] = schema
            value = self.model.model_validate(manifest)
            return PackEntry(value, pack_dir, source)
        except (OSError, ValueError, TypeError, ValidationError, yaml.YAMLError) as exc:
            return PackEntry(None, pack_dir, source, str(exc))


def _read_yaml(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"missing {path.name}")
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a mapping")
    return value


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"missing {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def _roots(kind: str) -> list[tuple[str, Path]]:
    return [
        ("bundled", get_app_root() / "backend" / "content" / kind),
        ("local", get_data_dir() / "packs" / kind),
    ]


class RulesetRegistry(PackRegistry[Ruleset]):
    def __init__(self, roots: list[tuple[str, Path]] | None = None):
        super().__init__(Ruleset, "ruleset.yaml", roots or _roots("rulesets"), "sheet.schema.json")


class SettingRegistry(PackRegistry[SettingPack]):
    def __init__(self, roots: list[tuple[str, Path]] | None = None):
        super().__init__(SettingPack, "setting.yaml", roots or _roots("settings"))


class PackRegistrySet:
    def __init__(self):
        self.rulesets = RulesetRegistry()
        self.settings = SettingRegistry()

    def refresh(self) -> None:
        self.rulesets.refresh()
        self.settings.refresh()


pack_registry = PackRegistrySet()