import subprocess

from src.settings.filepaths import SRC_DIR, ROOT_DIR


def run_interface():
    # Use the subcommand to run the GUI:

    folder_name = "sql-visualizer"
    command = f"cd {str(ROOT_DIR / folder_name)} && npm run dev"

    subprocess.run(command, shell=True)


if __name__ == "__main__":
    print(SRC_DIR)
    print(ROOT_DIR)
    run_interface()