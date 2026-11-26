"""Creator of a new mission: its directory and the three files it starts with.

Usage: python3 <plugin root>/tools/define_mission.py --at SCOPE --title TITLE  (goal text on stdin)

Run from the workspace root. The mission is created at <scope>/mission_<slug>/, directly in
the scope given as --at with no container between them, and named by its slug alone behind
the mission_ prefix, with no number.

Scope: --at names the directory holding the core of the mission's work, relative to the
working directory, "." (or "./") naming the root. It is required, with no default. It is
normalized lexically, with no filesystem lookup: "." components, duplicate and trailing
slashes, and a leading "./" are collapsed, and a ".." component cancels the component
before it. A scope that is empty, absolute, or that climbs above the working directory with
".." once normalized is refused. So is a normalized scope holding whitespace or any
character a shell reads as syntax in an unquoted word, since every later command line carries
the mission path unquoted as one word: any of " ' ` $ \\ ( ) [ ] { } * ? ; & | < > !
anywhere, or ~, #, or = as its first character; every other character is accepted. The
check is made here, at definition, alone: a mission already standing under such a scope is
read by no check of this tool. The normalized scope must then be an existing directory of
the working tree, tested on the filesystem (the tool touches no git); a scope missing there,
or naming something that is not a directory, is refused. Every scope refusal names the scope
as given, and nothing is written. The tool never creates the scope, nor any directory but the
mission's own.

The title comes as --title and is folded to one line (whitespace runs and newlines
collapsed to one space, ends trimmed); it is refused only when empty after that fold, and
is otherwise written into the requirements.md heading with its words, case, and
punctuation unchanged. The goal text travels on standard input, never as an argument: the
tool reads sys.stdin.buffer to end of file exactly once and decodes it as UTF-8 itself,
refusing a terminal, closed, or non-UTF-8 stdin, and refusing text that is empty or only
whitespace. The goal is written under `## Goal` exactly as received with only its leading
and trailing whitespace trimmed.

Slug: the first five whitespace-separated words of the folded title that survive
cleaning, joined by hyphens. Each word is folded to its ASCII base with NFKD and its
combining marks dropped, lowercased, stripped of apostrophes, and every remaining run of
characters outside [a-z0-9] turned into one hyphen with edge hyphens trimmed, so a
hyphenated compound stays one word; a word that cleans down to nothing is skipped and the
five are filled from the words that follow. A title no word of which survives is refused.

Conflict: the mission directory <scope>/mission_<slug> is created exclusively, so anything
already at that path (a directory, a file, or a symlink) refuses the call before anything is
written. That is the only conflict check: the same slug may stand in two scopes.

Files, written in this order into the new directory, each through a temporary file in the
same directory renamed over the target:
  - open_questions.xml, the empty open-question document: <open-questions/> and a newline
  - requirements.md, headed "# <title>", the goal under "## Goal", then empty
    "## Relevant starting state", "## Decisions", and "## Out of Scope" sections
  - TASKS_TODO.md, headed "# TASKS TODO"

Output and error contract:
  - on success exactly two unlabeled lines on stdout: the commit subject
    "Mission-definition: <path>", then the mission path "<path>" itself, where <path> is the
    canonical repo-relative path of the mission directory with its trailing slash,
    "mission_<slug>/" for the root and "<scope>/mission_<slug>/" otherwise, the scope in its
    normalized form however it was typed
  - every failure is exactly one line "Error: <reason>" on stderr with exit status 1 and
    empty stdout; a malformed invocation (no --at or no --title included) gets argparse's
    own usage message and exit status 2; no traceback ever reaches the caller
  - a failure after the call created the mission directory removes what the call created, in
    reverse creation order, with a plain unlink for each file and a non-recursive rmdir for
    the mission directory, so nothing the call did not create is ever removed; a removal that
    fails stops the cleanup, and the one Error line then gives the original reason followed
    by the paths left in place

Standard library only; runs on Python 3.9 and later.
"""

import argparse
import os
import posixpath
import re
import sys
import tempfile
import unicodedata

DIRECTORY_PREFIX = "mission_"
SUBJECT_MARKER = "Mission-definition"
ROOT_SCOPE = "."
SLUG_WORDS = 5
APOSTROPHES = ("'", "‘", "’", "ʼ")
NOT_SLUG_CHARACTERS = re.compile(r"[^a-z0-9]+")
SHELL_SYNTAX_CHARACTERS = frozenset("\"'`$\\()[]{}*?;&|<>!")
SHELL_SYNTAX_OPENINGS = frozenset("~#=")

