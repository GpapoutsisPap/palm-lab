warning: in the working copy of '.github/workflows/ci.yml', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'pyproject.toml', LF will be replaced by CRLF the next time Git touches it
[1mdiff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml[m
[1mindex 931f294..3f17d1d 100644[m
[1m--- a/.github/workflows/ci.yml[m
[1m+++ b/.github/workflows/ci.yml[m
[36m@@ -32,4 +32,4 @@[m [mjobs:[m
         run: uv run mypy[m
 [m
       - name: Run tests[m
[31m-        run: uv run pytest[m
\ No newline at end of file[m
[32m+[m[32m        run: uv run pytest[m
[1mdiff --git a/.gitignore b/.gitignore[m
[1mindex 8c02273..d99a8b0 100644[m
[1m--- a/.gitignore[m
[1m+++ b/.gitignore[m
[36m@@ -195,9 +195,9 @@[m [mcython_debug/[m
 .abstra/[m
 [m
 # Visual Studio Code[m
[31m-#   Visual Studio Code specific template is maintained in a separate VisualStudioCode.gitignore [m
[32m+[m[32m#   Visual Studio Code specific template is maintained in a separate VisualStudioCode.gitignore[m
 #   that can be found at https://github.com/github/gitignore/blob/main/Global/VisualStudioCode.gitignore[m
[31m-#   and can be added to the global gitignore or merged into this file. However, if you prefer, [m
[32m+[m[32m#   and can be added to the global gitignore or merged into this file. However, if you prefer,[m
 #   you could uncomment the following to ignore the entire vscode folder[m
 # .vscode/[m
 # Temporary file for partial code execution[m
[36m@@ -216,4 +216,3 @@[m [m__marimo__/[m
 [m
 # Streamlit[m
 .streamlit/secrets.toml[m
[31m-[m
[1mdiff --git a/README.md b/README.md[m
[1mindex 0f35d19..6d30d27 100644[m
[1m--- a/README.md[m
[1m+++ b/README.md[m
[36m@@ -1,3 +1,3 @@[m
 # palm-lab[m
[31m-Hand gesture application for automations. [m
[32m+[m[32mHand gesture application for automations.[m
 A gesture-controlled shortcut launcher for Windows.[m
[1mdiff --git a/pyproject.toml b/pyproject.toml[m
[1mindex e6d5f28..48917f8 100644[m
[1m--- a/pyproject.toml[m
[1m+++ b/pyproject.toml[m
[36m@@ -38,4 +38,4 @@[m [mfiles = ["src", "tests"][m
 [m
 [tool.pytest.ini_options][m
 testpaths = ["tests"][m
[31m-addopts = "-v --cov=palm_lab --cov-report=term-missing"[m
\ No newline at end of file[m
[32m+[m[32maddopts = "-v --cov=palm_lab --cov-report=term-missing"[m
