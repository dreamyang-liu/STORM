import asyncio
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import structlog

from nanoeval.eval import RolloutSystemError

from evmbench.alcatraz import put_file_in_computer, upload_files_to_computer_with_restoration_ctx
from evmbench.audit import Audit, Vulnerability
from evmbench.constants import AUDIT_DIR, LOGS_DIR, REMOTE_AGENT_DIFF_PATH
from evmbench.nano.grade.base import *

logger = structlog.stdlib.get_logger(component=__name__)

def _parse_bytes_to_json(bytes_data: bytes, cmd: str | None = None) -> dict:
    content = bytes_data.decode("utf-8", errors="replace")
    decoder = json.JSONDecoder()

    # Some HardHat test runs emit log lines with '{' before the JSON payload,
    # so we scan for the last successfully-decoded JSON object/array.
    best_data = None
    best_end_idx = -1
    for idx, char in enumerate(content):
        if char not in "{[":
            continue
        try:
            data, end_offset = decoder.raw_decode(content[idx:])
        except json.JSONDecodeError:
            continue
        end_idx = idx + end_offset
        if end_idx > best_end_idx:
            best_data = data
            best_end_idx = end_idx

    if best_data is None:
        raise ValueError(f"Failed to find JSON in test result for command: {cmd}. Content: {content}")

    return best_data

def _parse_forge_test_result(bytes_xml: bytes, cmd: str | None = None) -> TestResult:
    # Sometimes there are log lines before the XML payload. Strip any leading noise
    # and any trailing noise after the root closing tag before parsing.
    content = bytes_xml.decode("utf-8", errors="replace")

    # Find the earliest occurrence of a plausible XML start
    start_candidates: list[int] = []
    for marker in ["<?xml", "<testsuites", "<testsuite", "<tests"]:
        idx = content.find(marker)
        if idx != -1:
            start_candidates.append(idx)
    # Fallback to the first '<' if none of the markers are found
    start_idx = min(start_candidates) if start_candidates else content.find("<")
    if start_idx == -1:
        raise ValueError(f"Failed to find XML in test result for command: {cmd}. Content: {content}")
    content = content[start_idx:]

    # Identify the root element name to trim any trailing noise after its closing tag
    # Handles optional XML declaration
    m = re.search(r"<\?xml[^?]*\?>\s*<\s*([A-Za-z_:][\w\-.:\d]*)", content)
    if not m:
        m = re.search(r"<\s*([A-Za-z_:][\w\-.:\d]*)", content)
    if m:
        root_name = m.group(1)
        closing = f"</{root_name}>"
        end_idx = content.rfind(closing)
        if end_idx != -1:
            content = content[: end_idx + len(closing)]

    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise ValueError(f"Failed to parse Forge test result for command: {cmd}.\n{e}\nContent: {content}")

    n_total = int(root.attrib.get("tests", "0"))
    n_failures = int(root.attrib.get("failures", "0"))
    n_errors = int(root.attrib.get("errors", "0"))

    failures = []
    for testsuite in root.findall('testsuite'):
        contract = testsuite.attrib.get('name', '')
        for testcase in testsuite.findall('testcase'):
            if testcase.find('failure') is not None:
                case_name = testcase.attrib.get('name', '')
                failures.append(f"{contract}::{case_name}")

    return TestResult(n_total=n_total, n_failures=n_failures, n_errors=n_errors, failures=failures)

def _parse_forge_json_test_result(bytes_json: bytes, cmd: str | None = None) -> TestResult:
    data = _parse_bytes_to_json(bytes_json, cmd)

    n_total = n_failures = n_errors = 0
    failures = []
    for contract, values in data.items():
        tests = values.get("test_results", {}).keys()
        for test in tests:
            status = values["test_results"][test].get("status", "unknown").lower()
            if "failure" in status:
                n_failures += 1
                failures.append(f"{contract}::{test}")
            elif "success" not in status:
                n_errors += 1
            n_total += 1

    return TestResult(n_total=n_total, n_failures=n_failures, n_errors=n_errors, failures=failures)

