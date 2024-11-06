import csv
import json
from operator import index
import os
from re import I
import shutil
import sys
from ExtractingData import *

def CreatingOutputFiles(input_files_path, plist_found_in_files, output_path, outputs_in_tp, conf_file_path, test_instances_caught_by_regex, log_file_path, json_file_path, test_instances_not_caught, dont_run_chk, ignore_patterns_with_regexes, other_options_values, supersede_dir_path):
    #Create NPRCriteriaFile.csv
    npr_criteria_csv_path = os.path.join(outputs_in_tp, "NPRCriteriaFile.csv")
    print("Creating NPRCriteriaFile.csv file.")
    unique_model_names, encode_values = FillNPRCriteriaFile(conf_file_path, npr_criteria_csv_path, dont_run_chk, other_options_values)

    #Create NPRInputFile.csv
    npr_input_csv_path = os.path.join(outputs_in_tp, "NPRInputFile.csv")
    print("Creating NPRInputFile.csv file.")
    cleaned_plist_names_combined = FillNPRInputFile(unique_model_names, test_instances_caught_by_regex, npr_input_csv_path, dont_run_chk, other_options_values)

    #Create PAS_PTD.pup.json
    pup_json_path = os.path.join(outputs_in_tp, "PAS_PTD.pup.json")
    print("Creating PAS_PTD.pup.json file.")
    #List of all the tests that will go into the PAS_PTD.pup.json file
    pas_ptd_complete_tests_list = []
    FillPASPTDFile(pup_json_path, encode_values, cleaned_plist_names_combined, test_instances_caught_by_regex, pas_ptd_complete_tests_list, dont_run_chk)

    #If AB_LIST file exists, update the file
    if json_file_path is not None:
        UpdatePASPTDFile(json_file_path, pup_json_path, test_instances_caught_by_regex, test_instances_not_caught, conf_file_path, pas_ptd_complete_tests_list, ignore_patterns_with_regexes, supersede_dir_path)
        
    #Create FlatFile.csv
    flat_file_csv_path = os.path.join(output_path, "FlatFile.csv")
    print("Creating FlatFile.csv file.")
    FillFlatFile(pas_ptd_complete_tests_list, flat_file_csv_path)

    # Create PatternsLeftFile.csv
    patterns_left_file_path = os.path.join(output_path, "PatternsLeftFile.csv")
    print("Creating PatternsLeftFile.csv file.")
    FillPatternsLeftFile(test_instances_caught_by_regex, patterns_left_file_path)

    #Create SourceFiles directory
    source_files_directory = os.path.join(output_path, "SourceFiles")
    if not os.path.exists(source_files_directory):
        os.makedirs(source_files_directory)
    print("Creating a directory for source files.")
    FillSourceFilesDirectory(source_files_directory, input_files_path, plist_found_in_files)

    #Create LogFiles directory
    log_files_directory = os.path.join(output_path, "LogFiles")
    if not os.path.exists(log_files_directory):
        os.makedirs(log_files_directory)
    print("Creating a directory for log files.")
    FillLogFilesDirectory(log_files_directory, test_instances_caught_by_regex, pup_json_path, test_instances_not_caught)

    return log_files_directory

