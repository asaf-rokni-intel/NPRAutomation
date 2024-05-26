import os
import csv
from queue import Empty
import re
import sys
from warnings import catch_warnings

# Getting inputs from the user:
def get_automatic_paths():
    # Determine the base path depending on whether the script is frozen (packaged as an exe)
    base_path = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)
    
    # Move up two directories for tp_path
    tp_path = os.path.abspath(os.path.join(base_path, "..", ".."))
    
    # Inputs and Outputs directories are assumed to be in the same directory as the exe
    input_files_path = os.path.join(base_path, "Inputs")
    output_path = os.path.join(base_path, "Outputs")
    
    return tp_path, input_files_path, output_path

def paths_exist(tp_path, input_files_path, output_path):
    # Check if the automatically determined paths exist
    return os.path.exists(tp_path) and os.path.exists(input_files_path) and os.path.exists(output_path)

def GetTpPath():
    while True:
        tp_path = input("Please provide a TP path: ")

        if '/' in tp_path:  # Unix format
            print("Error: The provided path is in Unix format. Please use Windows format (backslashes).")
        elif '\\' in tp_path:  # Windows format
            return tp_path
        else:
            print("Error: The provided path format is not recognized.")

def VerifyRuleDirectory(directory_path):
    directories = [d for d in os.listdir(directory_path) if os.path.isdir(os.path.join(directory_path, d))]
    if len(directories) != 1:
        return False

    rules_directory = os.path.join(directory_path, directories[0])
    rule_files = [file for file in os.listdir(rules_directory) if file.endswith(".rule")]
    non_rule_files = [file for file in os.listdir(rules_directory) if not file.endswith(".rule")]
    return len(non_rule_files) == 0

def VerifyConfFile(directory_path):
    conf_files = [file for file in os.listdir(directory_path) if file.endswith(".conf")]
    return len(conf_files) == 1 and os.path.isfile(os.path.join(directory_path, conf_files[0]))

def VerifyCsvFile(directory_path):
    csv_files = [file for file in os.listdir(directory_path) if file.endswith(".csv")]
    return len(csv_files) == 1 and os.path.isfile(os.path.join(directory_path, csv_files[0]))

def VerifyJsonFile(directory_path):
    json_files = [file for file in os.listdir(directory_path) if file.endswith(".json")]
    return len(json_files) <= 1 and (len(json_files) == 0 or os.path.isfile(os.path.join(directory_path, json_files[0])))

def GetInputFilesPath():
    while True:
        inputFilesPath = input("Please provide the Input Files Path: ")

        if '/' in inputFilesPath:  # Unix format
            print("Error: The provided path is in Unix format. Please use Windows format (backslashes).")
        elif '\\' in inputFilesPath:  # Windows format
            if os.path.isdir(inputFilesPath):
                if VerifyConfFile(inputFilesPath) and VerifyCsvFile(inputFilesPath) and VerifyJsonFile(inputFilesPath) and VerifyRuleDirectory(inputFilesPath):
                    return inputFilesPath
                else:
                    if not VerifyConfFile(inputFilesPath):
                        print("Error: The input files directory should contain one .conf file.")
                    if not VerifyCsvFile(inputFilesPath):
                        print("Error: The input files directory should contain one .csv file.")
                    if not VerifyJsonFile(inputFilesPath):
                        print("Warning: The input files directory may contain at most one .json file.")
                    if not VerifyRuleDirectory(inputFilesPath):
                        print("Error: The input files directory should contain one directory with only .rule files. Please check your rules directory.")
            else:
                print("Error: The provided path is not a valid directory.")

def VerifyEmptyDirectory(directory_path):
    return not os.listdir(directory_path)

def GetOutputPath():
    while True:
        output_path = input("Please provide an empty Output Path: ")

        if '/' in output_path:
            print("Error: The provided path is in Unix format. Please use Windows format (backslashes).")
        else:
            #Create the output directory if it doesn't exist
            if not os.path.exists(output_path):
                proceed = input("The output directory does no exist, do you want to create one? (Y/N): ")
                if proceed.lower() == "y":
                    os.makedirs(output_path)
                    return output_path

            elif os.path.isdir(output_path):
                if VerifyEmptyDirectory(output_path):
                    return output_path
                else:
                    print("Warning: The output directory is not empty.")
                    proceed = input("Do you want to proceed anyway? (Y/N): ")
                    if proceed.lower() == "y":
                        return output_path
            else:
                print("Error: The provided path is not a valid directory.")

def GetConfFilePath(input_files_path):
    conf_file_path = None
    for filename in os.listdir(input_files_path):
        if filename.endswith(".conf"):
            conf_file_path = os.path.join(input_files_path, filename)
            break

    return conf_file_path