OPEN_QUESTIONS_NAME = "open_questions.xml"
OPEN_QUESTIONS_TEMPLATE = "<open-questions/>\n"

REQUIREMENTS_NAME = "requirements.md"
REQUIREMENTS_TEMPLATE = """\
# {title}

## Goal

{goal}

## Relevant starting state

## Decisions

## Out of Scope

"""

TASKS_TODO_NAME = "TASKS_TODO.md"
TASKS_TODO_TEMPLATE = """\
# TASKS TODO

"""


class ToolError(Exception):
    """A failure the caller is told about as one `Error: <reason>` line with exit status 1."""


# --- inputs ---------------------------------------------------------------------------


def fold(text):
    """The text as one line: whitespace runs and newlines collapsed to a space, ends trimmed."""
    return " ".join((text or "").split())


def read_body(what):
    """The one free-text body a call carries on standard input, read to end of file once
    and decoded as UTF-8; a terminal, closed, or non-UTF-8 stdin is a ToolError, so a call
    that forgot to pipe its body fails instead of blocking."""
    stream = sys.stdin
    if stream is None or getattr(stream, "closed", False):
        raise ToolError(f"{what} must be supplied on standard input, which is closed")
    if stream.isatty():
        raise ToolError(f"{what} must be piped on standard input (as a quoted heredoc or a redirected file), not typed at a terminal")
    data = stream.buffer.read()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ToolError(f"{what} on standard input is not UTF-8 text")


def read_title(value):
    title = fold(value)
    if not title:
        raise ToolError("the title given as --title is empty")
    return title


def read_goal():
    goal = read_body("the goal text").strip()
    if not goal:
        raise ToolError("the goal text on standard input is empty")
    return goal


def normalize_scope(value):
    """The scope given as --at in its normalized form, "." for the root: collapsed lexically,
    with no filesystem lookup; an empty, absolute, or climbing scope is a ToolError."""
    if value == "":
        raise ToolError("the scope given as --at is empty")
    if posixpath.isabs(value):
        raise ToolError(
            f"the scope {value} given as --at is an absolute path; name a directory relative to the workspace root"
        )
    scope = posixpath.normpath(value)
    if scope == os.pardir or scope.startswith(os.pardir + "/"):
        raise ToolError(f"the scope {value} given as --at climbs out of the workspace root with ..")
    return scope


def describe_character(character):
    """A refused scope character as the Error line names it."""
    if character.isspace():
        return "whitespace"
    return repr(character)


def check_scope_characters(scope, value):
    """Refuse a normalized scope holding whitespace or a character a shell reads as syntax in
    an unquoted word (~, #, and = only as its first character), naming the scope as given."""
    for character in scope:
        if character.isspace() or character in SHELL_SYNTAX_CHARACTERS:
            raise ToolError(
                f"the scope {value} given as --at holds {describe_character(character)}, which a shell reads "
                "as syntax in an unquoted mission path; nothing was written"
            )
    if scope[:1] in SHELL_SYNTAX_OPENINGS:
        raise ToolError(
            f"the scope {value} given as --at opens with {describe_character(scope[0])}, which a shell reads "
            "as syntax in an unquoted mission path; nothing was written"
        )


def check_scope(scope, value):
    """Refuse a normalized scope that is not an existing directory of the working tree,
    naming the scope as given."""
    if not os.path.isdir(scope):
        if os.path.lexists(scope):
            raise ToolError(f"the scope {value} given as --at is not a directory; nothing was written")
        raise ToolError(f"the scope {value} given as --at does not exist in the working tree; nothing was written")


# --- naming ---------------------------------------------------------------------------


def slug_word(word):
    """One title word as a slug word: ASCII-folded, lowercased, apostrophes deleted, every
    other run outside [a-z0-9] one hyphen, edge hyphens trimmed; empty when nothing survives."""
    decomposed = unicodedata.normalize("NFKD", word)
    base = "".join(character for character in decomposed if not unicodedata.combining(character))
    lowered = base.lower()
    for apostrophe in APOSTROPHES:
        lowered = lowered.replace(apostrophe, "")
    return NOT_SLUG_CHARACTERS.sub("-", lowered).strip("-")


def derive_slug(title):
    words = []
    for word in title.split():
        cleaned = slug_word(word)
        if cleaned:
            words.append(cleaned)
            if len(words) == SLUG_WORDS:
                break
    if not words:
        raise ToolError(f"no word of the title {title!r} leaves any letter or digit to build the mission slug from")
    return "-".join(words)


