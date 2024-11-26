import csv
import os
import json
from queue import Empty
import re
from tkinter import N
from tracemalloc import take_snapshot
import xml.etree.ElementTree as ET

def CheckModulesDirectory(tp_path):
    modules_path = os.path.join(tp_path, "Modules")

    if not os.path.exists(modules_path) or not os.path.isdir(modules_path):
        print("The TP you provided does not contain the 'Modules' directory. Please make sure you are providing a valid TP path.")
        return None

    mtpl_files_with_mconfig = []

    for root, dirs, files in os.walk(modules_path):
        mtpl_file = None
        mconfig_file = None

        for file in files:
            if file.endswith(".mtpl"):
                mtpl_file = os.path.join(root, file)
            elif file.endswith(".mconfig"):
                mconfig_file = os.path.join(root, file)

        if mtpl_file and mconfig_file:
            mtpl_files_with_mconfig.append({"mtpl": mtpl_file, "mconfig": mconfig_file})

    return mtpl_files_with_mconfig

def RemoveExcludedPatlists(tests_with_patlist, conf_file_path):
    print("Removing excluded patlists as stated in the configuration file.")
    excluded_patlists = []

    with open(conf_file_path, 'r') as conf_file:
        for line in conf_file:
            line = line.strip()
            if line.startswith("ExcludedPlistsRegexes:"):
                excluded_patlists = [item.strip() for item in line.split(":")[1].split(',') if item.strip()]

    filtered_tests = []
    excluded_tests = []
    for test_name, patlist, scoreboard_base_number, pattern_name_map, template, mtpl_file, mconfig_file in tests_with_patlist:
        test_dict = {
            "test_name": test_name,
            "patlist": patlist,
            "scoreboard_base_number": scoreboard_base_number,
            "pattern_name_map": pattern_name_map,
            "template": template,
            "mtpl_file": mtpl_file,
            "mconfig_file": mconfig_file
        }
        if patlist not in excluded_patlists:
            filtered_tests.append(test_dict)
        else:
            excluded_tests.append(test_dict)
            print(f"Excluded Test Name: {test_dict['test_name']}")

    return filtered_tests, excluded_tests

def ExtractTestsWithPatlist(mtpl_files_with_mconfig, uservar_file_path):
    try:
        print("Extracting all the tests with a patlist in them.")
        tests_with_patlist = []

        for file_pair in mtpl_files_with_mconfig:
            mtpl_file = file_pair["mtpl"]
            mconfig_file = file_pair["mconfig"]

            with open(mtpl_file, 'r') as file:
                lines = file.readlines()

            test_name = None
            inside_test = False
            patlist = None
            scoreboard_base_number = None
            pattern_name_map = None
            template = None
            bypass_port = False  # Flag to track BypassPort condition
            curly_bracket_count = 0

            for line in lines:
                line = line.strip()

                if line.startswith("Test "):
                    parts = line.split()
                    test_name = parts[-1]
                    template = parts[1]  # Extract the template from "Test template_name test_name"
                    inside_test = True
                    curly_bracket_count = 0
                    bypass_port = False  # Reset bypass_port flag when entering a new test
                elif line.startswith("MultiTrialTest "):
                    parts = line.split()
                    test_name = parts[-1]
                    inside_test = True
                    curly_bracket_count = 0
                    bypass_port = False  # Reset bypass_port flag when entering a new test
                elif inside_test:
                    curly_bracket_count += line.count("{")
                    curly_bracket_count -= line.count("}")
                    if curly_bracket_count <= 0:
                        inside_test = False
                        if patlist is not None and not bypass_port:
                            tests_with_patlist.append((test_name, patlist, scoreboard_base_number, pattern_name_map, template, mtpl_file, mconfig_file))
                            patlist = None
                if inside_test and "BypassPort" in line and "=" in line and "#" not in line:
                    bypass_port_value = line.split("=")[1].split(";")[0].strip()
                    if bypass_port_value == "1":
                        bypass_port = True
                if inside_test and "TrialTest" in line and test_name in line:
                    template = line.split()[1]
                if re.search(r"Patlist\s*=", line):
                    patlist = line.split("=")[1].split(";")[0].strip().strip('"')
                if ("ScoreboardBaseNumber" in line or "BaseNumbers" in line) and "=" in line:
                    scoreboard_base_number = line.split("=")[1].split(";")[0].strip().strip('"')
                 
                pattern1 = r'"([^"]+)"\s*;'

                # Define a regular expression pattern for the second case.
                pattern2 = r'([^";\s]+);'

                # Check if "PatternNameMap" is in the line and "=" is in the line.
                if "PatternNameMap" in line and "=" in line:
                    parts = line.split("=")
                    if len(parts) > 1:
                        right_side = parts[1].strip()

                        # Try to match the first pattern.
                        match1 = re.match(pattern1, right_side)

                        if match1:
                            # Case 1: Extract numbers and commas from the matched pattern.
                            pattern_name_map = match1.group(1).replace(" ", "").replace('"', "")
                        else:
                            # Try to match the second pattern.
                            match2 = re.match(pattern2, right_side)

                            if match2:
                                # Case 2: Call ExtractPatternNameMap with the matched pattern.
                                temp_pattern_name_map = match2.group(1).rstrip(';')
                                pattern_name_map = ExtractPatternNameMap(uservar_file_path, temp_pattern_name_map)
                            else:
                                # Handle other cases here if needed.
                                pattern_name_map = None  # Placeholder for other cases.


    except Exception as error:
        print("An exception occurred in ExtractTestsWithPatlist:", error)
        print(f"The error is in instance {test_name} where right_side is {right_side} in module {mtpl_file} pattern name map is {pattern_name_map}")
        
    return tests_with_patlist

