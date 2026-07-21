# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Module nox file for automating tasks"""

import os
import shutil
import glob
import sys
from datetime import datetime
from pathlib import Path

import nox

_LICENSE_HEADER = """# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""

PROJECT = "rad_cal"
PY_VERSIONS = ["3.11", "3.12", "3.13", "3.14"]
WIN32 = sys.platform == "win32"
PLATFORM = "win" if WIN32 else "linux"


@nox.session()
def fix_format(session: nox.Session):
    """Reformat code base with ruff"""
    session.install("ruff")
    session.run("ruff", "check", "--select", "I", "--fix-only")
    session.run("ruff", "format")


@nox.session()
def check_format(session: nox.Session):
    """Check proper formatting with ruff. Check presence of license header"""
    session.install("ruff")
    session.run("ruff", "format", "--check")
    session.run("ruff", "check")

    def wrong_license_header(file: str) -> bool:
        with open(file, "r", encoding="utf-8") as ifile:
            header = ifile.readline() + ifile.readline() + ifile.readline()
            return header != _LICENSE_HEADER

    source_files = glob.glob(f"src/{PROJECT}/**/*.py", recursive=True)
    no_licensed_files = list(filter(wrong_license_header, source_files))

    if len(no_licensed_files) > 0:
        for file in no_licensed_files:
            session.warn(f"{file} has no license header")
        session.error()


@nox.session()
def pylint(session: nox.Session):
    """Analysis of code-base quality with pylint"""
    session.install("pylint")
    session.run("python", "-m", "pylint", f"src/{PROJECT}")


def pytest_executor(session: nox.Session, project: str) -> None:
    """Executor of pytest from nox session.
    Parameters
    ----------
    session : nox.Session
        nox session
    project : str
        project name, with "-" as separator for namespace sub-packages
    """
    Path("_build").mkdir(exist_ok=True)
    project = project.replace("-", "_")
    session.install("-e", ".[test]", silent=True)
    # Run pytest with coverage and JUnit XML output
    session.run(
        "python",
        "-m",
        "pytest",
        f"--junitxml=_build/pytest-report-{nox_common.PLATFORM}-py{session.python}.xml",
        f"--cov-report=xml:_build/pytest-coverage-{nox_common.PLATFORM}-py{session.python}.xml",
    )


@nox.session(python=nox_common.PY_VERSIONS)
def pytest(session: nox.Session):
    """Module testing with pytest"""
    cwd = Path.cwd()
    pytest_executor(session, project=cwd.name)


@nox.session()
def build_sdist(session: nox.Session):
    """Build source distribution package"""
    session.install("build")
    session.run("python", "-m", "build", "--sdist", silent=True)


@nox.session()
def build_wheel(session: nox.Session):
    """Build wheel distribution package"""
    session.install("build")
    session.run("python", "-m", "build", "--wheel", silent=True)


@nox.session()
def build_doc(session: nox.Session):
    """Building documentation"""

    if Path("site").exists():
        shutil.rmtree("site")

    tag = os.getenv("CI_COMMIT_TAG", "dev")
    sha = os.getenv("CI_COMMIT_SHORT_SHA")
    date = datetime.now().strftime("%Y-%m-%d")

    if sha is None:
        try:
            sha = session.run("git", "rev-parse", "--short", "HEAD", external=True, silent=True).strip()
        except Exception:
            sha = ""

    doc_name = f"{date}-{tag}-{sha}-html-doc"

    session.log("Adding build info to documentation section")
    build_info_file = Path("docs/about/build.template.md")
    build_info = build_info_file.read_text()
    build_info = build_info.replace("__SHA__", sha).replace("__TAG__", tag).replace("__DATE__", date)
    build_info_file.parent.joinpath("build.md").write_text(build_info)
    build_info_file.unlink()

    session.log(f"Current dir: {Path.cwd()}")
    session.log(f"Building documentation: {doc_name}")

    session.install(".[doc]")
    session.run("pip", "list")
    session.run("zensical", "build", "-f", str(Path.cwd() / "zensical.toml"))

    if os.getenv("CI") == "true":
        session.log("compressing documentation")
        shutil.make_archive(f"documentation-{doc_name}", "zip", root_dir=".", base_dir="site")