def FillNPRCriteriaFile(conf_file_path, npr_criteria_csv_path, dont_run_chk, other_options_values):
    with open(conf_file_path, 'r') as conf_file:
        lines = conf_file.readlines()

    location_codes = []
    encode_values = []
    unique_model_names = set()  #Initialize a set to collect unique ModelName values, will sort it at the end

    for line in lines:
        line = line.strip()
        if line.startswith("LocationCodes:"):
            location_codes = [item.strip() for item in line.split(":")[1].split(',') if item.strip()]
        elif line.startswith("Encode:"):
            encode_values = [item.strip() for item in line.split(":")[1].split(',') if item.strip()]

    with open(npr_criteria_csv_path, 'w', newline='') as csvfile:
        fieldnames = ['LotType', 'Pkg', 'Device', 'Revision', 'Stepping', 'LocationCode', 'EngId', 'Encode', 'ModelName', 'FullPercentage']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        
        for encode_value in sorted(encode_values):
            for location_code in sorted(location_codes):
                if dont_run_chk is True:
                    range_for_percentages = 1
                else:
                    range_for_percentages = 2
                
                range_for_percentages += len(other_options_values)
                    
                for full_percentage in range(range_for_percentages):
                    model_name = f'{encode_value}NPRR{full_percentage}'
                    unique_model_names.add(model_name)  #Add to the set of unique ModelName values
                    writer.writerow({
                        'LotType': '.',
                        'Pkg': '.',
                        'Device': '.',
                        'Revision': '.',
                        'Stepping': '.',
                        'LocationCode': location_code,
                        'EngId': '.',
                        'Encode': encode_value,
                        'ModelName': model_name,
                        'FullPercentage': 0 if dont_run_chk else (full_percentage if full_percentage <= 1 else 0)
                    })

    return sorted(unique_model_names), encode_values

def FillNPRInputFile(unique_model_names, test_instances_caught_by_regex, npr_input_csv_path, dont_run_chk, other_options_values):
    plist_names_combined = set()

    # Check if the length of other_options_values matches the expectation
    if len(other_options_values) != len(unique_model_names) - 1:
        print("Warning: The number of entries in other_options_values does not match the expected number based on unique_model_names.")
    
    with open(npr_input_csv_path, 'w', newline='') as csvfile:
        fieldnames = ['ModelName', 'PlistName', 'Ipname']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        sorted_model_names = sorted(unique_model_names)
        other_options_values_list = list(other_options_values)
        model_name_to_option = {model_name: other_options_values_list[i] for i, model_name in enumerate(sorted_model_names[1:])}
        
        if dont_run_chk is True:
            for model_name in sorted_model_names:
                if model_name.endswith('0'):
                    plist_names = [(test["patlist"], test["scope"]) for test in test_instances_caught_by_regex if test.get("search_or_check") not in other_options_values]
                else:
                    # Use the mapped value for search_or_check based on the model_name
                    search_or_check_value = model_name_to_option[model_name]
                    plist_names = [(test["patlist"], test["scope"]) for test in test_instances_caught_by_regex if test.get("rule_file") is not None and test.get("search_or_check") == search_or_check_value]
                    
                plist_names_combined.update(plist_names)

                cleaned_plist_names = CleanUpPlistNames(plist_names)
                for plist_name, ip_name in cleaned_plist_names:
                    writer.writerow({
                        'ModelName': model_name,
                        'PlistName': plist_name,
                        'Ipname': ip_name
                    })
        else:
            for model_name in sorted_model_names:
                plist_names = []
                if model_name.endswith('0'):
                    plist_names = [(test.get("patlist", "MissingPatlist"), test.get("scope", "MissingScope")) for test in test_instances_caught_by_regex if test.get("rule_file") is not None and test.get("search_or_check") not in other_options_values and test.get("MatchFound") is True]
                elif model_name.endswith('1'):
                        plist_names = [(test.get("patlist", "MissingPatlist"), test.get("scope", "MissingScope")) for test in test_instances_caught_by_regex if test.get("rule_file") is None and test.get("search_or_check") not in other_options_values and test.get("MatchFound") is True]
                else:
                    search_or_check_value = model_name_to_option.get(model_name)
                    if search_or_check_value:
                        plist_names = [(test.get("patlist", "MissingPatlist"), test.get("scope", "MissingScope")) for test in test_instances_caught_by_regex if test.get("rule_file") is not None and test.get("search_or_check") == search_or_check_value]
                    else:
                        print(f"Warning: No search_or_check value mapped for model_name {model_name}.")
                
                plist_names_combined.update(plist_names)

                cleaned_plist_names = CleanUpPlistNames(plist_names)
                for plist_name, ip_name in cleaned_plist_names:
                    writer.writerow({
                        'ModelName': model_name,
                        'PlistName': plist_name,
                        'Ipname': ip_name
                    })
    cleaned_plist_names_combined = CleanUpPlistNames(sorted(plist_names_combined))
    return cleaned_plist_names_combined