def GetTemplateForMTT(lines, test_name):
    template = None
    for line in lines:
        if "TrialTest" in line and test_name in line:
            parts = line.split()
            index = parts.index(test_name)
            if index < len(parts) - 2:  # Ensure there's at least one word after the test name
                template = parts[index + 1]
            break  # Stop searching once the relevant line is found
    return template

def ExtractPatternNameMap(uservar_file_path, temp_pattern_name_map):
    block_name, string_name = temp_pattern_name_map.split('.')
    
    with open(uservar_file_path, 'r') as usr_file:
        lines = usr_file.readlines()

    inside_block = False
    inside_string = False
    found_value = None

    for line in lines:
        line = line.strip()

        if line.startswith(f"UserVars {block_name}"):
            inside_block = True
            continue

        if inside_block and line.startswith(f"Const String {string_name}"):
            found_value = line.split('=')[1].strip().strip(';').strip('"')
            break

        if inside_block and line.startswith("}"):
            break

    return found_value

def CatchTestInstancesByRegex(csv_file_path, filtered_tests):
    print()
    print("Catching all test instances that match the regexes in the csv input file.")
    with open(csv_file_path, 'r', newline='') as csvfile:
        reader = csv.reader(csvfile)
        regex_patterns = [row for row in reader if row[0] != "Test Regex"]

    test_instances_caught_by_regex = []
    test_instances_not_caught = []

    for test in filtered_tests:
        test_name = test["test_name"]
        matched = False
        for pattern_row in regex_patterns:
            pattern = pattern_row[0]
            if re.match(pattern, test_name):
                search_or_check = pattern_row[1]
                power_domain = pattern_row[2]
                corner = pattern_row[3]

                test_instances_caught_by_regex.append({
                    "test_name": test_name,
                    "patlist": test["patlist"],
                    "scoreboard_base_number": test["scoreboard_base_number"],
                    "pattern_name_map": test["pattern_name_map"],
                    "template": test["template"],
                    "mtpl_file": test["mtpl_file"],
                    "mconfig_file": test["mconfig_file"],
                    "search_or_check": search_or_check,
                    "power_domain": power_domain,
                    "corner": corner
                })

                matched = True
                break
            if not matched:
                test_instances_not_caught.append({
                    "test_name": test_name,
                    "patlist": test["patlist"],
                    "scoreboard_base_number": test["scoreboard_base_number"],
                    "pattern_name_map": test["pattern_name_map"],
                    "template": test["template"],
                    "mtpl_file": test["mtpl_file"],
                    "mconfig_file": test["mconfig_file"],
                    "search_or_check": None,
                    "power_domain": None,
                    "corner": None
                })

    return test_instances_caught_by_regex, test_instances_not_caught