def CheckConfFile(tp_path, conf_path, json_file_path = None):
    try:
        required_parameters = {"LocationCodes", "Encode", "SearchOption", "CheckOption"}
        allowed_parameters = required_parameters | {"ExcludedPlistsRegexes", "OtherOptions", "BaseNumberLength", "DontRunChk", "IgnorePatternsWithRegexes", "OutputsPathInTP"}
        errors = []

        # Get the path to the 'BLLEncoder.txt' file
        if getattr(sys, 'frozen', False):
            # Running as a PyInstaller executable
            base_path = sys._MEIPASS
        else:
            # Running as a regular script
            base_path = os.path.dirname(__file__)

        file_path = os.path.join(base_path, "BLLEncoder.txt")

        # Read the allowed Encode values from BLLEncoder file
        allowed_encode_values = set()
        with open(file_path, 'r') as encoder_file:
            for line in encoder_file:
                line = line.strip()
                if line:
                    parts = line.split(":")
                    allowed_encode_values.add(parts[0])

        with open(conf_path, 'r') as conf_file:
            lines = conf_file.readlines()

        ignore_patterns_with_regexes = set()
        search_option_value = None
        check_option_value = None
        dont_run_chk = None
        other_options_values = set()
        provided_parameters = set()

        for line_number, line in enumerate(lines, start=1):
            line = line.strip()
            if not line:
                continue

            parts = line.split(":")
            if len(parts) != 2:
                errors.append(f"Error in line {line_number}: Invalid format. Expected 'X:Y' format for all lines.")
                continue

            parameter, values = parts
            parameter = parameter.strip()
            values = values.replace(",", " ").split()

            if parameter not in allowed_parameters:
                errors.append(f"Error in line {line_number}: Unknown parameter '{parameter}'.")
                print(f"Allowed parameters in the configuration file are: {', '.join(allowed_parameters)}.")
                continue

            provided_parameters.add(parameter)

            if parameter == "Encode":
                for value in values:
                    if value not in allowed_encode_values:
                        errors.append(f"Error in line {line_number}: Invalid Encode value '{value}'. Allowed values are: {', '.join(allowed_encode_values)}.")

            if parameter == "LocationCodes":
                for value in values:
                    if len(value) != 4 or not value.isdigit():
                        errors.append(f"Error in line {line_number}: Invalid LocationCode '{value}'. LocationCodes should be comma-separated numbers with 4 digits each.")

            if parameter == "SearchOption":
                if len(values) != 1:
                    errors.append(f"Error in line {line_number}: SearchOption should have exactly 1 value.")
                else:
                    search_option_value = values[0]

            if parameter == "CheckOption":
                if len(values) != 1:
                    errors.append(f"Error in line {line_number}: CheckOption should have exactly 1 value.")
                else:
                    check_option_value = values[0]
            
            if parameter == "DontRunChk":
                if len(values) != 1:
                    errors.append(f"Error in line {line_number}: DontRunChk should have exactly 1 value.")
                elif values[0] != "True" and values[0] != "False":
                    errors.append(f"Error in line {line_number}: DontRunChk can be either True or False only.")
                elif values[0] == "True":
                    dont_run_chk = True
                else:
                    dont_run_chk = False

            if parameter == "OtherOptions":
                for value in values:
                    if value is search_option_value or value is check_option_value:
                        errors.append(f"OtherOptions' value {value} should be different from {search_option_value} and {check_option_value}")
                    else:
                        other_options_values.add(value)
                       
            if parameter == "IgnorePatternsWithRegexes":
                for value in values:
                    if re.compile(value):
                        ignore_patterns_with_regexes.add(value)
                    else:
                        errors.append(f"IgnorePatternsWithRegexes' value {value} is not a legitimate regex.\nPlease provide valid regexes only.")
                        
            if parameter == "OutputsPathInTP":
                if len(values) != 1:
                    errors.append(f"Error in line {line_number}: OutputsPathInTP should have exactly 1 value.")
                    continue  # Skip further checks if the number of values is incorrect

                # Normalize the path to ensure compatibility with forward/backward slashes
                normalized_value = os.path.normpath(values[0])

                # Construct the full path by joining tp_path with the normalized OutputsPathInTP value
                outputs_in_tp = os.path.normpath(os.path.join(tp_path, normalized_value))

                # Check if the constructed path exists
                if not os.path.exists(outputs_in_tp):
                    errors.append(f"Error in line {line_number}: The path '{outputs_in_tp}' does not exist.")
                    
            # Check BaseNumberLength only if json_file_path is not None
            if json_file_path is not None and parameter == "BaseNumberLength":
                if not values[0].isdigit():
                    errors.append(f"Error in line {line_number}: BaseNumberLength parameter must be a number.")
        
        if json_file_path is not None and "BaseNumberLength" not in provided_parameters:
            errors.append("Error: Required parameter 'BaseNumberLength' is missing.")

        if search_option_value is not None and check_option_value is not None and search_option_value == check_option_value:
            errors.append("SearchOption and CheckOption values should be different.")

        missing_parameters = required_parameters - provided_parameters
        for missing_parameter in missing_parameters:
            errors.append(f"Required parameter '{missing_parameter}' is missing.")

        if errors:
            print("Configuration file errors:")
            for error in errors:
                print(error)
            sys.exit(1)

        return search_option_value, check_option_value, other_options_values, dont_run_chk, ignore_patterns_with_regexes, outputs_in_tp
    except Exception as error:
        print("An exception occurred in CheckConf:", error)
    