def CleanUpPlistNames(plist_names):
    cleaned_names = []
    for plist, scope in plist_names:
        parts = plist.split("::")
        if len(parts) > 1:
            plist_name = parts[1].strip()
            ip_name = parts[0].strip()
        else:
            plist_name = plist.strip()
            ip_name = scope.strip()

        cleaned_names.append((plist_name, ip_name))
    return cleaned_names

def ReadEncoderMapping():
    encoder_mapping = {}

    # Get the path to the 'BLLEncoder.txt' file
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller executable
        base_path = sys._MEIPASS
    else:
        # Running as a regular script
        base_path = os.path.dirname(__file__)

    file_path = os.path.join(base_path, "BLLEncoder.txt")

    with open(file_path, 'r') as encoder_file:
        for line in encoder_file:
            line = line.strip()
            if line:
                encode_value, name = line.split(':')
                encoder_mapping[encode_value] = name

    return encoder_mapping

def FillPASPTDFile(pup_json_path, encode_values, cleaned_plist_names_combined, test_instances_caught_by_regex, pas_ptd_complete_tests_list, dont_run_chk):
    try:
        data = {
            "Version": "1000",
            "ProcessTypes": []
        }

        encoder_mapping = ReadEncoderMapping()

        for encode_value in encode_values:
            if encode_value in encoder_mapping:
                name = encoder_mapping[encode_value].strip()
            else:
                name = encode_value.strip()
            process_type = {
                "Name": name,
                "StepName": name,
                "PerPatlistPatternsToDisable": []
            }

            for plist_name, _ in cleaned_plist_names_combined:
                patterns_to_disable = []
                added_patterns = set()  # Keep track of patterns already added

                for instance in test_instances_caught_by_regex:
                    if not dont_run_chk:
                        if instance["MatchFound"]:
                            if instance["patlist"] == plist_name:
                                if "scope" in instance:
                                    patlist_with_scope = f"{instance['scope']}::{plist_name}"
                                else:
                                    patlist_with_scope = plist_name

                                # Check and append patterns with their occurrences
                                for pattern_info in instance["patterns_to_disable"]:
                                    if pattern_info not in added_patterns:  # Check if pattern has not been added already
                                        pattern_entry = {"Pattern": pattern_info}
                                        # Check if the pattern exists in patterns_with_multiple_occurrences
                                        if pattern_info in instance.get("patterns_with_multiple_occurrences", {}):
                                            occurrences = instance["patterns_with_multiple_occurrences"][pattern_info]
                                            pattern_entry["Occurrence"] = ",".join(map(str, occurrences))
                                        patterns_to_disable.append(pattern_entry)
                                        added_patterns.add(pattern_info)  # Mark pattern as added
                                break
                    else:
                        if plist_name in instance["patlist"]:
                            if "scope" in instance:
                                patlist_with_scope = f"{instance['scope']}::{plist_name}"
                            else:
                                patlist_with_scope = plist_name
                            # Check and append patterns with their occurrences
                            for pattern_info in instance["patterns_to_disable"]:
                                if pattern_info not in added_patterns:  # Check if pattern has not been added already
                                    pattern_entry = {"Pattern": pattern_info}
                                    # Check if the pattern exists in patterns_with_multiple_occurrences
                                    if pattern_info in instance.get("patterns_with_multiple_occurrences", {}):
                                        occurrences = instance["patterns_with_multiple_occurrences"][pattern_info]
                                        pattern_entry["Occurrence"] = ",".join(map(str, occurrences))
                                    patterns_to_disable.append(pattern_entry)
                                    added_patterns.add(pattern_info)  # Mark pattern as added
                            break
                        
                #if not(dont_run_chk == True and instance["search_or_check"] == "CHK"):
                if patterns_to_disable:
                    process_type["PerPatlistPatternsToDisable"].append({
                        "Patlist": patlist_with_scope,
                        "Functionality": "Short",
                        "PatternsToDisable": patterns_to_disable
                    })
                    pas_ptd_complete_tests_list.append(instance)

            data["ProcessTypes"].append(process_type)

        with open(pup_json_path, 'w') as json_file:
            json.dump(data, json_file, indent=4)
            
    except Exception as error:
        print("An exception occurred in PAS_PTD:", error)

