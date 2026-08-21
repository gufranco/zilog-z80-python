import importlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "conformance"))

regenerate: Any = importlib.import_module("regenerate")

A_GENERATOR = {
    "repository": "https://example.invalid/generator.git",
    "commit": "0123456789abcdef0123456789abcdef01234567",
    "entryPoint": "misc/z80_test_generator.js, generate_Z80_tests",
    "requires": ["helpers.js", "common.js"],
    "flags": {"Z80_DO_FULL_MEMCYCLES": False, "Z80_DO_MEM_REFRESHES": True},
}

A_TINY_GENERATOR = """
let Z80_DO_FULL_MEMCYCLES = false;
function generate_Z80_tests() {
  const zip = new JSZip();
  zip.file('00.json', JSON.stringify([{ full: Z80_DO_FULL_MEMCYCLES }]));
  dconsole.addl('done');
  save_js('tests.zip', '');
}
"""


def a_source_tree(where: Path, body: str = A_TINY_GENERATOR) -> Path:
    (where / "misc").mkdir(parents=True, exist_ok=True)
    (where / "helpers.js").write_text("function save_js() { new Blob(); }\n")
    (where / "common.js").write_text("const unused = 1;\n")
    (where / "misc" / "z80_test_generator.js").write_text(body)
    return where


class DefinitionTest(unittest.TestCase):
    def test_the_repository_declares_the_generator_it_came_from(self) -> None:
        self.assertEqual(len(regenerate.definition()["commit"]), 40)

    def test_it_names_every_file_the_generator_has_to_be_given(self) -> None:
        self.assertTrue(regenerate.definition()["requires"])

    def test_a_definition_is_read_from_where_it_is_asked_for(self) -> None:
        where = Path(tempfile.mkdtemp())
        path = where / "suites.json"
        path.write_text(json.dumps({"suites": [{"generator": A_GENERATOR}]}))

        self.assertEqual(regenerate.definition(path)["commit"], A_GENERATOR["commit"])


class CloneCommandTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.steps = regenerate.clone_command(A_GENERATOR, "/tmp/somewhere")

    def test_the_commit_is_fetched_rather_than_a_branch(self) -> None:
        fetching = [step for step in self.steps if "fetch" in step]

        self.assertIn(A_GENERATOR["commit"], fetching[0])

    def test_only_one_commit_is_brought_down(self) -> None:
        fetching = [step for step in self.steps if "fetch" in step]

        self.assertIn("--depth=1", fetching[0])

    def test_the_checkout_is_of_what_was_fetched(self) -> None:
        self.assertIn("FETCH_HEAD", self.steps[-1])


class DriverTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.driver = regenerate.driver(A_GENERATOR)

    def test_every_required_source_is_named(self) -> None:
        missing = [name for name in A_GENERATOR["requires"] if name not in self.driver]

        self.assertEqual(missing, [])

    def test_and_so_is_the_file_holding_the_entry_point(self) -> None:
        self.assertIn("misc/z80_test_generator.js", self.driver)

    def test_the_entry_point_is_called_rather_than_only_loaded(self) -> None:
        self.assertIn("generate_Z80_tests(null, false)", self.driver)

    def test_the_flag_line_is_matched_exactly_so_a_rename_is_a_failure(self) -> None:
        self.assertIn(json.dumps(regenerate.FLAG), self.driver)


@unittest.skipIf(shutil.which("node") is None, "node is not on the path")
class GenerateTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.source = a_source_tree(Path(tempfile.mkdtemp()))
        self.output = Path(tempfile.mkdtemp())

    def written(self, full: bool = False) -> dict[str, Any]:
        code = regenerate.generate(A_GENERATOR, self.source, self.output, full)
        self.assertEqual(code, 0)
        held: list[dict[str, Any]] = json.loads((self.output / "00.json").read_text())
        return held[0]

    def test_a_run_writes_one_file_per_opcode(self) -> None:
        self.assertEqual(self.written()["full"], False)

    def test_the_full_flag_reaches_the_generator(self) -> None:
        self.assertEqual(self.written(full=True)["full"], True)

    def test_the_driver_is_not_left_behind_among_the_cases(self) -> None:
        self.written()

        self.assertEqual(list(self.output.glob("*.js")), [])

    def test_a_generator_that_no_longer_carries_the_flag_line_is_a_failure(self) -> None:
        (self.source / "misc" / "z80_test_generator.js").write_text(
            A_TINY_GENERATOR.replace(regenerate.FLAG, "let Z80_DO_FULL_MEMCYCLES = 0;")
        )

        self.assertNotEqual(regenerate.generate(A_GENERATOR, self.source, self.output, True), 0)

    def test_the_browser_download_step_is_not_a_failure(self) -> None:
        self.assertEqual(regenerate.generate(A_GENERATOR, self.source, self.output, False), 0)