def TestCsvDataVerification(input_files_path, search_option_value, check_option_value, other_options_values):
    csv_files = [file for file in os.listdir(input_files_path) if file.endswith(".csv")]

    # Making sure only one csv file exists.
    if len(csv_files) != 1:
        print("Error: There should be exactly one CSV file in the input files directory.")
    else:
        csv_path = os.path.join(input_files_path, csv_files[0])
        errors = VerifyCsvData(csv_path, search_option_value, check_option_value, other_options_values)

        if errors:
            print(f"The following errors were found in the {os.path.basename(csv_path)} file:")
            for error in errors:
                print(error)
            sys.exit(1)

        else:
            print("CSV data verified successfully.")
    return csv_path

def VerifyCsvData(csv_path, search_option_value, check_option_value, other_options_values):
    with open(csv_path, 'r', newline='') as csvfile:
        errors = []
        reader = csv.reader(csvfile)

        header_row = next(reader)
        valid_options = header_row[1].split('|')

        if len(valid_options) < 2:
            errors.append("The valid_options in the CSV header should contain at least the two options for Search and Check as they appear in the configuration file.")

        if search_option_value not in valid_options or check_option_value not in valid_options:
            errors.append("Both SearchOption and CheckOption from the configurations file should be present in the CSV's header.")

        if other_options_values:
            for option in other_options_values:
                if option not in valid_options:
                    errors.append(f"All the given options in OtherOptions should appear in the CSV's' header")

        if header_row[0] != "Test Regex":
            errors.append(f"Error in the header row, column A: First cell should be 'Test Regex' but it's {header_row}")

        if header_row[2] != "Power Domain":
            errors.append(f"Error in the header row, column C: First cell should be 'Power Domain' but it's {header_row[2]}")

        if header_row[3] != "Corner":
            errors.append(f"Error in the header row, column D: First cell should be 'Corner' but it's {header_row[3]}")

        for row_number, row in enumerate(reader, start=2):
            if len(row) > 4:
                errors.append(f"Error in row {row_number}: More than 4 columns are filled.")
            
            # Validate column A: regexes.
            try:
                re.compile(row[0])
            except re.error:
                errors.append(f"Error in cell A{row_number}: Invalid regex format in Test Regex column.")

            # Validate column B: matching Search and Check options.
            if row[1] not in valid_options:
                errors.append(f"Error in cell B{row_number}: Must match one of the valid options. The valid options are in cell B1.")

            # Validate column C: Power Domain format.
            if not row[2].isupper() or row[2] == "Power Domain":
                errors.append(f"Error in cell C{row_number}: The power domain must be one word in upper case letters.")

            # Validate column D: Corner format.
            if row[3] and not re.match(r'^F[0-9]\d*$', row[3]):
                errors.append(f"Error in cell D{row_number}: The corner must be of the format 'F$' (F0, F1, F2 etc.) or remain empty")
        
        return errors
    
def FindJsonFile(input_files_path):
    files = os.listdir(input_files_path)
    for file in files:
        if file.endswith(".json"):
            return os.path.join(input_files_path, file)
    return None

def FindSupersedePath(tp_path):
    supersede_dir_path = None

    # Traverse the directory tree to find a directory that matches "Supersedes" case-insensitively
    for root, dirs, files in os.walk(tp_path):
        for dir in dirs:
            if dir.lower() == "supersedes":
                supersede_dir_path = os.path.join(root, dir)
                return supersede_dir_path
            
    # If the loop completes without finding the directory, print an error message
    if supersede_dir_path is None:
        print("Error: 'Supersedes' directory not found in the given path.")
        return None