def CopyFilesAndDirectories(source, destination):
    for item in os.listdir(source):
        source_path = os.path.join(source, item)
        destination_path = os.path.join(destination, item)

        if os.path.isdir(source_path):
            shutil.copytree(source_path, destination_path)
        else:
            shutil.copy2(source_path, destination_path)

def FillSourceFilesDirectory(source_files_directory, input_files_path, plist_found_in_files):
    #Copy all files and directories from input_files_path to source_files_directory
    CopyFilesAndDirectories(input_files_path, source_files_directory)

    #Create a "Plists" directory within source_files_directory
    plists_directory = os.path.join(source_files_directory, "Plists")
    os.makedirs(plists_directory, exist_ok=True)

    #Copy plist files from plist_found_in_files to the "Plists" directory
    for plist_path in plist_found_in_files:
        plist_filename = os.path.basename(plist_path)
        destination_path = os.path.join(plists_directory, plist_filename)
        shutil.copy(plist_path, destination_path)

def FillLogFilesDirectory(log_files_directory, test_instances_caught_by_regex, pup_json_path, test_instances_not_caught):
    CreateSrhChkMappingFile(log_files_directory, test_instances_caught_by_regex)
    CreateBasicStatsFile(log_files_directory, test_instances_caught_by_regex, pup_json_path, test_instances_not_caught)

def CreateSrhChkMappingFile(log_files_directory, test_instances_caught_by_regex):
    csv_path = os.path.join(log_files_directory, "SRH_CHK_Mapping.csv")

    with open(csv_path, 'w', newline='') as csvfile:
        fieldnames = ['Module Name', 'Test Instance', 'Flow', 'Power Domain', 'Corner', 'Template', 'ScoreboardBaseNumber', 'Patlist', 'Scope', 'Match Found']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()

        for test in test_instances_caught_by_regex:
            module_name = os.path.splitext(os.path.basename(test["mtpl_file"]))[0]
            test_instance = test.get("test_name", "")
            flow = test.get("search_or_check", "")
            power_domain = test.get("power_domain", "")
            corner = test.get("corner", "")
            template = test.get("template", "")
            scoreboard_base_number = test.get("scoreboard_base_number", "")
            patlist = test.get("patlist", "")
            scope = test.get("scope", "")
            match_found = test.get("MatchFound", "")

            writer.writerow({
                'Module Name': module_name,
                'Test Instance': test_instance,
                'Flow': flow,
                'Power Domain': power_domain,
                'Corner': corner,
                'Template': template,
                'ScoreboardBaseNumber': scoreboard_base_number,
                'Patlist': patlist,
                'Scope': scope,
                'Match Found': match_found
            })

    print(f"CSV file '{csv_path}' has been created.")

