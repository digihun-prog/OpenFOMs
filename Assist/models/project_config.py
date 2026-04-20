from __future__ import annotations
import os
from dataclasses import dataclass, field
from .mapping_rule import MappingRuleSet, CauseMapping


@dataclass
class ProjectConfig:
    name:           str
    project_dir:    str           # 절대 경로: projects/<name>/
    rules:          MappingRuleSet = field(default_factory=dict)
    cause_mapping:  CauseMapping   = field(default_factory=CauseMapping)
    source_file:    str = ""      # 마지막으로 사용한 원천 파일 경로
    source_headers: list[str] = field(default_factory=list)  # 원천 파일 헤더 목록

    def output_dir(self) -> str:
        return os.path.join(self.project_dir, "output")

    def mapping_rules_path(self) -> str:
        return os.path.join(self.project_dir, "mapping_rules.json")

    def config_json_path(self) -> str:
        return os.path.join(self.project_dir, "config.json")