def ExtractPlistFilesFromMconfig(test, mconfig_file, supersede_dir_path):
    plist_files = []
    scope = None
    
    tree = ET.parse(mconfig_file)
    root = tree.getroot()
    
    ip_names = root.findall(".//IPName")
    
    if len(ip_names) > 1:
        raise ValueError(f"Error: More than one IPName found in the file: {mconfig_file}.")
    elif len(ip_names) == 1:
        scope = ip_names[0].text
        
    for por_root in root.findall(".//PORRoot"):
        path = por_root.get("Path")
        rev = por_root.get("Rev")
        patch = por_root.get("Patch")
        
        for plist_file_elem in por_root.findall(".//PlistFile"):
            plist_file = plist_file_elem.text.strip()
            full_path = os.path.join(path, rev, patch, "plb", plist_file)
            plist_files.append(full_path)
    
    plist_files = FindAndReplaceWithSupersedePlists(test, plist_files, supersede_dir_path)
    
    return plist_files, scope

def FindAndReplaceWithSupersedePlists(test, plist_files, supersede_dir_path):
    superseded_plist_files = []
    swaps_to_print = set()

    if supersede_dir_path:
        for plist_file in plist_files:
            plist_file_name = os.path.basename(plist_file)
            file_swapped = False

            for root, dirs, files in os.walk(supersede_dir_path):
                if plist_file_name in files:
                    supersede_path = os.path.join(root, plist_file_name)
                    superseded_plist_files.append(supersede_path)
                    file_swapped = True
                    swaps_to_print.add((plist_file_name, supersede_path))
                    break

            if not file_swapped:
                superseded_plist_files.append(plist_file)
    else:
        superseded_plist_files = plist_files

    for plist_file_name, supersede_path in set(swaps_to_print):
        print(f"Test '{test['test_name']}': Swapped {plist_file_name} with supersede version at {supersede_path}")

    return superseded_plist_files

def AddRuleFileToTestInstances(test_instances_caught_by_regex, input_files_path, other_options_values):
    removed_tests = []
    # Iterate over a copy of the list to safely modify the original list
    for test in test_instances_caught_by_regex[:]:
        rule_file = LocateRuleFile(test["patlist"], input_files_path)
        test["rule_file"] = rule_file
        
        if test.get("search_or_check") in other_options_values and not test.get("rule_file"):
            print(f"The test instance {test.get('test_name', 'Unknown')} was removed from the tests list because it was in OtherOptions flow ({test.get('search_or_check')}) and had no rule.")
            test_instances_caught_by_regex.remove(test)
            if test not in removed_tests:
                removed_tests.append(test)
    return removed_tests

def ProcessPlistFiles(tests, input_files_path, search_option_value, check_option_value, other_options_values, ignore_patterns_with_regexes, supersede_dir_path):
    errors = []
    plist_found_in_files = set()

    for test in tests:
        test_name = test["test_name"]
        patlist = test["patlist"]
        mtpl_file = test["mtpl_file"]
        mconfig_file = test["mconfig_file"]
        search_or_check = test["search_or_check"]
        test["removed_test_from_files"] = False

        if "::" in patlist:
            patlist = patlist.split("::", 1)[1]

        plist_files, scope = ExtractPlistFilesFromMconfig(test, mconfig_file, supersede_dir_path)
        
        test["scope"] = scope
        
        test["MatchFound"] = False
        
        plist_found = False

        for plist_file in plist_files:
            with open(plist_file, 'r') as plist_content:
                if patlist in plist_content.read():
                    plist_found = True
                    plist_found_in_files.add(plist_file)
                    test["patterns"], test["total_num_of_patterns_in_plist"], test["num_of_patterns_to_keep"], test["patterns_to_keep"], test["patterns_with_multiple_occurrences"] = ExtractPatternsFromPlist(patlist, plist_file, ignore_patterns_with_regexes)
                    if search_or_check == search_option_value:
                        test["patterns_to_disable"], errors_from_rules_search, test["patterns_to_keep_from_npr"] = RemoveEnabledContentFromPatterns(test_name, test, input_files_path)
                        for error in errors_from_rules_search:
                            errors.append(error)
                        FindTestWithMatchingPatlist(test, tests, search_option_value, check_option_value)
                    elif search_or_check == check_option_value:
                        test["patterns_to_disable"], errors_from_rules_check, test["patterns_to_keep_from_npr"] = RemoveNotEnabledContentFromPatterns(test_name, test, input_files_path, search_option_value, check_option_value)
                        for error in errors_from_rules_check:
                            errors.append(error)
                    else:
                        for value in other_options_values:
                            if search_or_check == value:
                                test["patterns_to_disable"], errors_from_rules_search, test["patterns_to_keep_from_npr"] = RemoveEnabledContentFromPatterns(test_name, test, input_files_path)
                                for error in errors_from_rules_search:
                                    errors.append(error)
                    break

        if not plist_found:
            errors.append((f"The plist wasn't found in any of the files in the mconfig file for test: {test_name}, patlist: {patlist}, mtpl_file: {mtpl_file}, mconfig_file: {mconfig_file}"))

        if test["total_num_of_patterns_in_plist"] == len(test["patterns_to_disable"]):
            test["patterns_to_disable"].pop(0) #Remove the first pattern in the list
            
    if errors:
        print("\nErrors with plists:")
        for error in errors:
            print(error)

    return sorted(plist_found_in_files)

