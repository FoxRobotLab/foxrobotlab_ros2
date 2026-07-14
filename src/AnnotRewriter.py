import os
from pathlib import Path


def populate_mapping_ranges(mapping_dict, region_name, range_list):
  """
  Helper function to unpack start/end boundaries and assign them
  to the specific region in the mapping dictionary.
  """
  for start, end in range_list:
    for cell in range(start, end + 1):
      mapping_dict[cell] = region_name


def build_region_mapping():
  """
  Creates a ictionary mapping every individual cell number
  directly to its corresponding region label.
  """
  mapping = {}

  populate_mapping_ranges(mapping, "Green_Floor_Hallway", [(20, 65), (142, 165), (221, 229)])
  populate_mapping_ranges(mapping, "Brick_Hallway", [(230, 270), (166, 175)])
  populate_mapping_ranges(mapping, "West_Faculty_Offices", [(176, 220)])
  populate_mapping_ranges(mapping, "East_Faculty_Offices", [(0, 19)])
  populate_mapping_ranges(mapping, "Smail", [(66, 141)])

  return mapping


def process_single_line(line, region_mapping):
  """
  Takes a single annotation line, finds the cell number, and swaps
  it for the region string. Returns the updated line.
  """
  parts = line.strip().split()

  if len(parts) >= 6:
    try:
      cell = int(parts[3])
      parts[3] = region_mapping.get(cell, "Unknown_Region")
    except ValueError:
      pass

    return " ".join(parts) + "\n"

  return line


def process_single_file(input_filepath, output_filepath, region_mapping):
  """
  Handles file I/O for a single annotation text file.
  """
  with open(input_filepath, 'r') as infile, open(output_filepath, 'w') as outfile:
    for line in infile:
      new_line = process_single_line(line, region_mapping)
      outfile.write(new_line)


if __name__ == "__main__":

  base_path = Path("/home/macalester/PycharmProjects/catkin_ws/src/match_seeker/res/classifier2022Data/DATA/")
  annot_data_dir = base_path / "AnnotData"
  region_data_dir = base_path / "RegionAnnotData"

  # region_data_dir.mkdir(parents=True, exist_ok=True)
  #
  # region_mapping = build_region_mapping()
  #
  # file_count = 0
  # for filepath in annot_data_dir.glob("*.txt"):
  #   output_filepath = region_data_dir / filepath.name
  #   process_single_file(filepath, output_filepath, region_mapping)
  #   file_count += 1
  #
  # print(f"Successfully processed {file_count} files.")
  # print(f"Region annotations saved to: {region_data_dir}")

  if not region_data_dir.exists():
    print(f"[ERROR] Directory not found: {region_data_dir}")
  else:
    file_count = 0

    for filepath in region_data_dir.glob("*.txt"):

      with open(filepath, 'r') as infile:
        lines = infile.readlines()

      with open(filepath, 'w') as outfile:
        for line in lines:
          parts = line.strip().split()

          if len(parts) >= 5:
            region_str = parts[3]

            if region_str == "Green_Floor_Hallway":
              parts[3] = "0"
            elif region_str == "Brick_Hallway":
              parts[3] = "1"
            elif region_str == "West_Faculty_Offices":
              parts[3] = "2"
            elif region_str == "East_Faculty_Offices":
              parts[3] = "3"
            elif region_str == "Smail":
              parts[3] = "4"

            new_line = " ".join(parts) + "\n"
            outfile.write(new_line)
          else:
            outfile.write(line)

      file_count += 1

    print(f"Successfully processed and updated {file_count} files in place.")



