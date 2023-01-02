import argparse
import xml.etree.ElementTree as ET
from xml.dom import minidom


XML_ROOT = "."
XML_TESTSUITE = f"{XML_ROOT}/testsuite"
XML_TESTSUITE_PROPS = "properties/property"
XML_TESTCASE = "testcase"
SEPARATOR = "============================================="


def setup_command():
    parser = argparse.ArgumentParser(description='Combine xml pytest reports')
    parser.add_argument('-i', '--input-reports', default=[], nargs='+', required=True)
    parser.add_argument('-o', '--output-file', type=str, required=True)
    return parser.parse_args()


def load_reports(input_reports):
    test_reports = {}
    for input_path in input_reports:
        try: 
            with open(input_path, 'r', encoding='utf-8') as xdf_file:
                tree = ET.parse(xdf_file)
        except FileNotFoundError:
            raise FileNotFoundError(f"There is not any xml file in the path: {input_path}")
        root = tree.getroot()
        testsuite = root.find(XML_TESTSUITE)
        properties = testsuite.findall(XML_TESTSUITE_PROPS)
        protocol = [prop.attrib["value"] for prop in properties if prop.attrib["name"] == "protocol"][0]
        slave = [prop.attrib["value"] for prop in properties if prop.attrib["name"] == "slave"][0]
        test_reports[input_path] = {
            "errors": int(testsuite.attrib["errors"]),
            "failures": int(testsuite.attrib["failures"]),
            "skipped": int(testsuite.attrib["skipped"]),
            "tests": int(testsuite.attrib["tests"]),
            "time": float(testsuite.attrib["time"]),
            "timestamp": testsuite.attrib["timestamp"],
            "hostname": testsuite.attrib["hostname"],
            "protocol": protocol,
            "slave": slave,
            "testcases": {}
        } 
        testcases = testsuite.findall(XML_TESTCASE)
        
        for testcase in testcases:
            classname = testcase.attrib["classname"]
            name = testcase.attrib["name"]
            if classname not in test_reports[input_path]["testcases"]:
                test_reports[input_path]["testcases"][classname] = {}
            
            failure = testcase.find("failure")
            skipped = testcase.find("skipped")
            error = testcase.find("error")
            if failure is not None:
                test_reports[input_path]["testcases"][classname][name] = {
                    "result": "FAILED",
                    "message": failure.attrib["message"],
                    "output": failure.text
                }
            elif skipped is not None:
                test_reports[input_path]["testcases"][classname][name] = {
                    "result": "SKIPPED",
                    "message": skipped.attrib["message"],
                    "output": skipped.text
                }
            elif error is not None:
                test_reports[input_path]["testcases"][classname][name] = {
                    "result": "ERROR",
                    "message": error.attrib["message"],
                    "output": error.text
                }
            else:
                test_reports[input_path]["testcases"][classname][name] = {
                    "result": "PASSED",
                    "message": "",
                    "output": ""
                }
            test_reports[input_path]["testcases"][classname][name]["time"] = float(testcase.attrib["time"])
        
    return test_reports


