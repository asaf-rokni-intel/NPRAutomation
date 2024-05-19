from VerifyInputs import *
from ExtractingData import *
from CreatingOutputFiles import *

if __name__ == "__main__":

    # Getting inputs from the user:
    tp_path = GetTpPath()
    input_files_path = GetInputFilesPath()
    output_path = GetOutputPath()

    log_file_path = os.path.join(output_path, "log.txt")
    
    # Store original stdout and stderr streams
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    # Redirect prints and errors to the log file
    with open(log_file_path, "w") as log_file:
        sys.stdout = log_file
        sys.stderr = log_file

        # Verifying inputs:
        json_file_path = FindJsonFile(input_files_path)
        conf_file_path = GetConfFilePath(input_files_path)
        search_option_value, check_option_value, other_options_values, dont_run_chk, ignore_patterns_with_regexes = CheckConfFile(conf_file_path, json_file_path)
        csv_file_path = TestCsvDataVerification(input_files_path, search_option_value, check_option_value, other_options_values)
        
        # Extracting data from input files:
        uservar_file_path = os.path.join(tp_path, "Shared", "CPU_Shared", "UservarDefinitions_IP_CPU.usrv")    
        mtpl_files_with_mconfig = CheckModulesDirectory(tp_path)
        tests_with_patlist = ExtractTestsWithPatlist(mtpl_files_with_mconfig, uservar_file_path)
        filtered_tests, excluded_tests = RemoveExcludedPatlists(tests_with_patlist, conf_file_path)
        test_instances_caught_by_regex, test_instances_not_caught = CatchTestInstancesByRegex(csv_file_path, filtered_tests)    
        AddRuleFileToTestInstances(test_instances_caught_by_regex, input_files_path)
        plist_found_in_files = ProcessPlistFiles(test_instances_caught_by_regex, input_files_path, search_option_value, check_option_value, other_options_values, ignore_patterns_with_regexes)
        
        print()
        print("Plist files where a patlist was found:")
        for plist_file in plist_found_in_files:
            print(plist_file)

        print()
        print("Information on tests derived from the NPR rules:")
        print(f"Total tests that were found by regexes ({len(test_instances_caught_by_regex)} tests found) and their details:")
        for test in test_instances_caught_by_regex:
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
            if dont_run_chk == False:
                print(f"Matching test found: {test['MatchFound']}")
            print(f"Amount of patterns in plist: {test['total_num_of_patterns_in_plist']}")
            print(f"Amount of patterns to disable in the plist: {len(test['patterns_to_disable'])}")
            print(f"Amount of patterns to keep in the plist (#KEEP# || Mask || pre): {test['num_of_patterns_to_keep']}")
            print()

        print()
        for test in test_instances_caught_by_regex:
            test_name = test["test_name"]
            patlist = test["patlist"]
            patterns_to_disable = test.get("patterns_to_disable", [])
    
            print(f"Test: {test_name}, Patlist: {patlist}")
            if patterns_to_disable: # and test["MatchFound"]:
                print("Patterns found to disable due to NPR rules:")
                for pattern in patterns_to_disable:
                    print(pattern)
            else:
                print("No patterns found to disable.")
            print()

        #Creating output files:
        log_files_directory = CreatingOutputFiles(input_files_path, plist_found_in_files, output_path, conf_file_path, test_instances_caught_by_regex, log_file_path, json_file_path, test_instances_not_caught, dont_run_chk, ignore_patterns_with_regexes, other_options_values)

        sys.stdout = original_stdout
        sys.stderr = original_stderr

    shutil.move(log_file_path, log_files_directory)