class OptionTest(unittest.TestCase):
    def test_an_output_directory_is_required(self) -> None:
        with self.assertRaises(SystemExit):
            regenerate.options([])

    def test_the_output_directory_is_read_off_the_command_line(self) -> None:
        self.assertEqual(regenerate.options(["somewhere"])[0], Path("somewhere"))

    def test_the_published_shape_is_what_a_run_gets_without_asking(self) -> None:
        self.assertEqual(regenerate.options(["somewhere"])[1], False)

    def test_the_widened_shape_can_be_asked_for(self) -> None:
        self.assertEqual(regenerate.options(["somewhere", "--full"])[1], True)

    def test_an_existing_clone_can_be_pointed_at(self) -> None:
        self.assertEqual(
            regenerate.options(["somewhere", "--clone", "elsewhere"])[2], Path("elsewhere")
        )

    def test_and_is_absent_when_it_is_not(self) -> None:
        self.assertIsNone(regenerate.options(["somewhere"])[2])

    def test_a_clone_with_nothing_after_it_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            regenerate.options(["somewhere", "--clone"])

    def test_a_second_directory_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            regenerate.options(["somewhere", "elsewhere"])

    def test_flags_with_no_directory_among_them_are_refused(self) -> None:
        with self.assertRaises(SystemExit):
            regenerate.options(["--full"])


class CloneTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())

    def upstream(self) -> tuple[str, str]:
        where = self.root / "upstream"
        a_source_tree(where)
        for step in (
            ["git", "init", "-q", "-b", "main", str(where)],
            ["git", "-C", str(where), "config", "user.email", "nobody@example.invalid"],
            ["git", "-C", str(where), "config", "user.name", "Nobody"],
            ["git", "-C", str(where), "add", "-A"],
            ["git", "-C", str(where), "commit", "-q", "-m", "generator"],
        ):
            subprocess.run(step, check=True, capture_output=True)
        found = subprocess.run(
            ["git", "-C", str(where), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return str(where), found.stdout.strip()

    def test_a_generator_is_brought_down_at_the_commit_it_is_pinned_to(self) -> None:
        repository, commit = self.upstream()
        held = {**A_GENERATOR, "repository": repository, "commit": commit}

        where = regenerate.clone(held, self.root / "down")

        self.assertTrue((where / "helpers.js").is_file())

    def test_a_clone_that_is_already_there_is_left_alone(self) -> None:
        repository, commit = self.upstream()
        held = {**A_GENERATOR, "repository": repository, "commit": commit}
        where = regenerate.clone(held, self.root / "down")
        (where / "marker").write_text("kept")

        regenerate.clone(held, self.root / "down")

        self.assertEqual((where / "marker").read_text(), "kept")

    def test_a_repository_that_is_not_there_is_reported(self) -> None:
        with self.assertRaises(SystemExit):
            regenerate.clone(A_GENERATOR, self.root / "missing")


@unittest.skipIf(shutil.which("node") is None, "node is not on the path")
class MainTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.source = a_source_tree(self.root / "generator")
        self.held = self.root / "suites.json"
        self.held.write_text(json.dumps({"suites": [{"generator": A_GENERATOR}]}))

    def test_a_run_reports_where_the_cases_landed(self) -> None:
        code = regenerate.main([str(self.root / "out"), "--clone", str(self.source)], self.held)

        self.assertEqual(code, 0)

    def test_a_generator_that_fails_is_reported_rather_than_passing(self) -> None:
        (self.source / "misc" / "z80_test_generator.js").write_text("throw new Error('no');")

        code = regenerate.main([str(self.root / "out"), "--clone", str(self.source)], self.held)

        self.assertNotEqual(code, 0)


class NodeTest(unittest.TestCase):
    def test_a_machine_without_node_is_told_so_rather_than_failing_obscurely(self) -> None:
        held = regenerate.shutil.which
        regenerate.shutil.which = lambda _name: None
        self.addCleanup(setattr, regenerate.shutil, "which", held)

        with self.assertRaises(SystemExit):
            regenerate.generate(
                A_GENERATOR, Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp()), False
            )


if __name__ == "__main__":
    unittest.main()
