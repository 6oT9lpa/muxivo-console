from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_all_alembic_revisions_define_upgrade_and_downgrade() -> None:
    config = Config(str(Path("alembic.ini")))
    script_directory = ScriptDirectory.from_config(config)

    revisions = list(script_directory.walk_revisions())

    assert revisions
    for revision in revisions:
        assert callable(revision.module.upgrade)
        assert callable(revision.module.downgrade)


def test_alembic_head_is_the_latest_console_foundation_revision() -> None:
    config = Config(str(Path("alembic.ini")))
    script_directory = ScriptDirectory.from_config(config)

    assert script_directory.get_current_head() == "20260905_0007"