def mission_path(scope, slug):
    """The repo-relative path of the mission directory in the scope, with no trailing slash."""
    name = DIRECTORY_PREFIX + slug
    if scope == ROOT_SCOPE:
        return name
    return posixpath.join(scope, name)


def path_label(path):
    """A directory path in its printed form: with its trailing slash."""
    return path.rstrip("/") + "/"


# --- writing --------------------------------------------------------------------------


def write_new_file(path, text):
    """Write text as UTF-8 through a temporary file in the same directory renamed over the
    target; the file takes the default mode."""
    directory = os.path.dirname(path) or os.curdir
    name = os.path.basename(path)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{name}.", suffix=".tmp", dir=directory)
    try:
        umask = os.umask(0)
        os.umask(umask)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(text.encode("utf-8"))
        os.chmod(temporary, 0o666 & ~umask)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def mission_files(title, goal):
    """The three files of a new mission, in creation order, as (name, text) pairs."""
    return [
        (OPEN_QUESTIONS_NAME, OPEN_QUESTIONS_TEMPLATE),
        (REQUIREMENTS_NAME, REQUIREMENTS_TEMPLATE.format(title=title, goal=goal)),
        (TASKS_TODO_NAME, TASKS_TODO_TEMPLATE),
    ]


def create_directory(directory):
    """Create the mission directory exclusively; anything already at its path is a ToolError."""
    try:
        os.mkdir(directory)
    except FileExistsError:
        raise ToolError(f"{directory} already exists; nothing was written")


def remove_created(created):
    """Remove the created paths in reverse creation order, stopping at the first that cannot
    be removed; the paths left in place, in creation order."""
    remaining = list(created)
    while remaining:
        path = remaining[-1]
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                os.rmdir(path)
            else:
                os.unlink(path)
        except FileNotFoundError:
            pass
        except OSError:
            return remaining
        remaining.pop()
    return []


def create_mission(directory, files):
    """Create the mission directory exclusively and write the files into it; on any failure
    after the directory was created remove what was created and raise one ToolError carrying
    the reason."""
    create_directory(directory)
    created = [directory]
    try:
        for name, text in files:
            path = os.path.join(directory, name)
            write_new_file(path, text)
            created.append(path)
    except BaseException as error:
        left = remove_created(created)
        if not isinstance(error, Exception):
            raise
        reason = describe(error)
        if left:
            reason += "; the cleanup could not remove " + ", ".join(left)
        raise ToolError(reason) from error


# --- command --------------------------------------------------------------------------


def define(args):
    title = read_title(args.title)
    slug = derive_slug(title)
    scope = normalize_scope(args.at)
    check_scope_characters(scope, args.at)
    goal = read_goal()
    check_scope(scope, args.at)
    directory = mission_path(scope, slug)
    create_mission(directory, mission_files(title, goal))
    path = path_label(directory)
    sys.stdout.write(f"{SUBJECT_MARKER}: {path}\n{path}\n")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="define_mission.py",
        description=(
            "Create a new mission directory at <scope>/mission_<slug>/, directly in the scope, with its "
            "open_questions.xml, requirements.md, and TASKS_TODO.md; the goal text is read from standard input"
        ),
    )
    parser.add_argument(
        "--at",
        required=True,
        metavar="SCOPE",
        help=(
            "the existing directory holding the core of the mission's work, relative to the workspace root, "
            "\".\" for the root; normalized lexically, and refused when absolute, climbing out with \"..\", "
            "or holding whitespace or a shell-syntax character"
        ),
    )
    parser.add_argument(
        "--title",
        required=True,
        help="the mission title, written into the requirements.md heading and the source of the slug",
    )
    parser.set_defaults(func=define)
    return parser


def describe(error):
    """The reason a failure reports, as the one Error line gives it."""
    if isinstance(error, ToolError):
        return str(error)
    if isinstance(error, OSError):
        if error.strerror and error.filename is not None:
            return f"{error.strerror}: {error.filename}"
        return str(error)
    return f"{type(error).__name__}: {error}"


def _fail(reason):
    print("Error: " + fold(reason), file=sys.stderr)
    return 1


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ToolError as error:
        return _fail(str(error))
    except OSError as error:
        if error.strerror and error.filename is not None:
            return _fail(f"{error.strerror}: {error.filename}")
        return _fail(str(error))
    except Exception as error:  # the contract: no traceback ever reaches the caller
        return _fail(f"{type(error).__name__}: {error}")


if __name__ == "__main__":
    sys.exit(main())