def FindTestWithMatchingPatlist(test, tests, search_option_value, check_option_value):  
    possible_patlists = GeneratePossiblePatlists(test["patlist"], search_option_value, check_option_value)

    for test_to_check in tests:
        patlist_to_check = test_to_check["patlist"]

        if patlist_to_check in possible_patlists:
            test_to_check["MatchFound"] = True
            if test["removed_test_from_files"] == True:
                test_to_check["removed_test_from_files"] = True
            test["MatchFound"] = True
            return test_to_check

    test["MatchFound"] = False
    return None

def GeneratePossiblePatlists(patlist, search_option_value, check_option_value):
    possible_patlists = set()

    for option in [search_option_value.lower(), search_option_value.upper()]:
        for replacement in [check_option_value.lower(), check_option_value.upper()]:
            if option != replacement:
                new_patlist = re.sub(option, replacement, patlist)
                possible_patlists.add(new_patlist)

    possible_patlists.discard(patlist)

    return list(possible_patlists)

def ExtractPatternsFromPlist(patlist, plist_content_path, ignore_patterns_with_regexes):
    patterns = []
    patterns_to_keep = []
    inside_patlist = False
    curly_bracket_count = 0
    total_num_of_patterns_in_plist = 0
    num_of_patterns_to_keep = 0
    pattern_occurrences = {}  # Dictionary to track occurrences of each pattern
    pattern_keep_indices = {}  # Dictionary to track indices of occurrences to remove due to #KEEP#

    with open(plist_content_path, 'r') as plist_content:
        for line in plist_content:
            line = line.strip()

            if inside_patlist:
                curly_bracket_count += line.count("{")
                curly_bracket_count -= line.count("}")

                if curly_bracket_count <= 0:
                    break
                elif line.startswith("Pat "):
                    pattern = line.lstrip("Pat ").rstrip(";")
                    
                    # Increment the occurrence count correctly before checking for #KEEP#
                    occurrence_number = len(pattern_occurrences.get(pattern, [])) + 1
                    
                    # Track occurrences of each pattern
                    if pattern in pattern_occurrences:
                        pattern_occurrences[pattern].append(occurrence_number)
                    else:
                        pattern_occurrences[pattern] = [occurrence_number]

                    if "#KEEP#" in line:
                        if pattern in pattern_keep_indices:
                            pattern_keep_indices[pattern].append(occurrence_number)
                        else:
                            pattern_keep_indices[pattern] = [occurrence_number]

                    # KEEP is in the line, after the ";", so search there and not in the pattern.
                    if not (re.search(r'\[Mask', pattern) or "#KEEP#" in line or any(re.search(regex, pattern) for regex in ignore_patterns_with_regexes)):
                        #TODO: make sure the ignore_patterns_with_regexes captures every regex split by , like in the line below, use chatgpt.
                        #[item.strip() for item in line.split(":")[1].split(',') if item.strip()]
                        patterns.append(pattern)
                    else:
                        num_of_patterns_to_keep += 1
                        patterns_to_keep.append(pattern)
                    total_num_of_patterns_in_plist += 1
            elif f"GlobalPList " in line and patlist in line:
                if "{" in line:
                    inside_patlist = True
                    curly_bracket_count = line.count("{")
                else:
                    inside_patlist = True
                    for next_line in plist_content:
                        next_line = next_line.strip()
                        if "{" in next_line:
                            curly_bracket_count = next_line.count("{")
                            break

    # Adjust occurrences for patterns with #KEEP#
    for pattern, keep_indices in pattern_keep_indices.items():
        if pattern in pattern_occurrences:
            adjusted_occurrences = [occ for occ in pattern_occurrences[pattern] if occ not in keep_indices]
            pattern_occurrences[pattern] = adjusted_occurrences

    # Filter to keep only patterns with more than one occurrence
    patterns_with_multiple_occurrences = {pattern: occurrences for pattern, occurrences in pattern_occurrences.items() if len(occurrences) > 1}
                               
    return patterns, total_num_of_patterns_in_plist, num_of_patterns_to_keep, patterns_to_keep, patterns_with_multiple_occurrences