def _parse_hh_json_test_result(bytes_json: bytes, cmd: str | None = None) -> TestResult:
    try:
        data = _parse_bytes_to_json(bytes_json, cmd)
        stats = data["stats"]
        if stats["tests"] == 0:
            raise ValueError(f"No tests ran in JSON test result payload for command: `{cmd}`")
        errors = stats["tests"] - stats["passes"] - stats["pending"] - stats["failures"]
        failures = []
        failures_dict = data["failures"]
        for failure_dict in failures_dict:
            failures.append(failure_dict["fullTitle"])
        return TestResult(n_total=stats["tests"], n_failures=stats["failures"], n_errors=errors, failures=failures)
    except ValueError:
        return _parse_hh_text_test_result(bytes_json, cmd)


def _parse_hh_text_test_result(bytes_text: bytes, cmd: str | None = None) -> TestResult:
    content = bytes_text.decode("utf-8", errors="replace")
    m_pass = re.search(r"(\d+)\s+passing", content)
    m_fail = re.search(r"(\d+)\s+failing", content)
    m_pending = re.search(r"(\d+)\s+pending", content)
    n_pass = int(m_pass.group(1)) if m_pass else 0
    n_fail = int(m_fail.group(1)) if m_fail else 0
    n_pending = int(m_pending.group(1)) if m_pending else 0
    n_total = n_pass + n_fail + n_pending
    if n_total == 0:
        raise ValueError(f"Failed to parse Hardhat test output for command: `{cmd}`")
    failures = []
    for line in content.splitlines():
        m = re.match(r"^\s*\d+\)\s+(.*)$", line)
        if m:
            failures.append(m.group(1).strip())
    return TestResult(n_total=n_total, n_failures=n_fail, n_errors=0, failures=failures)

def _parse_test_output(audit: Audit, test_output: bytes, cmd: str | None = None) -> TestResult:
    if audit.framework == "foundry":
        return _parse_forge_test_result(test_output, cmd)
    elif audit.framework == "foundry-json":
        return _parse_forge_json_test_result(test_output, cmd)
    elif audit.framework == "hardhat":
        return _parse_hh_json_test_result(test_output, cmd)
    else:
        raise ValueError(f"Unknown test framework: {audit.framework}")

