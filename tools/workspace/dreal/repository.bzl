# -*- mode: python -*-

load("@drake//tools/workspace:github.bzl", "github_archive")

# N.B. This repository is deprecated for removal on 2023-02-01.
# For details see https://github.com/RobotLocomotion/drake/pull/18156.

def dreal_repository(
        name,
        mirrors = None):
    github_archive(
        name = name,
        repository = "dreal/dreal4",
        commit = "4.21.06.2",
        sha256 = "7bbd328a25c14cff814753694b1823257bb7cff7f84a7b705b9f111624d5b2e4",  # noqa
        mirrors = mirrors,
        patches = [
            ":patches/ibex_2.8.6.patch",
            ":patches/platforms.patch",
            ":patches/pull283.patch",
            ":patches/warnings.patch",
            ":patches/pull18545.patch",
        ],
        repo_mapping = {
            "@nlopt": "@nlopt_internal",
        },
    )