def LocateRuleFile(patlist, directory):
    for root, _, files in os.walk(directory):
        for filename in files:
            if patlist in filename and filename.endswith('.rule'):
                return os.path.join(root, filename)
    return None

def RemoveEnabledContentFromPatterns(test_name, test, input_files_path):
    patlist = test["patlist"]
    patterns = test["patterns"]
    rule_files = LocateRuleFile(patlist, input_files_path)
    patterns_to_keep = []

    if len(patterns) == 1:
        test["removed_test_from_files"] = True
        return [], [f"The test {test_name} with patlist {patlist} has only 1 pattern in the patlist, so it was not removed."], patterns

    if rule_files is None or len(rule_files) == 0:
        if len(patterns) == 1:
            patterns.pop()
            return [], [f"No rule file found for test: {test_name} with patlist {patlist}. Only 1 pattern was in the patlist, so it was not removed."], patterns
        elif len(test["patterns"]) > 1:
            patterns_to_keep = [test["patterns"][0]]  # Keep the first pattern
            patterns = test["patterns"][1:]  # Disable the rest
            return patterns, [f"No rule file found for test: {test_name} with patlist {patlist}"], patterns_to_keep

    if isinstance(rule_files, list) and len(rule_files) > 1:
        error_msg = f"Multiple rule files found for test: {test_name} with patlist {patlist}. Only one rule file is allowed per Plist."
        return patterns, [error_msg], patterns_to_keep

    with open(rule_files, 'r') as file:
        lines = file.readlines()

    enable_content_found = False
    errors = []
    total_numbers_to_remove = []

    for line in lines:
        if "::ENABLECONTENT::" in line:
            enable_content_found = True
            continue

        if enable_content_found:
            parts = line.strip().split()
            if len(parts) == 2 and parts[1].isdigit():
                number_to_remove = parts[1]
                patterns = [pattern for pattern in patterns if number_to_remove not in pattern]
            elif len(parts) == 0:
                continue
            else:
                error_msg = f"Invalid line in rule file '{rule_files}': Line {line.strip()} is not a valid number."
                errors.append(error_msg)
                
        
    for pattern in patterns:
        if not any(str(num) in pattern for num in total_numbers_to_remove):
            patterns_to_keep.append(pattern)

    return patterns, errors, patterns_to_keep

def RemoveNotEnabledContentFromPatterns(test_name, test, input_files_path, search_option_value, check_option_value):
    patlist = test["patlist"]
    patterns = test["patterns"]
    patterns_to_keep = []
    possible_patlists = [
        re.sub(check_option_value.lower(), search_option_value.lower(), patlist),
        re.sub(check_option_value.lower(), search_option_value.upper(), patlist),
        re.sub(check_option_value.upper(), search_option_value.lower(), patlist),
        re.sub(check_option_value.upper(), search_option_value.upper(), patlist)
    ]
    
    rule_files = []

    for possible_patlist in possible_patlists:
        rule_file = LocateRuleFile(possible_patlist, input_files_path)
        if rule_file:
            rule_files.append(rule_file)

    rule_files = list(set(rule_files))

    if rule_files is None or len(rule_files) == 0:
        return patterns, [f"No rule file found for test: {test_name} with patlist {patlist}."], patterns

    if isinstance(rule_files, list) and len(rule_files) > 1:
        error_msg = f"Multiple rule files found for test: {test_name} with patlist {patlist}. Only one rule file is allowed per Plist."
        return patterns, [error_msg], []

    with open(rule_files[0], 'r') as file:
        lines = file.readlines()

    enable_content_found = False
    errors = []
    new_patterns = []
    total_numbers_to_remove = []

    for line in lines:
        if "::ENABLECONTENT::" in line:
            enable_content_found = True
            continue

        if enable_content_found:
            parts = line.strip().split()
            if len(parts) == 2 and parts[1].isdigit():
                number_to_remove = parts[1]
                new_patterns.extend(pattern for pattern in patterns if number_to_remove in pattern)
                total_numbers_to_remove.append(number_to_remove)
            elif len(parts) == 0:
                continue
            else:
                error_msg = f"Invalid line in rule file '{rule_files}': Line {line.strip()} is not a valid number."
                errors.append(error_msg)
    
    for pattern in patterns:
        if not any(str(num) in pattern for num in total_numbers_to_remove):
            patterns_to_keep.append(pattern)

    return new_patterns, errors, patterns_to_keep

