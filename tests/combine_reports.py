import os
import glob
import argparse
import xml.etree.ElementTree as ET
from xml.dom import minidom


XML_ROOT = "."
XML_TESTSUITE = f"{XML_ROOT}/testsuite"
XML_TESTSUITE_PROPS = "properties/property"
XML_TESTCASE = "testcase"
SEPARATOR = "============================================="


def setup_command():
    parser = argparse.ArgumentParser(description="Combine xml pytest reports")
    parser.add_argument("-i", "--input-reports", default=[], nargs="+", required=True)
    parser.add_argument("-o", "--output-file", type=str, required=True)
    return parser.parse_args()


def load_reports(input_reports):
    test_reports = {}
    for input_path in input_reports:
        try:
            with open(input_path, "r", encoding="utf-8") as xml_file:
                tree = ET.parse(xml_file)
        except FileNotFoundError:
            raise FileNotFoundError(f"There is not any xml file in the path: {input_path}")
        root = tree.getroot()
        testsuite = root.find(XML_TESTSUITE)
        properties = testsuite.findall(XML_TESTSUITE_PROPS)
        protocol = [
            prop.attrib["value"] for prop in properties if prop.attrib["name"] == "protocol"
        ][0]
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
            "testcases": {},
        }
        testcases = testsuite.findall(XML_TESTCASE)

        for testcase in testcases:
            classname = testcase.attrib["classname"]
            name = testcase.attrib["name"]
            if classname not in test_reports[input_path]["testcases"]:
                test_reports[input_path]["testcases"][classname] = {}

            results = [
                (case, testcase.find(case))
                for case in ["failure", "skipped", "error"]
                if testcase.find(case) is not None
            ]
            if not results:
                result = "passed"
                message = ""
                output = ""
            else:
                result = results[0][0]
                message = results[0][1].attrib["message"]
                output = results[0][1].text
            test_reports[input_path]["testcases"][classname][name] = {
                "result": result,
                "message": message,
                "output": output,
                "time": float(testcase.attrib["time"]),
            }

    return test_reports


def get_result_based_on_previous(previous_result, actual_result):
    results = [previous_result, actual_result]
    if previous_result == actual_result:
        result = actual_result
    elif "error" in results:
        result = "error"
    elif "failure" in results:
        result = "failure"
    else:
        result = "passed"

    return result


def combine_reports(test_reports):
    result_dict = {
        "passed": "PASSED",
        "error": "ERROR",
        "failure": "FAILED",
        "skipped": "SKIPPED",
    }
    combined_report = {
        "time": 0,
        "errors": 0,
        "failures": 0,
        "passed": 0,
        "skipped": 0,
        "tests": 0,
        "testcases": {},
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
                    if result != "passed":
                        message = "PROTOCOL: {} - SLAVE: {} --> {} ({})".format(
                            str(protocol),
                            str(slave),
                            result_dict[report_dict["testcases"][classname][name]["result"]],
                            report_dict["testcases"][classname][name]["message"],
                        )
                        output = "\n PROTOCOL: {} - SLAVE: {} --> {} \n {} \n {}".format(
                            str(protocol),
                            str(slave),
                            result_dict[report_dict["testcases"][classname][name]["result"]],
                            SEPARATOR,
                            report_dict["testcases"][classname][name]["output"],
                        )
                    else:
                        message = ""
                        output = ""

                    combined_report["testcases"][classname][name] = {
                        "result": report_dict["testcases"][classname][name]["result"],
                        "message": message,
                        "output": output,
                        "time": report_dict["testcases"][classname][name]["time"],
                    }
                else:
                    previous_result = combined_report["testcases"][classname][name]["result"]
                    actual_result = report_dict["testcases"][classname][name]["result"]
                    result = get_result_based_on_previous(previous_result, actual_result)

                    if report_dict["testcases"][classname][name]["result"] != "passed":
                        message = "{} // PROTOCOL: {} - SLAVE: {} --> {} ({})".format(
                            combined_report["testcases"][classname][name]["message"],
                            str(protocol),
                            str(slave),
                            result_dict[report_dict["testcases"][classname][name]["result"]],
                            report_dict["testcases"][classname][name]["message"],
                        )
                        output = "{} \n\n PROTOCOL: {} - SLAVE: {} --> {} \n {} \n {}".format(
                            combined_report["testcases"][classname][name]["output"],
                            str(protocol),
                            str(slave),
                            result_dict[report_dict["testcases"][classname][name]["result"]],
                            SEPARATOR,
                            report_dict["testcases"][classname][name]["output"],
                        )
                    else:
                        message = combined_report["testcases"][classname][name]["message"]
                        output = combined_report["testcases"][classname][name]["output"]

                    combined_report["testcases"][classname][name] = {
                        "result": result,
                        "message": message,
                        "output": output,
                        "time": combined_report["testcases"][classname][name]["time"]
                        + report_dict["testcases"][classname][name]["time"],
                    }

    total_numbers_dict = {
        "failure": "failures",
        "passed": "passed",
        "skipped": "skipped",
        "error": "errors",
    }
    for classname in combined_report["testcases"].keys():
        for name in combined_report["testcases"][classname].keys():
            result = combined_report["testcases"][classname][name]["result"]
            combined_report[total_numbers_dict[result]] += 1

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

            if testcase_dict["result"] == "skipped":
                skip = ET.SubElement(testcase, "skipped")
                skip.set("type", "pytest.skip")
                skip.set("message", testcase_dict["message"])
                skip.text = testcase_dict["output"]
            elif testcase_dict["result"] == "error":
                skip = ET.SubElement(testcase, "error")
                skip.set("message", testcase_dict["message"])
                skip.text = testcase_dict["output"]
            elif testcase_dict["result"] == "failure":
                skip = ET.SubElement(testcase, "failure")
                skip.set("message", testcase_dict["message"])
                skip.text = testcase_dict["output"]

    dom = minidom.parseString(ET.tostring(tree, encoding="utf-8"))
    with open(output_file, "wb") as f:
        f.write(dom.toprettyxml(indent="\t").encode())


def main(args):
    input_reports = []
    for input_report in args.input_reports:
        if os.path.isdir(input_report):
            xml_files = glob.glob(os.path.join(input_report, "*.xml"))
            if len(xml_files) == 0:
                raise AttributeError(f"Folder {input_report} is empty")
            input_reports.extend(xml_files)
        elif input_report.endswith(".xml"):
            input_reports.append(input_report)
        else:
            raise AttributeError(f"Incorrect extension: {input_report}")

    if len(input_reports) < 2:
        raise AttributeError("At least two input reports are needed to be combined")

    test_reports = load_reports(input_reports)
    combined_report = combine_reports(test_reports)
    save_xml(combined_report, args.output_file)


if __name__ == "__main__":
    args = setup_command()
    main(args)
