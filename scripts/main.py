import dataclasses
import datetime
import pathlib
import sys
from typing import Any, Dict, List

import markdown
from dateutil.parser import parse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger

ROOT_DIR: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR: pathlib.Path = ROOT_DIR / "src"
POSTS_DIR: pathlib.Path = ROOT_DIR / "posts"
TEMPLATES_DIR: pathlib.Path = ROOT_DIR / "templates"
HEADER_LINES: int = 5
HEADERS: Dict[(str, str)] = {
    "Title": str,
    "Template": str,
    "MetaDescription": str,
    "DatePublished": parse,
    "IsDraft": int,
}
JINJA2_ENV = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape()
)


def head_to_context(head: List[str], path: pathlib.Path) -> Dict[str, Any]:
    result = {}
    header_keys = set(HEADERS.keys())
    for line in head:
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key not in header_keys:
            logger.error(f"File {path} has invalid header field: {key}.")
            sys.exit(1)
        try:
            result[key] = HEADERS[key](value)
        except Exception as exc:  # noqa
            logger.error(f"Unable to parse {key} from {path}.")
            sys.exit(1)

    if difference := header_keys.difference(set(result.keys())):
        logger.error(f"Missing header fields {difference} in the file {path}.")
        sys.exit(1)

    return result


@dataclasses.dataclass
class RenderRecord:
    InPath: pathlib.Path
    OutPath: pathlib.Path
    Title: str
    DatePublished: datetime.datetime
    IsDraft: int

    @property
    def Url(self) -> str:  # noqa
        return f"posts/{self.OutPath.name}"


def run():
    md = markdown.Markdown()
    render_paths: List[RenderRecord] = []

    # Empty the posts directory
    [f.unlink() for f in POSTS_DIR.glob("*") if f.is_file()]

    # Parse files in the markdown directory
    for match in SRC_DIR.glob("*.md"):
        path = pathlib.Path(match)
        with open(path, "r", encoding="utf-8") as in_file:
            try:
                head = [next(in_file) for x in range(HEADER_LINES)]
            except StopIteration:
                logger.error(f"Not all header provided in {path}")
                sys.exit(1)

            context = head_to_context(head, path)
            text = in_file.read()
            context["PostMarkup"] = md.convert(text)
            if tpl := TEMPLATES_DIR.joinpath(context["Template"]).exists():
                template = JINJA2_ENV.get_template(context["Template"])
                render = template.render(**context)
            else:
                logger.error(f"Template {tpl} does not exists.")
                sys.exit(1)

            out_path = POSTS_DIR.joinpath(path.stem + ".html")
            with open(out_path, "w") as out_file:
                out_file.write(render)
                out_file.flush()
                render_paths.append(
                    RenderRecord(
                        path,
                        out_path,
                        context["Title"],
                        context["DatePublished"],
                        context["IsDraft"],
                    )
                )
                logger.info(f"Rendered {out_path}.")

    # Create the index.html in the root directory
    with open(ROOT_DIR.joinpath("index.html"), "w") as index:
        template = JINJA2_ENV.get_template("index.jinja2")
        render = template.render(
            posts=sorted(
                render_paths, key=lambda x: x.DatePublished, reverse=True
            ),
            Title="liquidscorpio - weblog",
        )
        index.write(render)
        index.flush()


if __name__ == "__main__":
    run()
