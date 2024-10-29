import os
from src.settings.filepaths import CSV_DIR

def remove_pipe_from_file(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    with open(file_path, 'w') as file:
        for line in lines:
            if line.endswith('|\n'):
                line = line[:-2] + '\n'
            elif line.endswith('|'):
                line = line[:-1]
            file.write(line)


def process_csv_folder(folder_path):
    for filename in os.listdir(folder_path):
        if filename.endswith('.csv'):
            file_path = os.path.join(folder_path, filename)
            remove_pipe_from_file(file_path)
            print(f"Processed: {filename}")


if __name__ == "__main__":
    process_csv_folder(CSV_DIR)
    print("All CSV files in the folder have been processed.")