def combine_reports(test_reports):
    combined_report = {
        "time": 0,
        "errors": 0,
        "failures": 0,
        "passed": 0,
        "skipped": 0,
        "tests": 0,
        "testcases": {}
    }
    for report_path, report_dict in test_reports.items():
        protocol = report_dict["protocol"]
        slave = report_dict["slave"]
        if "timestamp" not in combined_report:
            combined_report["timestamp"] = report_dict["timestamp"]
            combined_report["hostname"] = report_dict["hostname"]
        combined_report["time"] += report_dict["time"]
        combined_report["tests"] = report_dict["tests"]

        for classname in report_dict["testcases"].keys():
            if classname not in combined_report["testcases"]:
                combined_report["testcases"][classname] = {}
            for name in report_dict["testcases"][classname].keys():
                if name not in combined_report["testcases"][classname]:
                    result = report_dict["testcases"][classname][name]["result"]
                    if result != "PASSED":
                        message = "PROTOCOL: {} - SLAVE: {} --> {} ({})".format(
                            str(protocol),
                            str(slave),
                            report_dict["testcases"][classname][name]["result"],
                            report_dict["testcases"][classname][name]["message"]
                        )
                        output =  "\n PROTOCOL: {} - SLAVE: {} --> {} \n {} \n {}".format(
                            str(protocol),
                            str(slave),
                            report_dict["testcases"][classname][name]["result"],
                            SEPARATOR,
                            report_dict["testcases"][classname][name]["output"]
                        )
                    else:
                        message = ""
                        output = ""
                    
                    combined_report["testcases"][classname][name] = {
                        "result": report_dict["testcases"][classname][name]["result"],
                        "message": message,
                        "output": output,
                        "time": report_dict["testcases"][classname][name]["time"]
                    }
                else:
                    if combined_report["testcases"][classname][name]["result"] == "ERROR":
                        result = "ERROR" # ERROR before
                    elif report_dict["testcases"][classname][name]["result"] == "ERROR":
                        result = "ERROR" # ERROR now
                    elif combined_report["testcases"][classname][name]["result"] == "FAILED":
                        result = "FAILED" # FAILED before
                    elif report_dict["testcases"][classname][name]["result"] == "FAILED":
                        result = "FAILED" # FAILED now
                    elif combined_report["testcases"][classname][name]["result"] == "SKIPPED":
                        # SKIPPED before
                        if combined_report["testcases"][classname][name]["result"] == "PASSED":
                            result = "PASSED"
                        else:
                            result = "SKIPPED"
                    else:
                        if combined_report["testcases"][classname][name]["result"] == "PASSED":
                            result = "PASSED"

                    if report_dict["testcases"][classname][name]["result"] != "PASSED":
                        message = "{} // PROTOCOL: {} - SLAVE: {} --> {} ({})".format(
                            combined_report["testcases"][classname][name]["message"],
                            str(protocol),
                            str(slave),
                            report_dict["testcases"][classname][name]["result"],
                            report_dict["testcases"][classname][name]["message"]
                        )
                        output = "{} \n\n PROTOCOL: {} - SLAVE: {} --> {} \n {} \n {}".format(
                            combined_report["testcases"][classname][name]["output"],
                            str(protocol),
                            str(slave),
                            report_dict["testcases"][classname][name]["result"],
                            SEPARATOR,
                            report_dict["testcases"][classname][name]["output"]
                        )
                    else:
                        message = combined_report["testcases"][classname][name]["message"]
                        output = combined_report["testcases"][classname][name]["output"]

                    combined_report["testcases"][classname][name] = {
                        "result": result,
                        "message": message,
                        "output": output,
                        "time": combined_report["testcases"][classname][name]["time"] + report_dict["testcases"][classname][name]["time"]
                    }

    for classname in combined_report["testcases"].keys():
        for name in combined_report["testcases"][classname].keys():
            result = combined_report["testcases"][classname][name]["result"]
            if result == "PASSED":
                combined_report["passed"] += 1
            elif result == "ERROR":
                combined_report["errors"] += 1        
            elif result == "FAILED":
                combined_report["failures"] += 1    
            else:
                combined_report["skipped"] += 1    

    return combined_report


def save_xml(combined_report, output_file):
    tree = ET.Element("testsuites")
    testsuite = ET.SubElement(tree, "testsuite")
    testsuite.set("name", "pytest")
    testsuite.set("errors", str(combined_report["errors"]))
    testsuite.set("failures", str(combined_report["failures"]))
    testsuite.set("skipped", str(combined_report["skipped"]))
    testsuite.set("tests", str(combined_report["tests"]))
    testsuite.set("time", str(combined_report["time"]))
    testsuite.set("timestamp", combined_report["timestamp"])
    testsuite.set("hostname", combined_report["hostname"])

    for classname in combined_report["testcases"].keys():
        for name, testcase_dict in combined_report["testcases"][classname].items():
            testcase = ET.SubElement(testsuite, "testcase")
            testcase.set("time", str(testcase_dict["time"]))
            testcase.set("classname", classname)
            testcase.set("name", name)

            if testcase_dict["result"] == "SKIPPED":
                skip = ET.SubElement(testcase, "skipped")
                skip.set("type", "pytest.skip") 
                skip.set("message", testcase_dict["message"]) 
                skip.text = testcase_dict["output"] 
            elif testcase_dict["result"] == "ERROR":
                skip = ET.SubElement(testcase, "error")
                skip.set("message", testcase_dict["message"]) 
                skip.text = testcase_dict["output"] 
            elif testcase_dict["result"] == "FAILED":
                skip = ET.SubElement(testcase, "failure")
                skip.set("message", testcase_dict["message"]) 
                skip.text = testcase_dict["output"] 

    dom = minidom.parseString(ET.tostring(tree, encoding='utf-8'))
    with open(output_file, "wb") as f:
        f.write(dom.toprettyxml(indent='\t').encode())


def main(args):
    if len(args.input_reports) < 2:
        raise AttributeError("At least two input reports are needed to be combined")

    test_reports = load_reports(args.input_reports)
    combined_report = combine_reports(test_reports)
    save_xml(combined_report, args.output_file)        

if __name__ == '__main__':
    args = setup_command()
    main(args)