def CreateBasicStatsFile(log_files_directory, test_instances_caught_by_regex, json_output_file, test_instances_not_caught):
    csv_file_path = os.path.join(log_files_directory, "BasicStats.csv")

    with open(json_output_file, 'r') as output_file:
        output_data = json.load(output_file)

    with open(csv_file_path, mode='w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)

        header_row = ['Module Name', 'Test Name', 'Patlist', 'Monitor/Short', 'Total Patterns', 'Removed Patterns', 'Executed Patterns', 'Reduction Rate (%)', 'Test Impacted By', 'Comments']
        csv_writer.writerow(header_row)

        patlist_data = GetPatlistDataFromJson(json_output_file)

        for data in patlist_data:
            patlist = data["patlist"]
            functionality = data["functionality"]
            removed_patterns = data["patterns_count"]
            comment = None
            test_impacted_by = "Nothing"
            total_patterns = 0

            # Search in test_instances_caught_by_regex:
            for test in test_instances_caught_by_regex:
                if patlist == test["scope"] + "::" + test["patlist"] or patlist == test["patlist"]:
                    total_patterns = test.get("total_num_of_patterns_in_plist", 0)
                    match_found = test.get("MatchFound", False)
                    ab_list_numbers = test.get("ab_list_numbers", [])
                    if match_found:
                        test_impacted_by = "NPR Rule"
                        if ab_list_numbers:
                            test_impacted_by = "NPR Rule + AB List"
                    else:
                        if ab_list_numbers:
                            test_impacted_by = "AB List"
                        else:
                            test_impacted_by = "Nothing"
                    if test["removed_test_from_files"] == True:
                        comment = "Patterns were disabled in CHK without being enabled in a corresponding SRH! Please check the NPR rules, PAS_PTD.json file is invalid!"
                    else:
                        comment = None
                    break

            # If not found, search in test_instances_not_caught
            if total_patterns == 0:
                for test in test_instances_not_caught:
                    if patlist.split("::")[1] == test["patlist"]:
                        total_patterns = test.get("total_num_of_patterns_in_plist", 0)
                        match_found = test.get("MatchFound", False)
                        ab_list_numbers = test.get("ab_list_numbers", [])
                        if match_found:
                            if ab_list_numbers:
                                test_impacted_by = "NPR Rule + AB List"
                        else:
                            if ab_list_numbers:
                                test_impacted_by = "AB List"
                            else:
                                test_impacted_by = None
                        break

            # if "patterns_to_disable" in test:
            #     patterns_to_disable_in_test = test.get("patterns_to_disable")
            # elif "patterns_to_remove_ab_list" in test:
            #     patterns_to_disable_in_test = test.get("patterns_to_remove_ab_list")
            # else:
            #     patterns_to_disable_in_test = []

            reduction_rate = (removed_patterns / total_patterns) * 100 if total_patterns > 0 else 0
            executed_patterns = total_patterns - removed_patterns
            test_name = test.get("test_name")
            module_name = os.path.splitext(os.path.basename(test.get("mtpl_file")))[0]

            csv_writer.writerow([module_name, test_name, patlist, functionality, total_patterns, removed_patterns, executed_patterns, reduction_rate, test_impacted_by, comment])

    print(f"BasicStats CSV file created at {csv_file_path}")
   
def GetPatlistDataFromJson(json_output_file):
    patlist_data = []

    with open(json_output_file, 'r') as output_file:
        output_data = json.load(output_file)

    for process_type in output_data.get("ProcessTypes", []):
        socket_name = process_type.get("Name")
        for per_patlist in process_type.get("PerPatlistPatternsToDisable", []):
            patlist = per_patlist.get("Patlist", "")
            functionality = per_patlist.get("Functionality", "")
            patterns_count = len(per_patlist.get("PatternsToDisable", []))

            patlist_data.append({
                "socket": socket_name,
                "patlist": patlist,
                "functionality": functionality,
                "patterns_count": patterns_count
            })

    return patlist_data

def UpdatePASPTDFile(json_input_file, json_output_file, test_instances_caught_by_regex, test_instances_not_caught, conf_file_path, pas_ptd_complete_tests_list, ignore_patterns_with_regexes, supersede_dir_path):
    print("Updating PAS_PTD.pup.json file")
    print()
    
    print("Information on tests derived from the AB list:")
    
    # Extract just the file name from the json_input_file path
    json_file_name = json_input_file.split('/')[-1]

    # Call ExtractAbListPatlists method
    ab_list_patlists = ExtractAbListPatlists(json_input_file)

    # Execute the GetBaseNumberLength method
    base_number_length = GetBaseNumberLength(conf_file_path)

    # Create a dictionary to store ab_list_tests per socket
    ab_list_tests = {}

    # Initialize the errors list
    errors = []

    # Iterate through sockets and patlists in ab_list_patlists
    for socket_name, socket_data in ab_list_patlists.items():
        # Initialize the ab_list_tests list for this socket
        ab_list_tests[socket_name] = []

        for patlist_name, patlist_info in socket_data.items():
            # Try to match with test_instances_caught_by_regex
            matched = False
            clean_patlist_name = CleanPatlistName(patlist_name)
            for test_instance in test_instances_caught_by_regex:
                patlist_pattern = test_instance["patlist"]
                if patlist_pattern == clean_patlist_name:
                    # Match found, add ab_list_numbers to the test instance
                    test_instance["ab_list_numbers"] = patlist_info["numbers"]
                    # Add the test instance to ab_list_tests for this socket
                    ab_list_tests[socket_name].append(test_instance)
                    matched = True
                    break

            # If no match was found in test_instances_caught_by_regex, try with test_instances_not_caught
            if not matched:
                for test_instance in test_instances_not_caught:
                    patlist_pattern = test_instance["patlist"]
                    if patlist_pattern == clean_patlist_name:
                        # Match found, add ab_list_numbers to the test instance
                        test_instance["ab_list_numbers"] = patlist_info["numbers"]
                        # Add the test instance to ab_list_tests for this socket
                        ab_list_tests[socket_name].append(test_instance)
                        matched = True
                        test_instance["MatchFound"] = True
                        break

            # If still no matches were found, append an error message to the errors list
            if not matched:
                error_message = f"The patlist {clean_patlist_name} from the {json_file_name} file didn't have a matching test instance in the test program that uses it. Please verify that the patlist is being used by an instance in the test program and that it is not bypassed."
                errors.append(error_message)
                
        # Iterate through tests in ab_list_tests for this socket
        for test in ab_list_tests[socket_name]:
            if "patterns" not in test:
                AddPatternsAndScope(test, ignore_patterns_with_regexes, supersede_dir_path)

        for test in ab_list_tests[socket_name]:
            if "ab_list_numbers" in test:
                tuples_to_keep = []

                for number in test["ab_list_numbers"]:
                    base_number, tuple_part = ExtractBaseNumberAndTuple(number, base_number_length)
                    tuples_to_keep.append(tuple_part)

                test["tuples_to_keep"] = tuples_to_keep

                # Compare base_number with scoreboard_base_number
                if "scoreboard_base_number" in test:
                    if base_number != test["scoreboard_base_number"]:
                        errors.append(f"The base number {test['scoreboard_base_number']} of the test instance {test['test_name']} does not match the base number given in the {os.path.basename(json_input_file)} file.")
                
                # Copy the "patterns" variable into "patterns_to_remove_ab_list" and create an empty list for patterns to keep from ab_list
                if "patterns" in test:
                    test["patterns_to_remove_ab_list"] = []
                    added_patterns = set()  # Keep track of patterns already added

                    for pattern_info in test["patterns"]:
                        if pattern_info not in added_patterns:  # Check if pattern has not been added already
                            pattern_entry = {"Pattern": pattern_info}
                            
                            # Only add "Occurrence" if there are occurrences in patterns_with_multiple_occurrences
                            if pattern_info in test.get("patterns_with_multiple_occurrences", {}):
                                occurrences = test["patterns_with_multiple_occurrences"][pattern_info]
                                if occurrences:  # Only add if there are occurrences
                                    pattern_entry["Occurrence"] = ",".join(map(str, occurrences))

                            test["patterns_to_remove_ab_list"].append(pattern_entry)
                            added_patterns.add(pattern_info)  # Mark pattern as added
            
        for test in ab_list_tests[socket_name]:
            print(f"Test Name: {test['test_name']}")
            print(f"Patlist: {test['patlist']}")
            print(f"Scope: {test['scope']}")
            print(f"Scoreboard Base Number: {test['scoreboard_base_number']}")
            print(f"Pattern Name Map: {test['pattern_name_map']}")
            print(f"Template: {test['template']}")
            print(f"MTPL File: {test['mtpl_file']}")
            print(f"Mconfig File: {test['mconfig_file']}")
            print(f"Search or Check: {test['search_or_check']}")
            print(f"Power Domain: {test['power_domain']}")
            print(f"Corner: {test['corner']}")
            print(f"Matching test found: {test['MatchFound']}")
            print(f"Amount of patterns in plist: {test['total_num_of_patterns_in_plist']}")
            print(f"Amount of patterns to keep in the plist (#KEEP# || Mask || pre): {test['num_of_patterns_to_keep']}")
            print()

        # Now, let's call the "RemovePatternsABList" method
        for test in ab_list_tests[socket_name]:
            if "patterns_to_remove_ab_list" in test:
                RemovePatternsABList(test)
         
            test_name = test["test_name"]
            patlist = test["patlist"]
            patterns_to_disable_ab_list = test.get("patterns_to_remove_ab_list", [])
    
            print(f"Test: {test_name}, Patlist: {patlist}")
            if patterns_to_disable_ab_list:
                print(f"Patterns found to disable due to rules from the {os.path.basename(json_input_file)} file:")
                for pattern in patterns_to_disable_ab_list:
                    print(pattern)
            else:
                print("No patterns found to disable.")
            print()
        
    with open(json_output_file, 'r') as output_file:
        output_data = json.load(output_file)

    # Update the output_data with the information from ab_list_tests
    UpdateOutputData(output_data, ab_list_tests, json_output_file, pas_ptd_complete_tests_list)

    if errors:
        print("\nErrors found when trying to update the PAS_PTD file based on the given JSON input file:")
        for error in errors:
            print(error)

def CleanPatlistName(patlist_name):
    if "::" in patlist_name:
        _, right_part = patlist_name.split("::", 1)
        return right_part
    else:
        return patlist_name

def UpdateOutputData(output_data, ab_list_tests, json_output_file, pas_ptd_complete_tests_list):
    all_tests = []
    for socket_name, socket_tests in ab_list_tests.items():
        for process_type in output_data.get("ProcessTypes", []):
            if process_type.get("Name") == socket_name:
                for test in socket_tests:
                    pas_ptd_complete_tests_list.append(test)
                    test_patlist = test['patlist']
                    test_scope = test['scope']
                    matched = False

                    for per_patlist in process_type.get("PerPatlistPatternsToDisable", []):
                        patlist = per_patlist.get("Patlist", "")
                        if test_scope + "::" + test_patlist == patlist:
                            all_tests.append((test, process_type, process_type.get("PerPatlistPatternsToDisable", []).index(per_patlist), "Monitor"))
                            matched = True
                            break

                    if not matched:
                        all_tests.append((test, process_type, len(process_type.get("PerPatlistPatternsToDisable", [])), "Short"))

    # Update all tests with their respective functionalities in one call
    UpdatePerPatlist(json_output_file, all_tests)

def CleanPatlistName(patlist_name):
    if "::" in patlist_name:
        _, right_part = patlist_name.split("::", 1)
        return right_part
    else:
        return patlist_name

def UpdateOutputData(output_data, ab_list_tests, json_output_file, pas_ptd_complete_tests_list):
    all_tests = []
    for socket_name, socket_tests in ab_list_tests.items():
        for process_type in output_data.get("ProcessTypes", []):
            if process_type.get("Name") == socket_name:
                for test in socket_tests:
                    pas_ptd_complete_tests_list.append(test)
                    test_patlist = test['patlist']
                    test_scope = test['scope']
                    matched = False

                    for per_patlist in process_type.get("PerPatlistPatternsToDisable", []):
                        patlist = per_patlist.get("Patlist", "")
                        if test_scope + "::" + test_patlist == patlist:
                            all_tests.append((test, process_type, process_type.get("PerPatlistPatternsToDisable", []).index(per_patlist), "Monitor"))
                            matched = True
                            break

                    if not matched:
                        all_tests.append((test, process_type, len(process_type.get("PerPatlistPatternsToDisable", [])), "Short"))

    # Update all tests with their respective functionalities in one call
    UpdatePerPatlist(json_output_file, all_tests)

def UpdatePerPatlist(json_output_file, tests):
    # Load the existing JSON data from the output file
    tests.sort(key=lambda x: x[0]['test_name'])
    with open(json_output_file, 'r') as output_file:
        output_data = json.load(output_file)

    # Process each test
    for test, process_type, index, functionality in tests:
        new_per_patlist = {
            "Patlist": test['scope'] + "::" + test["patlist"],
            "Functionality": functionality,
            "PatternsToDisable": [
                {
                    "Pattern": pattern["Pattern"],
                    **({"Occurrence": pattern["Occurrence"]} if "Occurrence" in pattern and pattern["Occurrence"] else {})
                }
                for pattern in test["patterns_to_remove_ab_list"]
            ]
        }

        # Check if the entry already exists with "Short" functionality
        existing_entry = next((entry for entry in process_type["PerPatlistPatternsToDisable"] if entry["Patlist"] == new_per_patlist["Patlist"] and entry["Functionality"] == "Short"), None)
        
        if existing_entry:
            # Update the existing entry to "Monitor"
            existing_entry["Functionality"] = "Monitor"
            # Insert the new entry with "Short" functionality right after it
            new_per_patlist["Functionality"] = "Short"
            process_type["PerPatlistPatternsToDisable"].insert(index + 1, new_per_patlist)
        else:
            # Insert the new entry with "Short" functionality
            process_type["PerPatlistPatternsToDisable"].insert(index, new_per_patlist)

        # Update the process_type in output_data
        for pt in output_data.get("ProcessTypes", []):
            if pt["Name"] == process_type["Name"]:
                pt["PerPatlistPatternsToDisable"] = process_type["PerPatlistPatternsToDisable"]

    # Write the modified data back to the output file
    with open(json_output_file, 'w') as output_file:
        json.dump(output_data, output_file, indent=4)
        
def FillFlatFile(pas_ptd_complete_tests_list, flat_file_csv_path):
    # Use a list to maintain order and a set for quick lookup
    unique_patlists = []
    unique_patlists_set = set()
    unique_tests = []

    # Ensure that each test is added only once and maintain insertion order
    for test_tuple in pas_ptd_complete_tests_list:
        test = dict(test_tuple)
        patlist_name = test.get("patlist", "")

        if patlist_name not in unique_patlists_set:
            unique_tests.append(test)
            unique_patlists.append(patlist_name)
            unique_patlists_set.add(patlist_name)

    # Write to CSV, ensuring the order of patlists is maintained as collected
    with open(flat_file_csv_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Patlist Name', 'Type', 'Patterns Strings'])

        for test in unique_tests:
            patlist_name = test.get("patlist", "")
            npr_patterns = test.get("patterns_to_keep_from_npr", [])
            ab_patterns = test.get("patterns_to_keep_from_ab_list", [])

            output_lines = []

            # Check if npr_patterns is empty and handle accordingly
            if not npr_patterns:  # If no NPR patterns, only AB patterns are considered
                for pattern in ab_patterns:
                    output_lines.append([patlist_name, 'PUP', pattern])
            else:
                for pattern in npr_patterns:
                    output_lines.append([patlist_name, 'NPR', pattern])

                # Check for existing patterns in AB list to update the type if necessary
                for pattern in ab_patterns:
                    existing_line = next((line for line in output_lines if line[2] == pattern), None)
                    if existing_line:
                        existing_line[1] = 'PUP'  # Update type to 'PUP' if pattern is already listed under 'NPR'

            writer.writerows(output_lines)

def FillPatternsLeftFile(test_instances, output_csv_path):
    with open(output_csv_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Test Name', 'Patlist Name', 'Patterns Strings'])

        for test in test_instances:
            test_name = test.get("test_name", "Unknown Test")
            patlist_name = test.get("patlist", "Unknown Patlist")
            patterns_to_keep = test.get("patterns_to_keep", []) + test.get("patterns_to_keep_from_npr", [])

            for pattern in patterns_to_keep:
                writer.writerow([test_name, patlist_name, pattern])