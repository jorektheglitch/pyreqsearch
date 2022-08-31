import asyncio  # noqa  # useless import for self-testing purpose
import ast
from importlib.util import find_spec
from queue import Queue
from typing import Any, Dict, List, Optional, Tuple, Union


ImportSpec = Union[Tuple[str, Optional[str]], Tuple[Optional[str], str]]


class ImportsFinder(ast.NodeVisitor):

    imports: List[ImportSpec]
    direct_imports: List[ImportSpec]
    conditional_imports: List[ImportSpec]
    functions_imports: List[ImportSpec]

    def __init__(self, package: Optional[str] = None) -> None:
        self.package = package
        self.imports = []
        self.direct_imports = []
        self.conditional_imports = []
        self.functions_imports = []
        self.in_conditional: List[None] = []
        self.in_function: List[None] = []
        super().__init__()

    def search(self, tree: ast.AST):
        self.visit(tree)

    def visit_Import(self, node: ast.Import) -> Any:
        for source in node.names:
            info = (source.name, None)
            self.imports.append(info)
            if self.in_conditional:
                self.conditional_imports.append(info)
            if self.in_function:
                self.functions_imports.append(info)
            if not (self.in_conditional or self.in_function):
                self.direct_imports.append(info)
        return super().generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        for source in node.names:
            module = "." * node.level
            if node.module:
                module += node.module
            info = (module, source.name)
            self.imports.append(info)
            if self.in_conditional:
                self.conditional_imports.append(info)
            if self.in_function:
                self.functions_imports.append(info)
            if not (self.in_conditional or self.in_function):
                self.direct_imports.append(info)
        return super().generic_visit(node)

    def visit_If(self, node: ast.If) -> Any:
        self.in_conditional.append(None)
        result = super().generic_visit(node)
        self.in_conditional.pop()
        return result

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.in_function.append(None)
        result = super().generic_visit(node)
        self.in_function.pop()
        return result

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.in_function.append(None)
        result = super().generic_visit(node)
        self.in_function.pop()
        return result


def find_imports(pyfile: str, package: Optional[str] = None):
    if pyfile.endswith(".pyd"):
        print("compiled extension", pyfile)
        # compiled extension
        return []
    with open(pyfile) as f:
        source = f.read()
    file_ast = ast.parse(source)
    finder = ImportsFinder(package)
    finder.search(file_ast)
    # print(finder.imports)
    # print(finder.direct_imports)
    # print(finder.conditional_imports)
    # print(finder.functions_imports)
    return finder.direct_imports


def requirements_info(pyfile):
    visited = set()
    modules: Dict[str, List[str]] = {}
    queue = Queue()
    queue.put((("__main__", None), pyfile))
    while not queue.empty():
        (dependent, dependent_package), path = queue.get()
        if path in (None, "built-in"):
            continue
        if path in visited:
            continue
        else:
            visited.add(path)
        # print(f"Dependencies for {dependent} module from {path or 'internals'}")
        imports = find_imports(path, dependent_package)
        for source, name in imports:
            # print(f"  {source} ({name or source} for {dependent})")
            if source == ".":
                module = "." + name
                package = dependent_package
            elif source.startswith("."):
                module = source
                package = dependent_package
            elif "." in source:
                *parent_path, module = source.split(".")
                package = ".".join(parent_path)
            else:
                module = source
                package = None
            try:
                spec = find_spec(module, package)
            except ModuleNotFoundError:
                continue
            if spec:
                qualname = spec.name
                dependencies = modules.setdefault(dependent, [])
                if qualname not in dependencies:
                    dependencies.append(qualname)
                module_path = spec.origin or "built-in"
                if source.startswith("."):
                    queue.put(((qualname, dependent), module_path))
                else:
                    queue.put(((qualname, qualname), module_path))
    return modules


if __name__ == "__main__":
    reqs = requirements_info(__file__)
    print()