def RemovePatternsABList(test):
    if "patterns_to_keep_from_ab_list" not in test:
        test["patterns_to_keep_from_ab_list"] = []

    if "patterns_to_remove_ab_list" in test and "tuples_to_keep" in test:
        patterns_to_remove_ab_list = test["patterns_to_remove_ab_list"]
        tuples_to_keep = test["tuples_to_keep"]
        
        # Create a list to store updated patterns
        updated_patterns = []

        # Iterate through patterns_to_remove_ab_list
        for pattern in patterns_to_remove_ab_list:
            # Extract the value of the pattern's "Pattern" field
            pattern_value = pattern["Pattern"]
            # Check if any of the tuple_part elements are in the pattern's value
            if not any(tuple_part.strip("'") in pattern_value for tuple_part in tuples_to_keep):
                # Add the pattern to updated_patterns if none of the tuple_part elements are in it
                updated_patterns.append(pattern)
            else:
                test["patterns_to_keep_from_ab_list"].append(pattern)


        # Check if the number of patterns is the same as the start
        if len(updated_patterns) == len(patterns_to_remove_ab_list):
            if updated_patterns:
                # Remove the first pattern
                updated_patterns = updated_patterns[1:]

        # Assign the updated patterns to the test
        test["patterns_to_remove_ab_list"] = updated_patterns
        
def ExtractBaseNumberAndTuple(combined_number, base_number_length):
    combined_number_str = str(combined_number)
    baseNumber = combined_number_str[:base_number_length]
    tuplePart = combined_number_str[base_number_length:]
    return baseNumber, tuplePart

def GetBaseNumberLength(conf_file_path):
    # Read the configuration file and look for the "BaseNumberLength" line
    with open(conf_file_path, 'r') as conf_file:
        for line in conf_file:
            if line.startswith("BaseNumberLength:"):
                # Extract the value after the colon
                base_number_length = int(line.split(":")[1].strip())
                return base_number_length

    # Return a default value if "BaseNumberLength" is not found
    return None

def ExtractAbListPatlists(json_input_file):
    ab_list_patlists = {}  # Dictionary to store ab_list_patlists for each socket

    # Load the JSON input file
    with open(json_input_file, 'r') as jsonInput:
        input_data = json.load(jsonInput)

        # Iterate through sockets
        for socket_name, socket_data in input_data.items():
            patlists = {}  # Dictionary to store patlists and associated numbers
            for patlist_name, numbers in socket_data.items():
                patlists[patlist_name] = {"numbers": numbers}
            ab_list_patlists[socket_name] = patlists

    return ab_list_patlists

def AddPatternsAndScope(test, ignore_patterns_with_regexes, supersede_dir_path):
    patlist = test["patlist"]
    mconfig_file = test["mconfig_file"]

    if "::" in patlist:
        patlist = patlist.split("::", 1)[1]

    # Extract plist files and scope from mconfig file
    plist_files, scope = ExtractPlistFilesFromMconfig(test, mconfig_file, supersede_dir_path)

    # Assign the extracted scope to the test
    test["scope"] = scope

    # Search for patlist in plist files
    for plist_file in plist_files:
        with open(plist_file, 'r') as plist_content:
            if patlist in plist_content.read():
                test["patterns"], test["total_num_of_patterns_in_plist"], test["num_of_patterns_to_keep"], test["patterns_to_keep"], test["patterns_with_multiple_occurrences"] = ExtractPatternsFromPlist(patlist, plist_file, ignore_patterns_with_regexes)
