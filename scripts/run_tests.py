#!/bin/sh
"." "`dirname $0`/envsetup.sh"; "exec" "$PY3" "$0" "$@"
#
# Copyright (C) 2018 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#
# This test script to be used by the build server.
# It is supposed to be executed from trusty root directory
# and expects the following environment variables:
#
"""Run tests for a project."""

import argparse
import subprocess
import sys
import time

import trusty_build_config


class TestResults(object):
    """Stores test results.

    Attributes:
        project: Name of project that tests were run on.
        passed: True if all tests passed, False if one or more tests failed.
        passed_count: Number of tests passed.
        failed_count: Number of tests failed.
        test_results: List of tuples storing test name an status.
    """

    def __init__(self, project):
        """Inits TestResults with project name and empty test results."""
        self.project = project
        self.passed = True
        self.passed_count = 0
        self.failed_count = 0
        self.test_results = []

    def add_result(self, test, passed):
        """Add a test result."""
        self.test_results.append((test, passed))
        if passed:
            self.passed_count += 1
        else:
            self.passed = False
            self.failed_count += 1

    def print_results(self, print_failed_only=False):
        """Print test results."""
        if print_failed_only:
            if self.passed:
                return
            sys.stdout.flush()
            out = sys.stderr
        else:
            out = sys.stdout
        test_count = self.passed_count + self.failed_count
        out.write("\n"
                  "Ran {} tests for project {}.\n".format(
                      test_count, self.project))
        if test_count:
            for test, passed in self.test_results:
                if passed:
                    if not print_failed_only:
                        out.write("[ {:>8} ] {}\n".format("OK", test))
                else:
                    out.write("[ {:^8} ] {}\n".format("FAILED", test))
            out.write("[==========] {} tests ran for project {}.\n".format(
                test_count, self.project))
            if self.passed_count and not print_failed_only:
                out.write("[  PASSED  ] {} tests.\n".format(self.passed_count))
            if self.failed_count:
                out.write("[  FAILED  ] {} tests.\n".format(self.failed_count))


def test_should_run(testname, test_filter):
    """Check if test should run.

    Args:
        testname: Name of test to check.
        test_filter: Regex list that limits the tests to run.

    Returns:
        True if test_filter list is empty or None, True if testname matches any
        regex in test_filter, False otherwise.
    """
    if not test_filter:
        return True
    for r in test_filter:
        if r.search(testname):
            return True
    return False


def run_tests(build_config, root, project, run_disabled_tests=False,
              test_filter=None, verbose=False, debug_on_error=False, run_groups_individually=False):
    """Run tests for a project.

    Args:
        build_config: TrustyBuildConfig object.
        root: Trusty build root output directory.
        project: Project name.
        run_disabled_tests: Also run disabled tests from config file.
        test_filter: Optional list that limits the tests to run.
        verbose: Enable debug output.
        debug_on_error: Wait for debugger connection on errors.

    Returns:
        TestResults object listing overall and detailed test results.
    """
    project_config = build_config.get_project(project=project)

    test_results = TestResults(project)
    test_failed = []
    test_passed = []

    def run_test_get_option_string(test):
        if isinstance(test, trusty_build_config.TrustyPortTest):
            return ["--boot-test"] + test.command
        if isinstance(test, trusty_build_config.TrustyHostTest):
            return ["--shell-command"] + test.command
        if isinstance(test, trusty_build_config.TrustyTest):
            return ["--shell-command"] + test.command


    def run_test_cmd(run_test_option, name):
        project_root = root + "/build-" + project + "/"

        cmd = (["nice", project_root + run_test_option
               + ("--verbose" if verbose else " ")
               + ("--debug-on-error" if debug_on_error else " ")])
        print()
        print("Running", name, "on", project)
        print("Command line:", " ".join([s.replace(" ", "\\ ") for s in cmd]))
        sys.stdout.flush()
        test_start_time = time.time()
        status = subprocess.call(cmd)
        test_run_time = time.time() - test_start_time
        print("{:s} returned {:d} after {:.3f} seconds".format(
            name, status, test_run_time))
        test_results.add_result(name, status == 0)
        (test_failed if status else test_passed).append(name)
        return status, test_run_time

    def run_test_list(test_group):
        name_list = []
        multi_test_option_strng = ""
        for test in test_group.test_list:
            if not test.enabled and not run_disabled_tests:
                continue
            if not test_should_run(test.name, test_filter):
                continue
            name = test.name
            multi_test_option_strng.join(run_test_cmd(run_test_get_option_string(test), name))

        return multi_test_option_strng

    def run_test(rtest):
        if not rtest.enabled and not run_disabled_tests:
            return
        if not test_should_run(rtest.name, test_filter):
            return
        name = rtest.name

        run_test_option = "".join(run_test_get_option_string(rtest))

        return run_test_cmd(run_test_option, name)

    for item in project_config.tests:
        if type(item) == type([]):
            test_group = item
            if run_groups_individually:
                for test in test_group.test_list:
                    run_test(test)
            else:
                run_test_list(test_group)
        else:
            test = item
            run_test(test)

    return test_results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, required=True,
                        help="Root of intermediate build directory.")
    parser.add_argument("--project", type=str, required=True,
                        help="Project to test.")
    args = parser.parse_args()

    build_config = trusty_build_config.TrustyBuildConfig()
    test_results = run_tests(build_config, args.root, args.project)
    test_results.print_results()
    if not test_results.passed:
        exit(1)


if __name__ == "__main__":
    main()