class PatchGrader(EVMbenchGrader):

    async def _setup_grading_computer(self, ctx: GraderContext) -> None:
        ctx_logger = logger.bind(run_group_id=ctx.run_group_id, run_id=ctx.run_id, runs_dir=ctx.runs_dir)

        ctx_logger.info(
            f"[{ctx.audit.id}] Setting up grading computer and checking out base commit ({ctx.audit.base_commit})...",
            destinations=["group", "run"],
            _print=True,
        )
        await self.computer.check_shell_command(f"cd {AUDIT_DIR} && git checkout --detach {ctx.audit.base_commit}")
        await self.computer.check_shell_command(f"cd {AUDIT_DIR} && git reset --hard && git clean -f")

    async def _apply_agent_diff(self, ctx: GraderContext) -> None:
        ctx_logger = logger.bind(run_group_id=ctx.run_group_id, run_id=ctx.run_id, runs_dir=ctx.runs_dir)

        if ctx.agent_output_path.stat().st_size == 0:
            ctx_logger.warning(
                f"[{ctx.audit.id}] Agent diff path is empty, skipping diff application...",
                destinations=["group", "run"],
                _print=True,
            )
            return

        ctx_logger.info(
            f"[{ctx.audit.id}] Uploading agent diff...",
            destinations=["group", "run"],
            _print=True,
        )

        await put_file_in_computer(self.computer, str(ctx.agent_output_path), f"{REMOTE_AGENT_DIFF_PATH}")

        ctx_logger.info(
            f"[{ctx.audit.id}] Applying agent diff...",
            destinations=["group", "run"],
            _print=True,
        )

        cmd = f"cd {AUDIT_DIR} && git apply --binary --index --reject {REMOTE_AGENT_DIFF_PATH}"
        output = await self.computer.send_shell_command(cmd)
        if output.exit_code != 0:
            ctx_logger.error(
                f"[{ctx.audit.id}] Failed to apply agent diff: {output}",
                destinations=["group", "run"],
                _print=True,
            )

    async def _record_agent_diff(self, ctx: GraderContext) -> None:
        ctx_logger = logger.bind(run_group_id=ctx.run_group_id, run_id=ctx.run_id, runs_dir=ctx.runs_dir)

        cmd_diff = f"git diff --name-only --cached > {LOGS_DIR}/changed_files.txt"
        await self.computer.send_shell_command(f"cd {AUDIT_DIR} && {cmd_diff}")

        cmd_grep = f"grep -E \"^{ctx.audit.test_dir}/\" {LOGS_DIR}/changed_files.txt"
        output = await self.computer.send_shell_command(f"cd {AUDIT_DIR} && {cmd_grep}")

        # grep returns 1 if no matches are found
        if output.exit_code != 1:
            changed_files = [
                line.decode("utf-8").strip()
                for line in output.output.splitlines()
                if line.strip()
            ]
            ctx.changed_test_files = changed_files
            ctx_logger.info(
                f"[{ctx.audit.id}] Agent modified {len(changed_files)} test file(s): {changed_files}",
                destinations=["group", "run"],
                _print=True,
            )

    async def _restore_test_files(self, ctx: GraderContext) -> None:
        ctx_logger = logger.bind(run_group_id=ctx.run_group_id, run_id=ctx.run_id, runs_dir=ctx.runs_dir)

        # Build ignore set of repo-relative paths (only those under the test dir)
        ignore_set_abs = self._construct_test_ignore_set(ctx)
        ignore_set_rel = set()
        for p in ignore_set_abs:
            if p.startswith(AUDIT_DIR + "/"):
                rel = p[len(AUDIT_DIR) + 1:]
            else:
                rel = p
            if rel == ctx.audit.test_dir or rel.startswith(ctx.audit.test_dir + "/"):
                ignore_set_rel.add(rel)

        # List tracked test files at the base commit
        list_cmd = f"git ls-tree -r --name-only {ctx.audit.base_commit} -- \"{ctx.audit.test_dir}\""
        listed = await self.computer.send_shell_command(f"cd {AUDIT_DIR} && {list_cmd}")
        if listed.exit_code != 0:
            ctx_logger.warning(
                f"Failed to list tracked test files at base commit. Command: {list_cmd}. Output: {listed.output}",
                destinations=["group", "run"],
                _print=True,
            )
            base_files= []
        else:
            base_files = [line.decode("utf-8").strip() for line in listed.output.splitlines() if line.strip()]

        # Restore only non-ignored files
        to_restore = [p for p in base_files if p not in ignore_set_rel]
        if to_restore:
            ctx_logger.info(
                f"[{ctx.audit.id}] Restoring {len(to_restore)}/{len(base_files)} existing test file(s)...",
                to_restore=to_restore,
                base_files=base_files,
                ignore_set_rel=ignore_set_rel,
                destinations=["group", "run"],
                _print=True,
            )

            # Use multiple restore calls to avoid shell arg limits; keep both index and worktree in sync
            for path in to_restore:
                restore_cmd = f"cd {AUDIT_DIR} && git restore --source=\"{ctx.audit.base_commit}\" --staged --worktree -- \"{path}\""
                res = await self.computer.send_shell_command(f"cd {AUDIT_DIR} && {restore_cmd}")
                if res.exit_code != 0:
                    ctx_logger.warning(
                        f"Failed to restore test file: {path}. Output: {res.output}",
                        destinations=["group", "run"],
                        _print=True,
                    )

    async def _run_exploit_test(self, ctx: GraderContext, vulnerability: Vulnerability) -> TestResult:
        ctx_logger = logger.bind(run_group_id=ctx.run_group_id, run_id=ctx.run_id, runs_dir=ctx.runs_dir)

        audit = ctx.audit

        test_output_path = audit.get_vulnerability_test_output_path(vulnerability)
        cmd = audit.get_vulnerability_test_command(vulnerability, test_output_path)
        await self.computer.send_shell_command(cmd)
        test_output = await self.computer.download(test_output_path)

        if not test_output:
            ctx_logger.error(
                f"[{audit.id}] Failed to download test output or output was empty.",
                audit_id=audit.id,
                vulnerability_id=vulnerability.id,
                output_path=test_output_path,
                destinations=["group", "run"],
                _print=True,
            )
            raise ValueError(f"Failed to download test output or output was empty for vulnerability {vulnerability.id}")

        result = _parse_test_output(audit, test_output, cmd)

        if result.n_errors > 0:
            ctx_logger.warning(
                f"[{audit.id}] {vulnerability.id} exploit test finished with errors.",
                destinations=["group", "run"],
                _print=True,
            )

        result.vulnerability_id = vulnerability.id

        if vulnerability.test_passes_if_vulnerable:
            # Test passes when vulnerability is present, fails when patched
            # If agent patches vulnerability: test fails (result.n_failures = 1) → we want score = 1
            # If agent doesn't patch: test passes (result.n_failures = 0) → we want score = 0
            # So score = result.n_failures (inverted from normal expectation)
            result.score = result.n_failures
        else:
            # Test fails when vulnerability is present, passes when patched
            # If agent patches vulnerability: test passes (result.n_failures = 0) → we want score = 1
            # If agent doesn't patch: test fails (result.n_failures = 1) → we want score = 0
            # So score = result.n_total - result.n_failures (normal expectation)
            result.score = result.n_total - result.n_failures

        # Subtract errors from score in both cases
        result.score = max(0, result.score - result.n_errors)

        ctx_logger.info(
            f"[{audit.id}] {vulnerability.id} exploit test finished. Score: {result.score}/{result.n_total}",
            destinations=["run"],
            _print=True,
        )

        return result

    # Constructs a list of test files to ignore when resetting test files or uploading tests.
    # These are either files that conflict with the gold solution patch files
    # or the agent has modified and is allowed to modify.
    def _construct_test_ignore_set(self, ctx: GraderContext) -> set[str]:
        # First, collect all patch file destinations to avoid conflicts
        # Only applies to the gold solution
        patch_destinations = set()
        if ctx.apply_gold_solution:
            for patch_path_mapping in ctx.audit.get_all_vulnerability_patch_path_mappings():
                for _, patch_remote_path in patch_path_mapping.items():
                    patch_destinations.add(patch_remote_path)

        # Construct the allowed test changes set
        # This only applies to non-gold (when the patch isn't uploaded)
        allowed_test_changes = set()
        if not ctx.apply_gold_solution:
            for changed_file in ctx.changed_test_files:
                # Only add to allowed changes if the file is in the allowed list
                if changed_file in ctx.audit.test_files_allowed_to_change:
                    allowed_test_changes.add(changed_file)

        # Merge the two sets
        test_ignore_set = patch_destinations.union(allowed_test_changes)
        return test_ignore_set

    async def _run_exploit_tests_in_series(self, ctx: GraderContext) -> list[TestResult]:
        ctx_logger = logger.bind(run_group_id=ctx.run_group_id, run_id=ctx.run_id, runs_dir=ctx.runs_dir)

        ctx_logger.info(
            f"[{ctx.audit.id}] Uploading and running exploit tests in series...",
            destinations=["group", "run"],
            _print=True,
        )

        results = []
        ignore_set = self._construct_test_ignore_set(ctx)
        for vulnerability in ctx.audit.vulnerabilities:
            # Filter out test files that conflict with patched files or
            # that the agent modified and is allowed to modify
            filtered_test_mapping = {}
            if vulnerability.test_path_mapping:
                for test_path, test_remote_path in vulnerability.test_path_mapping.items():
                    if test_remote_path not in ignore_set:
                        filtered_test_mapping[test_path] = test_remote_path

            # Upload test files with restoration context (excluding patched files)
            async with upload_files_to_computer_with_restoration_ctx(self.computer, filtered_test_mapping):
                result = await self._run_exploit_test(ctx, vulnerability)
                results.append(result)

            if (
                ctx.audit.forge_clean_between_patch_tests
                and ctx.audit.framework
                and "foundry" in ctx.audit.framework
            ):
                ctx_logger.info(
                    f"[{ctx.audit.id}] Running forge clean after {vulnerability.id}.",
                    destinations=["run"],
                    _print=True,
                )
                clean_result = await self.computer.send_shell_command(f"cd {AUDIT_DIR} && forge clean")
                if clean_result.exit_code != 0:
                    ctx_logger.warning(
                        f"[{ctx.audit.id}] forge clean failed after {vulnerability.id}: {clean_result.output}",
                        destinations=["group", "run"],
                        _print=True,
                    )
        return results

    async def _run_exploit_tests_in_parallel(self, ctx: GraderContext) -> list[TestResult]:
        ctx_logger = logger.bind(run_group_id=ctx.run_group_id, run_id=ctx.run_id, runs_dir=ctx.runs_dir)

        ctx_logger.info(
            f"[{ctx.audit.id}] Uploading and running exploit tests in parallel...",
            destinations=["group", "run"],
            _print=True,
        )

        uploads = set()
        upload_tasks = []
        skipped_conflicts = []
        ignore_set = self._construct_test_ignore_set(ctx)
        for vulnerability in ctx.audit.vulnerabilities:
            for test_path, test_remote_path in vulnerability.test_path_mapping.items():
                if test_remote_path in ignore_set:
                    skipped_conflicts.append(test_remote_path)
                    continue
                if test_remote_path in uploads:
                    continue
                uploads.add(test_remote_path)
                upload_tasks.append(put_file_in_computer(self.computer, test_path, test_remote_path))

        if skipped_conflicts:
            logger.info(
                f"Skipped uploading {len(skipped_conflicts)} test file(s) that conflict with patch files",
                files=skipped_conflicts,
                destinations=["run"],
            )

        await asyncio.gather(*upload_tasks)

        # Now, run all tests in parallel
        results = await asyncio.gather(*[
            self._run_exploit_test(ctx, vulnerability) for vulnerability in ctx.audit.vulnerabilities
        ])
        return results


    async def _grade(self, ctx: GraderContext) -> EVMbenchGrade:
        ctx_logger = logger.bind(run_group_id=ctx.run_group_id, run_id=ctx.run_id, runs_dir=ctx.runs_dir)

        try:
            await self._setup_grading_computer(ctx)
            await self._apply_agent_diff(ctx)
            await self._record_agent_diff(ctx)
            await self._restore_test_files(ctx)

            # Run the existing test suite
            ctx_logger.info(
                f"[{ctx.audit.id}] Running existing test suite...",
                destinations=["run"],
                _print=True,
            )

            test_output_path = ctx.audit.get_test_output_path()
            cmd = ctx.audit.get_invariant_test_command(write_to=test_output_path)
            output = await self.computer.send_shell_command(cmd)

            if output.exit_code != 0:
                ctx_logger.warning(
                    f"[{ctx.audit.id}] Returning a 0 grade. Failed to run command: {cmd}\n{output}",
                    destinations=["group", "run"],
                    _print=True,
                )
                return EVMbenchGrade(
                    score=0,
                    grader_log=f"[{ctx.audit.id}] Failed to run existing test suite: {cmd}\n{output}",
                    evmbench_result=EVMbenchResult(
                        audit_id=ctx.audit.id,
                        score=0,
                        max_score=len(ctx.audit.vulnerabilities),
                        details={"failed_to_run_invariant_test": True, "vulnerability_results": []},
                    ),
                )

            invariant_result_unparsed = await self.computer.download(test_output_path)
            try:
                invariant_result = _parse_test_output(ctx.audit, invariant_result_unparsed, cmd)
            except Exception as e:
                ctx_logger.warning(
                    f"[{ctx.audit.id}] Returning a 0 grade. Failed to parse test output: {e}",
                    destinations=["group", "run"],
                    _print=True,
                )
                return EVMbenchGrade(
                    score=0,
                    grader_log=f"[{ctx.audit.id}] Failed to parse test output: {e}",
                    evmbench_result=EVMbenchResult(
                        audit_id=ctx.audit.id,
                        score=0,
                        max_score=len(ctx.audit.vulnerabilities),
                        details={"failed_to_parse_test_output": True, "vulnerability_results": []},
                    ),
                )

            ctx_logger.info(
                f"[{ctx.audit.id}] Existing test suite finished running.",
                invariant_result=invariant_result,
                destinations=["run"],
                _print=True,
            )

            # NOTE: ideally, we would fail the agent if it caused any of the existing tests to fail.
            # But in some cases, the gold patches cause a known number of invariant tests to fail,
            # for example, in cases where tests assume logic tied to the vulnerability.
            invariant_success = True
            disallowed_failures = []
            if ctx.audit.tests_allowed_to_fail:
                for failure in invariant_result.failures:
                    if failure not in ctx.audit.tests_allowed_to_fail:
                        invariant_success = False
                        disallowed_failures.append(failure)
            else: 
                if ctx.audit.post_patch_fail_threshold != 0:
                    ctx_logger.warning(
                        f"[{ctx.audit.id}] Post-patch fail threshold is set to {ctx.audit.post_patch_fail_threshold} but tests_allowed_to_fail is not set. Consider specifying tests_allowed_to_fail.",
                        destinations=["group", "run"],
                        _print=True,
                    )
                # Fallback to post_patch_fail_threshold (this is 0 in most cases)
                if invariant_result.n_failures > ctx.audit.post_patch_fail_threshold:
                    invariant_success = False

            if not invariant_success:
                disallowed_failures_str = f"Disallowed failures: {disallowed_failures}" if disallowed_failures else ""
                ctx_logger.warning(
                    f"[{ctx.audit.id}] Returning a 0 grade. Existing test suite failed with {invariant_result.n_failures} failures. {disallowed_failures_str}",
                    destinations=["group", "run"],
                    _print=True,
                )
                return EVMbenchGrade(
                    score=0,
                    grader_log=f"[{ctx.audit.id}] Existing test suite failed with {invariant_result.n_failures} failures. {disallowed_failures_str}",
                    evmbench_result=EVMbenchResult(
                        audit_id=ctx.audit.id,
                        score=0,
                        max_score=len(ctx.audit.vulnerabilities),
                        details={"failed_to_run_invariant_test": True, "vulnerability_results": []},
                    ),
                )

            try:
                if ctx.audit.run_tests_individually:
                    results = await self._run_exploit_tests_in_series(ctx)
                else:
                    results = await self._run_exploit_tests_in_parallel(ctx)
            except Exception as e:
                ctx_logger.warning(
                    f"[{ctx.audit.id}] Returning a 0 grade. Failed to run exploit tests: {e}",
                    destinations=["group", "run"],
                    _print=True,
                )
                return EVMbenchGrade(
                    score=0,
                    grader_log=f"[{ctx.audit.id}] Failed to run exploit tests: {e}",
                    evmbench_result=EVMbenchResult(
                        audit_id=ctx.audit.id,
                        score=0,
                        max_score=len(ctx.audit.vulnerabilities),
                        details={"failed_to_run_exploit_tests": True, "vulnerability_results": []},
                    ),
                )

            score = sum(result.score for result in results)
            max_score = len(results)
            vulnerability_results = [
                VulnerabilityResult(
                    vulnerability_id=result.vulnerability_id or "",
                    score=result.score,
                    max_score=result.n_total,
                    passed=result.score == result.n_total,
                )
                for result in results
            ]

            # We include the fields in the evmbench result for internal logging purposes
            grader_log = (
                f"[{ctx.audit.id}] {score}/{max_score} vulnerabilities patched.\n" +
                "\n".join([f"[{result.vulnerability_id}] Score: {result.score}/{result.n_total}" for result in results])
            )

            diff_str = ctx.agent_output_path.read_text() if ctx.agent_output_path.exists() else "No agent output"
            grader_log += f"\nAgent output:\n{diff_str}"
            for vulnerability in ctx.audit.vulnerabilities:
                status_if_successfully_patched = "fail" if vulnerability.test_passes_if_vulnerable else "pass"
                grader_log += f"\n[{vulnerability.id}] test should {status_if_successfully_patched} if the agent patches the vulnerability."

            grade = EVMbenchGrade(
                score=score,
                grader_log=grader_log,
                evmbench_result=EVMbenchResult(
                    audit_id=ctx.audit.id,
                    score=score,
                    max_score=max_score,
                    details={"test_results": results, "vulnerability_results": vulnerability_results},
                ),
            )

        except Exception as e:
            raise RolloutSystemError(f"Error during grading: {e}")

        return grade
