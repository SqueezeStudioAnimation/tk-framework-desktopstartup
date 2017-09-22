import os
import os.path
import shutil
import subprocess

def build(source_path, build_path, install_path, targets):
    print source_path, build_path, install_path, targets

    if "install" in (targets or []):
        # De-init git submodules as this create unnecessary files
        subprocess.Popen('git submodule deinit --force .', shell=True, cwd=source_path).wait()

        if os.path.exists(install_path) and os.path.isdir(install_path):
            os.rmdir(install_path)  # Directory should be empty, let if crash if it fail.

        shutil.copytree(source_path, install_path, symlinks=True)
